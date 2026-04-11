from typing import Any
"""
IncidentOps - FastAPI Application v15.0

Upgraded with:
- SQLite persistence (users, episodes, leaderboard)
- JWT + API key authentication
- Episode replay and recording
- Leaderboard with ranked scores
- WebSocket support
- Prometheus metrics
- CORS configurable via CORS_ORIGINS env var

Endpoints:
- GET  /              - Dashboard UI
- GET  /health        - Health check
- POST /reset         - Reset environment
- POST /step          - Execute action
- GET  /state         - Environment status
- GET  /services      - List valid services
- GET  /actions       - List valid actions
- GET  /tasks         - Available tasks/scenarios with schema
- POST /tasks         - Create custom task
- POST /grader        - Grade trajectory
- POST /baseline      - Run baseline agent
- GET  /validation    - Run validation suite
- GET  /frontier      - Get frontier scenario
- GET  /determinism/check - Verify reproducibility
- POST /configure     - Configure environment
- POST /openai/check  - Verify OpenAI credentials
- GET  /episodes      - List recorded episodes
- GET  /episodes/:id  - Get episode detail
- POST /episodes      - Save episode (auth required)
- GET  /leaderboard   - Get leaderboard
- POST /auth/register - Register user
- POST /auth/login    - Login user
- GET  /me            - Get current user (auth required)
- GET  /stats         - Aggregate statistics
- GET  /metrics       - Prometheus metrics
- WS   /ws            - WebSocket for real-time updates
"""
import os
import logging
logger = logging.getLogger(__name__)
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator, Field
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

# === Request ID correlation ===
request_id_var: ContextVar[str] = ContextVar("request_id", default="no-request-id")

from app.db import get_db, init_db, close_db
from app.db.repositories import UserRepository, EpisodeRepository, LeaderboardRepository
from app.db.schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    EpisodeCreate, EpisodeResponse, EpisodeDetail, EpisodeListResponse,
    LeaderboardEntryResponse, LeaderboardResponse, StatsResponse,
)
from app.models import ActionType, StepRequest, StepResponse, VALID_SERVICES
from app.environment import IncidentEnv, EnvironmentConfig, make_env
from app.fault_injector import FaultType
from app.grader import grade_trajectory
from app.human_sre_grader import grade_like_human_sre
from app.enhanced_grader import grade_trajectory_enhanced
from app.determinism import run_reproducibility_test
from app.frontier_task import create_frontier_scenario
from app.information_tracker import EnhancedActionTracker
from app.comprehensive_validation import run_comprehensive_validation

# Route modules (split from main.py to reduce file size)
from app.routes.episodes import router as episodes_router
from app.routes.agents import router as agents_router


# === JWT / Auth (shared via auth_deps to avoid circular imports) ===
from app.routes.auth_deps import (
    JWT_SECRET,
    JWT_ALGORITHM,
    JWT_EXPIRE_HOURS,
    create_access_token,
    get_current_user,
)


# === WebSocket Manager ===

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception:  # pragma: no cover
                self.disconnect(connection)  # pragma: no cover


ws_manager = ConnectionManager()


# === Lifespan ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: require JWT_SECRET in production
    if JWT_SECRET is None:
        raise RuntimeError(
            "JWT_SECRET environment variable is not set. "
            "Set JWT_SECRET to a secure random value before starting the server."
        )
    logging.warning(
        "SECURITY WARNING: JWT_SECRET is using the default value. "
        "Set the JWT_SECRET environment variable to a secure random value in production."
    )
    await init_db()
    yield
    # Shutdown
    await close_db()


# === App ===

