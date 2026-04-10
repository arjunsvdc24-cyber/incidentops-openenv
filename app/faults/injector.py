"""
IncidentOps - Fault Injector and Fault Simulator

Deterministic fault injection for the IncidentOps RL environment.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Union
from enum import Enum
import random

from app.faults.noise import (
    DependencyPropagator,
    LogNoiseGenerator,
    MetricNoiseGenerator,
    PartialObservabilityManager,
    ServiceStatus,
    get_deterministic_timestamp,
)


class FaultType(str, Enum):
    """All 15 fault types - 5 canonical + 10 extended via FaultRegistry"""
    # Original 5 canonical (graded tasks)
    OOM = "oom"
    CASCADE = "cascade"
    GHOST = "ghost"
    DEPLOYMENT = "deployment"
    NETWORK = "network"
    # 10 extended (wired via FaultRegistry, available via /tasks)
    CERT_EXPIRY = "cert_expiry"
    CONFIG_DRIFT = "config_drift"
    DATA_CORRUPTION = "data_corruption"
    NETWORK_PARTITION = "network_partition"
    SLOW_DOWNSTREAM = "slow_downstream"
    THUNDERING_HERD = "thundering_herd"
    ZOMBIE_PROCESS = "zombie_process"
    ZOMBIE = "zombie"
    VERSION_MISMATCH = "version_mismatch"
    MEMORY_LEAK = "memory_leak"
    DDOS = "ddos"


from datetime import datetime


@dataclass
class DeployEvent:
    """A deployment event in the timeline"""
    timestamp: datetime
    service: str
    version: str
    commit_hash: str
    author: str
    description: str
    is_problematic: bool = False


from datetime import datetime


@dataclass
class FaultScenario:
    """Complete fault scenario specification"""
    fault_type: Union[FaultType, str]  # FaultType for built-ins, str for extended faults
    root_cause_service: str
    affected_services: list[str]
    symptoms: list[str]
    misleading_signals: list[str]
    required_investigation_steps: list[str]
    correct_fix: str
    difficulty: int
    deploy_timeline: list[DeployEvent] = field(default_factory=list)
    degradation_pattern: Optional[dict] = None
    is_memory_leak: bool = False  # Task 5: slow leak requiring step-trend detection
    # Partial network partition: simulate partial packet loss (e.g. 20% packet loss)
    partial_partition_loss: Optional[float] = None
    # Decoy alerts: injected into observation to mislead rule-based agents.
    # Each is a dict with 'service', 'severity', 'message' fields.
    decoy_alerts: list[dict] = field(default_factory=list)


# ============================================================================
# FAULT INJECTOR (Deterministic)
# ============================================================================

class FaultInjector:
    """
    Deterministic fault injector with no time-based randomness.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed
        self.current_scenario: Optional[FaultScenario] = None

        self.log_noise = LogNoiseGenerator(seed)
        self.metric_noise = MetricNoiseGenerator(seed)
        self.observability = PartialObservabilityManager(seed)
        self.propagator = DependencyPropagator(seed)

        self.services = list(DependencyPropagator.DEPENDENCY_GRAPH.keys())

    def generate_scenario(
        self,
        fault_type: Optional[FaultType] = None,
        difficulty: int = 3
    ) -> FaultScenario:
        # Handle string input (from FaultRegistry extended faults)
        if isinstance(fault_type, str):  # pragma: no cover
            ft_value = fault_type  # pragma: no cover
        elif fault_type is None:
            fault_type = self.rng.choice(list(FaultType))
            ft_value = fault_type.value
        else:
            ft_value = fault_type.value

        # Task 4: DDoS Flood -> difficulty=3 (hardcoded root cause)
        if ft_value == FaultType.NETWORK.value and difficulty == 3:
            return self._generate_ddos_scenario(difficulty)
        # Task 5: Memory Spiral -> difficulty=4 (hardcoded root cause)
        if ft_value == FaultType.OOM.value and difficulty == 4:
            return self._generate_memory_leak_scenario(difficulty)

        # 5 original canonical generators (OOM d1-3/d5, CASCADE, GHOST, DEPLOYMENT, generic NETWORK)
        canonical_generators = {
            FaultType.OOM: self._generate_oom_scenario,
            FaultType.CASCADE: self._generate_cascade_scenario,
            FaultType.GHOST: self._generate_ghost_scenario,
            FaultType.DEPLOYMENT: self._generate_deployment_scenario,
            FaultType.NETWORK: self._generate_network_scenario,
        }

        # 10 extended generators via FaultRegistry
        extended_names = {
            FaultType.CERT_EXPIRY,
            FaultType.CONFIG_DRIFT,
            FaultType.DATA_CORRUPTION,
            FaultType.NETWORK_PARTITION,
            FaultType.SLOW_DOWNSTREAM,
            FaultType.THUNDERING_HERD,
            FaultType.ZOMBIE_PROCESS,
            FaultType.ZOMBIE,
            FaultType.VERSION_MISMATCH,
            FaultType.MEMORY_LEAK,
            FaultType.DDOS,
        }

        if fault_type in canonical_generators:
            return canonical_generators[fault_type](difficulty)

        if fault_type in extended_names:
            # Lazy import to avoid circular dependency
            from app.faults import FaultRegistry
            from app.determinism import DeterministicRNG
            rng = DeterministicRNG(self.seed)
            return FaultRegistry.generate(ft_value, rng, difficulty, self.services)

        # Fallback: random from all
        fault_type = self.rng.choice(list(FaultType))  # pragma: no cover
        return self.generate_scenario(fault_type, difficulty)  # pragma: no cover

    def _generate_oom_scenario(self, difficulty: int) -> FaultScenario:
        java_services = [s for s in self.services if "service" in s]
        root_cause = self.rng.choice(java_services)

        affected = [root_cause] + self.propagator.get_downstream_services(root_cause, depth=difficulty)

        # At difficulty 3+: symptoms become ambiguous (not clearly pointing to root_cause)
        # At difficulty 4+: add symptoms that point to other Java services as potential causes
        symptoms = [
            "OutOfMemoryError in logs",
            "High memory usage",
            "Slow GC pauses",
        ]

        decoy_alerts: list[dict] = []

        if difficulty >= 2:
            # Decoy at difficulty 2: other Java service shows elevated memory - makes OOM less obvious
            other_java = [s for s in java_services if s != root_cause]
            if other_java:
                decoy_svc = self.rng.choice(other_java)
                decoy_alerts.append({
                    "service": decoy_svc,
                    "severity": "warning",
                    "message": f"Service {decoy_svc} is degraded - high memory footprint detected",
                })
                symptoms.append(f"{decoy_svc}: Memory usage approaching limit")

        if difficulty >= 3:
            # Strong decoy at difficulty 3+: unrelated non-Java service shows resource issues
            other_services = [s for s in self.services if s != root_cause and s not in [d["service"] for d in decoy_alerts]]
            if other_services:
                decoy_svc2 = self.rng.choice(other_services)
                decoy_alerts.append({
                    "service": decoy_svc2,
                    "severity": "warning",
                    "message": f"Service {decoy_svc2} is degraded - thread pool saturation detected",
                })
                symptoms.append("Multiple Java services reporting high resource utilization")

        return FaultScenario(
            fault_type=FaultType.OOM,
            root_cause_service=root_cause,
            affected_services=affected[:difficulty + 2],
            symptoms=symptoms,
            misleading_signals=self._generate_misleading_signals(difficulty),
            required_investigation_steps=[
                "query_metrics:memory_usage",
                "query_logs:OutOfMemoryError",
                "query_service:root_cause",
            ],
            correct_fix="restart_service:" + root_cause,
            difficulty=difficulty,
            decoy_alerts=decoy_alerts,
        )

    def _generate_cascade_scenario(self, difficulty: int) -> FaultScenario:
        core_services = ["database-primary", "cache-service", "auth-service"]
        root_cause = self.rng.choice(core_services)

        affected = [root_cause] + self.propagator.get_downstream_services(root_cause)

        symptoms = [
            "Multiple services reporting errors",
            "Connection timeouts",
            "High latency across services",
        ]

        decoy_alerts: list[dict] = []

        if difficulty >= 2:  # pragma: no cover
            # Decoy at difficulty 2: unrelated healthy service shows connection/scale symptoms  # pragma: no cover
            # Misdirects agents away from the real root_cause  # pragma: no cover
            unrelated = [s for s in self.services if s != root_cause]  # pragma: no cover
            decoy_candidates = [s for s in unrelated if s not in self.propagator.get_downstream_services(root_cause)]  # pragma: no cover
            if not decoy_candidates:  # pragma: no cover
                decoy_candidates = unrelated  # pragma: no cover
            if decoy_candidates:  # pragma: no cover
                decoy_svc = self.rng.choice(decoy_candidates)  # pragma: no cover
                decoy_alerts.append({  # pragma: no cover
                    "service": decoy_svc,  # pragma: no cover
                    "severity": "warning",  # pragma: no cover
                    "message": f"Service {decoy_svc}: High latency spike - connection timeout to upstream",  # pragma: no cover
                })  # pragma: no cover
                symptoms.append(f"{decoy_svc}: Latency anomaly detected")  # pragma: no cover

        if difficulty >= 3:  # pragma: no cover
            # Second decoy at difficulty 3+: another unrelated service  # pragma: no cover
            already_decoyed = [d["service"] for d in decoy_alerts]  # pragma: no cover
            unrelated2 = [s for s in self.services if s != root_cause and s not in already_decoyed]  # pragma: no cover
            if unrelated2:  # pragma: no cover
                decoy_svc2 = self.rng.choice(unrelated2)  # pragma: no cover
                decoy_alerts.append({  # pragma: no cover
                    "service": decoy_svc2,  # pragma: no cover
                    "severity": "warning",  # pragma: no cover
                    "message": f"Service {decoy_svc2}: Error rate spike - retry storm detected",  # pragma: no cover
                })  # pragma: no cover
                symptoms.append("Connection errors visible across unrelated services")  # pragma: no cover

        return FaultScenario(
            fault_type=FaultType.CASCADE,
            root_cause_service=root_cause,
            affected_services=affected[:difficulty + 3],
            symptoms=symptoms,
            misleading_signals=self._generate_misleading_signals(difficulty),
            required_investigation_steps=[
                "query_dependencies:affected_services",
                "query_metrics:all_services",
                "identify_cascade_source",
            ],
            correct_fix="scale_service:" + root_cause,
            difficulty=difficulty,
            decoy_alerts=decoy_alerts,
        )

    def _generate_ghost_scenario(self, difficulty: int) -> FaultScenario:
        ghost_candidates = ["recommendation-service", "analytics-service", "search-service"]
        root_cause = self.rng.choice(ghost_candidates)

        # Deterministic timeline - no datetime.utcnow()
        timeline = []

        for i in range(5):
            timeline.append(DeployEvent(
                timestamp=get_deterministic_timestamp(self.seed, offset_hours=i * 4),
                service=self.rng.choice(self.services),
                version=f"v1.{i}.0",
                commit_hash=f"abc{i:03d}",
                author="alice",
                description=f"Regular update {i}",
            ))

        problem_time_offset = 20  # hours
        timeline.append(DeployEvent(
            timestamp=get_deterministic_timestamp(self.seed, offset_hours=problem_time_offset),
            service=root_cause,
            version="v2.1.0",
            commit_hash="bad789",
            author="bob",
            description="Refactor recommendation algorithm for performance",
            is_problematic=True
        ))

        timeline.append(DeployEvent(
            timestamp=get_deterministic_timestamp(self.seed, offset_hours=problem_time_offset, offset_seconds=1800),
            service="notification-service",
            version="v1.5.0",
            commit_hash="xyz123",
            author="charlie",
            description="Update notification templates",
        ))

        timeline.sort(key=lambda x: x.timestamp)

        affected = [root_cause] + self.propagator.get_downstream_services(root_cause, depth=2)

        # Decoy alerts for Ghost: at difficulty 4+, other services look suspicious
        decoy_alerts: list[dict] = []
        if difficulty >= 4:
            other = [s for s in self.services if s != root_cause and s != "notification-service"]
            decoy_svc = self.rng.choice(other) if other else None
            if decoy_svc:
                decoy_alerts.append({
                    "service": decoy_svc,
                    "severity": "info",
                    "message": f"Service {decoy_svc}: Anomalous traffic pattern detected",
                })
                decoy_alerts.append({
                    "service": "notification-service",
                    "severity": "info",
                    "message": "Recent deployment v1.5.0 - check for compatibility issues",
                })

        return FaultScenario(
            fault_type=FaultType.GHOST,
            root_cause_service=root_cause,
            affected_services=affected,
            symptoms=[
                "No explicit error logs",
                "CTR gradually declining",
                "Recommendation quality dropping",
            ],
            misleading_signals=self._generate_misleading_signals(max(difficulty, 4)),
            required_investigation_steps=[
                "query_metrics:ctr",
                "query_deployments:timeline",
                "correlate_deployment_with_metric",
                "rollback_deployment",
            ],
            correct_fix="rollback_deployment:" + root_cause,
            difficulty=max(difficulty, 4),
            deploy_timeline=timeline,
            degradation_pattern={
                "metric_name": "ctr",
                "initial_value": 3.5,
                "final_value": 1.8,
                "pattern": "linear_decline",
            },
            decoy_alerts=decoy_alerts,
        )

    def _generate_deployment_scenario(self, difficulty: int) -> FaultScenario:
        root_cause = self.rng.choice([s for s in self.services if "service" in s])
        affected = [root_cause] + self.propagator.get_downstream_services(root_cause, depth=2)

        return FaultScenario(
            fault_type=FaultType.DEPLOYMENT,
            root_cause_service=root_cause,
            affected_services=affected[:3],
            symptoms=[
                "New errors after deployment",
                "Version mismatch warnings",
            ],
            misleading_signals=self._generate_misleading_signals(difficulty),
            required_investigation_steps=[
                "query_deployments:recent",
                "query_logs:new_errors",
            ],
            correct_fix="rollback_deployment:" + root_cause,
            difficulty=difficulty,
        )

    def _generate_network_scenario(self, difficulty: int) -> FaultScenario:  # pragma: no cover
        root_cause = self.rng.choice(["api-gateway", "cache-service"])  # pragma: no cover
        # Partial network partition: 20% packet loss simulates lossy network links
        packet_loss = 0.20 if difficulty >= 2 else None  # pragma: no cover

        return FaultScenario(
            fault_type=FaultType.NETWORK,
            root_cause_service=root_cause,
            affected_services=[root_cause],
            symptoms=[
                "Connection timeouts",
                "High latency",
                "Packet loss observed (20%)" if packet_loss else "Intermittent timeouts",
            ],
            misleading_signals=self._generate_misleading_signals(difficulty),
            required_investigation_steps=[
                "query_metrics:latency",
                "query_logs:timeout",
            ],
            correct_fix="scale_service:" + root_cause,
            difficulty=difficulty,
            partial_partition_loss=packet_loss,
        )

    def _generate_ddos_scenario(self, difficulty: int) -> FaultScenario:
        """
        Task 4: DDoS Flood
        Root cause: api-gateway overwhelmed by 50x normal traffic.
        Correct fix: scale_service("api-gateway")
        Symptoms: api-gateway latency spikes to 2000ms+, all downstream services
                  show cascading timeouts, high error rate.
        Deceptive signal: logs show "connection timeout" on auth-service and
                          order-service, NOT on api-gateway itself - misleads
                          naive agents into fixing the wrong service.
        """
        root_cause = "api-gateway"

        # All services that depend on api-gateway get cascading timeouts
        downstream = self.propagator.get_downstream_services(root_cause, depth=difficulty)
        affected = [root_cause] + downstream

        return FaultScenario(
            fault_type=FaultType.NETWORK,
            root_cause_service=root_cause,
            affected_services=affected,
            symptoms=[
                "api-gateway latency spikes to 2000ms+",
                "All downstream services show cascading timeouts",
                "High error rate across the board",
            ],
            # Deceptive: downstream services blame each other, not the gateway
            misleading_signals=[
                "auth-service: ERROR: Connection timeout to upstream",
                "order-service: ERROR: Connection timeout to upstream",
                "user-service: WARNING: Retries exhausted for auth-service",
            ],
            required_investigation_steps=[
                "query_metrics:api-gateway",
                "check_throughput",
                "scale_service:api-gateway",
            ],
            correct_fix="scale_service:api-gateway",
            difficulty=difficulty,
        )

    def _generate_memory_leak_scenario(self, difficulty: int) -> FaultScenario:
        """
        Task 5: Memory Spiral
        Root cause: analytics-service has a slow memory leak (~4% per step).
        Correct fix: restart_service("analytics-service") then scale_service("analytics-service")
        Symptoms: memory_percent starts at 45%, grows ~4% per step, OOM at ~step 18.
        Deceptive signal: database-replica shows high CPU from analytics queries -
                          naive agents restart the DB instead.
        The leak is only obvious if agent queries metrics 3+ times and tracks the trend.
        """
        root_cause = "analytics-service"

        # DB replica gets hammered by analytics queries - misleading CPU spike
        db_replica_downstream = self.propagator.get_downstream_services("database-replica")
        affected = [root_cause, "database-replica"] + [
            s for s in db_replica_downstream if s in self.services
        ]

        return FaultScenario(
            fault_type=FaultType.OOM,
            root_cause_service=root_cause,
            affected_services=affected[:difficulty + 3],
            symptoms=[
                "analytics-service memory_percent grows ~4% per step",
                "Starts at 45%, OOM at step 18",
                "Trend only visible after 3+ metrics queries",
            ],
            # Deceptive: DB CPU spike misleads agents to restart database-replica
            misleading_signals=[
                "database-replica: WARNING: High CPU from analytics queries",
                "database-replica: INFO: Query queue depth elevated",
            ],
            required_investigation_steps=[
                "query_metrics:analytics-service",
                "query_metrics:analytics-service",
                "query_metrics:analytics-service",
                "observe_memory_trend",
                "restart_service:analytics-service",
            ],
            correct_fix="restart_service:analytics-service",
            difficulty=difficulty,
            is_memory_leak=True,
        )

    def _generate_misleading_signals(self, difficulty: int) -> list[str]:
        """
        Generate difficulty-aware misleading signals.
        At higher difficulty: more false leads, harder to identify root cause.
        Signals start at difficulty 2 (not 4) to make easy/medium tasks non-trivial.
        """
        base_signals = [
            "notification-service: WARNING: High queue depth",
            "cache-service: INFO: Cache miss rate elevated",
        ]

        oom_signals = [
            "search-service: WARNING: Memory usage elevated",
            "email-service: WARNING: SMTP connection pool exhausted",
            "inventory-service: ERROR: High latency detected",
            "recommendation-service: WARNING: Slow response from upstream",
        ]

        cascade_signals = [
            "search-service: WARNING: Response time above threshold",
            "analytics-service: ERROR: Batch job delayed",
            "email-service: WARNING: SMTP connection slow",
            "inventory-service: INFO: Stock sync delayed",
            "recommendation-service: WARNING: Timeout errors increasing",
        ]

        # At difficulty 2+: add 1 misleading signal (was difficulty 4+ before)
        # At difficulty 3+: add 2 misleading signals
        # At difficulty 4+: add 3 misleading signals
        count = max(0, difficulty - 1)  # diff 2 -> 1, diff 3 -> 2, diff 4+ -> 3

        # Mix OOM and cascade signals based on fault type context
        all_extra = oom_signals + cascade_signals
        extra_sample = self.rng.sample(all_extra, min(count, len(all_extra)))

        return base_signals + extra_sample

    def get_scenario_by_type(self, fault_type: FaultType, difficulty: int = 3) -> FaultScenario:
        return self.generate_scenario(fault_type, difficulty)

    def get_hardest_scenario(self) -> FaultScenario:  # pragma: no cover
        return self.generate_scenario(FaultType.GHOST, difficulty=5)  # pragma: no cover

    def generate_extended_scenario(
        self,
        fault_name: Optional[str] = None,
        difficulty: int = 3
    ) -> FaultScenario:  # pragma: no cover
        """Generate extended fault via FaultRegistry (convenience wrapper)."""  # pragma: no cover
        from app.faults import FaultRegistry  # pragma: no cover
        from app.determinism import DeterministicRNG  # pragma: no cover
        if fault_name is None:  # pragma: no cover
            fault_name = self.rng.choice(FaultRegistry.list())  # pragma: no cover
        rng = DeterministicRNG(self.seed)  # pragma: no cover
        return FaultRegistry.generate(fault_name, rng, difficulty, self.services)  # pragma: no cover

    def list_extended_faults(self) -> list[str]:  # pragma: no cover
        """
        List all fault types available in the extended FaultRegistry.

        Returns:
            Sorted list of fault names
        """
        from app.faults import FaultRegistry
        return FaultRegistry.list()


