# Changelog

All notable changes to IncidentOps are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [15.1] — 2026-04-10

### Changed

- **Full UI/UX audit** — Complete dashboard polish with premium styling across all pages
- **Dashboard fixes** — All pages validated: episodes, leaderboard, tasks, audit, validation
- **README.md polish** — Rewritten for hackathon judges with "Judge This" scoring section, benchmark table, architecture diagrams, getting started section, and complete API documentation
- **openenv.yaml** — Enhanced with comprehensive descriptions and all 15 fault types documented

### Added

- **TROUBLESHOOTING.md** — Common issues guide with quick fix commands
- **ARCHITECTURE.md** — System architecture documentation with text-based diagrams

### Fixed

- **API documentation** — All 36 endpoints documented with descriptions
- **Getting started section** — Docker one-liner + local dev instructions added to README
- **Benchmark table** — Easy-to-scan scores for all 3 canonical tasks in README

---

## [15.1] — 2026-04-09

### Added
- **Observability**: `/ready` (Kubernetes readiness probe) and `/live` (Kubernetes liveness probe) endpoints
- **Request ID correlation**: Unique request ID injected via middleware, returned in `X-Request-ID` response header
- **CHANGELOG.md**: This file — full project changelog going forward
- **Architecture Decision Records** (`docs/adr/`): ADR-001 (typed observation models), ADR-002 (deterministic environment), ADR-003 (anti-brute-force)
- **TROUBLESHOOTING.md** (`docs/`): Common issues and resolutions
- **Grafana dashboard enhancement**: Added panels for episode success rate, average episode length, action distribution, agent decision latency histogram, memory hit rate

### Changed
- **Dockerfile hardening**: Non-root user (`appuser:1000`), `COPY --chown` for all artifacts, `USER` directive, resource-limit HEALTHCHECK
- **Security hardening**: JWT secret validation warning at startup, API key checked for embedded newlines
- **API info version**: Bumped to 15.1

### Fixed
- **Test infrastructure**: PyO3/bcrypt lazy import issue resolved — bcrypt imported only when password hashing is needed
- **UI accessibility**: Dashboard contrast, focus states, keyboard navigation improvements
- **Pre-built dashboard**: Eliminated builder stage for Docker — `dashboard/dist/` is committed directly

### Security
- Container runs as non-root user (UID 1000)
- No hardcoded secrets in Docker image
- HEALTHCHECK validates readiness without exposing internals

---

## [15.0] — 2026-04-08

### Added
- **Full FastAPI backend** with 28+ REST endpoints + WebSocket support
- **15-service microservice architecture** (payment-service, user-db, api-gateway, etc.)
- **RL environment** (`IncidentEnv`) with Gym-compatible API (`reset`, `step`)
- **10 fault types**: OOM Crash, Cascade, Ghost, Network Partition, Data Corruption, Config Drift, DDoS, Slow Downstream, Version Mismatch, Cert Expiry
- **3 canonical tasks**: OOM Crash (easy), The Cascade (medium), The Ghost (hard)
- **Multi-agent system**: Investigator, Fixer, Analyst, Coordinator
- **Baseline agent** (rule-based + LLM with OpenAI/Groq/Gemini support)
- **Enhanced grader** with 5-axis SRE evaluation breakdown
- **Deceptive signals** anti-brute-force system
- **Action tracker** with brute-force detection and penalty
- **Information tracker** with reasoning score
- **Deterministic environment** (seed-based, no `datetime.now`)
- **Comprehensive validation** (31-test suite)
- **Frontier task generator** for difficulty-escalated scenarios
- **Episode recording & replay** with SQLite persistence
- **Leaderboard** with ranked scores per task
- **JWT + API key authentication** (bcrypt hashed)
- **React dashboard** (Vite + TypeScript + Tailwind) with real-time charts
- **Grafana + Prometheus** monitoring stack
- **OpenEnv-compatible** (`openenv.yaml` schema)
- **HuggingFace Spaces** deployment (Docker, pre-built dashboard)
- **Docker Compose** for local development