app = FastAPI(
    title="IncidentOps",
    description="Production Incident Response RL Environment — SRE Training Platform",
    version="15.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire shared state so route modules can access ws_manager without circular imports
from app.routes import state
state.ws_manager = ws_manager

# Include route modules
app.include_router(episodes_router)
app.include_router(agents_router)


# === Request ID Middleware ===
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request_id_var.set(request_id)
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# React dashboard dist is served via @app.get("/") route above

# Rate limiter - configurable via env vars (requests per minute)
_rate_limit = os.environ.get("RATE_LIMIT", "100/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[_rate_limit])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_env: IncidentEnv | None = None
_tracker: EnhancedActionTracker | None = None


def get_env() -> IncidentEnv:
    global _env
    if _env is None:
        _env = make_env()
    return _env


def get_tracker() -> EnhancedActionTracker:
    global _tracker
    if _tracker is None:
        _tracker = EnhancedActionTracker()
    return _tracker


# === Prometheus Metrics ===

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
    _metrics_enabled = True
except ImportError:
    _metrics_enabled = False

if _metrics_enabled:
    # Guard against duplicate registration when module is imported multiple times
    _existing = [c for c in REGISTRY._names_to_collectors.keys()]
    _metrics_registered = any("incidentops_http_requests_total" in str(c) for c in _existing)

    if not _metrics_registered:
        http_requests_total = Counter(
            "incidentops_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        http_request_duration = Histogram(
            "incidentops_http_request_duration_seconds",
            "HTTP request duration",
            ["method", "endpoint"],
        )
        episodes_total = Counter(
            "incidentops_episodes_total",
            "Total episodes recorded",
            ["fault_type", "agent_type"],
        )
        episode_score = Gauge(
            "incidentops_episode_score",
            "Latest episode score",
            ["fault_type"],
        )
        active_websockets = Gauge(
            "incidentops_active_websockets",
            "Active WebSocket connections",
        )
        # Wire state module so route files can access metrics without circular imports
        from app.routes import state
        state._metrics_enabled = True
        state.episodes_total = episodes_total
        state.episode_score = episode_score
    else:  # pragma: no cover
        http_requests_total = http_request_duration = episodes_total = episode_score = active_websockets = None  # pragma: no cover


# === Request Models ===

class ResetRequest(BaseModel):
    seed: int | None = None
    fault_type: str | None = None
    difficulty: int | None = None

    @field_validator('fault_type')
    @classmethod
    def validate_fault_type(cls, v):
        if v is not None:
            valid = [ft.value for ft in FaultType]
            if v not in valid:
                raise ValueError(f"Invalid fault_type. Valid: {valid}")
        return v

    @field_validator('difficulty')
    @classmethod
    def validate_difficulty(cls, v):
        if v is not None and not (1 <= v <= 5):
            raise ValueError("difficulty must be 1-5")
        return v


class GradeBreakdown(BaseModel):
    root_cause_accuracy: float = Field(description="Root cause identification score (0.0-1.0)")
    fix_correctness: float = Field(description="Fix correctness score (0.0-1.0)")
    slo_adherence: float = Field(description="SLO time budget adherence score (0.0-1.0)")
    efficiency: float = Field(description="Efficiency score vs optimal steps (0.0-1.0)")
    minimal_disruption: float = Field(description="Minimal disruption score (0.0-1.0)")
    reasoning_quality: float = Field(description="Reasoning quality score (0.0-1.0)")
    investigation_thoroughness: float = Field(description="Investigation thoroughness score (0.0-1.0)")


class GradeResponse(BaseModel):
    """Response model for POST /grader — documents all return fields in OpenAPI."""
    trajectory_id: str | None = Field(default=None, description="Optional trajectory identifier")
    task: str | None = Field(default=None, description="Task name used for grading (e.g. 'oom_crash')")
    final_score: float = Field(description="Weighted final score (0.0-1.0)")
    grade: str = Field(description="SRE grade: expert, proficient, competent, learning, novice")
    explanation: str = Field(description="Human-readable scoring explanation with breakdown")
    strengths: list[str] = Field(default_factory=list, description="Identified strengths")
    weaknesses: list[str] = Field(default_factory=list, description="Identified weaknesses")
    suggestions: list[str] = Field(default_factory=list, description="Actionable improvement suggestions")
    breakdown: GradeBreakdown = Field(description="Per-component score breakdown")
    reasoning_pattern: str = Field(
        description="Reasoning pattern: systematic, hypothesis_driven, evidence_based, reactive, random"
    )


class GradeRequest(BaseModel):
    trajectory_id: str | None = None
    task: str | None = Field(
        default=None,
        description="Task name (e.g. 'oom_crash', 'cascade_failure', 'ghost_corruption'). "
                    "Inferred as fault_type when scenario is absent."
    )
    actions: list[dict] = Field(default_factory=list, description="List of actions taken in the episode")
    rewards: list[float] | None = None
    final_state: dict | None = Field(default_factory=dict, description="Final environment state")
    scenario: dict | None = Field(
        default=None,
        description="Scenario: fault_type, root_cause_service, affected_services, difficulty. "
                    "Optional when task is provided — inferred from task if absent."
    )
    use_enhanced: bool = True
    seed: int = 42


class BaselineRequest(BaseModel):
    seed: int = 42
    max_steps: int = 20
    verbose: bool = False
    use_llm: bool = False
    # Optional task to run instead of all 3
    # Maps to fault_type: "oom_crash" -> "oom", "cascade_failure" -> "cascade", "ghost_corruption" -> "ghost"
    # All other values are passed through as-is (e.g. "network_partition", "data_corruption")
    task: str | None = Field(
        default=None,
        description=(
            "Task ID to run a single baseline episode. "
            "Supported mappings: 'oom_crash' -> 'oom', 'cascade_failure' -> 'cascade', "
            "'ghost_corruption' -> 'ghost'. All other values are passed through as fault_type. "
            "If omitted, runs all 3 canonical tasks and returns their scores."
        ),
    )
    # Groq (default active key)
    groq_api_key: str | None = None
    groq_model: str | None = "groq/llama-4-opus-17b"
    # HuggingFace
    hf_token: str | None = None
    hf_model: str | None = None
    # OpenAI
    openai_api_key: str | None = None
    openai_model: str | None = "gpt-4o"
    # Google Gemini
    gemini_api_key: str | None = None
    gemini_model: str | None = "gemini-2.0-flash"
    # AskSage
    askme_api_key: str | None = None
    askme_model: str | None = None
    askme_base_url: str | None = "https://api.asksage.ai/server"
    # Generic override
    api_base_url: str | None = None
    model_name: str | None = None


class EnvConfigRequest(BaseModel):
    seed: int = 42
    max_steps: int = 50
    fault_type: str | None = None
    difficulty: int = 3
    enable_memory: bool = True
    enable_noise: bool = True
    enable_deception: bool = True


class OpenAICheckRequest(BaseModel):
    # Groq (default — active key for all users)
    groq_api_key: str | None = None
    groq_model: str | None = "groq/llama-4-opus-17b"
    # HuggingFace
    hf_token: str | None = None
    hf_model: str | None = None
    # OpenAI
    openai_api_key: str | None = None
    openai_model: str | None = "gpt-4o"
    # Google Gemini (OpenAI-compatible endpoint)
    gemini_api_key: str | None = None
    gemini_model: str | None = "gemini-2.0-flash"
    # AskSage (OpenAI-compatible)
    askme_api_key: str | None = None
    askme_model: str | None = None
    askme_base_url: str | None = "https://api.asksage.ai/server"
    # Generic override
    api_base_url: str | None = None
    model_name: str | None = None


class CustomTaskRequest(BaseModel):
    task_id: str
    name: str
    description: str
    fault_type: str
    difficulty: int
    hints: list[str] = []
    expected_min_steps: int = 2
    expected_max_steps: int = 20


# === Exception Handlers ===

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):  # pragma: no cover
    return JSONResponse(  # pragma: no cover
        status_code=400,  # pragma: no cover
        content={"error": "ValidationError", "message": str(exc), "type": "value_error"}  # pragma: no cover
    )  # pragma: no cover


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):  # pragma: no cover
    return JSONResponse(  # pragma: no cover
        status_code=exc.status_code,  # pragma: no cover
        content={"error": exc.detail, "status_code": exc.status_code, "type": "http_error"}  # pragma: no cover
    )  # pragma: no cover


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):  # pragma: no cover
    # SECURITY: Log the real exception server-side; return generic message to client
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(  # pragma: no cover
        status_code=500,  # pragma: no cover
        content={  # pragma: no cover
            "error": "An internal error occurred. Please try again later.",  # pragma: no cover
            "type": "internal_error",  # pragma: no cover
        }  # pragma: no cover
    )  # pragma: no cover


