"""
IncidentOps - Configuration Drift Fault

Service has wrong configuration after config changes.
Logs show config-reload events with wrong values.
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


class ConfigDriftFault(BaseFault):
    """
    Configuration drift fault.

    A service has incorrect configuration after a config change.
    Logs show config-reload events with wrong values.

    Symptoms:
    - Unexpected latency changes
    - Wrong feature flags active
    - Config reload logs with suspicious values
    - Throughput changes

    Correct fix: apply_fix with correct config
    """

    name = "config_drift"
    difficulty_range = (2, 4)
    affected_services_hint = [
        "api-gateway",
        "order-service",
        "user-service",
        "auth-service",
    ]

    # Possible config drifts
    CONFIG_DRIFT_TYPES = [
        ("timeout_ms", "timeout_reached", "Timeout threshold set too low"),
        ("max_connections", "connection_exhausted", "Connection pool too small"),
        ("retry_count", "retry_storm", "Retry count set too high"),
        ("cache_ttl", "cache_ineffective", "Cache TTL set to 0"),
        ("batch_size", "processing_slowdown", "Batch size set too large"),
        ("worker_count", "resource_exhaustion", "Worker count misconfigured"),
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a configuration drift scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Pick a random service and config drift type
        root_cause = rng.choice([s for s in services if "service" in s] or services)
        drift_type = rng.choice(self.CONFIG_DRIFT_TYPES)

        # Affected services include the root cause and possibly dependents
        affected = [root_cause]
        downstream = DependencyPropagator.DEPENDENCY_GRAPH.get(root_cause, [])
        affected.extend(rng.sample(downstream, min(difficulty, len(downstream))))

        # Generate timeline with config change
        timeline = self._generate_config_timeline(rng, root_cause, difficulty)

        # Symptoms
        symptoms = self.get_symptoms()

        # Misleading signals - point to code issues or external factors
        misleading_signals = [
            f"{rng.choice(services)}: WARNING: High latency detected",
            f"{rng.choice(services)}: INFO: Request queue growing",
        ]

        if difficulty >= 3:
            misleading_signals.append(
                f"{rng.choice(services)}: ERROR: External API responding slowly"
            )

        return FaultScenario(
            fault_type=FaultType.CONFIG_DRIFT,
            root_cause_service=root_cause,
            affected_services=affected[:difficulty + 2],
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_deployments:recent",
                "query_logs:config_reload",
                "compare_config:current_vs_expected",
                "identify_drifted_config",
            ],
            correct_fix=f"apply_fix:{root_cause}",
            difficulty=difficulty,
            deploy_timeline=timeline,
        )

    def _generate_config_timeline(
        self,
        rng: "DeterministicRNG",
        root_cause: str,
        difficulty: int
    ) -> list[DeployEvent]:
        """Generate deployment timeline with config drift"""
        timeline = []

        # Normal deployments before drift
        for i in range(3):
            timeline.append(DeployEvent(
                timestamp=get_deterministic_timestamp(rng.seed, offset_hours=i * 6),
                service=rng.choice(list(DependencyPropagator.DEPENDENCY_GRAPH.keys())),
                version=f"v1.{i}.0",
                commit_hash=f"abc{i:03d}",
                author="alice",
                description=f"Regular deployment {i}",
            ))

        # Config change that caused drift
        timeline.append(DeployEvent(
            timestamp=get_deterministic_timestamp(rng.seed, offset_hours=20),
            service=root_cause,
            version=f"v1.3.{difficulty}",
            commit_hash="config123",
            author="bob",
            description="Update timeout configuration",
            is_problematic=True,
        ))

        return sorted(timeline, key=lambda x: x.timestamp)

    def get_symptoms(self) -> list[str]:
        """Get configuration drift symptoms"""
        return [
            "Unexpected latency changes",
            "Config reload logs with wrong values",
            "Wrong feature flags active",
            "Throughput significantly changed",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "Config reload: timeout_ms=100 (was 5000)",
            "WARNING: Feature flag cache_enabled=false",
            "Config change applied: max_connections=10",
            "Reload complete: using drift config",
            "WARNING: Non-standard configuration detected",
        ]
