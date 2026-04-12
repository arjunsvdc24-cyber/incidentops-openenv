# ADR-001: Typed Observation Models over Plain Dicts

## Status
Accepted

## Context

The IncidentOps RL environment exposes state via an `observation` dictionary returned from `env.step()` and `env.reset()`. Early versions of the codebase used plain Python `dict` objects with arbitrary keys, loosely documented in docstrings. Consumers of the API (dashboard, grading system, LLM agent) had to introspect dicts at runtime to understand available fields, leading to fragile code and runtime errors.

Two concrete problems emerged:
1. The dashboard's TypeScript frontend needed a canonical schema to generate type-safe API clients — without a formal model, developers had to maintain a separate hand-written `.d.ts` file that could drift from the actual Python output.
2. The grader and reward system accessed fields like `root_cause_service` and `correct_fix` by string key — typos in field names were only caught at runtime, causing silent scoring bugs in production.

Pydantic models were the natural choice given the existing FastAPI + Pydantic stack.

## Decision

We adopted Pydantic `BaseModel` for all API request/response schemas and for the RL environment's observation output. Specifically:

- `StepResponse` (observation + reward + terminated + info) is a typed Pydantic model
- `ObservationState` (services, alerts, metrics, logs) is a typed Pydantic model
- All 11 action types are defined as `ActionType` enum values (not raw strings)
- The `openenv.yaml` schema file reflects the actual Pydantic field names and types

The environment still serializes to a `dict` for Gym compatibility, but the internal representation is typed. The FastAPI layer re-validates the dict against the Pydantic model before returning it.

## Consequences

**Positive:**
- OpenAPI schema auto-generated from Pydantic models — Swagger docs are always in sync with the actual API
- TypeScript code generation tools (or manual translation) can produce a matching TypeScript interface
- Field typos are caught at validation time (Pydantic raises `ValidationError`) rather than silently producing wrong scores
- IDE autocomplete works for all response fields

**Negative:**
- Adding a new observation field requires updating two places: the Python model and the TypeScript interface
- Pydantic validation has a small runtime cost (~0.1–0.3 ms per request); acceptable for this workload

**Neutral:**
- The decision is localized to `app/models.py` — changing the serialization format does not affect the RL environment logic