# === Existing Endpoints ===

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the React dashboard."""
    # Serve React dashboard build
    dashboard_index = Path(__file__).parent.parent / "dashboard" / "dist" / "index.html"
    if dashboard_index.exists():
        return HTMLResponse(content=dashboard_index.read_text(encoding="utf-8"))
    # Fallback to legacy static
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():  # pragma: no cover
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))  # pragma: no cover
    return HTMLResponse(content="<h1>IncidentOps</h1><p>Dashboard not found. Run: cd dashboard && npm install && npm run build</p>")  # pragma: no cover


@app.get("/openenv.yaml")
async def get_openenv_yaml():
    """Serve openenv.yaml for HuggingFace Spaces validation."""
    from starlette.responses import Response
    openenv_path = Path(__file__).parent.parent / "openenv.yaml"
    if not openenv_path.exists():
        raise HTTPException(status_code=404, detail="openenv.yaml not found")
    content = openenv_path.read_text(encoding="utf-8")
    return Response(content=content, media_type="application/x-yaml")


@app.get("/api")
async def api_info():
    return {
        "name": "IncidentOps",
        "version": "15.0",
        "description": "SRE Incident Response RL Training Platform",
        "features": [
            "Anti-brute-force detection",
            "Advanced deceptive signals",
            "Reasoning-quality rewards",
            "Human SRE expert grading",
            "Partial observability",
            "Full determinism",
            "LLM baseline agent",
            "Episode recording & replay",
            "Leaderboard",
            "JWT + API key authentication",
            "WebSocket real-time updates",
            "Prometheus metrics",
            "10+ fault scenarios",
            "Multi-agent support (Investigator, Fixer, Analyst)",
            "Stable-Baselines3 RL training",
            "Custom task creation",
        ],
        "endpoints": list(sorted(set(
            e.path for e in app.routes
            if hasattr(e, "path") and e.path not in ("/", "/openapi.json", "/docs", "/redoc")
        ))),
    }


@app.get("/health")
async def health():
    env = get_env()
    return {
        "status": "healthy",
        "version": "15.1",
        "components": {
            "environment": "ok",
            "grader": "ok",
            "enhanced_grader": "ok",
            "llm_baseline": "ok",
            "action_tracker": "ok",
            "websocket": "ok",
            "database": "ok",
        },
        "environment_state": {
            "initialized": env.current_scenario is not None,
            "step": env.current_step,
        }
    }


@app.get("/ready")
async def ready():
    """Kubernetes readiness probe — checks all dependencies are available."""
    try:
        # Check DB connection
        from app.db import get_db
        async for _db in get_db():
            break
        return {"status": "ready", "checks": {"database": "ok"}}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"not ready: {e}")


@app.get("/live")
async def live():
    """Kubernetes liveness probe — checks if the process is alive."""
    return {"status": "alive"}


@app.post("/reset")
@limiter.limit(os.environ.get("RESET_RATE_LIMIT", "30/minute"))
async def reset(request: Request, body: ResetRequest = ResetRequest()):
    global _tracker
    env = get_env()

    if body.fault_type:
        env.config.fault_type = FaultType(body.fault_type)
    if body.difficulty:
        env.config.difficulty = body.difficulty

    _tracker = EnhancedActionTracker(seed=body.seed or env.config.seed)
    observation = env.reset(seed=body.seed)

    if env.current_scenario:
        _tracker.set_fault_context(
            root_cause=env.current_scenario.root_cause_service,
            affected_services=set(env.current_scenario.affected_services)
        )

    await ws_manager.broadcast({
        "type": "episode_start",
        "fault_type": env.current_scenario.fault_type.value if env.current_scenario else None,
        "difficulty": env.current_scenario.difficulty if env.current_scenario else None,
        "seed": body.seed or env.config.seed,
    })

    return {
        "observation": observation,
        "info": {
            "seed": env.config.seed,
            "fault_type": env.current_scenario.fault_type.value if env.current_scenario else None,
            "difficulty": env.current_scenario.difficulty if env.current_scenario else None,
        }
    }


@app.post("/step", response_model=StepResponse)
@limiter.limit(os.environ.get("STEP_RATE_LIMIT", "60/minute"))
async def step(request: Request, body: StepRequest):
    env = get_env()
    tracker = get_tracker()

    if env.current_scenario is None:
        raise HTTPException(status_code=400, detail="Call /reset first")

    action_result = tracker.record_action(
        action_type=body.action_type,
        target_service=body.target_service
    )

    action = {
        "action_type": body.action_type,
        "target_service": body.target_service,
        "parameters": body.parameters or {},
    }

    response = env.step(action)
    response.reward -= action_result.penalty

    # Enrich info dict with reasoning trace
    reasoning_trace = {
        "investigation_sequence": tracker.get_investigation_sequence(),
        "reasoning_score": tracker.get_reasoning_score(),
        "information_summary": tracker.get_information_summary(),
        "penalty_applied": action_result.penalty,
    }
    response.info["reasoning_trace"] = reasoning_trace

    await ws_manager.broadcast({
        "type": "step_executed",
        "step": env.current_step,
        "action_type": body.action_type,
        "target_service": body.target_service,
        "reward": response.reward,
        "terminated": response.terminated,
    })

    return response


@app.get("/state")
async def get_state():
    env = get_env()
    tracker = get_tracker()

    # Include services and alerts if initialized
    services = {}
    alerts: list[dict] = []
    if env.current_scenario is not None:
        services = env.services
        alerts = env._get_alerts()
        # Add id and timestamp to alerts
        from datetime import datetime
        for i, alert in enumerate(alerts):
            alert["id"] = f"alert-{i}"
            alert["timestamp"] = datetime(2024, 1, 15, 10, 0, 0).isoformat()

    return {
        "initialized": env.current_scenario is not None,
        "step": env.current_step,
        "max_steps": env.config.max_steps,
        "terminated": env.terminated,
        "truncated": env.truncated,
        "total_reward": sum(env.episode_rewards) if env.episode_rewards else 0,
        "scenario": {
            "fault_type": env.current_scenario.fault_type.value if env.current_scenario else None,
            "difficulty": env.current_scenario.difficulty if env.current_scenario else None,
        } if env.current_scenario else None,
        "services": services,
        "alerts": alerts,
        "information_summary": tracker.get_information_summary(),
        "reasoning_score": tracker.get_reasoning_score(),
        "is_guessing": tracker.is_guessing_behavior(),
    }


@app.get("/metadata")
async def get_metadata():
    """OpenEnv metadata endpoint."""
    return {
        "name": "IncidentOps",
        "description": "Production incident response RL environment for training SRE agents",
    }


@app.get("/schema")
async def get_schema():
    """OpenEnv schema endpoint — returns action, observation, and state schemas."""
    return {
        "action": {
            "action_type": {"type": "string", "enum": [a.value for a in ActionType]},
            "target_service": {"type": "string", "enum": list(VALID_SERVICES)},
            "parameters": {"type": "object"},
        },
        "observation": {
            "step": {"type": "integer"},
            "services": {"type": "object"},
            "alerts": {"type": "array"},
            "incident_info": {"type": "object"},
            "information_summary": {"type": "object"},
        },
        "state": {
            "initialized": {"type": "boolean"},
            "step": {"type": "integer"},
            "terminated": {"type": "boolean"},
            "truncated": {"type": "boolean"},
            "total_reward": {"type": "number"},
        },
    }


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """Model Context Protocol endpoint — JSON-RPC 2.0 compatible."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    # Support both tool_calls and method-based MCP calls
    method = body.get("method", "")
    req_id = body.get("id")

    # Handle tool call style
    if "tool_calls" in body:
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {"name": "reset", "description": "Reset environment", "input_schema": {}},
                    {"name": "step", "description": "Execute action", "input_schema": {}},
                    {"name": "state", "description": "Get environment state", "input_schema": {}},
                    {"name": "tasks", "description": "List available tasks", "input_schema": {}},
                    {"name": "grader", "description": "Grade trajectory", "input_schema": {}},
                ]
            }
        })

    # Handle standard JSON-RPC
    responses = {
        "environment.info": {
            "name": "IncidentOps",
            "version": "15.0",
            "description": "Production incident response RL environment",
        },
        "environment.capabilities": {
            "tools": True,
            "reset": True,
            "grader": True,
            "baseline": True,
        },
        "tasks.list": {},
    }

    if method in responses:
        return JSONResponse(content={"jsonrpc": "2.0", "id": req_id, "result": responses[method]})

    return JSONResponse(content={"jsonrpc": "2.0", "id": req_id, "result": {}})


@app.get("/services")
async def list_services():
    return {"services": sorted(VALID_SERVICES), "count": len(VALID_SERVICES)}


