"""
IncidentOps - Thundering Herd / Cache Stampede Fault

Cache misses cause all services to hit database simultaneously.
Database CPU spike, cascading latency.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.faults.base import BaseFault
from app.fault_injector import DependencyPropagator, FaultScenario, FaultType

if TYPE_CHECKING:
    from app.determinism import DeterministicRNG


class ThunderingHerdFault(BaseFault):
    """
    Thundering herd / cache stampede fault.

    Cache misses cause all services to hit database simultaneously.
    Database CPU spike, cascading latency.

    Symptoms:
    - Cache hit rate drops to 0
    - Database CPU spikes
    - All requests hit DB at once
    - Cascading latency

    Correct fix: restart_service on cache-service
    """

    name = "thundering_herd"
    difficulty_range = (1, 5)
    affected_services_hint = [
        "cache-service",
        "database-primary",
        "api-gateway",
        "user-service",
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a thundering herd scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Root cause is the cache service
        cache_candidates = [s for s in services if "cache" in s]
        if cache_candidates:
            root_cause = cache_candidates[0]
        else:
            root_cause = rng.choice(services)

        # Database is affected as all requests hit it
        affected = [root_cause]
        if "database-primary" in services:
            affected.append("database-primary")
        if "database-replica" in services:
            affected.append("database-replica")

        # Add services that depend on cache
        cache_dependents = DependencyPropagator.REVERSE_DEPENDENCY_GRAPH.get(root_cause, [])
        affected.extend(rng.sample(cache_dependents, min(difficulty, len(cache_dependents))))

        # Symptoms
        symptoms = self.get_symptoms()

        # Misleading signals - point to database or application issues
        misleading_signals = [
            f"{rng.choice(services)}: ERROR: Database connection slow",
            f"{rng.choice(services)}: WARNING: Query timeout",
        ]

        if difficulty >= 4:
            misleading_signals.extend([
                f"{rng.choice(services)}: ERROR: Database CPU at 100%",
                f"{rng.choice(services)}: WARNING: Lock contention detected",
            ])

        return FaultScenario(
            fault_type=FaultType.THUNDERING_HERD,
            root_cause_service=root_cause,
            affected_services=list(set(affected))[:difficulty + 3],
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_metrics:cache_hit_rate",
                "query_metrics:db_cpu",
                "identify_cache_stampede",
                "warm_cache",
            ],
            correct_fix=f"restart_service:{root_cause}",
            difficulty=difficulty,
            degradation_pattern={
                "metric_name": "cache_hit_rate",
                "initial_value": 0.85,
                "final_value": 0.0,
                "pattern": "sudden_drop",
            },
        )

    def get_symptoms(self) -> list[str]:
        """Get thundering herd symptoms"""
        return [
            "Cache hit rate drops to 0%",
            "Database CPU spikes to 100%",
            "All services hitting DB simultaneously",
            "Cascading latency across services",
            "Database connection pool exhausted",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "WARNING: Cache miss: key=user_data_123",
            "WARNING: Cache stampede detected - 100 requests for same key",
            "INFO: Database query flood: 5000 queries/second",
            "WARNING: DB CPU at 95%",
            "ERROR: Connection pool exhausted",
            "WARNING: Cache TTL expired for popular keys",
        ]

    def get_metric_noise_patterns(self) -> list[str]:
        """Get characteristic metric patterns"""
        return [
            "cache_hit_rate drops from 85% to 0%",
            "database_cpu spikes to 100%",
            "db_queries_per_second spikes 100x",
            "latency_p99 spikes",
        ]
