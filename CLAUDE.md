# IncidentOps - Project Context

## What is this?
IncidentOps is a Gym-style reinforcement learning environment that simulates production incidents across a realistic 15-service microservice architecture. Built for the OpenEnv hackathon (judged by Meta & HuggingFace engineers).

## Stack
- **Backend**: FastAPI + Pydantic + uvicorn + SQLAlchemy (async)
- **Frontend**: React dashboard (Vite + TypeScript + Tailwind) + legacy HTML fallback
- **Database**: SQLite via aiosqlite (async), upgradeable to PostgreSQL
- **Auth**: JWT + API key (bcrypt hashed)
- **Deployment**: Docker → HuggingFace Spaces
- **Python**: 3.11

## Architecture
- `app/main.py` - FastAPI v15 with 28+ REST endpoints + WebSocket
- `app/environment.py` - Core RL environment (IncidentEnv)
- `app/fault_injector.py` - Core fault injection (OOM, cascade, ghost)
- `app/faults/` - 10 extended fault generators (network partition, DDoS, cert expiry, etc.)
- `app/db/` - SQLAlchemy async DB layer (users, episodes, leaderboard)
- `app/agents/` - Multi-agent system (investigator, fixer, analyst, coordinator)
- `app/baseline.py` - Rule-based baseline agent
- `app/llm_baseline.py` - OpenAI LLM baseline agent (GPT-4o, temperature=0)
- `app/grader.py` - Basic trajectory grader
- `app/enhanced_grader.py` - Enhanced SRE grader with 5-axis breakdown
- `app/human_sre_grader.py` - Human-expert-style grading
- `app/reward.py` - Dense reward calculator
- `app/models.py` - Pydantic models (ActionType, StepRequest, StepResponse, VALID_SERVICES)
- `app/deceptive_signals.py` - Anti-brute-force deceptive signals
- `app/action_tracker.py` - Action tracking + brute-force detection
- `app/information_tracker.py` - Enhanced action tracking with reasoning score
- `app/determinism.py` - Reproducibility verification
- `app/comprehensive_validation.py` - 31-test validation suite
- `app/frontier_task.py` - Frontier-difficulty scenario generator
- `app/static/index.html` - Premium legacy dashboard UI
- `dashboard/` - React dashboard (new) with real-time charts, leaderboard, replay

## 3 Canonical Tasks
1. **The OOM Crash** (Easy, difficulty=2): payment-service OOM → restart_service
2. **The Cascade** (Medium, difficulty=3): database-primary pool exhaustion → scale_service
3. **The Ghost** (Hard, difficulty=5): recommendation-service silent corruption → rollback_deployment

## Baseline Scores (seed=42)
- Easy (OOM Crash): 0.3595 — Learning
- Medium (Cascade): 0.3400 — Learning
- Hard (Ghost): 0.3300 — Learning
- Mean: 0.3432 — Learning
- Difficulty ordering enforced: Easy > Medium > Hard (via PARTIAL_CREDIT caps)
- All scores reproducible via `/baseline` endpoint with seed=42

## Key Design Decisions
- All 31/31 validation tests pass
- Deterministic: same seed = identical episode
- Observations NEVER leak root cause or correct fix
- Brute-force strategies are detected and penalized
- Dense rewards at every step (-1.0 to +2.0)
- Partial observability: agents must actively investigate
- OpenAI API key accepted via UI or env var for LLM baseline

## Hackathon Scoring (from RULES.txt)
- Real-world utility: 30%
- Task & grader quality: 25%
- Environment design: 20%
- Code quality & spec compliance: 15%
- Creativity & novelty: 10%

## Critical: Don't Break These
- Never expose root_cause in /reset, /state, or /tasks responses
- Never add correct_fix to /tasks task definitions
- Baseline must show difficulty progression (easy > medium >> hard=0)
- All datetime usage must be deterministic (no datetime.now/utcnow)
- openenv.yaml schema must match actual observation output

## Bugs Fixed (History)
- reward.py: `field(default_factory=set)` outside dataclass → `set()`
- environment.py: first_observation always False → moved add() after check
- action_tracker.py: `dependencies_traces` typo → `dependencies_traced`
- 4 files: `datetime.utcnow()` → deterministic `datetime(2024, 1, 15, 10, 0, 0)`
- openenv.yaml: schema didn't match actual observation → rewrote to match
- llm_baseline.py: referenced nonexistent actions → removed
- baseline.py: wrong response format parsing → fixed
- fault_injector.py: cascade correct_fix was wrong → scale_service
- fault_injector.py: noisy metrics crash on dict values → isinstance check
- information_tracker.py: `action.step` on ActionResult → use enumerate
- main.py: /reset, /state, /tasks leaked root_cause → removed

## 13 Fault Types (v14)
1. **The OOM Crash** (Easy, difficulty=2): payment-service OOM → restart_service
2. **The Cascade** (Medium, difficulty=3): database-primary pool exhaustion → scale_service
3. **The Ghost** (Hard, difficulty=5): recommendation-service silent corruption → rollback_deployment
4. **Network Partition** (difficulty 1-4): split-brain between service groups
5. **Data Corruption** (difficulty 1-5): silent data inconsistency
6. **Config Drift** (difficulty 1-4): misconfigured service parameters
7. **DDoS Attack** (difficulty 2-4): traffic spike overload
8. **Slow Downstream** (difficulty 1-4): cascading latency from slow dependency
9. **Version Mismatch** (difficulty 2-4): incompatible API versions
10. **Cert Expiry** (difficulty 1-3): TLS certificate expiration
11. **Memory Leak** (difficulty 1-5): gradual OOM without instant crash
12. **Zombie Process** (difficulty 1-4): orphaned processes consuming resources
13. **Thundering Herd** (difficulty 2-4): cache stampede / DB overload

## API Endpoints
| Path | Method | Purpose |
|------|--------|---------|
| / | GET | Dashboard UI |
| /api | GET | API info JSON |
| /health | GET | Health check |
| /reset | POST | Reset environment |
| /step | POST | Execute action |
| /state | GET | Environment state |
| /services | GET | List 15 services |
| /actions | GET | List 11 action types |
| /tasks | GET | 13 tasks + action_schema |
| /grader | POST | Grade trajectory (0.0-1.0) |
| /baseline | POST | Run baseline (rule-based or LLM) |
| /validation | GET | 31-test validation suite |
| /frontier | GET | Frontier scenario |
| /determinism/check | GET | Verify determinism |
| /configure | POST | Configure environment |
| /openai/check | POST | Verify OpenAI API key |
| /episodes | GET | List recorded episodes |
| /episodes/{id} | GET | Get episode detail |
| /episodes | POST | Save episode (auth) |
| /leaderboard | GET | Get ranked leaderboard |
| /auth/register | POST | Register user |
| /auth/login | POST | Login user |
| /me | GET | Current user (auth) |
| /stats | GET | Aggregate statistics |
| /metrics | GET | Prometheus metrics |
| /ws | WS | WebSocket real-time |
| /docs | GET | OpenAPI Swagger docs |
| /redoc | GET | ReDoc documentation |