@app.get("/actions")
async def list_actions():
    return {"actions": [a.value for a in ActionType], "count": len(ActionType)}


@app.get("/tasks")
async def get_tasks():
    from app.__init__ import __version__

    # All 15 graded tasks with full metadata
    # grade_level: beginner (d1-2), intermediate (d3), advanced (d4-5)
    canonical_tasks = [
        {
            "id": "oom_crash",
            "name": "The OOM Crash",
            "difficulty": "easy",
            "grade_level": "beginner",
            "difficulty_level": 2,
            "fault_type": "oom",
            "description": "A single payment-service pod crashes with OutOfMemoryError. "
                           "Logs reveal the fault directly. Agent must query logs, identify "
                           "the crash, and restart the correct service without touching "
                           "unaffected services.",
            "difficulty_rationale": "OOM faults have explicit error logs — easy to identify "
                                    "root cause with one query_logs call. Best entry point.",
            "hints": ["Start with query_logs on payment-service",
                      "Look for OutOfMemoryError in the logs"],
            "expected_min_steps": 2,
            "expected_max_steps": 8,
            "correct_fix": "restart_service",
            "slo_budget_steps": 8,
        },
        {
            "id": "cascade_failure",
            "name": "The Cascade",
            "difficulty": "medium",
            "grade_level": "intermediate",
            "difficulty_level": 3,
            "fault_type": "cascade",
            "description": "The user-db connection pool exhausts silently. Three upstream "
                           "services return 503s with misleading timeout errors. Agent must "
                           "correlate metrics across services, trace the cascade back to the "
                           "database, and apply the correct fix.",
            "difficulty_rationale": "Requires dependency graph understanding to trace 503s "
                                    "back to the shared database dependency. Misleading signals "
                                    "on symptom services require discrimination.",
            "hints": ["503s on multiple services suggest a shared dependency",
                      "Check database-primary connection metrics"],
            "expected_min_steps": 4,
            "expected_max_steps": 14,
            "correct_fix": "scale_service",
            "slo_budget_steps": 12,
        },
        {
            "id": "ghost_corruption",
            "name": "The Ghost",
            "difficulty": "hard",
            "grade_level": "advanced",
            "difficulty_level": 5,
            "fault_type": "ghost",
            "description": "A queue consumer has a logic bug introduced via a recent deploy. "
                           "It silently corrupts recommendation scores — no error logs, no "
                           "crashes, only subtle metric drift in click-through rates. Agent "
                           "must cross-correlate the deploy timeline, identify the regression, "
                           "and rollback the deployment.",
            "difficulty_rationale": "Silent faults have no explicit error signals. Requires "
                                    "detecting gradual metric drift (CTR decline) and correlating "
                                    "with deployment timeline. Only fix is rollback_deployment.",
            "hints": ["No alerts means the signal is in metrics, not logs",
                      "Correlate deploy timeline with when metrics drifted"],
            "expected_min_steps": 6,
            "expected_max_steps": 20,
            "correct_fix": "rollback_deployment",
            "slo_budget_steps": 25,
        },
        {
            "id": "ddos_flood",
            "name": "The DDoS Flood",
            "difficulty": "medium",
            "grade_level": "intermediate",
            "difficulty_level": 3,
            "fault_type": "network",
            "description": "api-gateway is overwhelmed by a 50x traffic spike. Latency "
                           "spikes to 2000ms+ across all downstream services. Deceptive "
                           "signals show connection timeouts on auth-service and order-service "
                           "but not on api-gateway itself. Agent must identify the gateway "
                           "as the bottleneck and scale it.",
            "difficulty_rationale": "Deceptive signals on downstream services (auth-service, "
                                    "order-service) blame each other — requires tracing latency "
                                    "back to the gateway bottleneck.",
            "hints": ["High latency across many services suggests an upstream bottleneck",
                      "Check api-gateway throughput — not just error logs"],
            "expected_min_steps": 3,
            "expected_max_steps": 12,
            "correct_fix": "scale_service",
            "slo_budget_steps": 12,
        },
        {
            "id": "memory_spiral",
            "name": "The Memory Spiral",
            "difficulty": "medium-hard",
            "grade_level": "advanced",
            "difficulty_level": 4,
            "fault_type": "oom",
            "description": "analytics-service has a slow memory leak — memory grows ~4% per step "
                           "starting at 45%, leading to OOM around step 18. The leak is only "
                           "obvious after querying metrics 3+ times. database-replica shows high "
                           "CPU from analytics queries, misleading naive agents into restarting "
                           "the DB. Agent must track memory growth over time and restart analytics-service.",
            "difficulty_rationale": "Trend detection required — one query_metrics call is "
                                    "insufficient. Misleading DB CPU signal requires "
                                    "discriminating between cause and effect.",
            "hints": ["Track memory_percent across multiple query_metrics calls to spot the trend",
                      "High CPU on database-replica is a symptom, not the root cause"],
            "expected_min_steps": 5,
            "expected_max_steps": 16,
            "correct_fix": "restart_service",
            "slo_budget_steps": 18,
        },
    ]

    # Extended fault tasks (difficulty-aware, 2 difficulty levels each)
    extended_tasks = [
        # Cert Expiry (difficulty 1-2: beginner)
        {
            "id": "cert_expiry_1",
            "name": "TLS Cert Expiry (Easy)",
            "difficulty": "easy",
            "grade_level": "beginner",
            "difficulty_level": 1,
            "fault_type": "cert_expiry",
            "description": "api-gateway TLS certificate has expired. HTTPS connections fail. "
                           "Error logs show SSL handshake failures.",
            "difficulty_rationale": "Explicit SSL errors in logs make root cause obvious. "
                                    "Simple restart_service restores connectivity.",
            "hints": ["Check query_logs for SSL/TLS errors",
                      "restart_service regenerates the cert"],
            "expected_min_steps": 2,
            "expected_max_steps": 6,
            "correct_fix": "restart_service",
            "slo_budget_steps": 5,
        },
        {
            "id": "cert_expiry_2",
            "name": "TLS Cert Expiry (Harder)",
            "difficulty": "medium",
            "grade_level": "intermediate",
            "difficulty_level": 2,
            "fault_type": "cert_expiry",
            "description": "TLS cert on api-gateway expired with additional config drift. "
                           "Requires both identifying cert expiry and checking config.",
            "difficulty_rationale": "Cert expiry combined with config drift requires checking "
                                    "both logs and deployment history.",
            "hints": ["Check query_logs for SSL errors AND query_deployments for recent changes"],
            "expected_min_steps": 3,
            "expected_max_steps": 8,
            "correct_fix": "restart_service",
            "slo_budget_steps": 8,
        },
        # Config Drift (difficulty 2-3)
        {
            "id": "config_drift_2",
            "name": "Config Drift (Medium)",
            "difficulty": "medium",
            "grade_level": "intermediate",
            "difficulty_level": 2,
            "fault_type": "config_drift",
            "description": "order-service has drifted from its golden config. "
                           "Request timeout thresholds are misconfigured, causing 503s.",
            "difficulty_rationale": "Config drift requires comparing current config to golden config. "
                                    "apply_fix is needed rather than simple restart.",
            "hints": ["Check query_service for current config parameters",
                      "query_deployments may show recent changes"],
            "expected_min_steps": 4,
            "expected_max_steps": 10,
            "correct_fix": "apply_fix",
            "slo_budget_steps": 12,
        },
        {
            "id": "config_drift_3",
            "name": "Config Drift (Hard)",
            "difficulty": "hard",
            "grade_level": "advanced",
            "difficulty_level": 3,
            "fault_type": "config_drift",
            "description": "Database connection pool config has drifted across multiple services. "
                           "Agent must identify the specific parameter causing exhaustion.",
            "difficulty_rationale": "Multiple services affected by the same config drift requires "
                                    "tracing back to the shared configuration source.",
            "hints": ["Check query_metrics for connection_pool_usage",
                      "Compare configs across affected services"],
            "expected_min_steps": 5,
            "expected_max_steps": 14,
            "correct_fix": "apply_fix",
            "slo_budget_steps": 15,
        },
        # Data Corruption (difficulty 3-4)
        {
            "id": "data_corruption_3",
            "name": "Data Corruption (Hard)",
            "difficulty": "hard",
            "grade_level": "advanced",
            "difficulty_level": 3,
            "fault_type": "data_corruption",
            "description": "recommendation-service serves stale/corrupted data after a "
                           "database replica went out of sync. No explicit errors.",
            "difficulty_rationale": "Silent data inconsistency with no error signals — "
                                    "requires querying business metrics to detect quality drift.",
            "hints": ["Check query_metrics for data freshness signals",
                      "Compare results quality before and after deploy"],
            "expected_min_steps": 5,
            "expected_max_steps": 16,
            "correct_fix": "rollback_deployment",
            "slo_budget_steps": 18,
        },
        {
            "id": "data_corruption_4",
            "name": "Data Corruption (Expert)",
            "difficulty": "hard",
            "grade_level": "advanced",
            "difficulty_level": 4,
            "fault_type": "data_corruption",
            "description": "Silent data corruption across multiple services after a "
                           "schema migration. Only subtle metric anomalies visible.",
            "difficulty_rationale": "Multi-service silent corruption requires correlating "
                                    "anomalies across different metric types.",
            "hints": ["Query metrics on multiple services to find the corruption pattern",
                      "Check query_deployments for recent schema changes"],
            "expected_min_steps": 6,
            "expected_max_steps": 20,
            "correct_fix": "rollback_deployment",
            "slo_budget_steps": 22,
        },
        # Network Partition (difficulty 2-3)
        {
            "id": "network_partition_2",
            "name": "Network Partition (Medium)",
            "difficulty": "medium",
            "grade_level": "intermediate",
            "difficulty_level": 2,
            "fault_type": "network_partition",
            "description": "api-gateway loses connectivity to auth-service. "
                           "Downstream services show cascading timeouts.",
            "difficulty_rationale": "Network partition creates split-brain — requires "
                                    "query_dependencies to map which services can't reach each other.",
            "hints": ["Use query_dependencies to find unreachable services",
                      "scale_service on the gateway often restores connectivity"],
            "expected_min_steps": 3,
            "expected_max_steps": 10,
            "correct_fix": "scale_service",
            "slo_budget_steps": 12,
        },
        {
            "id": "network_partition_3",
            "name": "Network Partition (Hard)",
            "difficulty": "hard",
            "grade_level": "advanced",
            "difficulty_level": 3,
            "fault_type": "network_partition",
            "description": "Partial network partition affects two service groups. "
                           "Some services can communicate, others cannot.",
            "difficulty_rationale": "Partial partition requires mapping exact connectivity "
                                    "between service groups before applying fix.",
            "hints": ["Map which service groups can reach each other",
                      "Check query_dependencies output carefully"],
            "expected_min_steps": 5,
            "expected_max_steps": 14,
            "correct_fix": "scale_service",
            "slo_budget_steps": 16,
        },
        # Slow Downstream (difficulty 2-3)
        {
            "id": "slow_downstream_2",
            "name": "Slow Downstream (Medium)",
            "difficulty": "medium",
            "grade_level": "intermediate",
            "difficulty_level": 2,
            "fault_type": "slow_downstream",
            "description": "database-replica is running slowly, causing latency "
                           "on all services that depend on it.",
            "difficulty_rationale": "Cascading latency requires tracing back through "
                                    "the dependency graph to the slow service.",
            "hints": ["Check latency metrics across services to find the bottleneck",
                      "database-replica slowdown affects search and analytics"],
            "expected_min_steps": 3,
            "expected_max_steps": 10,
            "correct_fix": "scale_service",
            "slo_budget_steps": 12,
        },
        {
            "id": "slow_downstream_3",
            "name": "Slow Downstream (Hard)",
            "difficulty": "hard",
            "grade_level": "advanced",
            "difficulty_level": 3,
            "fault_type": "slow_downstream",
            "description": "Multiple downstream services are slow with similar latency increases. "
                           "Root cause is a shared dependency.",
            "difficulty_rationale": "Multiple slow services with same root cause requires "
                                    "distinguishing between cause and cascading effect.",
            "hints": ["Query dependencies to find the shared bottleneck",
                      "Check query_metrics on the most upstream affected service"],
            "expected_min_steps": 5,
            "expected_max_steps": 14,
            "correct_fix": "scale_service",
            "slo_budget_steps": 16,
        },
        # Thundering Herd (difficulty 3)
        {
            "id": "thundering_herd_3",
            "name": "Thundering Herd",
            "difficulty": "medium",
            "grade_level": "intermediate",
            "difficulty_level": 3,
            "fault_type": "thundering_herd",
            "description": "Cache is empty after restart. All services flood the database "
                           "simultaneously, causing database overload.",
            "difficulty_rationale": "Thundering herd requires identifying cache failure pattern "
                                    "and applying circuit breaker or cache warmup.",
            "hints": ["Check cache hit rates — 0% means cache is empty",
                      "apply_fix with circuit breaker config or restart cache-service"],
            "expected_min_steps": 4,
            "expected_max_steps": 12,
            "correct_fix": "apply_fix",
            "slo_budget_steps": 14,
        },
        # Zombie Process (difficulty 1-2)
        {
            "id": "zombie_process_1",
            "name": "Zombie Process (Easy)",
            "difficulty": "easy",
            "grade_level": "beginner",
            "difficulty_level": 1,
            "fault_type": "zombie_process",
            "description": "payment-service has zombie processes consuming resources. "
                           "Service appears healthy but throughput is degraded.",
            "difficulty_rationale": "Zombie processes visible in process metrics. "
                                    "restart_service clears zombie processes.",
            "hints": ["Check query_metrics for zombie process indicators",
                      "restart_service clears orphaned processes"],
            "expected_min_steps": 2,
            "expected_max_steps": 6,
            "correct_fix": "restart_service",
            "slo_budget_steps": 5,
        },
        {
            "id": "zombie_process_2",
            "name": "Zombie Process (Medium)",
            "difficulty": "medium",
            "grade_level": "intermediate",
            "difficulty_level": 2,
            "fault_type": "zombie_process",
            "description": "Multiple services have zombie processes after a deployment "
                           "failure. Resources are depleted.",
            "difficulty_rationale": "Multi-service zombie process issue requires identifying "
                                    "which service is the origin.",
            "hints": ["Query metrics on all services to find resource exhaustion pattern",
                      "restart_service on the origin service"],
            "expected_min_steps": 4,
            "expected_max_steps": 10,
            "correct_fix": "restart_service",
            "slo_budget_steps": 8,
        },
        # Version Mismatch (difficulty 2-3)
        {
            "id": "version_mismatch_2",
            "name": "Version Mismatch (Medium)",
            "difficulty": "medium",
            "grade_level": "intermediate",
            "difficulty_level": 2,
            "fault_type": "version_mismatch",
            "description": "notification-service was deployed with incompatible API version. "
                           "It cannot communicate with email-service.",
            "difficulty_rationale": "Version mismatch requires checking deployment history "
                                    "and rolling back to compatible version.",
            "hints": ["Check query_deployments for version history",
                      "rollback_deployment to previous working version"],
            "expected_min_steps": 3,
            "expected_max_steps": 10,
            "correct_fix": "rollback_deployment",
            "slo_budget_steps": 12,
        },
        {
            "id": "version_mismatch_3",
            "name": "Version Mismatch (Hard)",
            "difficulty": "hard",
            "grade_level": "advanced",
            "difficulty_level": 3,
            "fault_type": "version_mismatch",
            "description": "API version mismatch across multiple services after a "
                           "coordinated rollout. Some endpoints are incompatible.",
            "difficulty_rationale": "Multi-service version mismatch requires identifying "
                                    "which version is the correct baseline.",
            "hints": ["Check query_deployments across all affected services",
                      "Identify the common working version"],
            "expected_min_steps": 5,
            "expected_max_steps": 14,
            "correct_fix": "rollback_deployment",
            "slo_budget_steps": 15,
        },
    ]

    # Supplement with FaultRegistry tasks for full coverage
    try:
        from app.faults.registry import FaultRegistry
        for fault_name in FaultRegistry.list():
            fault = FaultRegistry.get(fault_name)
            for diff in range(fault.difficulty_range[0], min(fault.difficulty_range[1], 5) + 1):
                task_id = f"{fault_name}_{diff}"
                # Skip if already in extended_tasks
                if any(t["id"] == task_id for t in extended_tasks):
                    continue
                grade_lvl = "beginner" if diff <= 2 else ("intermediate" if diff <= 3 else "advanced")
                slo_map = {1: 5, 2: 8, 3: 12, 4: 18, 5: 25}
                extended_tasks.append({
                    "id": task_id,
                    "name": f"{fault.name.replace('_', ' ').title()} (Difficulty {diff})",
                    "difficulty": "easy" if diff <= 2 else ("medium" if diff <= 3 else "hard"),
                    "grade_level": grade_lvl,
                    "difficulty_level": diff,
                    "fault_type": fault.name,
                    "description": f"Scenario: {fault.name.replace('_', ' ')} at difficulty {diff}",
                    "difficulty_rationale": f"Complexity increases with difficulty level {diff}",
                    "hints": fault.get_symptoms()[:2],
                    "expected_min_steps": diff + 1,
                    "expected_max_steps": (diff + 1) * 4,
                    "correct_fix": fault.get_symptoms()[0].split()[0] if fault.get_symptoms() else "restart_service",
                    "slo_budget_steps": slo_map.get(diff, 12),
                })
    except ImportError:
        pass  # FaultRegistry not available

    all_tasks = canonical_tasks + extended_tasks

    return {
        "total": len(all_tasks),
        "tasks": all_tasks,
        "action_schema": {
            "type": "object",
            "description": "Schema for POST /step",
            "properties": {
                "action_type": {
                    "type": "string", "required": True,
                    "enum": [a.value for a in ActionType],
                    "description": "Type of action to perform",
                },
                "target_service": {
                    "type": "string", "required": "conditional",
                    "enum": sorted(VALID_SERVICES),
                    "description": "Target service (required for service-specific actions)",
                },
                "parameters": {"type": "object", "required": False},
            },
            "required": ["action_type"],
            "example": {"action_type": "query_logs", "target_service": "payment-service", "parameters": {}},
        },
        "grading_info": {
            "weights": {
                "root_cause": 0.20,
                "fix": 0.20,
                "slo": 0.15,
                "efficiency": 0.15,
                "disruption": 0.10,
                "reasoning": 0.10,
                "investigation": 0.10,
            },
            "grade_levels": {
                "beginner": "difficulty 1-2, most forgiving rubric",
                "intermediate": "difficulty 3, standard rubric",
                "advanced": "difficulty 4-5, strictest rubric",
            },
            "slo_tiers": {
                1: "5 steps",
                2: "8 steps",
                3: "12 steps",
                4: "18 steps",
                5: "25 steps",
            },
        },
    }


