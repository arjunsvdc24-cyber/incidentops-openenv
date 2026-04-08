"""
IncidentOps - Memory Leak Fault

Gradual memory growth, no OOM yet.
Increasing GC pauses, latency degradation over time.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.faults.base import BaseFault
from app.fault_injector import DependencyPropagator, FaultScenario, FaultType

if TYPE_CHECKING:
    from app.determinism import DeterministicRNG


class MemoryLeakFault(BaseFault):
    """
    Memory leak fault.

    Gradual memory growth, no OOM yet.
    Increasing GC pauses, latency degradation over time.

    Symptoms:
    - Memory growing +10% per step
    - GC pause warnings
    - Latency gradually increasing
    - No sudden crash (unlike OOM)

    Correct fix: restart_service (unlike OOM which can be more urgent)
    """

    name = "memory_leak"
    difficulty_range = (2, 5)
    affected_services_hint = [
        "order-service",
        "recommendation-service",
        "analytics-service",
        "search-service",
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a memory leak scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Root cause is typically a Java/Python service
        root_candidates = [s for s in services if "service" in s]
        if not root_candidates:
            root_candidates = services

        root_cause = rng.choice(root_candidates)

        # Affected includes downstream
        affected = [root_cause]
        downstream = DependencyPropagator.DEPENDENCY_GRAPH.get(root_cause, [])
        affected.extend(rng.sample(downstream, min(difficulty, len(downstream))))

        # Symptoms
        symptoms = self.get_symptoms()

        # Misleading signals - point to other issues
        misleading_signals = [
            f"{rng.choice(services)}: WARNING: High CPU usage",
            f"{rng.choice(services)}: INFO: Request backlog growing",
        ]

        if difficulty >= 4:
            misleading_signals.extend([
                f"{rng.choice(services)}: ERROR: Slow response from upstream",
                f"{rng.choice(services)}: WARNING: Connection pool full",
            ])

        return FaultScenario(
            fault_type=FaultType.MEMORY_LEAK,
            root_cause_service=root_cause,
            affected_services=affected[:difficulty + 2],
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_memory:usage_trend",
                "query_logs:gc_pause",
                "analyze_heap_dump",
                "identify_leak_source",
            ],
            correct_fix=f"restart_service:{root_cause}",
            difficulty=difficulty,
            degradation_pattern={
                "metric_name": "memory_percent",
                "initial_value": 50.0,
                "final_value": 85.0,
                "pattern": "gradual_increase",
            },
        )

    def get_symptoms(self) -> list[str]:
        """Get memory leak symptoms"""
        return [
            "Memory growing gradually (+10% per hour)",
            "Increasing GC pause warnings",
            "Latency slowly degrading",
            "No sudden crash (unlike OOM)",
            "Eventually leads to OOM if not fixed",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "WARNING: GC pause: 500ms",
            "WARNING: Memory usage: 75% (was 50% 1h ago)",
            "INFO: Full GC triggered",
            "WARNING: Heap usage approaching limit",
            "WARNING: GC overhead limit exceeded",
            "INFO: Allocation rate: 500MB/s",
        ]

    def get_metric_noise_patterns(self) -> list[str]:
        """Get characteristic metric patterns"""
        return [
            "memory_percent increases 10% per step",
            "gc_pause_duration increases",
            "latency_p99 gradually increases",
            "no sudden CPU spike (unlike OOM)",
        ]
