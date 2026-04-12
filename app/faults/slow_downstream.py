"""
IncidentOps - Slow Downstream Dependency Fault

A dependency service is responding slowly.
Cascading latency through dependent services.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.faults.base import BaseFault
from app.fault_injector import DependencyPropagator, FaultScenario, FaultType

if TYPE_CHECKING:
    from app.determinism import DeterministicRNG


class SlowDownstreamFault(BaseFault):
    """
    Slow downstream dependency fault.

    A dependency service is responding slowly.
    Cascading latency through all dependent services.

    Symptoms:
    - Latency 5-10x baseline
    - Timeout errors
    - Slow queries accumulating
    - Backpressure signals

    Correct fix: restart_service on slow service OR scale_service
    """

    name = "slow_downstream"
    difficulty_range = (2, 5)
    affected_services_hint = [
        "database-primary",
        "database-replica",
        "cache-service",
        "auth-service",
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a slow downstream scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Root cause is typically a core dependency
        root_candidates = [
            s for s in services
            if any(keyword in s for keyword in ["database", "cache", "auth"])
        ]
        if not root_candidates:
            root_candidates = list(DependencyPropagator.DEPENDENCY_GRAPH.keys())

        root_cause = rng.choice(root_candidates)

        # Get all services that depend on this
        affected = [root_cause]
        dependents = DependencyPropagator.REVERSE_DEPENDENCY_GRAPH.get(root_cause, [])
        affected.extend(rng.sample(dependents, min(difficulty + 2, len(dependents))))

        # Symptoms
        symptoms = self.get_symptoms()

        # Misleading signals - point to upstream issues
        misleading_signals = [
            f"{rng.choice(services)}: WARNING: Slow response from {root_cause}",
            f"{rng.choice(services)}: INFO: Retrying request to {root_cause}",
        ]

        if difficulty >= 4:
            misleading_signals.extend([
                f"{rng.choice(services)}: ERROR: Deadlock detected",
                f"{rng.choice(services)}: WARNING: Thread pool exhausted",
            ])

        return FaultScenario(
            fault_type=FaultType.SLOW_DOWNSTREAM,
            root_cause_service=root_cause,
            affected_services=affected[:difficulty + 3],
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_metrics:latency",
                "query_dependencies:trace_slowdown",
                "identify_slow_service",
                "restart_or_scale",
            ],
            correct_fix=f"restart_service:{root_cause}",
            difficulty=difficulty,
            degradation_pattern={
                "metric_name": "latency_p99",
                "initial_value": 100,
                "final_value": 5000,
                "pattern": "gradual_increase",
            },
        )

    def get_symptoms(self) -> list[str]:
        """Get slow downstream symptoms"""
        return [
            "Latency 5-10x baseline",
            "Timeout errors accumulating",
            "Slow queries building up",
            "Backpressure signals in logs",
            "Request queue growing",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "WARNING: Response time exceeds threshold: 5000ms",
            "WARNING: Slow query detected: execution time 10s",
            "Timeout waiting for response from downstream",
            "WARNING: Retry attempt 2 of 3",
            "Connection pool waiting for available connection",
            "WARNING: Backpressure applied to incoming requests",
        ]

    def get_metric_noise_patterns(self) -> list[str]:
        """Get characteristic metric patterns"""
        return [
            "latency_p99 increases 5-10x baseline",
            "timeout_error_rate increases",
            "throughput decreases",
            "queue_depth grows",
        ]