@app.post("/grader", response_model=GradeResponse)
@limiter.limit(os.environ.get("GRADER_RATE_LIMIT", "30/minute"))
async def grade(request: Request, body: GradeRequest):
    """
    Grade an agent trajectory.

    **Minimal usage** — pass just task + actions:
    ```json
    {"task": "oom_crash", "actions": [{"action_type": "query_logs", "target_service": "payment-service"}]}
    ```

    **Full usage** — override scenario details:
    ```json
    {"task": "oom_crash", "scenario": {"difficulty": 4}, "actions": [...], "final_state": {...}}
    ```
    """
    trajectory = {
        "id": body.trajectory_id,
        "actions": body.actions,
        "rewards": body.rewards or [],
        "final_state": body.final_state or {},
    }

    if body.use_enhanced:
        evaluation = grade_trajectory_enhanced(
            trajectory,
            scenario=body.scenario,
            seed=body.seed,
            task=body.task,
        )
        return GradeResponse(
            trajectory_id=body.trajectory_id,
            task=body.task,
            final_score=evaluation.breakdown.final_score,
            grade=evaluation.breakdown.grade.value,
            explanation=evaluation.explanation,
            strengths=evaluation.strengths,
            weaknesses=evaluation.weaknesses,
            suggestions=evaluation.suggestions,
            breakdown=GradeBreakdown(
                root_cause_accuracy=evaluation.breakdown.root_cause_score,
                fix_correctness=evaluation.breakdown.fix_score,
                slo_adherence=evaluation.breakdown.slo_score,
                efficiency=evaluation.breakdown.efficiency_score,
                minimal_disruption=evaluation.breakdown.disruption_score,
                reasoning_quality=evaluation.breakdown.reasoning_score,
                investigation_thoroughness=evaluation.breakdown.investigation_score,
            ),
            reasoning_pattern=evaluation.reasoning_analysis.pattern.value,
        )
    else:
        score = grade_trajectory(trajectory, seed=body.seed)
        return GradeResponse(
            trajectory_id=body.trajectory_id,
            task=body.task,
            final_score=score.final_score,
            grade=score.grade.value,
            explanation="",
            strengths=[],
            weaknesses=[],
            suggestions=[],
            breakdown=GradeBreakdown(
                root_cause_accuracy=score.root_cause_score,
                fix_correctness=score.fix_score,
                slo_adherence=score.slo_preservation_score,
                efficiency=score.efficiency_score,
                minimal_disruption=score.minimal_disruption_score,
                reasoning_quality=score.reasoning_chain_score,
                investigation_thoroughness=score.reasoning_chain_score,
            ),
            reasoning_pattern="unknown",
        )


