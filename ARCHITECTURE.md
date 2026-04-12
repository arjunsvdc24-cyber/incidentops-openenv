# IncidentOps Architecture

This document describes the system architecture, service topology, agent coordination, and database schema.

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              IncidentOps System                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         Frontend Layer                                  │  │
│  │  ┌───────────────────┐           ┌─────────────────────────────────┐   │  │
│  │  │  React Dashboard  │           │    OpenAPI Docs (Swagger/Redoc)  │   │  │
│  │  │  Vite + Tailwind  │           │    Interactive API Explorer       │   │  │
│  │  │  Port 3000 (dev)  │           │    Port 7860/docs                 │   │  │
│  │  └───────────────────┘           └─────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                          │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                      FastAPI Backend (app/main.py)                    │  │
│  │                                                                          │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐    │  │
│  │  │                      API Endpoints (36 routes)                  │    │  │
│  │  │  /reset /step /state     → OpenEnv Core Interface               │    │  │
│  │  │  /tasks /grader /baseline → Evaluation & Grading               │    │  │
│  │  │  /auth/* /me            → JWT Authentication                   │    │  │
│  │  │  /episodes /leaderboard /stats → Persistence & Rankings        │    │  │
│  │  │  /ws                    → WebSocket Real-time Updates         │    │  │
│  │  │  /health /metrics /validation → Operational & Monitoring       │    │  │
│  │  └──────────────────────────────────────────────────────────────────┘    │  │
│  │                                    │                                    │  │
│  │  ┌─────────────────────────────────┼──────────────────────────────┐    │  │
│  │  │                                 ▼                              │    │  │
│  │  │  ┌─────────────────────────────────────────────────────────┐    │    │  │
│  │  │  │            IncidentEnv (Core RL Environment)             │    │    │  │
│  │  │  │                                                          │    │    │  │
│  │  │  │  ┌─────────────┐  ┌──────────────────┐  ┌──────────────┐  │    │    │  │
│  │  │  │  │    Fault    │  │   15-Service     │  │   Reward /  │  │    │    │  │
│  │  │  │  │  Injector   │─►│  Mesh Topology   │─►│   Grader    │  │    │    │  │
│  │  │  │  │ (13 faults) │  │  (Observations) │  │ (5-axis)    │  │    │    │  │
│  │  │  │  └─────────────┘  └──────────────────┘  └──────────────┘  │    │    │  │
│  │  │  │                                                          │    │    │  │
│  │  │  │  ┌───────────────────────────────────────────────────┐    │    │    │  │
│  │  │  │  │              Agent System                         │    │    │    │  │
│  │  │  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐        │    │    │    │  │
│  │  │  │  │  │Investiga-│  │  Fixer   │  │ Analyst  │        │    │    │    │  │
│  │  │  │  │  │   tor    │─►│          │─►│          │        │    │    │    │  │
│  │  │  │  │  └────┬─────┘  └──────────┘  └──────────┘        │    │    │    │  │
│  │  │  │  │       │                                        │    │    │    │  │
│  │  │  │  │       └────────────► Coordinator ◄───────────┘    │    │    │    │  │
│  │  │  │  └───────────────────────────────────────────────────┘    │    │    │  │
│  │  │  └─────────────────────────────────────────────────────────┘    │    │    │
│  │  └──────────────────────────────────────────────────────────────────┘    │
│  │                                    │                                    │
│                                    ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │              SQLAlchemy Async (SQLite / PostgreSQL-ready)              │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐       │ │
│  │  │  Users   │  │ Episodes │  │Leaderboard│ │   Statistics       │       │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────────┘       │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 15-Service Microservice Topology

The environment simulates a production e-commerce platform with 15 interconnected services:

```
                            ┌─────────────────┐
                            │   API Gateway   │  ← Entry point (port 8080)
                            │  (api-gateway)  │
                            └────────┬────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
     ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
     │    User         │◄──│    Auth        │   │   Payment      │ ← Fault target
     │   Service       │◄──►│   Service      │   │  (payment-     │   (OOM/Crash)
     │ (user-service)  │    │ (auth-service)│   │   service)     │
     └────────┬────────┘    └────────────────┘   └────────┬────────┘
              │                                        │
              │                                        │
              ▼                                        ▼
     ┌────────────────┐                    ┌────────────────┐
     │    Cache       │◄────────────────────│    Order       │
     │   Service      │                    │   Service      │
     │(cache-service) │                    │(order-service) │
     └────────┬────────┘                    └───────┬────────┘
              │                                     │
              │            ┌─────────────────────────┤
              │            │                         │
              ▼            ▼                         ▼
     ┌────────────────┐ ┌───────────────────────────────┐
     │  Database-     │ │     Notification Service      │
     │  Primary       │ │  (notification-service)        │
     │(database-      │ │                                │
     │  primary)      │ │         ◄───► Email Service ◄───►│
     └────────┬───────┘ │        (email-service)         │
              │        └───────────────────────────────────┘
              │
     ┌────────┴────────┐
     │                 │
     ▼                 ▼
┌──────────┐    ┌────────────────┐
│Database- │    │    Services    │
│ Replica  │    │  depending on  │
│(database-│    │  primary DB:   │
│ replica) │    │                │
└──────────┘    │ • Inventory    │
                │ • Recommendation
                │ • Search
                │ • Analytics
                │ • Shipping
                │ • Notification
                │ • Email
                │ • Notification
                └────────────────┘

Service dependencies flow upward through the graph.
Failures cascade downward (e.g., DB failure → all dependent services fail).
```

### Service Definitions

| Service | Port | Type | Dependencies | Common Faults |
|---------|------|------|--------------|---------------|
| `api-gateway` | 8080 | Gateway | — | DDoS, overload |
| `user-service` | 8081 | Business | auth, cache | Slow downstream |
| `auth-service` | 8082 | Business | database-primary | Config drift |
| `payment-service` | 8083 | Business | database-primary, order-service | OOM, crash |
| `order-service` | 8084 | Business | inventory, payment, database-primary | Memory leak |
| `inventory-service` | 8085 | Business | database-primary | Data corruption |
| `recommendation-service` | 8086 | Business | analytics, cache | Ghost corruption |
| `notification-service` | 8087 | Business | email-service | Slow downstream |
| `cache-service` | 8088 | Infrastructure | database-primary | Thundering herd |
| `database-primary` | 5432 | Data | — | Cascade, pool exhaustion |
| `database-replica` | 5433 | Data | database-primary | Network partition |
| `search-service` | 8089 | Business | database-primary, cache | Slow downstream |
| `analytics-service` | 8090 | Business | database-primary | Data corruption |
| `email-service` | 8091 | Business | database-primary | Zombie process |
| `shipping-service` | 8092 | Business | order-service | Cert expiry |

---

## Agent Coordination Flow

The multi-agent system uses a observe → plan → act → evaluate loop:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Agent Coordination Flow                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐                                                 │
│   │   INCIDENT   │                                                 │
│   │   DETECTED   │                                                 │
│   └──────┬───────┘                                                 │
│          │                                                         │
│          ▼                                                         │
│   ┌──────────────────────────────────────────────────────────┐     │
│   │                    OBSERVE PHASE                         │     │
│   │                                                          │     │
│   │  ┌────────────────┐     ┌────────────────┐              │     │
│   │  │  Investigator   │────►│  Information   │              │     │
│   │  │   Agent        │     │   Tracker      │              │     │
│   │  │                │     │                │              │     │
│   │  │ • Suspicion    │     │ • Observed     │              │     │
│   │  │   scoring      │     │   services     │              │     │
│   │  │ • Dependency   │     │ • Log patterns │              │     │
│   │  │   propagation  │     │ • Metric drift │              │     │
│   │  └───────┬────────┘     └────────────────┘              │     │
│   │          │                                               │     │
│   └──────────┼───────────────────────────────────────────────┘     │
│              │                                                       │
│              ▼                                                       │
│   ┌──────────────────────────────────────────────────────────┐     │
│   │                     PLAN PHASE                            │     │
│   │                                                          │     │
│   │  ┌────────────────┐     ┌────────────────┐              │     │
│   │  │   Coordinator   │────►│    Analyst     │              │     │
│   │  │     Agent       │     │    Agent       │              │     │
│   │  │                │     │                │              │     │
│   │  │ • Synthesizes   │     │ • Pattern      │              │     │
│   │  │   findings     │     │   matching     │              │     │
│   │  │ • Prioritizes  │     │ • Historical   │              │     │
│   │  │   actions      │     │   incidents    │              │     │
│   │  └───────┬────────┘     └────────────────┘              │     │
│   │          │                                               │     │
│   └──────────┼───────────────────────────────────────────────┘     │
│              │                                                       │
│              ▼                                                       │
│   ┌──────────────────────────────────────────────────────────┐     │
│   │                      ACT PHASE                            │     │
│   │                                                          │     │
│   │  ┌────────────────┐     ┌────────────────┐              │     │
│   │  │    Fixer       │────►│  Environment   │              │     │
│   │  │    Agent       │     │                │              │     │
│   │  │                │     │ • restart_     │              │     │
│   │  │ • Maps faults  │     │   service     │              │     │
│   │  │   to fixes    │     │ • scale_       │              │     │
│   │  │ • Executes    │     │   service     │              │     │
│   │  │   remediation │     │ • rollback_    │              │     │
│   │  └───────┬────────┘     │   deployment  │              │     │
│   │          │               └────────────────┘              │     │
│   └──────────┼───────────────────────────────────────────────┘     │
│              │                                                       │
│              ▼                                                       │
│   ┌──────────────────────────────────────────────────────────┐     │
│   │                   EVALUATE PHASE                          │     │
│   │                                                          │     │
│   │  ┌────────────────┐     ┌────────────────┐              │     │
│   │  │    Grader      │◄────│   Action       │              │     │
│   │  │                │     │   Tracker      │              │     │
│   │  │ • Root cause   │     │                │              │     │
│   │  │ • Fix correct  │     │ • Brute-force  │              │     │
│   │  │ • Efficiency  │     │   detection    │              │     │
│   │  │ • Reasoning   │     │ • Redundancy   │              │     │
│   │  │ • SLA preserved│     │   penalties   │              │     │
│   │  └────────────────┘     └────────────────┘              │     │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent | Primary Role | Key Methods |
|-------|-------------|------------|
| **Investigator** | Suspicion scoring via dependency propagation | `score_suspicion()`, `propagate_alerts()` |
| **Fixer** | Maps fault types to remediation actions | `determine_fix()`, `execute_remediation()` |
| **Analyst** | Pattern matching against incident memory | `match_pattern()`, `search_similar()` |
| **Coordinator** | Synthesizes agent outputs, prioritizes actions | `coordinate()`, `prioritize()` |
| **Action Tracker** | Detects brute-force patterns, tracks redundancy | `track_action()`, `detect_brute_force()` |
| **Information Tracker** | Scores reasoning quality | `score_reasoning()`, `track_investigation()` |

---

## Database Schema

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Database Schema                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐      ┌──────────────────┐                    │
│  │      users       │      │     episodes      │                    │
│  ├──────────────────┤      ├──────────────────┤                    │
│  │ id (PK)          │      │ id (PK)          │                    │
│  │ username (UK)    │◄────┐│ user_id (FK)     │◄───┐               │
│  │ email (UK)       │      │ task_id          │    │               │
│  │ password_hash    │      │ score            │    │               │
│  │ is_active        │      │ trajectory (JSON)│    │               │
│  │ created_at       │      │ seed             │    │               │
│  │ last_login       │      │ difficulty       │    │               │
│  └──────────────────┘      │ status          │    │               │
│                             │ created_at      │    │               │
│                             └──────────────────┘    │               │
│                                                     │               │
│                             ┌──────────────────┐    │               │
│                             │   leaderboard    │    │               │
│                             ├──────────────────┤    │               │
│                             │ id (PK)          │    │               │
│                             │ episode_id (FK)  │────┘               │
│                             │ task_id          │                    │
│                             │ score            │                    │
│                             │ rank              │                    │
│                             │ recorded_at       │                    │
│                             └──────────────────┘                    │
│                                                                     │
│                             ┌──────────────────┐                    │
│                             │   statistics     │                    │
│                             ├──────────────────┤                    │
│                             │ id (PK)          │                    │
│                             │ metric_type      │                    │
│                             │ value            │                    │
│                             │ recorded_at      │                    │
│                             │ metadata (JSON)  │                    │
│                             └──────────────────┘                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Table Relationships

```
users (1) ──── (N) episodes ──── (1) leaderboard
                              │
                              └─── (N) statistics

• Each user can have multiple recorded episodes
• Each episode appears on the leaderboard once
• Statistics are aggregated from all episodes
```

---

## Fault Injection Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Fault Injection Flow                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐       │
│   │   /reset     │────►│   Fault      │────►│   Service    │       │
│   │  (seed,      │     │  Injector    │     │    Mesh      │       │
│   │   fault_     │     │              │     │              │       │
│   │   type)      │     │ • Selects    │     │ • Applies    │       │
│   │              │     │   fault      │     │   metrics    │       │
│   │              │     │ • Injects    │     │ • Generates  │       │
│   │              │     │   into       │     │   alerts     │       │
│   │              │     │   services   │     │              │       │
│   └──────────────┘     └──────────────┘     └──────────────┘       │
│                                                            │       │
│                                                            ▼       │
│   ┌────────────────────────────────────────────────────────────────┐│
│   │                 Deceptive Signal Generator                      ││
│   │                                                                  ││
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           ││
│   │  │ False Alert │  │  Metric Lag  │  │  Cascade     │           ││
│   │  │  Patterns   │  │  (1-3 steps) │  │   Effects    │           ││
│   │  └──────────────┘  └──────────────┘  └──────────────┘           ││
│   │                                                                  ││
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           ││
│   │  │ Ghost Deploy │  │  Noisy Logs │  │ Misleading   │           ││
│   │  │   (silent)  │  │             │  │  Warnings    │           ││
│   │  └──────────────┘  └──────────────┘  └──────────────┘           ││
│   └────────────────────────────────────────────────────────────────┘│
│                                    │                                 │
│                                    ▼                                 │
│   ┌────────────────────────────────────────────────────────────────┐│
│   │                 Agent Receives Observation                      ││
│   │                                                                  ││
│   │  • Services: some degraded (not necessarily the root cause)    ││
│   │  • Alerts: false positives pointing away from root             ││
│   │  • Metrics: lagging, incomplete                                ││
│   │  • Logs: noisy, misleading                                    ││
│   │                                                                  ││
│   │  Agent must: INVESTIGATE before acting                         ││
│   └────────────────────────────────────────────────────────────────┘│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Deployment Topology                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    Production (Docker)                        │   │
│   │                                                              │   │
│   │   ┌─────────────────────────────────────────────────────┐   │   │
│   │   │              Container (port 7860)                   │   │   │
│   │   │                                                      │   │   │
│   │   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │   │
│   │   │   │  FastAPI   │  │  SQLite    │  │   React     │  │   │   │
│   │   │   │  Backend   │  │  Database  │  │  Dashboard  │  │   │   │
│   │   │   │            │  │            │  │  (static)   │  │   │   │
│   │   │   └─────────────┘  └─────────────┘  └─────────────┘  │   │   │
│   │   └─────────────────────────────────────────────────────┘   │   │
│   │                                                              │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                               │                                     │
│                               ▼                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                  HuggingFace Spaces                          │   │
│   │                                                              │   │
│   │   Git Push ──► GitHub Actions ──► Docker Build ──► HF Space  │   │
│   │                                                              │   │
│   │   • Automated CI/CD on push to main                          │   │
│   │   • Docker image at ghcr.io/incidentops/incidentops:<sha>    │   │
│   │   • Space URL: https://incidentops-incidentops.hf.space      │   │
│   │   • Hardware: CPU basic or T4 small                          │   │
│   │                                                              │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                  Local Development                           │   │
│   │                                                              │   │
│   │   Backend: python -m app.main          (port 7860)          │   │
│   │   Dashboard: cd dashboard && npm run dev (port 3000)        │   │
│   │   Database: SQLite file (incidentops.db)                   │   │
│   │                                                              │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend** | FastAPI v15 | REST API, WebSocket, async |
| **Database** | SQLite (prod) / PostgreSQL (ready) | Persistence via SQLAlchemy async |
| **Auth** | JWT + API keys | Stateless auth with bcrypt hashing |
| **RL Environment** | Gymnasium-compatible | reset/step/state interface |
| **Agents** | Multi-agent system | Investigator, Fixer, Analyst, Coordinator |
| **Grading** | 5-axis SRE evaluator | Root cause, fix, efficiency, reasoning, SLA |
| **Frontend** | React + Vite + TailwindCSS | Interactive dashboard |
| **State** | Zustand | Lightweight React state management |
| **Charts** | Recharts | Real-time visualization |
| **Monitoring** | Prometheus + Grafana | Metrics and dashboards |
| **Container** | Docker | Reproducible deployment |
| **CI/CD** | GitHub Actions | Automated testing and deployment |
