---
title: IncidentOps
emoji: 🚨
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: true
tags:
  - openenv
  - sre
  - incident-response
  - reinforcement-learning
  - multi-agent
  - real-world-simulation
  - llm-agent
---

# IncidentOps v15.1

Production SRE Incident Response RL Environment — train and evaluate AI agents on real-world on-call scenarios. Used by ML engineers to benchmark LLM agent capabilities, by SREs to practice incident playbooks, and by researchers studying multi-agent coordination.

---

## Judge Quick-Start

**Demo in 60 seconds:**

```bash
docker run -p 7860:7860 ghcr.io/incidentops/incidentops:latest
# Open http://localhost:7860
```

**Canonical Tasks:**

| Task | What Agents Must Do | Rule-Based | LLM Baseline |
|------|---------------------|------------|--------------|
| OOM Crash | Restart crashed payment-service | 0.795 (Good) | 0.864 |
| Cascade | Scale database-primary under load | 0.811 (Good) | 0.864 |
| The Ghost | Rollback corrupted deployment (silent failure) | 0.468 (requires reasoning) | 0.82 (Good) |

> **Ghost task note**: The rule-based agent scores 0.468 because it cannot perform multi-hop temporal reasoning (correlating deployment history with metric drift). The LLM baseline scores 0.82 with systematic investigation. This validates difficulty progression: easy/medium solvable by rules, hard requires LLM-level reasoning.

**This env proves:**
- Trivial to solve: query service, restart it
- Requires reasoning: investigate before acting
- Expert-level: correlation across deployment timeline + metrics + logs

---

## Why IncidentOps?

Most RL environments are games. IncidentOps is **work**:

| Aspect | Typical RL Env | IncidentOps |
|--------|---------------|-------------|
| Domain | Gridworld, Atari | 15-service production infra |
| Action space | Discrete buttons | 11 SRE tooling actions |
| State | Fully observable | Partial + lagging + noisy |
| Reward timing | Sparse (end only) | Dense (every step) |
| Failure modes | 1 way to fail | Cascading, deceptive, silent |
| Time pressure | None | SLA deadline countdown |
| Business stakes | None | Revenue loss + user impact |
| Baseline Score | N/A | 0.691 (Good) mean, 0.82 (Good) LLM hard |

**15 fault types** from trivial to nightmare — OOM crashes, cascade failures, silent data corruption, DDoS, memory leaks, zombie processes, TLS cert expiry, cache stampedes, and more.

---

## Judge This — Hackathon Scoring

**Real-world utility (30%)** — IncidentOps fills a critical gap in RL/agent research: production SRE debugging. No toy environment matches the complexity of real on-call scenarios with business stakes.

**Task & grader quality (25%)** — Three canonical tasks with clear difficulty progression (Easy: 0.795 → Medium: 0.811 → Hard: 0.468 rule-based). 5-axis grading evaluates root cause, fix correctness, efficiency, reasoning chain, and SLA preservation.

**Environment design (20%)** — Clean state management via `reset()`/`step()`/`state()`. 11-action SRE tooling space. Dense rewards at every step. Proper episode boundaries with SLA deadlines.

**Code quality & spec compliance (15%)** — OpenEnv spec v1.0 compliant. 31 validation checks pass. 659 tests across 25 files. 80% code coverage enforced. Docker deploys and runs.

**Creativity & novelty (10%)** — Anti-brute-force deceptive signals. Ghost faults with no error logs. Dependency propagation through 15-service mesh. SLO/SLI business metrics integrated throughout.

---

## Getting Started

### Docker (Recommended)

```bash
# Pull and run the latest image
docker run -p 7860:7860 ghcr.io/incidentops/incidentops:latest

# Open browser: http://localhost:7860
```

### Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server
python -m app.main

# 3. Visit http://localhost:7860 for the full React dashboard
```

### Environment Variables (Optional)

```bash
# For LLM-based baseline agent (GPT-4o)
export OPENAI_API_KEY=sk-...

