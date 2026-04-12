# ADR-003: Anti-Brute-Force Detection (Deceptive Signals + Action Tracking)

## Status
Accepted

## Context

The original IncidentOps environment was susceptible to a brute-force strategy: an agent could cycle through every service and every action within the step limit, guaranteeing discovery of the root cause by exhaustion. This trivially defeats the purpose of the SRE training scenario, which is designed to reward systematic investigation and causal reasoning.

The core problem is that the observation space provides only partial information — a correct agent must actively investigate and correlate signals across services to identify the root cause. A brute-force agent ignores investigation quality and simply tries every combination.

## Decision

We implemented a two-layer anti-brute-force system:

### Layer 1: Deceptive Signals (`app/deceptive_signals.py`)

Injected signals that are plausible but irrelevant to the actual root cause. These are generated per scenario and per action type, and are returned alongside genuine signals in logs and metrics queries. They increase the cost of brute-force by creating false leads that must be recognized and discarded.

Example: during a `ghost` fault (silent recommendation corruption), logs from `auth-service` and `user-db` show misleading connection pool warnings. An agent that acts on these misleading signals wastes steps and receives a lower efficiency score.

### Layer 2: Action Tracking + Penalty (`app/action_tracker.py`, `app/information_tracker.py`)

A stateful tracker records every action taken in an episode and computes a reasoning-quality score. Excessive repetition, random targeting, and blind action sequences incur escalating penalties that reduce the final episode score.

Key metrics tracked:
- **Investigation sequence**: Were actions performed in a logical order?
- **Service diversity vs repetition**: Repeating the same service many times signals guessing behavior
- **Information gain**: Did each action provide new information, or was it redundant?
- **Confidence score**: The multi-agent coordinator uses this to decide when to activate the fixer

A penalty is applied to the reward at each step and to the final score by the grader.

## Consequences

**Positive:**
- Agents must reason systematically — brute-force is no longer optimal
- The deceptive signals encourage reading and interpreting logs, not just scanning for errors
- Action tracking provides rich data for post-episode analysis and coaching
- The reasoning-quality dimension in the grader rewards good investigation habits

**Negative:**
- Legitimate random exploration (e.g., early in training) is penalized, which may slow RL policy convergence
- Deceptive signals require careful tuning to be plausible without being frustrating
- Action tracking adds statefulness to the environment — the tracker must be reset with each episode

**Neutral:**
- The system does not block brute-force outright; it penalizes it. An agent that prioritizes score must still reason correctly.
- This decision interacts with ADR-002: the deterministic seed means deceptive signal generation is also deterministic, so the same agent behavior produces the same penalty across runs.
