"""
IncidentOps - Network Partition Fault

Split-brain scenario where two groups of services cannot communicate.
Services in different partitions show timeout errors and connection refused.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.faults.base import BaseFault
from app.fault_injector import (
    DependencyPropagator,
    DeployEvent,
    FaultScenario,
    FaultType,
    get_deterministic_timestamp,
)

if TYPE_CHECKING:
    from app.determinism import DeterministicRNG


class NetworkPartitionFault(BaseFault):
    """
    Network partition / split-brain fault.

    Two groups of services become isolated from each other.
    Cross-partition communication shows timeouts and connection refused.

    Symptoms:
    - Timeout errors in cross-partition calls
    - Connection refused errors
    - Split-brain warnings in logs
    - Inconsistent state between partitions

    Correct fix: identify_partition -> restore_network_route
    """

    name = "network_partition"
    difficulty_range = (2, 5)
    affected_services_hint = [
        "api-gateway",
        "user-service",
        "auth-service",
        "order-service",
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a network partition scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Split services into two partitions
        service_list = list(services)
        rng.shuffle(service_list)

        mid_point = len(service_list) // 2
        partition_a = service_list[:mid_point]
        partition_b = service_list[mid_point:]

        # Root cause is typically a network component or gateway
        root_candidates = [s for s in services if "gateway" in s or "cache" in s]
        if not root_candidates:
            root_candidates = [s for s in services if "service" in s]

        root_cause = rng.choice(root_candidates) if root_candidates else services[0]

        # Affected services are those in the partition with the root cause
        if root_cause in partition_a:
            affected = partition_a + rng.sample(partition_b, min(difficulty, len(partition_b)))
        else:
            affected = partition_b + rng.sample(partition_a, min(difficulty, len(partition_a)))

        affected = list(set(affected))[:difficulty + 4]

        # Generate symptoms
        symptoms = self.get_symptoms()

        # Generate misleading signals - focus on individual services
        misleading_signals = [
            f"{rng.choice(services)}: WARNING: Connection timeout to {rng.choice(services)}",
            f"{rng.choice(services)}: ERROR: Failed to acquire lock",
            f"{rng.choice(services)}: INFO: Health check failed for replica",
        ]

        # Add split-brain red herrings
        if difficulty >= 4:
            misleading_signals.append(
                f"{rng.choice(services)}: WARNING: Data inconsistency detected between replicas"
            )

        return FaultScenario(
            fault_type=FaultType.NETWORK_PARTITION,
            root_cause_service=root_cause,
            affected_services=affected,
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_dependencies:all",
                "query_logs:timeout",
                "query_logs:connection_refused",
                "identify_network_partition",
            ],
            correct_fix=f"restore_network_route:{root_cause}",
            difficulty=difficulty,
        )

    def get_symptoms(self) -> list[str]:
        """Get network partition symptoms"""
        return [
            "Timeout errors in cross-partition calls",
            "Connection refused errors between service groups",
            "Split-brain warnings in logs",
            "Inconsistent data reads between partitions",
            "High latency for cross-partition requests",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "Connection timeout after 30000ms",
            "Connection refused: No route to host",
            "Network partition detected",
            "Split-brain warning: conflicting writes",
            "Failed to acquire distributed lock",
        ]