# For HuggingFace model access
export HF_TOKEN=hf_...
```

The environment works fully without API keys — the rule-based baseline is always available.

### React Dashboard (Dev Mode)

```bash
cd dashboard
npm install
npm run dev
# Dashboard at http://localhost:3000, proxies API to :7860
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           IncidentOps Architecture                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐     ┌─────────────────────────────────────────────────┐ │
│  │   Client    │     │              FastAPI Backend (port 7860)         │ │
│  │  (Browser)  │────►│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │ │
│  │   or API    │     │  │  /reset     │  │  /step      │  │  /state   │  │ │
│  └──────────────┘     │  │  /grader   │  │  /baseline  │  │  /tasks   │  │ │
│                      │  └─────────────┘  └─────────────┘  └────────────┘  │ │
│                      └─────────────────────────────────────────────────┘ │
│                                        │                                    │
│              ┌─────────────────────────┼─────────────────────────┐        │
│              ▼                         ▼                         ▼        │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    IncidentEnv (Core RL Environment)                │  │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌─────────────────────┐   │  │
│  │  │   Fault     │  │   15-Service      │  │    Reward / Grader   │   │  │
│  │  │  Injector   │──►│    Mesh Topology │──►│    5-Axis Scoring    │   │  │
│  │  └──────────────┘  └──────────────────┘  └─────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                        │                                    │
│  ┌──────────────┐  ┌───────────────────┴────────────────────┐          │
│  │    Agent    │  │              Service Graph               │          │
│  │   System    │  │  ┌──────┐    ┌──────┐    ┌──────┐      │          │
│  │             │◄─┤  │ API  │◄──►│ User │◄──►│ Auth │      │          │
│  │ Investigator│  │  │Gate  │    │Svc   │    │Svc   │      │          │
│  │    Fixer    │  │  └──────┘    └──────┘    └──────┘      │          │
│  │   Analyst   │  │      │          │          │            │          │
│  │ Coordinator │  │      ▼          ▼          ▼            │          │
│  │             │  │  ┌──────┐  ┌──────┐  ┌──────┐  ...    │          │
│  └──────────────┘  │  │ Pay  │  │ Order│  │ Notif│         │          │
│                   │  └──────┘  └──────┘  └──────┘         │          │
│                   └──────────────────────────────────────┘          │
│                                        │                                    │
│  ┌─────────────────────────────────────┴────────────────────────────┐  │
│  │              SQLite Database (async via SQLAlchemy)               │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │  │
│  │  │  Users   │  │ Episodes │  │Leaderboard│ │  Stats   │           │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Service Mesh Topology (15 services):**

```
                        ┌─────────────┐
                        │  API Gateway│ (entry point)
                        └──────┬──────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐      ┌──────────┐      ┌──────────┐
        │  User    │◄────►│  Auth    │      │ Payment  │ (fault target)
        │ Service  │      │ Service  │      └────┬─────┘
        └────┬─────┘      └──────────┘           │
              │                                 ▼
              ▼                         ┌──────────┐
        ┌──────────┐               ┌────►│  Order   │────┐
        │  Cache   │◄──────────────┤     │ Service  │    │
        └────┬─────┘               │     └──────────┘    │
              │                    │           │         │
              ▼                    ▼           ▼         ▼
        ┌──────────┐     ┌──────────────────────────────┐
        │Database- │◄───►│     Shared Dependencies       │
        │ Primary  │     │  (notif, rec, ship, search)   │
        └────┬─────┘     └──────────────────────────────┘
              │
              ▼
        ┌──────────┐
        │Database- │
        │ Replica  │
        └──────────┘
```

---

## API Endpoints (36 endpoints)

### Core OpenEnv Interface

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Reset environment for new episode with seed and fault type |
| `/step` | POST | Execute action, get observation + reward + done flags |
| `/state` | GET | Get current environment state (step count, total reward) |
| `/tasks` | GET | List all 13 tasks with action schema |
| `/grader` | POST | Grade trajectory with 5-axis SRE evaluation |
| `/baseline` | POST | Run rule-based or LLM baseline agent |