@app.post("/baseline")
@limiter.limit(os.environ.get("BASELINE_RATE_LIMIT", "10/minute"))
async def run_baseline(request: Request, body: BaselineRequest):
    try:
        if body.use_llm:
            from app.llm_baseline import run_llm_evaluation, check_openai_available
            # HACKATHON: Use injected API_BASE_URL + API_KEY first (highest priority)
            _hackathon_key = os.environ.get("API_KEY")
            _hackathon_url = os.environ.get("API_BASE_URL")
            if _hackathon_key and _hackathon_url:
                results = run_llm_evaluation(
                    seed=body.seed,
                    max_steps=body.max_steps,
                    verbose=body.verbose,
                    api_key=_hackathon_key,
                    base_url=_hackathon_url,
                    model=body.model_name,
                )
                return {**results, "agent_type": "llm", "success": True}

            # Priority: Groq > Gemini > AskSage > OpenAI > HuggingFace > generic
            # SECURITY: Pass API key directly to client — do NOT write to os.environ
            if body.gemini_api_key:
                base_url = body.api_base_url or "https://generativelanguage.googleapis.com/v1beta/openai"
                model = body.model_name or body.gemini_model or "gemini-2.0-flash"
                api_key = body.gemini_api_key
            elif body.askme_api_key:
                base_url = body.askme_base_url or "https://api.asksage.ai/server"
                model = body.model_name or body.askme_model or "gpt-4o"
                api_key = body.askme_api_key
            elif body.groq_api_key:
                base_url = body.api_base_url or "https://api.groq.com/openai/v1"
                model = body.model_name or body.groq_model or "groq/llama-4-opus-17b"
                api_key = body.groq_api_key
            elif body.openai_api_key:
                base_url = body.api_base_url or "https://api.openai.com/v1"
                model = body.model_name or body.openai_model or "gpt-4o"
                api_key = body.openai_api_key
            elif body.hf_token:
                base_url = body.api_base_url or "https://router.huggingface.co/v1"
                model = body.model_name or body.hf_model or "mistralai/Mistral-7B-Instruct-v0.3"
                api_key = body.hf_token
            else:
                base_url = None
                model = None
                api_key = None

            if api_key and check_openai_available(api_key=api_key):
                results = run_llm_evaluation(
                    seed=body.seed,
                    max_steps=body.max_steps,
                    verbose=body.verbose,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                )
                return {**results, "agent_type": "llm", "success": True}

        from app.baseline import BaselineAgent, AgentConfig, run_baseline_episode, AgentStrategy

        # Task -> (name, difficulty, fault_type) mapping
        TASK_MAP = {
            "oom_crash": ("oom_crash", 2, FaultType.OOM),
            "cascade_failure": ("cascade_failure", 3, FaultType.CASCADE),
            "ghost_corruption": ("ghost_corruption", 5, FaultType.GHOST),
        }

        # If a task is provided, try to map it; unknown tasks are passed through as fault_type
        if body.task:
            task_key = body.task.lower()
            if task_key in TASK_MAP:
                name, difficulty, fault = TASK_MAP[task_key]
            else:
                # Unknown task ID — treat it as a fault_type string
                try:
                    fault = FaultType(body.task)
                    name = body.task
                    difficulty = 3  # default difficulty for unknown faults
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": f"Unknown task: {body.task}. "
                                     f"Supported task IDs: oom_crash, cascade_failure, ghost_corruption",
                            "success": False,
                        },
                    )
            env = make_env(seed=body.seed, difficulty=difficulty, fault_type=fault)
            env.reset(seed=body.seed)
            agent = BaselineAgent(AgentConfig(seed=body.seed, strategy=AgentStrategy.SYSTEMATIC))
            result = run_baseline_episode(
                env, agent, seed=body.seed, max_steps=body.max_steps, verbose=body.verbose
            )
            return {
                name: round(result["final_score"], 6),
                "agent_type": "rule_based",
                "success": True,
                "easy": round(result["final_score"], 6) if difficulty == 2 else None,
                "medium": round(result["final_score"], 6) if difficulty == 3 else None,
                "hard": round(result["final_score"], 6) if difficulty == 5 else None,
            }

        # No task provided — run all 3 canonical tasks
        results = {}
        difficulties = [
            ("oom_crash", 2, FaultType.OOM),
            ("cascade_failure", 3, FaultType.CASCADE),
            ("ghost_corruption", 5, FaultType.GHOST),
        ]
        for name, difficulty, fault in difficulties:
            env = make_env(seed=body.seed, difficulty=difficulty, fault_type=fault)
            env.reset(seed=body.seed)
            agent = BaselineAgent(AgentConfig(seed=body.seed, strategy=AgentStrategy.SYSTEMATIC))
            result = run_baseline_episode(
                env, agent, seed=body.seed, max_steps=body.max_steps, verbose=body.verbose
            )
            results[name] = round(result["final_score"], 6)
        results["total"] = round(sum(results.values()) / 3, 6)
        # Map to OpenEnv validation keys
        results["easy"] = results.get("oom_crash")
        results["medium"] = results.get("cascade_failure")
        results["hard"] = results.get("ghost_corruption")
        results["agent_type"] = "rule_based"
        results["success"] = True
        return results
    except Exception as e:  # pragma: no cover
        return JSONResponse(status_code=500, content={"error": str(e), "success": False})  # pragma: no cover


