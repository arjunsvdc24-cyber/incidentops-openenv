"""
IncidentOps - Noisy Neighbor Fault

A "noisy neighbor" fault where one service consumes excessive shared resources,
degrading performance of neighboring (innocent) services on the same host.

This is a realistic cloud-native fault that tests the agent's ability to:
1. Distinguish between faulty and victim services
2. Identify resource contention rather than service-level errors
3. Apply capacity-based fixes (scale, isolate, limit) rather than restarts
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.faults.base import BaseFault
from app.fault_injector import (
    FaultScenario,
)


class NoisyNeighborFault(BaseFault):
    """
    Noisy Neighbor fault — shared-host resource contention.

    A tenant/service consumes excessive CPU, memory, disk I/O, or network bandwidth,
    causing neighboring services on the same host to degrade without showing
    "faulty" service-level errors.

    Key challenge: victim services look degraded, but the root cause (the noisy neighbor)
    may appear healthy from its own metrics.

    Symptoms:
    - High CPU/disk/memory on shared host (visible via node_exporter)
    - Latency spikes on victim services
    - Error rate: low (requests are slow but succeed)
    - No obvious OOM or crash logs

    Correct fix: scale_service(root_cause) to add capacity, or restart_service
    to clear resource hog
    """

    name = "noisy_neighbor"
    difficulty_range = (2, 4)
    affected_services_hint = [
        "api-gateway",
        "user-service",
        "auth-service",
        "order-service",
        "search-service",
        "notification-service",
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a noisy neighbor scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Noisy neighbor candidates — services that typically use heavy batch jobs
        neighbor_candidates = [
            "analytics-service",
            "order-service",
            "notification-service",
            "inventory-service",
        ]
        root_cause = rng.choice(neighbor_candidates)

        # Victim services — depend on shared resources with noisy neighbor
        # At difficulty 2: 1 victim. At difficulty 3: 2 victims. At difficulty 4: 3 victims.
        victim_count = difficulty - 1
        victims = rng.sample(
            [s for s in services if s != root_cause],
            min(victim_count, len(services) - 1)
        )
        affected = [root_cause] + victims

        symptoms = self.get_symptoms()

        # Misleading signals — make it look like victim services are faulty
        misleading_signals = [
            f"{victims[0]}: WARNING: Response time above threshold",
            f"{victims[0]}: INFO: High latency observed",
        ]

        if difficulty >= 3:
            misleading_signals.append(
                f"{victims[0]}: WARNING: Timeout errors increasing"
            )
            if len(victims) > 1:
                misleading_signals.append(
                    f"{victims[1]}: WARNING: Slow response from upstream"
                )

        # At difficulty 3+: decoy alert pointing at a victim
        decoy_alerts = []
        if difficulty >= 3 and victims:
            decoy_alerts.append({
                "service": victims[0],
                "severity": "warning",
                "message": f"Service {victims[0]}: High latency spike detected",
            })

        return FaultScenario(
            fault_type="noisy_neighbor",  # str, not FaultType enum (not in canonical list)
            root_cause_service=root_cause,
            affected_services=affected,
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_metrics:cpu_percent",
                "query_metrics:memory_percent",
                "check_shared_host_resources",
                "identify_resource_contention",
                "scale_service:noisy_neighbor",
            ],
            correct_fix=f"scale_service:{root_cause}",
            difficulty=difficulty,
            decoy_alerts=decoy_alerts,
        )

    def get_symptoms(self) -> list[str]:
        """Get noisy neighbor symptoms"""
        return [
            "Latency spikes on multiple services without clear service-level errors",
            "High CPU or memory pressure on shared host (visible via node metrics)",
            "No OOM or crash logs — requests are slow but succeed",
            "Victim services degrade while root cause appears relatively healthy",
            "Resource contention pattern: degradation correlates with batch job schedule",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "Batch job consuming excessive CPU",
            "Disk I/O saturation on shared volume",
            "Network bandwidth limit approaching",
            "Memory pressure from background tasks",
        ]