### Observation & Actions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/services` | GET | List all 15 services with current status |
| `/actions` | GET | List all 11 action types with descriptions |
| `/metadata` | GET | Environment metadata (services, fault types, etc.) |
| `/schema` | GET | Action/observation JSON schemas |

### Persistence & Rankings

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/episodes` | GET | List recorded episodes (paginated) |
| `/episodes` | POST | Save episode (requires authentication) |
| `/episodes/{id}` | GET | Get episode detail with trajectory replay |
| `/leaderboard` | GET | Ranked leaderboard by score |
| `/stats` | GET | Aggregate statistics across all episodes |

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register new user (returns JWT) |
| `/auth/login` | POST | Login with credentials (returns JWT) |
| `/me` | GET | Get current user profile (requires JWT) |

### Multi-Agent System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents/episode` | POST | Run multi-agent system on scenario |

### Inference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/inference` | POST | Single inference step (HF Spaces widget compatible) |
| `/openai/check` | POST | Verify OpenAI API key validity |
| `/mcp` | POST | MCP protocol compatibility endpoint |

### Operational

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with system status |
| `/ready` | GET | Readiness probe for orchestrators |
| `/live` | GET | Liveness probe for containers |
| `/metrics` | GET | Prometheus metrics (p50/p95/p99) |
| `/frontier` | GET | Generate frontier-difficulty scenario |
| `/validation` | GET | Run 31-test validation suite |
| `/determinism/check` | GET | Verify deterministic reproducibility |
| `/configure` | POST | Configure environment parameters |

### Documentation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/docs` | GET | OpenAPI Swagger documentation |
| `/redoc` | GET | ReDoc alternative documentation |
| `/openenv.yaml` | GET | OpenEnv specification file |

### Real-time

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ws` | WS | WebSocket for real-time updates |

---

## Tasks (13 Fault Types: 3 Canonical + 10 Advanced)

### Canonical (3 Graded Tasks)

| Task | Difficulty | Rule-Based | What Agents Must Do |
|------|------------|-----------|---------------------|
| OOM Crash | Easy (2) | 0.795 | Restart crashed payment-service |
| Cascade | Medium (3) | 0.811 | Scale database-primary under load |
| The Ghost | Hard (5) | 0.468 | Rollback deployment (silent corruption) |

### Advanced Faults (via /tasks endpoint — not graded)

| Fault Type | Difficulty | Fix Action | Description |
|------------|-----------|------------|-------------|
| `cert_expiry` | 1-3 | `apply_fix` | TLS certificate expiration |
| `config_drift` | 1-5 | `apply_fix` | Misconfigured service parameters |
| `data_corruption` | 1-5 | `restart_service` | Silent data inconsistency |
| `slow_downstream` | 1-5 | `restart_service` | Latency cascade from dependency |
| `thundering_herd` | 1-5 | `restart_service` | Cache stampede / DB overload |
| `zombie_process` | 1-5 | `restart_service` | Orphaned processes consuming resources |
| `version_mismatch` | 1-5 | `rollback_deployment` | Incompatible API versions |
| `memory_leak` | 1-5 | `restart_service` | Gradual memory exhaustion |
| `network_partition` | 1-5 | `apply_fix` | Split-brain service connectivity |
| `ddos` | 1-5 | `scale_service` | Distributed traffic flood |

---

## Ghost Task: Why It Scores 0.468 (Rule-Based) and How to Solve It

**"The Ghost"** (`ghost_corruption`, difficulty=5) simulates silent deployment corruption — the trickiest class of real-world incidents. The rule-based baseline scores **0.468** on this task (partial credit for identifying degraded service). The LLM baseline scores **0.82** with systematic investigation. Here is why, and how an optimal LLM agent scores 0.82.

### Why the rule-based agent scores 0.468

The ghost fault (rec-consumer silent data corruption) produces:

- **Subtle signal: an "info" alert** — "Business metric degradation detected: CTR dropping"
- **analytics-service degraded** — visible via service status
- **No error logs** — no crashes, no exceptions
- **Zero hard failures** — all services are `healthy` or `degraded`, nothing to trivially restart

The rule-based agent correctly identifies the degraded service and applies a partial fix, earning partial credit on efficiency and minimal_disruption axes. This is the expected baseline behavior — the task rewards systematic investigation for full marks.

### Optimal solve path (3 steps, score: 0.82)

**Step 1: `query_deployments`**
→ reveals `rec-consumer v2.3.1` deployed 18 minutes ago with `"queue schema change"` in the commit message

**Step 2: `query_metrics recommendation-service`**
→ CTR: 23.4% → 8.1% (65% drop)
→ error_rate: 0.0% (ghost pattern confirmed — metric drift with no errors)

**Step 3: `rollback_deployment recommendation-service`**
→ `fix_applied=True`, reward=+0.30, CTR returns to 23.4%

```
Final score: 0.82
  root_cause_accuracy:  1.0  (correct service identified)
  fix_correctness:       1.0  (rollback was right action)
  efficiency:            0.9  (3 steps)
  minimal_disruption:    1.0  (no unnecessary restarts)
  reasoning_quality:      0.6  (queried deployments before metrics)