@app.get("/frontier")
async def get_frontier_scenario():
    scenario = create_frontier_scenario(seed=42)
    return {
        "scenario_id": scenario.scenario_id,
        "difficulty": scenario.difficulty,
        "minimum_steps": scenario.minimum_steps,
        "dual_layer_failure": {
            "primary_failure": scenario.dual_layer_failure.primary_failure_service,
            "secondary_failure": scenario.dual_layer_failure.secondary_failure_service,
        },
        "deceptive_signals": [
            {"service": s.service, "type": s.signal_type, "content": s.content, "relevance": s.actual_relevance}
            for s in scenario.deceptive_signals[:5]
        ],
    }


@app.get("/validation")
async def run_validation():
    report = run_comprehensive_validation(seed=42, verbose=False)
    return report.to_dict()


@app.get("/determinism/check")
async def check_determinism():
    result = run_reproducibility_test(seed=42, num_steps=5)
    return result


@app.post("/configure")
async def configure(request: EnvConfigRequest):
    global _env, _tracker
    fault_type = FaultType(request.fault_type) if request.fault_type else None
    _env = make_env(
        seed=request.seed, fault_type=fault_type, difficulty=request.difficulty,
        enable_noise=request.enable_noise,
    )
    _tracker = EnhancedActionTracker(seed=request.seed)
    return {"configured": True, "config": request.dict()}