# ============================================================================
# FAULT SIMULATOR (Deterministic)
# ============================================================================

class FaultSimulator:
    """
    Deterministic fault simulator.
    """

    def __init__(self, scenario: FaultScenario, seed: int = 42):
        self.scenario = scenario
        self.rng = random.Random(seed)
        self.seed = seed
        self.step = 0

        self.log_noise = LogNoiseGenerator(seed, base_step=0)
        self.metric_noise = MetricNoiseGenerator(seed)
        self.observability = PartialObservabilityManager(seed)
        self.propagator = DependencyPropagator(seed)

    def get_service_states(self, apply_propagation: bool = True) -> dict:
        states = {}

        for service in self._get_all_services():
            if service == self.scenario.root_cause_service:
                states[service] = self._generate_faulty_state(service)
            elif service in self.scenario.affected_services:
                states[service] = self._generate_affected_state(service)
            else:
                states[service] = self._generate_healthy_state(service)

        if apply_propagation and self.scenario.fault_type in (FaultType.CASCADE, FaultType.OOM):
            states = self.propagator.propagate_failure(
                self.scenario.root_cause_service,
                states,
                severity=0.8
            )

        # Task 4: DDoS - api-gateway shows 2000ms+ latency, not the normal faulty range
        if self.scenario.fault_type == FaultType.NETWORK:
            if "api-gateway" in states:
                states["api-gateway"] = {
                    "status": ServiceStatus.UNHEALTHY.value,
                    "latency_ms": self.rng.uniform(2000, 3000),
                    "error_rate": self.rng.uniform(0.4, 0.6),
                    "cpu_percent": self.rng.uniform(90, 99),
                    "memory_percent": self.rng.uniform(60, 80),
                    "requests_per_sec": self.rng.uniform(50000, 80000),
                    "packet_loss_rate": self.scenario.partial_partition_loss or 0.0,
                }
            # Downstream services show cascading degradation but NOT UNHEALTHY root cause
            for svc in self.scenario.affected_services:  # pragma: no cover
                if svc != "api-gateway" and svc in states:  # pragma: no cover
                    states[svc]["latency_ms"] = self.rng.uniform(800, 1500)  # pragma: no cover
                    states[svc]["error_rate"] = self.rng.uniform(0.2, 0.4)  # pragma: no cover
                    states[svc]["status"] = ServiceStatus.DEGRADED.value  # pragma: no cover
                    states[svc]["packet_loss_rate"] = (self.scenario.partial_partition_loss or 0.0) * 0.5  # pragma: no cover

        return states

    def get_metrics(self, service: str, apply_noise: bool = True) -> dict:
        base_metrics = self._get_base_metrics(service)

        # Task 4: DDoS - api-gateway metrics show 50x traffic spike  # pragma: no cover
        if self.scenario.fault_type == FaultType.NETWORK and service == "api-gateway":  # pragma: no cover
            base_metrics = {  # pragma: no cover
                "latency_p50": self.rng.uniform(2000, 3000),  # pragma: no cover
                "latency_p99": self.rng.uniform(4000, 6000),  # pragma: no cover
                "error_rate": self.rng.uniform(0.4, 0.6),  # pragma: no cover
                "throughput": self.rng.uniform(50000, 80000),  # pragma: no cover
                "cpu_percent": self.rng.uniform(90, 99),  # pragma: no cover
                "memory_percent": self.rng.uniform(60, 80),  # pragma: no cover
            }  # pragma: no cover

        # Task 5: Memory spiral - database-replica shows misleading high CPU from analytics queries  # pragma: no cover
        if (self.scenario.is_memory_leak and service == "database-replica"):  # pragma: no cover
            base_metrics = {  # pragma: no cover
                "latency_p50": self.rng.uniform(15, 30),  # pragma: no cover
                "latency_p99": self.rng.uniform(50, 100),  # pragma: no cover
                "error_rate": self.rng.uniform(0, 0.01),  # pragma: no cover
                "throughput": self.rng.uniform(1000, 5000),  # pragma: no cover
                "cpu_percent": self.rng.uniform(75, 90),  # pragma: no cover
                "memory_percent": self.rng.uniform(40, 60),  # pragma: no cover
            }  # pragma: no cover

        if apply_noise:
            return self.metric_noise.generate_noisy_metrics(
                base_metrics,
                service,
                self.step
            )

        return base_metrics

    def get_logs(self, service: str, apply_noise: bool = True) -> list[dict]:
        logs, was_hidden = self.observability.query_logs(service)

        if not logs:
            if service == self.scenario.root_cause_service:
                if self.scenario.fault_type == FaultType.GHOST:
                    logs = self._generate_ghost_logs(service)
                else:
                    logs = self._generate_faulty_logs(service)
            elif service in self.scenario.affected_services:
                logs = self._generate_affected_logs(service)
            else:
                logs = self._generate_healthy_logs(service)

        # Task 4: DDoS deceptive signals - downstream services blame each other,
        # NOT api-gateway. This is the core deception: timeouts appear on auth-service
        # and order-service, misleading agents into fixing the wrong service.
        if self.scenario.fault_type == FaultType.NETWORK:
            ddos_deceptive_logs = {
                "auth-service": [
                    {
                        "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=10).isoformat(),
                        "level": "ERROR",
                        "message": "Connection timeout: upstream service did not respond in 5000ms",
                        "service": "auth-service",
                        "noise_type": "deceptive",
                    },
                    {
                        "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=5).isoformat(),
                        "level": "WARNING",
                        "message": "Retries exhausted for order-service",
                        "service": "auth-service",
                        "noise_type": "deceptive",
                    },
                ],
                "order-service": [
                    {
                        "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=12).isoformat(),
                        "level": "ERROR",
                        "message": "Connection timeout to auth-service",
                        "service": "order-service",
                        "noise_type": "deceptive",
                    },
                    {
                        "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=8).isoformat(),
                        "level": "ERROR",
                        "message": "503 Service Unavailable",
                        "service": "order-service",
                        "noise_type": "deceptive",
                    },
                ],
                "user-service": [
                    {
                        "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=15).isoformat(),
                        "level": "WARNING",
                        "message": "High latency observed: 2000ms+ from api-gateway",
                        "service": "user-service",
                        "noise_type": "deceptive",
                    },
                ],
            }
            if service in ddos_deceptive_logs:
                logs = ddos_deceptive_logs[service]

        if apply_noise:
            noise_ratio = 0.3 if self.scenario.difficulty >= 3 else 0.1
            logs = self.log_noise.inject_noise_into_logs(logs, service, noise_ratio)

        return logs

    def get_deploy_timeline(self) -> list[dict]:
        return [
            {
                "timestamp": d.timestamp.isoformat(),
                "service": d.service,
                "version": d.version,
                "commit_hash": d.commit_hash,
                "author": d.author,
                "description": d.description,
            }
            for d in self.scenario.deploy_timeline
        ]

    def propagate_failure(self, service: str, states: dict) -> dict:
        return self.propagator.propagate_failure(service, states)

    def propagate_recovery(self, service: str, states: dict) -> dict:
        return self.propagator.propagate_recovery(service, states)

    def advance_step(self) -> None:
        self.step += 1
        self.log_noise.base_step = self.step
        self.propagator.step_propagation({})

    def _get_all_services(self) -> list[str]:
        return list(DependencyPropagator.DEPENDENCY_GRAPH.keys())

    def _get_base_metrics(self, service: str) -> dict:
        if service == self.scenario.root_cause_service:
            return self._generate_faulty_metrics(service)
        elif service in self.scenario.affected_services:
            return self._generate_affected_metrics(service)
        return self._generate_healthy_metrics(service)

    def _generate_healthy_state(self, service: str) -> dict:
        return {
            "status": ServiceStatus.HEALTHY.value,
            "latency_ms": self.rng.uniform(20, 50),
            "error_rate": self.rng.uniform(0, 0.005),
            "cpu_percent": self.rng.uniform(20, 40),
            "memory_percent": self.rng.uniform(40, 60),
        }

    def _generate_faulty_state(self, service: str) -> dict:
        if self.scenario.fault_type == FaultType.GHOST:
            return {
                "status": ServiceStatus.HEALTHY.value,
                "latency_ms": self.rng.uniform(50, 70),
                "error_rate": self.rng.uniform(0, 0.002),
                "cpu_percent": self.rng.uniform(25, 45),
                "memory_percent": self.rng.uniform(45, 65),
                "business_metrics": {
                    "ctr": 1.8 + self.rng.uniform(-0.2, 0.2),
                    "recommendation_quality": 0.65,
                }
            }

        state = {
            "status": ServiceStatus.UNHEALTHY.value,
            "latency_ms": self.rng.uniform(200, 500),
            "error_rate": self.rng.uniform(0.1, 0.3),
            "cpu_percent": self.rng.uniform(80, 95),
            "memory_percent": self.rng.uniform(85, 98),
        }
        # Add packet loss rate for partial network partition scenarios
        if self.scenario.partial_partition_loss:
            state["packet_loss_rate"] = self.scenario.partial_partition_loss
        return state

    def _generate_affected_state(self, service: str) -> dict:
        return {
            "status": ServiceStatus.DEGRADED.value,
            "latency_ms": self.rng.uniform(100, 200),
            "error_rate": self.rng.uniform(0.02, 0.08),
            "cpu_percent": self.rng.uniform(50, 70),
            "memory_percent": self.rng.uniform(60, 75),
        }

    def _generate_healthy_metrics(self, service: str) -> dict:
        return {
            "latency_p50": self.rng.uniform(15, 30),
            "latency_p99": self.rng.uniform(50, 100),
            "error_rate": self.rng.uniform(0, 0.01),
            "throughput": self.rng.uniform(1000, 5000),
            "cpu_percent": self.rng.uniform(20, 40),
            "memory_percent": self.rng.uniform(40, 60),
        }

    def _generate_faulty_metrics(self, service: str) -> dict:
        if self.scenario.fault_type == FaultType.GHOST:
            return {
                "latency_p50": self.rng.uniform(20, 35),
                "latency_p99": self.rng.uniform(60, 120),
                "error_rate": self.rng.uniform(0, 0.005),
                "throughput": self.rng.uniform(900, 1200),
                "cpu_percent": self.rng.uniform(25, 45),
                "memory_percent": self.rng.uniform(45, 65),
                "business_metrics": {
                    "ctr": 1.8,
                    "ctr_baseline": 3.5,
                    "recommendation_quality": 0.65,
                    "quality_baseline": 0.85,
                }
            }

        return {
            "latency_p50": self.rng.uniform(150, 300),
            "latency_p99": self.rng.uniform(400, 800),
            "error_rate": self.rng.uniform(0.1, 0.3),
            "throughput": self.rng.uniform(100, 500),
            "cpu_percent": self.rng.uniform(80, 95),
            "memory_percent": self.rng.uniform(85, 98),
        }

    def _generate_affected_metrics(self, service: str) -> dict:
        return {
            "latency_p50": self.rng.uniform(80, 150),
            "latency_p99": self.rng.uniform(200, 400),
            "error_rate": self.rng.uniform(0.02, 0.08),
            "throughput": self.rng.uniform(500, 1000),
            "cpu_percent": self.rng.uniform(50, 70),
            "memory_percent": self.rng.uniform(60, 75),
        }

    def _generate_faulty_logs(self, service: str) -> list[dict]:
        logs = []

        if self.scenario.fault_type == FaultType.OOM:
            logs.append({
                "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=30).isoformat(),
                "level": "ERROR",
                "message": "java.lang.OutOfMemoryError: Java heap space",
                "service": service,
            })
            logs.append({
                "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=25).isoformat(),
                "level": "WARNING",
                "message": "GC overhead limit exceeded",
                "service": service,
            })

            # Difficulty 4+: inject misleading logs in OTHER services to misdirect investigation  # pragma: no cover
            if self.scenario.difficulty >= 4 and service == self.scenario.root_cause_service:  # pragma: no cover
                other_services = [s for s in self._get_all_services() if s != service]  # pragma: no cover
                misleading = self.rng.sample(other_services, min(1, len(other_services)))  # pragma: no cover
                for ms in misleading:  # pragma: no cover
                    logs.append({  # pragma: no cover
                        "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=28).isoformat(),  # pragma: no cover
                        "level": "WARNING",  # pragma: no cover
                        "message": "High memory usage detected - GC pause above threshold",  # pragma: no cover
                        "service": ms,  # pragma: no cover
                    })  # pragma: no cover

        elif self.scenario.fault_type == FaultType.CASCADE:
            logs.append({
                "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=45).isoformat(),
                "level": "ERROR",
                "message": "Connection refused to upstream service",
                "service": service,
            })
            logs.append({
                "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=40).isoformat(),
                "level": "WARNING",
                "message": "Timeout waiting for response",
                "service": service,
            })

            # Difficulty 3+: inject misleading connection errors in OTHER services
            if self.scenario.difficulty >= 3 and service == self.scenario.root_cause_service:
                other = [s for s in self._get_all_services() if s != service]
                decoy_svc = self.rng.choice(other) if other else None
                if decoy_svc:
                    logs.append({
                        "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=43).isoformat(),
                        "level": "ERROR",
                        "message": "Connection timeout to downstream service",
                        "service": decoy_svc,
                    })
                    logs.append({
                        "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=42).isoformat(),
                        "level": "WARNING",
                        "message": "Circuit breaker open - too many failures",
                        "service": decoy_svc,
                    })

        elif self.scenario.fault_type == FaultType.DEPLOYMENT:
            logs.append({
                "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=20).isoformat(),
                "level": "ERROR",
                "message": "NullPointerException in processRequest",
                "service": service,
            })
            logs.append({
                "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=15).isoformat(),
                "level": "WARNING",
                "message": "API version mismatch detected",
                "service": service,
            })

        return logs

    def _generate_ghost_logs(self, service: str) -> list[dict]:
        """
        Generate ghost fault logs with SUBTLE anomalies.

        Ghost = silent data corruption with no obvious errors.
        Logs look mostly clean but contain subtle clues:
        - Schema mismatches in business metrics
        - Anomalous recommendation scores
        - Stale data warnings
        - Metric divergence from baseline
        """
        logs = [
            # Clean-looking startup
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_hours=1, offset_seconds=30).isoformat(),
                "level": "INFO",
                "message": "Recommendation model v2.1.0 loaded successfully",
                "service": service,
            },
            # SUBTLE: schema field type changed between versions (data quality drift)
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_hours=1, offset_seconds=28).isoformat(),
                "level": "WARN",
                "message": "Feature schema version mismatch: expected 12 fields, received 11",
                "service": service,
            },
            # SUBTLE: recommendation scores diverge from expected range
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_hours=1, offset_seconds=25).isoformat(),
                "level": "INFO",
                "message": "CTR: 1.82 (baseline: 3.50) - below threshold",
                "service": service,
                "metric_type": "business",
            },
            # SUBTLE: quality degradation detected but not surfaced as error
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_hours=1, offset_seconds=20).isoformat(),
                "level": "INFO",
                "message": "Recommendation quality score: 0.652 (p50 threshold: 0.70)",
                "service": service,
                "metric_type": "business",
            },
            # SUBTLE: model inference latency slightly elevated (not an error)
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_hours=1, offset_seconds=18).isoformat(),
                "level": "DEBUG",
                "message": "Model inference: 42ms (expected: 25-35ms range)",
                "service": service,
            },
            # SUBTLE: data freshness warning
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_hours=1, offset_seconds=15).isoformat(),
                "level": "INFO",
                "message": "Processing recommendation batch: 1000 items (batch_id: batch_001042)",
                "service": service,
            },
            # SUBTLE: ranking algorithm change reflected in different score distribution
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_hours=1, offset_seconds=12).isoformat(),
                "level": "INFO",
                "message": "Top-N recall@10: 0.18 (previous: 0.31) - trend decreasing",
                "service": service,
                "metric_type": "business",
            },
            # SUBTLE: data pipeline warning (not an error)
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_hours=1, offset_seconds=10).isoformat(),
                "level": "WARN",
                "message": "Feature pipeline: 3 fields missing default values",
                "service": service,
            },
            # SUBTLE: prediction confidence lower than normal
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_hours=1, offset_seconds=8).isoformat(),
                "level": "INFO",
                "message": "Prediction confidence: 0.61 (normal: 0.80-0.95)",
                "service": service,
            },
            # SUBTLE: cache hit ratio normal but effective hit quality low
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_hours=1, offset_seconds=5).isoformat(),
                "level": "INFO",
                "message": "Cache hit ratio: 78%",
                "service": service,
            },
        ]
        return logs

    def _generate_affected_logs(self, service: str) -> list[dict]:
        return [
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=60).isoformat(),
                "level": "WARNING",
                "message": f"Slow response from upstream: {self.scenario.root_cause_service}",
                "service": service,
            },
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=55).isoformat(),
                "level": "WARNING",
                "message": "Retry attempt 2 of 3",
                "service": service,
            },
        ]

    def _generate_healthy_logs(self, service: str) -> list[dict]:
        return [
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=120).isoformat(),
                "level": "INFO",
                "message": "Health check passed",
                "service": service,
            },
            {
                "timestamp": get_deterministic_timestamp(self.seed, offset_seconds=60).isoformat(),
                "level": "DEBUG",
                "message": "Processing request batch",
                "service": service,
            },
        ]