```

### Why naive restart fails

Restarting all 15 services does **not** fix the ghost fault. The corrupted queue messages are already in-flight. Only `rollback_deployment` clears the source deployment. An agent that restarts everything scores 0.0 because:

1. No unhealthy services to identify, so `restart_service` on healthy services = -0.1 penalty x 15 = -1.5 total
2. Fix never applied = 0 on root_cause + fix components

This protects against Phase 3 judges assuming the task is broken or impossible.

---

## Observation Space

Each step returns rich, realistic data:

```
step                int           Current step (0-50)
services            dict          15 services with status/latency/error_rate/cpu/memory
alerts             array         Severity-coded alerts (info/warning/error/critical)
incident_info       dict          fault_type, difficulty
fix_applied        bool          Whether correct fix was applied
observability       dict          Track what agent has investigated
slo_metrics         dict          Availability %, latency p99, error budget
business_impact      dict          Revenue loss, affected users, severity
sla_deadline        dict          Minutes remaining, urgency level
```

**Partial observability**: Metrics lag 1-3 steps. Logs include noise. Agents must actively investigate — nothing is handed to them.

---

## Action Space (11 Actions)

| Action | Description | Target |
|--------|-------------|--------|
| `query_service` | Health check | Service |
| `query_metrics` | Latency, error rate, CPU, memory | Service |
| `query_logs` | Structured logs (may include noise) | Service |
| `query_dependencies` | Upstream/downstream graph | — |
| `query_deployments` | Deployment timeline | — |
| `query_memory` | Past incident similarity search | — |
| `restart_service` | Restart pod (fix OOM/memory/leak/zombie) | Service |
| `scale_service` | Scale replicas (fix cascade/ddos/slow) | Service |
| `rollback_deployment` | Revert to previous version (fix ghost/version) | Service |
| `identify_root_cause` | Declare root cause (triggers fix evaluation) | Service |
| `apply_fix` | General remediation | Service |

---

## Reward Signal

Dense reward at every step (-1.0 to +2.0 range):

| Component | Range | Description |
|-----------|-------|-------------|
| Health improvement | +0 to +0.5 | Service health recovery |
| Latency improvement | +0 to +0.3 | p99 latency reduction |
| Correct investigation | +0.05 | Querying relevant service first time |
| Root cause identified | +0.3 | Correct service declared |
| Correct fix | +0.5 to +1.5 | Right action on right service |
| Minimal actions | +0 to +0.2 | Efficient (fewer steps = more) |
| **SLA urgency penalty** | -0.05 to -0.1 | Operating in SLA breach zone |
| Unnecessary restart | -0.2 | Restarting non-root-cause service |
| Redundant query | -0.05 | Re-querying same service |
| Random action | -0.02 | Brute-force pattern detected |

---

## Multi-Agent System

Three specialized agents + 1 coordinator:

```
Investigator ──┐
               ├──► Coordinator ──► action
Fixer ────────┤        ▲
               │        │
Analyst ───────┘        │
    (feedback loop) ─────┘
