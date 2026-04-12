# ADR-002: Deterministic Environment (No datetime.now)

## Status
Accepted

## Context

The IncidentOps environment must produce identical observations for the same `seed` value, even when episodes are run weeks apart on different machines. This is critical for:

1. **Reproducibility** — grading and leaderboard scoring must be stable; the same trajectory must receive the same score regardless of when or where it was recorded
2. **RL training** — agents trained in simulation need consistent reset behavior; non-deterministic seeds would make training runs incomparable
3. **Hackathon validation** — the OpenEnv harness runs episodes with known seeds and compares baseline scores; any non-determinism breaks the comparison

Initial versions of the codebase used `datetime.now()` and `datetime.utcnow()` in alert timestamps, metric generation, and log entries. This made the environment non-deterministic in two ways:
- `datetime.now()` uses the system clock, which changes between runs
- `datetime.utcnow()` is deprecated and also wall-clock dependent

## Decision

We adopted a fully deterministic datetime strategy:

1. **Fixed epoch**: All datetime values are fixed to `datetime(2024, 1, 15, 10, 0, 0)` — a deterministic "fictional now" used uniformly across the codebase
2. **Seed-based RNG for stochasticity**: Where randomness is needed (metric noise, log content variation), a `random.Random(seed)` instance seeded at environment creation drives all stochastic choices
3. **Forbidden APIs**: `datetime.now()`, `datetime.utcnow()`, `time.time()`, and `random.random()` (module-level) are replaced with seeded equivalents
4. **Validation test**: `app/determinism.py` runs a reproducibility check that resets the environment twice with the same seed and asserts the observations are byte-identical

```python
# Before (non-deterministic):
timestamp = datetime.utcnow().isoformat()

# After (deterministic):
FIXED_TIME = datetime(2024, 1, 15, 10, 0, 0)
timestamp = FIXED_TIME.isoformat()
```

## Consequences

**Positive:**
- Episodes are byte-for-byte reproducible across any machine and time — critical for leaderboard fairness
- Debugging is easier: the same seed always produces the same trace
- RL training runs are comparable: two researchers using seed=42 get identical environments
- OpenEnv validation harness scores are stable

**Negative:**
- Alert timestamps in replay data are always the same fictional time — visually misleading in playback timelines
- Metrics always show the same fictional "current time" — minor cosmetic limitation

**Neutral:**
- The fixed epoch `2024-01-15T10:00:00` is arbitrary but consistent; any fixed datetime works equally well