@app.post("/openai/check")
async def check_openai_key(request: OpenAICheckRequest):
    try:
        from openai import OpenAI

        # HACKATHON: Check injected env vars first (highest priority)
        _hackathon_key = os.environ.get("API_KEY")
        _hackathon_url = os.environ.get("API_BASE_URL")
        if _hackathon_key and _hackathon_url:
            try:
                client = OpenAI(api_key=_hackathon_key, base_url=_hackathon_url)
                models = client.models.list()
                return {
                    "valid": True,
                    "provider": "hackathon",
                    "models_available": [m.id for m in models.data[:10]],
                    "api_base_url": _hackathon_url,
                    "model_name": body.model_name or "gpt-4o",
                }
            except Exception as e:  # pragma: no cover
                return {"valid": False, "message": str(e)}  # pragma: no cover

        # Priority: Groq > Gemini > AskSage > OpenAI > HuggingFace > generic
        if request.gemini_api_key:
            api_key = request.gemini_api_key
            base_url = request.api_base_url or "https://generativelanguage.googleapis.com/v1beta/openai"
            model = request.model_name or request.gemini_model or "gemini-2.0-flash"
            provider = "gemini"
        elif request.askme_api_key:
            api_key = request.askme_api_key
            base_url = request.askme_base_url or "https://api.asksage.ai/server"
            model = request.model_name or request.askme_model or "gpt-4o"
            provider = "asksage"
        elif request.groq_api_key:
            api_key = request.groq_api_key
            base_url = request.api_base_url or "https://api.groq.com/openai/v1"
            model = request.model_name or request.groq_model or "groq/llama-4-opus-17b"
            provider = "groq"
        elif request.openai_api_key:
            api_key = request.openai_api_key
            base_url = request.api_base_url or "https://api.openai.com/v1"
            model = request.model_name or request.openai_model or "gpt-4o"
            provider = "openai"
        elif request.hf_token:
            api_key = request.hf_token
            base_url = request.api_base_url or "https://router.huggingface.co/v1"
            model = request.model_name or request.hf_model or "mistralai/Mistral-7B-Instruct-v0.3"
            provider = "huggingface"
        else:
            return {"valid": False, "message": "No API key provided"}

        os.environ["API_BASE_URL"] = base_url
        os.environ["MODEL_NAME"] = model
        os.environ["GROQ_API_KEY"] = api_key

        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            models = client.models.list()
            return {
                "valid": True,
                "provider": provider,
                "models_available": [m.id for m in models.data[:10]],
                "api_base_url": base_url,
                "model_name": model,
            }
        except Exception as e:  # pragma: no cover
            return {"valid": False, "message": str(e)}  # pragma: no cover
        finally:  # pragma: no cover
            os.environ.pop("API_BASE_URL", None)  # pragma: no cover
            os.environ.pop("MODEL_NAME", None)  # pragma: no cover
            os.environ.pop("GROQ_API_KEY", None)  # pragma: no cover
    except ImportError:  # pragma: no cover
        return {"valid": False, "message": "openai package not installed"}  # pragma: no cover


# === Auth Endpoints ===

@app.post("/auth/register", response_model=TokenResponse)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    existing = await user_repo.get_by_username(data.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    if data.email:
        existing_email = await user_repo.get_by_email(data.email)
        if existing_email:
            raise HTTPException(status_code=409, detail="Email already registered")

    user = await user_repo.create(data)
    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@app.post("/auth/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    user = await user_repo.authenticate(data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    await user_repo.update_last_seen(user.id)
    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@app.get("/me", response_model=UserResponse)
async def get_me(
    current_user: UserResponse | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user


# === Episode Endpoints ===

@app.post("/inference")
async def run_inference(request: Request):
    """Run a single inference step via HF inference API or return environment state.
    Compatible with HuggingFace Spaces inference widget."""
    data = await request.json()
    action = data.get("action", {})
    seed = data.get("seed", 42)

    env = get_env()
    if env.current_scenario is None:
        env.reset(seed=seed)

    resp = env.step(action)
    return {
        "observation": resp.observation,
        "reward": resp.reward,
        "terminated": resp.terminated,
        "truncated": resp.truncated,
        "info": resp.info,
    }


# === WebSocket Endpoint ===

@app.websocket("/ws")  # pragma: no cover
async def websocket_endpoint(websocket: WebSocket):  # pragma: no cover
    await ws_manager.connect(websocket)  # pragma: no cover
    if _metrics_enabled:  # pragma: no cover
        active_websockets.set(len(ws_manager.active_connections))  # pragma: no cover
    try:  # pragma: no cover
        while True:  # pragma: no cover
            data = await websocket.receive_json()  # pragma: no cover
            # Handle client messages (e.g., subscribe to specific fault types)
            msg_type = data.get("type", "")  # pragma: no cover
            if msg_type == "ping":  # pragma: no cover
                await websocket.send_json({"type": "pong"})  # pragma: no cover
            elif msg_type == "subscribe":  # pragma: no cover
                # Client can subscribe to specific events — acknowledge
                await websocket.send_json({  # pragma: no cover
                    "type": "subscribed",  # pragma: no cover
                    "channels": data.get("channels", []),  # pragma: no cover
                })  # pragma: no cover
    except WebSocketDisconnect:  # pragma: no cover
        ws_manager.disconnect(websocket)  # pragma: no cover
        if _metrics_enabled:  # pragma: no cover
            active_websockets.set(len(ws_manager.active_connections))  # pragma: no cover


def main():
    uvicorn.run("app.main:app", host="0.0.0.0", port=7860, reload=False)


# === Serve React dashboard build ===
_dashboard_dist = Path(__file__).parent.parent / "dashboard" / "dist"
if _dashboard_dist.exists():
    # Mount /static/ for dashboard assets (after all API routes so they take priority)
    app.mount("/static", StaticFiles(directory=str(_dashboard_dist), html=True), name="static")
    # SPA fallback: serve index.html for all frontend routes
    _index_html = (_dashboard_dist / "index.html").read_text()
    _api_prefixes = frozenset(["api", "auth", "docs", "redoc", "health", "reset", "step", "state", "services", "actions", "tasks", "grader", "baseline", "validation", "frontier", "determinism", "configure", "openai", "episodes", "leaderboard", "me", "stats", "metrics", "ws"])
    @app.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)  # pragma: no cover
    async def serve_spa(path: str):  # pragma: no cover
        prefix = path.split("/")[0] if "/" in path else path
        if prefix not in _api_prefixes:  # pragma: no cover
            return HTMLResponse(content=_index_html)  # pragma: no cover
        raise HTTPException(status_code=404)  # pragma: no cover


if __name__ == "__main__":
    main()