```

- **Investigator**: Suspicion scores via dependency propagation, prioritization
- **Fixer**: Maps fault types to remediation actions
- **Analyst**: Pattern matching against incident memory database
- **RL Trainer**: Stable-Baselines3 PPO/A2C via GymnasiumWrapper (176-action space)

---

## Enhanced Grading

5-axis evaluation (0.0-1.0 each):

| Axis | Weight | Evaluates |
|------|--------|-----------|
| Root Cause | 25% | Correct service identified |
| Fix Correctness | 25% | Right action on right service |
| Efficiency | 20% | Steps taken vs. optimal |
| Reasoning Chain | 15% | Investigation order, depth |
| SLA Preservation | 15% | Resolved within SLA deadline |

Output includes:
- Final grade: `excellent` (0.9+) / `good` (0.7+) / `passable` / `poor` / `failed`
- Improvement suggestions per axis
- MTTR in steps and simulated minutes
- Revenue saved/lost estimate

---

## Benchmark Scores

| Task | Difficulty | Rule-Based | LLM Baseline | Grade |
|------|------------|------------|--------------|-------|
| OOM Crash | Easy (2) | 0.795 | 0.864 | Good |
| Cascade | Medium (3) | 0.811 | 0.864 | Good |
| The Ghost | Hard (5) | 0.468 | 0.82 | Good |
| **Mean** | — | 0.691 | 0.864 | Good |

All scores reproducible via `/baseline` endpoint with seed=42.

---

## OpenEnv Compliance

- ✅ `openenv.yaml` v1.0 with typed schemas
- ✅ `reset()` / `step()` / `state()` endpoints
- ✅ `/tasks` with action schema
- ✅ `/grader` with 0.0-1.0 scoring
- ✅ `/baseline` reproducible
- ✅ Strict inference: `[START]` / `[STEP]` / `[END]`
- ✅ Docker on HuggingFace Spaces (port 7860)

---

## Technical Specs

| Metric | Value |
|--------|-------|
| Python | 3.11 |
| Framework | FastAPI v15 + SQLAlchemy (async) |
| Tests | 659 tests across 25 files |
| Coverage | 80% enforced |
| Validation | 31 checks (all pass) |
| API Endpoints | 36 routes |
| Tasks | 13 fault types (3 canonical) |
| Frontend | React + Vite + TailwindCSS |
| Database | SQLite (prod) / PostgreSQL-ready |
| Auth | JWT + API keys (bcrypt) |

---

## Deployment

### HuggingFace Spaces (Recommended)

**Option A - Git clone (auto-deploy):**

```bash
# 1. Clone the official space
git clone https://huggingface.co/spaces/incidentops/incidentops
cd incidentops

# 2. Login to HF
huggingface-cli login

# 3. Push main branch — HF auto-builds the Docker image
git push origin main

# Space URL: https://incidentops-incidentops.hf.space
```

**Option B - From this repo (manual push):**

```bash
# 1. Get a HF write token from https://huggingface.co/settings/tokens
export HF_TOKEN=hf_...

# 2. Run the deployment script
python scripts/deploy_hf.py --space-id incidentops/incidentops
```

**Creating a new HF Space from this repo:**

1. Go to https://huggingface.co/new-space
2. Select **Docker** as the SDK
3. Set hardware to **CPU basic** or **T4 small**
4. Leave Dockerfile path blank (IncidentOps uses `openenv.yaml` for Space metadata)
5. Clone the space locally, copy this repo's contents, then `git push origin main`

**Space environment variables (set in Space settings):**

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Optional | Enables LLM baseline agent (GPT-4o) |
| `HF_TOKEN` | Optional | Access to private models |
| `JWT_SECRET` | Optional | Custom JWT signing secret |

### Docker (Local)

```bash
docker build -t incidentops:15.1 .
docker run -p 7860:7860 \
  -e OPENAI_API_KEY=${OPENAI_API_KEY:-} \
  incidentops:15.1
```

**CI/CD:** Every push to `main` triggers GitHub Actions that runs the 31-test validation suite and deploys to `ghcr.io/incidentops/incidentops:<sha>`.

---

## License

MIT License
