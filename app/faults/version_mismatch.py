"""
IncidentOps - API Version Mismatch Fault

A service deployed with incompatible API version.
500 errors, schema mismatches, type errors.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.faults.base import BaseFault
from app.fault_injector import (
    DeployEvent,
    DependencyPropagator,
    FaultScenario,
    FaultType,
    get_deterministic_timestamp,
)

if TYPE_CHECKING:
    from app.determinism import DeterministicRNG


class VersionMismatchFault(BaseFault):
    """
    API version mismatch fault.

    A service deployed with incompatible API version.
    500 errors, schema mismatches, type errors.

    Symptoms:
    - 500 error rate spike
    - Schema mismatch errors
    - Type conversion errors
    - Failed API calls

    Correct fix: rollback_deployment
    """

    name = "version_mismatch"
    difficulty_range = (2, 5)
    affected_services_hint = [
        "order-service",
        "payment-service",
        "user-service",
        "recommendation-service",
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a version mismatch scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Pick a service that has dependents (so API changes matter)
        root_candidates = [
            s for s in services
            if DependencyPropagator.REVERSE_DEPENDENCY_GRAPH.get(s)
        ]
        if not root_candidates:
            root_candidates = [s for s in services if "service" in s]

        root_cause = rng.choice(root_candidates)

        # Affected are services calling the mismatched API
        affected = [root_cause]
        callers = DependencyPropagator.REVERSE_DEPENDENCY_GRAPH.get(root_cause, [])
        affected.extend(rng.sample(callers, min(difficulty + 1, len(callers))))

        # Generate timeline with version bump
        timeline = self._generate_version_timeline(rng, root_cause)

        # Symptoms
        symptoms = self.get_symptoms()

        # Misleading signals
        misleading_signals = [
            f"{rng.choice(services)}: ERROR: Null response from API",
            f"{rng.choice(services)}: WARNING: Client timeout",
        ]

        if difficulty >= 4:
            misleading_signals.extend([
                f"{rng.choice(services)}: ERROR: Client library outdated",
                f"{rng.choice(services)}: WARNING: Feature not available",
            ])

        return FaultScenario(
            fault_type=FaultType.VERSION_MISMATCH,
            root_cause_service=root_cause,
            affected_services=affected[:difficulty + 2],
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_deployments:recent",
                "query_logs:schema_error",
                "compare_api_versions",
                "rollback_deployment",
            ],
            correct_fix=f"rollback_deployment:{root_cause}",
            difficulty=difficulty,
            deploy_timeline=timeline,
        )

    def _generate_version_timeline(
        self,
        rng: "DeterministicRNG",
        root_cause: str
    ) -> list[DeployEvent]:
        """Generate timeline with version bump"""
        timeline = []

        # Normal deployments
        for i in range(4):
            timeline.append(DeployEvent(
                timestamp=get_deterministic_timestamp(rng.seed, offset_hours=i * 8),
                service=rng.choice(list(DependencyPropagator.DEPENDENCY_GRAPH.keys())),
                version=f"v1.{i}.0",
                commit_hash=f"abc{i:03d}",
                author="alice",
                description=f"Regular update {i}",
            ))

        # Problematic version bump
        timeline.append(DeployEvent(
            timestamp=get_deterministic_timestamp(rng.seed, offset_hours=36),
            service=root_cause,
            version="v2.0.0",
            commit_hash="breaking123",
            author="bob",
            description="Major version - breaking API changes",
            is_problematic=True,
        ))

        return sorted(timeline, key=lambda x: x.timestamp)

    def get_symptoms(self) -> list[str]:
        """Get version mismatch symptoms"""
        return [
            "500 error rate spike",
            "Schema mismatch errors in logs",
            "Type conversion errors",
            "Failed API calls between services",
            "Response parsing failures",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "ERROR: Schema mismatch: expected field 'user_id', got 'userId'",
            "ERROR: TypeError: Cannot convert string to int",
            "ERROR: HTTP 500: Internal Server Error",
            "WARNING: API version mismatch detected",
            "ERROR: Response validation failed",
            "ERROR: Required field missing in response",
        ]

    def get_metric_noise_patterns(self) -> list[str]:
        """Get characteristic metric patterns"""
        return [
            "500_error_rate spikes to 50%+",
            "latency_p99 increases due to retries",
            "throughput drops",
        ]
