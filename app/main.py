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
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

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


# === JWT Config ===

JWT_SECRET = os.environ.get("JWT_SECRET", "incidentops-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 1 week


def create_access_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[UserResponse]:
    """Extract user from JWT Bearer token or API key"""
    auth_header = request.headers.get("Authorization", "")
    api_key = request.headers.get("X-API-Key", "")

    user_repo = UserRepository(db)

    # Try Bearer token
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = int(payload.get("sub", 0))
            user = await user_repo.get_by_id(user_id)
            if user and user.is_active:
                return UserResponse.model_validate(user)
        except JWTError:
            pass

    # Try API key
    if api_key:
        user = await user_repo.get_by_api_key(api_key)
        if user and user.is_active:
            return UserResponse.model_validate(user)

    return None


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
    # Startup
    if JWT_SECRET == "incidentops-dev-secret-change-in-production":
        logging.warning(
            "SECURITY WARNING: Using default JWT_SECRET in production. "
            "Set the JWT_SECRET environment variable to a secure random value."
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

# React dashboard dist is served via @app.get("/") route above

# Rate limiter - configurable via env vars (requests per minute)
_rate_limit = os.environ.get("RATE_LIMIT", "100/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[_rate_limit])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_env: Optional[IncidentEnv] = None
_tracker: Optional[EnhancedActionTracker] = None


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
    else:  # pragma: no cover
        http_requests_total = http_request_duration = episodes_total = episode_score = active_websockets = None  # pragma: no cover


# === Request Models ===

class ResetRequest(BaseModel):
    seed: Optional[int] = None
    fault_type: Optional[str] = None
    difficulty: Optional[int] = None

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
    efficiency: float = Field(description="Efficiency score (0.0-1.0)")
    minimal_disruption: float = Field(description="Minimal disruption score (0.0-1.0)")
    reasoning_quality: float = Field(description="Reasoning quality score (0.0-1.0)")


class GradeResponse(BaseModel):
    """Response model for POST /grader — documents all return fields in OpenAPI."""
    trajectory_id: Optional[str] = Field(default=None, description="Optional trajectory identifier")
    task: Optional[str] = Field(default=None, description="Task name used for grading (e.g. 'oom_crash')")
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
    trajectory_id: Optional[str] = None
    task: Optional[str] = Field(
        default=None,
        description="Task name (e.g. 'oom_crash', 'cascade_failure', 'ghost_corruption'). "
                    "Inferred as fault_type when scenario is absent."
    )
    actions: list[dict] = Field(default_factory=list, description="List of actions taken in the episode")
    rewards: Optional[list[float]] = None
    final_state: Optional[dict] = Field(default_factory=dict, description="Final environment state")
    scenario: Optional[dict] = Field(
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
    task: Optional[str] = Field(
        default=None,
        description=(
            "Task ID to run a single baseline episode. "
            "Supported mappings: 'oom_crash' -> 'oom', 'cascade_failure' -> 'cascade', "
            "'ghost_corruption' -> 'ghost'. All other values are passed through as fault_type. "
            "If omitted, runs all 3 canonical tasks and returns their scores."
        ),
    )
    # Groq (default active key)
    groq_api_key: Optional[str] = None
    groq_model: Optional[str] = "groq/llama-4-opus-17b"
    # HuggingFace
    hf_token: Optional[str] = None
    hf_model: Optional[str] = None
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = "gpt-4o"
    # Google Gemini
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = "gemini-2.0-flash"
    # AskSage
    askme_api_key: Optional[str] = None
    askme_model: Optional[str] = None
    askme_base_url: Optional[str] = "https://api.asksage.ai/server"
    # Generic override
    api_base_url: Optional[str] = None
    model_name: Optional[str] = None


class EnvConfigRequest(BaseModel):
    seed: int = 42
    max_steps: int = 50
    fault_type: Optional[str] = None
    difficulty: int = 3
    enable_memory: bool = True
    enable_noise: bool = True
    enable_deception: bool = True


class OpenAICheckRequest(BaseModel):
    # Groq (default — active key for all users)
    groq_api_key: Optional[str] = None
    groq_model: Optional[str] = "groq/llama-4-opus-17b"
    # HuggingFace
    hf_token: Optional[str] = None
    hf_model: Optional[str] = None
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = "gpt-4o"
    # Google Gemini (OpenAI-compatible endpoint)
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = "gemini-2.0-flash"
    # AskSage (OpenAI-compatible)
    askme_api_key: Optional[str] = None
    askme_model: Optional[str] = None
    askme_base_url: Optional[str] = "https://api.asksage.ai/server"
    # Generic override
    api_base_url: Optional[str] = None
    model_name: Optional[str] = None


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
    return JSONResponse(  # pragma: no cover
        status_code=500,  # pragma: no cover
        content={  # pragma: no cover
            "error": str(exc),  # pragma: no cover
            "type": "internal_error",  # pragma: no cover
            "traceback": None,  # hide in production  # pragma: no cover
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
        "version": "15.0",
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


@app.get("/services")
async def list_services():
    return {"services": sorted(VALID_SERVICES), "count": len(VALID_SERVICES)}


@app.get("/actions")
async def list_actions():
    return {"actions": [a.value for a in ActionType], "count": len(ActionType)}


@app.get("/tasks")
async def get_tasks():
    from app.__init__ import __version__
    canonical_tasks = [
        {
            "id": "oom_crash",
            "name": "The OOM Crash",
            "difficulty": "easy",
            "difficulty_level": 2,
            "fault_type": "oom",
            "description": "A single payment-service pod crashes with OutOfMemoryError. "
                           "Logs reveal the fault directly. Agent must query logs, identify "
                           "the crash, and restart the correct service without touching "
                           "unaffected services.",
            "hints": ["Start with query_logs on payment-service",
                      "Look for OutOfMemoryError in the logs"],
            "expected_min_steps": 2,
            "expected_max_steps": 8,
        },
        {
            "id": "cascade_failure",
            "name": "The Cascade",
            "difficulty": "medium",
            "difficulty_level": 3,
            "fault_type": "cascade",
            "description": "The user-db connection pool exhausts silently. Three upstream "
                           "services return 503s with misleading timeout errors. Agent must "
                           "correlate metrics across services, trace the cascade back to the "
                           "database, and apply the correct fix.",
            "hints": ["503s on multiple services suggest a shared dependency",
                      "Check database-primary connection metrics"],
            "expected_min_steps": 4,
            "expected_max_steps": 14,
        },
        {
            "id": "ghost_corruption",
            "name": "The Ghost",
            "difficulty": "hard",
            "difficulty_level": 5,
            "fault_type": "ghost",
            "description": "A queue consumer has a logic bug introduced via a recent deploy. "
                           "It silently corrupts recommendation scores — no error logs, no "
                           "crashes, only subtle metric drift in click-through rates. Agent "
                           "must cross-correlate the deploy timeline, identify the regression, "
                           "and rollback the deployment.",
            "hints": ["No alerts means the signal is in metrics, not logs",
                      "Correlate deploy timeline with when metrics drifted"],
            "expected_min_steps": 6,
            "expected_max_steps": 20,
        },
        {
            "id": "ddos_flood",
            "name": "The DDoS Flood",
            "difficulty": "medium",
            "difficulty_level": 3,
            "fault_type": "network",
            "description": "api-gateway is overwhelmed by a 50x traffic spike. Latency "
                           "spikes to 2000ms+ across all downstream services. Deceptive "
                           "signals show connection timeouts on auth-service and order-service "
                           "but not on api-gateway itself. Agent must identify the gateway "
                           "as the bottleneck and scale it.",
            "hints": ["High latency across many services suggests an upstream bottleneck",
                      "Check api-gateway throughput — not just error logs"],
            "expected_min_steps": 3,
            "expected_max_steps": 12,
        },
        {
            "id": "memory_spiral",
            "name": "The Memory Spiral",
            "difficulty": "medium-hard",
            "difficulty_level": 4,
            "fault_type": "oom",
            "description": "analytics-service has a slow memory leak — memory grows ~4% per step "
                           "starting at 45%, leading to OOM around step 18. The leak is only "
                           "obvious after querying metrics 3+ times. database-replica shows high "
                           "CPU from analytics queries, misleading naive agents into restarting "
                           "the DB. Agent must track memory growth over time and restart analytics-service.",
            "hints": ["Track memory_percent across multiple query_metrics calls to spot the trend",
                      "High CPU on database-replica is a symptom, not the root cause"],
            "expected_min_steps": 5,
            "expected_max_steps": 16,
        },
    ]

    # Try loading extended faults from registry
    try:
        from app.faults.registry import FaultRegistry
        extended_tasks = []
        for fault_name in FaultRegistry.list():
            fault = FaultRegistry.get(fault_name)
            for diff in range(fault.difficulty_range[0], min(fault.difficulty_range[1], 5) + 1):
                extended_tasks.append({
                    "id": f"{fault_name}_{diff}",
                    "name": f"{fault.name.replace('_', ' ').title()} (Difficulty {diff})",
                    "difficulty": "easy" if diff <= 2 else ("medium" if diff <= 3 else "hard"),
                    "difficulty_level": diff,
                    "fault_type": fault.name,
                    "description": f"Scenario: {fault.name.replace('_', ' ')} at difficulty {diff}",
                    "hints": fault.get_symptoms()[:2],
                    "expected_min_steps": diff + 1,
                    "expected_max_steps": (diff + 1) * 4,
                })
        all_tasks = canonical_tasks + extended_tasks
    except ImportError:
        all_tasks = canonical_tasks

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
                efficiency=evaluation.breakdown.efficiency_score,
                minimal_disruption=evaluation.breakdown.disruption_score,
                reasoning_quality=evaluation.breakdown.reasoning_score,
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
                root_cause_accuracy=0.0,
                fix_correctness=0.0,
                efficiency=0.0,
                minimal_disruption=0.0,
                reasoning_quality=0.0,
            ),
            reasoning_pattern="unknown",
        )


@app.post("/baseline")
@limiter.limit(os.environ.get("BASELINE_RATE_LIMIT", "10/minute"))
async def run_baseline(request: Request, body: BaselineRequest):
    try:
        if body.use_llm:
            from app.llm_baseline import run_llm_evaluation, check_openai_available
            env_vars_set = []
            # Priority: Groq > Gemini > AskSage > OpenAI > HuggingFace > generic
            # Determine base URL and API key from provider fields
            if body.gemini_api_key:
                base_url = body.api_base_url or "https://generativelanguage.googleapis.com/v1beta/openai"
                model = body.model_name or body.gemini_model or "gemini-2.0-flash"
                api_key = body.gemini_api_key
                provider = "gemini"
            elif body.askme_api_key:
                base_url = body.askme_base_url or "https://api.asksage.ai/server"
                model = body.model_name or body.askme_model or "gpt-4o"
                api_key = body.askme_api_key
                provider = "asksage"
            elif body.groq_api_key:
                base_url = body.api_base_url or "https://api.groq.com/openai/v1"
                model = body.model_name or body.groq_model or "groq/llama-4-opus-17b"
                api_key = body.groq_api_key
                provider = "groq"
            elif body.openai_api_key:
                base_url = body.api_base_url or "https://api.openai.com/v1"
                model = body.model_name or body.openai_model or "gpt-4o"
                api_key = body.openai_api_key
                provider = "openai"
            elif body.hf_token:
                base_url = body.api_base_url or "https://router.huggingface.co/v1"
                model = body.model_name or body.hf_model or "mistralai/Mistral-7B-Instruct-v0.3"
                api_key = body.hf_token
                provider = "huggingface"
            else:
                base_url = body.api_base_url or "https://api.groq.com/openai/v1"
                model = body.model_name or "groq/llama-4-opus-17b"
                api_key = body.groq_api_key or ""
                provider = "groq"

            os.environ["API_BASE_URL"] = base_url
            os.environ["MODEL_NAME"] = model
            if api_key:
                os.environ["GROQ_API_KEY"] = api_key  # reused as generic key env var
                env_vars_set.append("GROQ_API_KEY")
            env_vars_set.extend(["API_BASE_URL", "MODEL_NAME"])

            try:
                if check_openai_available():
                    results = run_llm_evaluation(
                        seed=body.seed, max_steps=body.max_steps, verbose=body.verbose
                    )
                    return {**results, "agent_type": "llm", "success": True}
            except Exception:
                pass
            finally:
                for var in env_vars_set:
                    os.environ.pop(var, None)

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
                name: round(result["final_score"], 3),
                "agent_type": "rule_based",
                "success": True,
                "easy": round(result["final_score"], 3) if difficulty == 2 else None,
                "medium": round(result["final_score"], 3) if difficulty == 3 else None,
                "hard": round(result["final_score"], 3) if difficulty == 5 else None,
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
            results[name] = round(result["final_score"], 3)
        results["total"] = round(sum(results.values()) / 3, 3)
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


# === Multi-Agent Endpoints ===

class MultiAgentRequest(BaseModel):
    seed: int = 42
    max_steps: int = 20
    enable_analyst: bool = True
    confidence_threshold: float = 0.7


@app.post("/agents/episode")
async def run_multi_agent_episode(request: MultiAgentRequest):
    """
    Run a multi-agent coordinated episode.

    The multi-agent system includes:
    - Investigator: Gathers evidence by querying services
    - Fixer: Applies remediations (activates when suspicion > threshold)
    - Analyst: Provides pattern-based hints (optional)
    """
    from app.agents.coordinator import AgentCoordinator

    env = make_env(seed=request.seed)
    coordinator = AgentCoordinator(
        enable_analyst=request.enable_analyst,
        confidence_threshold=request.confidence_threshold,
        max_steps=request.max_steps,
    )

    result = coordinator.run_episode(env, seed=request.seed)

    return {
        "episode_id": result.episode_id,
        "total_reward": result.total_reward,
        "final_score": result.final_score,
        "grade": result.grade,
        "steps": result.steps,
        "duration_ms": result.duration_ms,
        "agent_decisions": {
            role: [
                {
                    "action": d.action_type,
                    "service": d.target_service,
                    "confidence": d.confidence,
                    "reasoning": d.reasoning,
                }
                for d in decisions
            ]
            for role, decisions in result.agent_decisions.items()
        },
        "investigation_summary": result.investigation_summary,
        "fix_summary": result.fix_summary,
        "analysis_summary": result.analysis_summary,
    }


@app.get("/agents/stats")
async def get_agent_stats():
    """Get multi-agent system statistics and configuration"""
    from app.agents.coordinator import AgentCoordinator

    coordinator = AgentCoordinator()
    return coordinator.get_coordinator_stats()


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
    current_user: Optional[UserResponse] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user


# === Episode Endpoints ===

@app.get("/episodes", response_model=EpisodeListResponse)
async def list_episodes(
    fault_type: Optional[str] = Query(None),
    agent_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    episode_repo = EpisodeRepository(db)
    offset = (page - 1) * per_page

    if agent_type:
        # Filter by agent type requires full scan for now
        all_eps = await episode_repo.list_recent(limit=per_page, offset=offset)
        all_eps = [e for e in all_eps if e.agent_type == agent_type]
        total = len(all_eps)
    elif fault_type:
        all_eps = await episode_repo.list_by_fault(fault_type, limit=per_page, offset=offset)
        total = len(all_eps)
    else:
        all_eps = await episode_repo.list_recent(limit=per_page, offset=offset)
        total = await episode_repo.count()

    return EpisodeListResponse(
        total=total,
        episodes=[EpisodeResponse.model_validate(e) for e in all_eps],
        page=page,
        per_page=per_page,
    )


@app.get("/episodes/{episode_id}", response_model=EpisodeDetail)
async def get_episode(
    episode_id: int,
    db: AsyncSession = Depends(get_db),
):
    episode_repo = EpisodeRepository(db)
    episode = await episode_repo.get_by_id(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return EpisodeDetail.model_validate(episode)


@app.get("/episodes/{episode_id}/replay")
async def get_episode_replay(
    episode_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get full episode replay with all steps for visualization."""
    episode_repo = EpisodeRepository(db)
    episode = await episode_repo.get_by_id(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    return {
        "episode_id": episode.id,
        "trajectory": getattr(episode, "trajectory", []),
        "final_state": getattr(episode, "final_state", {}),
        "score": episode.final_score,
        "fault_type": episode.fault_type,
        "difficulty": episode.difficulty,
        "agent_type": getattr(episode, "agent_type", "unknown"),
        "steps": len(getattr(episode, "trajectory", [])),
        "duration_minutes": getattr(episode, "duration_seconds", 0) / 60 if getattr(episode, "duration_seconds", 0) else None,
    }


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


@app.post("/episodes", response_model=EpisodeResponse)
async def save_episode(
    data: EpisodeCreate,
    current_user: Optional[UserResponse] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a completed episode to the database"""
    episode_repo = EpisodeRepository(db)
    leaderboard_repo = LeaderboardRepository(db)

    user_id = current_user.id if current_user else None

    # Check for duplicate
    existing = await episode_repo.get_by_episode_id(data.episode_id)
    if existing:
        raise HTTPException(status_code=409, detail="Episode already recorded")

    episode = await episode_repo.create(data, user_id=user_id)

    # Update leaderboard if user is authenticated
    if user_id:
        task_id = f"{data.fault_type}_d{data.difficulty}"
        await leaderboard_repo.upsert_entry(
            user_id=user_id,
            task_id=task_id,
            fault_type=data.fault_type,
            grader_type="enhanced",
            final_score=data.final_score,
        )

    # Prometheus metrics
    if _metrics_enabled:
        episodes_total.labels(fault_type=data.fault_type, agent_type=data.agent_type).inc()
        episode_score.labels(fault_type=data.fault_type).set(data.final_score)

    # Broadcast score
    await ws_manager.broadcast({
        "type": "score_recorded",
        "episode_id": data.episode_id,
        "fault_type": data.fault_type,
        "final_score": data.final_score,
        "grade": data.grade,
        "username": current_user.username if current_user else "anonymous",
    })

    return EpisodeResponse.model_validate(episode)


# === Leaderboard Endpoints ===

@app.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    task_id: Optional[str] = Query(None, description="Task ID e.g. 'oom_2', 'cascade_3'"),
    grader_type: str = Query("enhanced"),
    limit: int = Query(50, ge=1, le=200),
):
    if task_id is None:
        return LeaderboardResponse(grader_type=grader_type, entries=[], total=0)

    @asynccontextmanager
    async def _get_db_session():
        async for db in get_db():
            yield db

    async with _get_db_session() as db:
        leaderboard_repo = LeaderboardRepository(db)
        entries = await leaderboard_repo.get_leaderboard(task_id, grader_type, limit=limit)
        total = await leaderboard_repo.count_entries(task_id, grader_type)

        ranked = []
        for rank, (entry, user) in enumerate(entries, 1):
            ranked.append(LeaderboardEntryResponse(
                rank=rank,
                user_id=entry.user_id,
                username=user.username,
                task_id=entry.task_id,
                best_score=entry.best_score,
                avg_score=entry.avg_score,
                episode_count=entry.episode_count,
                updated_at=entry.updated_at,
            ))
        return LeaderboardResponse(
            task_id=task_id,
            grader_type=grader_type,
            entries=ranked,
            total=total,
        )


@app.get("/leaderboard/tasks")
async def list_leaderboard_tasks():
    """List all tasks that have leaderboard entries"""
    return {
        "tasks": [
            {"task_id": "oom_crash", "fault_type": "oom", "difficulty_level": 2, "name": "The OOM Crash"},
            {"task_id": "cascade_failure", "fault_type": "cascade", "difficulty_level": 3, "name": "The Cascade"},
            {"task_id": "ghost_corruption", "fault_type": "ghost", "difficulty_level": 5, "name": "The Ghost"},
            {"task_id": "ddos_flood", "fault_type": "network", "difficulty_level": 3, "name": "The DDoS Flood"},
            {"task_id": "memory_spiral", "fault_type": "oom", "difficulty_level": 4, "name": "The Memory Spiral"},
        ]
    }


# === Stats Endpoint ===

@app.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    episode_repo = EpisodeRepository(db)
    user_repo = UserRepository(db)

    total_episodes = await episode_repo.count()
    total_users = await user_repo.count()
    avg_score = await episode_repo.avg_score()
    scores_by_fault = await episode_repo.scores_by_fault()
    top_agents = await episode_repo.top_agents(limit=5)
    recent_episodes = await episode_repo.list_recent(limit=10)

    return StatsResponse(
        total_episodes=total_episodes,
        total_users=total_users,
        avg_score=round(avg_score, 3),
        scores_by_fault={k: round(v, 3) for k, v in scores_by_fault.items()},
        top_agents=top_agents,
        recent_episodes=[EpisodeResponse.model_validate(e) for e in recent_episodes],
    )


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


# === Prometheus Metrics Endpoint ===

@app.get("/metrics")
async def metrics():
    if not _metrics_enabled:
        raise HTTPException(status_code=503, detail="Prometheus client not installed")
    from starlette.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
