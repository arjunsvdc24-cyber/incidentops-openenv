"""
IncidentOps - Data Corruption Fault

Silent data corruption where reads return wrong values.
Business metrics drift (wrong recommendations, incorrect stats) but no errors thrown.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.faults.base import BaseFault
from app.fault_injector import DependencyPropagator, FaultScenario, FaultType

if TYPE_CHECKING:
    from app.determinism import DeterministicRNG


class DataCorruptionFault(BaseFault):
    """
    Silent data corruption fault.

    Data reads return wrong/corrupted values but no explicit errors.
    Business metrics gradually drift from expected values.

    Symptoms:
    - Business metrics drift (wrong recommendations, incorrect stats)
    - Checksum errors in logs (rare)
    - Null values appearing in data
    - CTR/revenue metrics declining

    Correct fix: restart_service on the corrupted service
    """

    name = "data_corruption"
    difficulty_range = (3, 5)
    affected_services_hint = [
        "recommendation-service",
        "analytics-service",
        "search-service",
        "order-service",
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a data corruption scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Target services that handle data
        corruption_targets = [
            s for s in services
            if any(keyword in s for keyword in ["recommendation", "analytics", "search", "order"])
        ]
        if not corruption_targets:
            corruption_targets = [s for s in services if "service" in s]

        root_cause = rng.choice(corruption_targets)

        # Get affected downstream services
        affected = [root_cause]
        downstream = DependencyPropagator.DEPENDENCY_GRAPH.get(root_cause, [])
        affected.extend(rng.sample(downstream, min(difficulty, len(downstream))))

        # Symptoms focus on business metrics
        symptoms = self.get_symptoms()

        # Misleading signals - point to database or cache issues
        misleading_signals = [
            f"{rng.choice(services)}: WARNING: Database connection slow",
            f"{rng.choice(services)}: INFO: Cache miss rate elevated to 45%",
        ]

        if difficulty >= 4:
            # Harder difficulty adds more misleading signals
            misleading_signals.extend([
                f"{rng.choice(services)}: ERROR: Null pointer in data handler",
                f"{rng.choice(services)}: WARNING: Disk I/O latency spike",
            ])

        return FaultScenario(
            fault_type=FaultType.DATA_CORRUPTION,
            root_cause_service=root_cause,
            affected_services=affected[:difficulty + 2],
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_metrics:business_metrics",
                "query_logs:checksum",
                "query_data:verify_values",
                "identify_corrupted_service",
            ],
            correct_fix=f"restart_service:{root_cause}",
            difficulty=difficulty,
            degradation_pattern={
                "metric_name": "data_accuracy",
                "initial_value": 1.0,
                "final_value": 0.6,
                "pattern": "gradual_decline",
            },
        )

    def get_symptoms(self) -> list[str]:
        """Get data corruption symptoms"""
        return [
            "Business metrics declining gradually",
            "Wrong values in data reads",
            "Null values appearing in results",
            "Checksum errors (rare)",
            "CTR/recommendation quality dropping",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "Checksum mismatch detected: expected abc123, got def456",
            "WARNING: Data integrity check failed",
            "Null value encountered in critical field",
            "Stale data warning: age exceeds threshold",
            "Corrupt record detected, skipping",
        ]

    def get_metric_noise_patterns(self) -> list[str]:
        """Get characteristic metric patterns"""
        return [
            "data_accuracy drops 5% per hour",
            "null_value_count increases",
            "checksum_errors appear sporadically",
            "CPU/memory stay normal (no errors thrown)",
        ]
