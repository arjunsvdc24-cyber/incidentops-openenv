"""
IncidentOps - DDoS / Traffic Spike Fault

Massive traffic spike overwhelming services.
High error rates, timeout errors, resource exhaustion.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.faults.base import BaseFault
from app.fault_injector import DependencyPropagator, FaultScenario, FaultType

if TYPE_CHECKING:
    from app.determinism import DeterministicRNG


class DdosFault(BaseFault):
    """
    DDoS / traffic spike fault.

    Massive traffic spike overwhelming services.
    High error rates, timeout errors, resource exhaustion.

    Symptoms:
    - Request rate 10x normal
    - High error rates
    - Timeout errors
    - CPU/memory spikes
    - Rate limit warnings

    Correct fix: scale_service up OR apply rate limit
    """

    name = "ddos"
    difficulty_range = (1, 4)
    affected_services_hint = [
        "api-gateway",
        "user-service",
        "order-service",
        "payment-service",
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a DDoS/traffic spike scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Root cause is typically the entry point
        root_candidates = [s for s in services if "gateway" in s or s == "api-gateway"]
        if not root_candidates:
            root_candidates = [s for s in services if "service" in s][:3]

        root_cause = rng.choice(root_candidates) if root_candidates else services[0]

        # Get downstream services affected by traffic
        affected = [root_cause]
        downstream = DependencyPropagator.DEPENDENCY_GRAPH.get(root_cause, [])
        affected.extend(rng.sample(downstream, min(difficulty + 1, len(downstream))))

        # Symptoms
        symptoms = self.get_symptoms()

        # Misleading signals - point to service bugs
        misleading_signals = [
            f"{rng.choice(services)}: ERROR: Internal server error",
            f"{rng.choice(services)}: WARNING: Memory usage high",
        ]

        if difficulty >= 3:
            misleading_signals.extend([
                f"{rng.choice(services)}: ERROR: Database connection pool exhausted",
                f"{rng.choice(services)}: WARNING: Slow query detected",
            ])

        return FaultScenario(
            fault_type=FaultType.DDOS,
            root_cause_service=root_cause,
            affected_services=affected[:difficulty + 3],
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_metrics:request_rate",
                "query_metrics:error_rate",
                "identify_traffic_source",
                "apply_rate_limit",
            ],
            correct_fix=f"scale_service:{root_cause}",
            difficulty=difficulty,
            degradation_pattern={
                "metric_name": "request_rate",
                "initial_value": 1000,
                "final_value": 50000,
                "pattern": "spike",
            },
        )

    def get_symptoms(self) -> list[str]:
        """Get DDoS/traffic spike symptoms"""
        return [
            "Request rate 10x normal",
            "High error rates (timeouts, 503)",
            "CPU and memory at maximum",
            "Connection pool exhausted",
            "Rate limit warnings triggered",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "WARNING: Rate limit threshold exceeded",
            "ERROR: HTTP 429 Too Many Requests",
            "WARNING: Connection pool at capacity",
            "ERROR: Upstream timeout after 30s",
            "WARNING: Request queue overflow",
            "ERROR: Too many open connections",
        ]

    def get_metric_noise_patterns(self) -> list[str]:
        """Get characteristic metric patterns"""
        return [
            "request_rate spikes to 50x baseline",
            "error_rate increases to 30%",
            "CPU reaches 95%+",
            "memory_usage spikes",
            "connection_pool_max_connections reached",
        ]
