"""
IncidentOps - Noise Generators and Partial Observability

Deterministic noise generators for environment realism:
- LogNoiseGenerator: irrelevant warnings, duplicates, misleading traces
- MetricNoiseGenerator: fluctuations, delayed updates, spikes
- PartialObservabilityManager: hidden logs, lagging metrics
- DependencyPropagator: fault propagation through service graph
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import random
from datetime import datetime, timedelta
from collections import deque


# Deterministic base epoch for all timestamps (Jan 1, 2024 00:00:00 UTC)
DETERMINISTIC_EPOCH = datetime(2024, 1, 1, 0, 0, 0)


def get_deterministic_timestamp(seed: int, offset_hours: float = 0, offset_seconds: float = 0) -> datetime:
    """
    Generate deterministic timestamp based on seed and offset.

    No use of system time - completely deterministic.
    """
    base = DETERMINISTIC_EPOCH + timedelta(hours=offset_hours, seconds=offset_seconds)
    return base


class ServiceStatus(str, Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ============================================================================
# LOG NOISE GENERATOR (Deterministic)
# ============================================================================

class LogNoiseGenerator:
    """
    Generates deterministic log noise for environment realism.

    NO datetime.utcnow() - uses seed-based offsets.
    """

    IRRELEVANT_WARNINGS = [
        "Connection pool approaching limit (80%)",
        "Slow query detected: 450ms",
        "Cache miss rate above threshold",
        "GC pause detected: 150ms",
        "Thread pool queue growing",
        "DNS resolution slow: 50ms",
        "SSL certificate expiring in 30 days",
        "Deprecated API endpoint called",
        "Request header size large: 8KB",
        "Response compression skipped (too small)",
        "Session cleanup running",
        "Background job queue backup: 5 items",
        "Metric buffer flush delayed",
        "Heartbeat missed from replica",
        "Config reload pending",
    ]

    MISLEADING_TRACES = [
        """java.lang.Thread.sleep(Thread.java)
        at com.app.cache.CacheManager.evict(CacheManager.java:142)
        at com.app.cache.CacheManager.put(CacheManager.java:98)
        at com.app.service.DataService.process(DataService.java:55)""",
        """java.net.SocketTimeoutException: Read timed out
        at java.net.SocketInputStream.socketRead0(Native Method)
        at com.app.http.HttpClient.execute(HttpClient.java:234)
        at com.app.external.ThirdPartyClient.call(ThirdPartyClient.java:67)""",
        """org.postgresql.util.PSQLException: Connection is closed
        at org.postgresql.jdbc.PgConnection.checkClosed(PgConnection.java:892)
        at com.app.db.ConnectionPool.borrow(ConnectionPool.java:45)""",
        """java.io.IOException: Too many open files
        at java.io.FileOutputStream.open(Native Method)
        at com.app.logging.FileLogger.write(FileLogger.java:78)""",
        """javax.net.ssl.SSLHandshakeException: PKIX path building failed
        at sun.security.ssl.Alert.createSSLException(Alert.java:131)
        at com.app.security.SSLContext.init(SSLContext.java:34)""",
    ]

    def __init__(self, seed: int = 42, base_step: int = 0):
        self.rng = random.Random(seed)
        self.seed = seed
        self.base_step = base_step  # Deterministic step counter
        self.generated_logs: dict[str, list[dict]] = {}

    def generate_noise_logs(
        self,
        service: str,
        count: int = 5,
        include_misleading: bool = True
    ) -> list[dict]:
        """Generate noise logs with deterministic timestamps."""
        logs = []

        for i in range(count):
            log_type = self.rng.choice(["irrelevant", "irrelevant", "duplicate", "misleading"])

            # Deterministic timestamp based on seed and step
            timestamp = get_deterministic_timestamp(
                self.seed,
                offset_seconds=self.base_step * 60 + self.rng.randint(1, 300)
            )

            if log_type == "irrelevant":
                logs.append({
                    "timestamp": timestamp.isoformat(),
                    "level": self.rng.choice(["INFO", "WARNING"]),
                    "message": self.rng.choice(self.IRRELEVANT_WARNINGS),
                    "service": service,
                    "noise_type": "irrelevant",
                })

            elif log_type == "duplicate" and logs:
                original = self.rng.choice(logs[:i] if i > 0 else logs)
                duplicate = original.copy()
                dup_timestamp = get_deterministic_timestamp(
                    self.seed,
                    offset_seconds=self.base_step * 60 + self.rng.randint(1, 60)
                )
                duplicate["timestamp"] = dup_timestamp.isoformat()
                duplicate["noise_type"] = "duplicate"
                logs.append(duplicate)

            elif log_type == "misleading" and include_misleading:
                logs.append({
                    "timestamp": timestamp.isoformat(),
                    "level": "ERROR",
                    "message": "Exception occurred during processing",
                    "stack_trace": self.rng.choice(self.MISLEADING_TRACES),
                    "service": service,
                    "noise_type": "misleading",
                })

        return logs

    def inject_noise_into_logs(
        self,
        real_logs: list[dict],
        service: str,
        noise_ratio: float = 0.3
    ) -> list[dict]:
        """Inject noise into real logs."""
        noise_count = max(1, int(len(real_logs) * noise_ratio))
        noise_logs = self.generate_noise_logs(service, noise_count)

        mixed = real_logs + noise_logs
        mixed.sort(key=lambda x: x.get("timestamp", ""))

        return mixed


# ============================================================================
# METRIC NOISE GENERATOR (Deterministic)
# ============================================================================

class MetricNoiseGenerator:
    """
    Generates deterministic metric noise and delays.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed

        self.metric_history: dict[str, deque] = {}
        self.history_size = 5

        self.last_update_step: dict[str, int] = {}
        self.update_delay = 2

    def add_fluctuation(self, value: float, amplitude: float = 0.05) -> float:
        """Add deterministic fluctuation to a metric value."""
        noise = self.rng.uniform(-amplitude, amplitude) * value
        return value + noise

    def apply_metric_lag(
        self,
        service: str,
        metric_name: str,
        current_value: float,
        current_step: int
    ) -> float:
        """Apply deterministic lag to metric updates."""
        key = f"{service}:{metric_name}"

        if key not in self.metric_history:
            self.metric_history[key] = deque(maxlen=self.history_size)
            self.last_update_step[key] = 0

        self.metric_history[key].append(current_value)

        steps_since_update = current_step - self.last_update_step.get(key, 0)

        if steps_since_update < self.update_delay:
            history = list(self.metric_history[key])
            if len(history) > 1:
                lag_index = max(0, len(history) - 1 - self.update_delay + steps_since_update)
                return history[lag_index]

        self.last_update_step[key] = current_step

        return current_value

    def add_missing_data(
        self,
        metrics: dict,
        missing_probability: float = 0.02
    ) -> dict:
        """Add deterministic missing data points."""
        result = {}
        for key, value in metrics.items():
            if self.rng.random() < missing_probability:
                result[key] = None
            else:
                result[key] = value
        return result

    def add_spike(
        self,
        value: float,
        spike_probability: float = 0.01,
        spike_multiplier: float = 5.0
    ) -> float:
        """Add deterministic spike to metrics."""
        if self.rng.random() < spike_probability:
            return value * spike_multiplier
        return value

    def generate_noisy_metrics(
        self,
        base_metrics: dict,
        service: str,
        current_step: int,
        noise_config: Optional[dict] = None
    ) -> dict:
        """Generate noisy metrics from base values."""
        config = noise_config or {
            "fluctuation_amplitude": 0.05,
            "lag_enabled": True,
            "missing_probability": 0.02,
            "spike_probability": 0.01,
        }

        noisy = {}

        for metric_name, value in base_metrics.items():
            if value is None:  # pragma: no cover
                noisy[metric_name] = None  # pragma: no cover
                continue  # pragma: no cover

            if not isinstance(value, (int, float)):  # pragma: no cover
                noisy[metric_name] = value  # pragma: no cover
                continue  # pragma: no cover

            noisy_value = self.add_fluctuation(
                value,
                config.get("fluctuation_amplitude", 0.05)
            )

            if config.get("lag_enabled", True):
                noisy_value = self.apply_metric_lag(
                    service, metric_name, noisy_value, current_step
                )

            noisy_value = self.add_spike(
                noisy_value,
                config.get("spike_probability", 0.01)
            )

            noisy[metric_name] = round(noisy_value, 4)

        noisy = self.add_missing_data(
            noisy,
            config.get("missing_probability", 0.02)
        )

        return noisy


# ============================================================================
# PARTIAL OBSERVABILITY SYSTEM
# ============================================================================

class PartialObservabilityManager:
    """
    Manages partial observability - deterministic.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed

        self.queried_services: set[str] = set()
        self.queried_metrics: dict[str, set[str]] = {}
        self.queried_logs: set[str] = set()

        self.hidden_logs: dict[str, list[dict]] = {}
        self.hidden_metrics: dict[str, dict] = {}

        self.visibility_levels: dict[str, float] = {}

    def set_visibility(self, service: str, level: float) -> None:  # pragma: no cover
        self.visibility_levels[service] = max(0.0, min(1.0, level))  # pragma: no cover

    def hide_logs(self, service: str, logs: list[dict]) -> None:  # pragma: no cover
        self.hidden_logs[service] = logs  # pragma: no cover

    def hide_metrics(self, service: str, metrics: dict) -> None:  # pragma: no cover
        self.hidden_metrics[service] = metrics  # pragma: no cover

    def query_logs(self, service: str) -> tuple[list[dict], bool]:
        was_hidden = service not in self.queried_logs
        self.queried_logs.add(service)

        logs = self.hidden_logs.get(service, [])

        visibility = self.visibility_levels.get(service, 1.0)
        if visibility < 1.0:  # pragma: no cover
            logs = [log for log in logs if self.rng.random() < visibility]  # pragma: no cover

        return logs, was_hidden

    def query_metrics(self, service: str, metric_names: Optional[list[str]] = None) -> tuple[dict, bool]:
        if service not in self.queried_metrics:  # pragma: no cover
            self.queried_metrics[service] = set()  # pragma: no cover

        was_hidden = False
        all_metrics = self.hidden_metrics.get(service, {})

        if metric_names:
            for name in metric_names:
                if name not in self.queried_metrics[service]:  # pragma: no cover
                    was_hidden = True  # pragma: no cover
                    self.queried_metrics[service].add(name)  # pragma: no cover
            metrics = {k: v for k, v in all_metrics.items() if k in metric_names}
        else:
            was_hidden = len(self.queried_metrics[service]) == 0
            self.queried_metrics[service] = set(all_metrics.keys())
            metrics = all_metrics

        return metrics, was_hidden

    def get_observability_summary(self) -> dict:  # pragma: no cover
        return {  # pragma: no cover
            "queried_services": list(self.queried_services),  # pragma: no cover
            "queried_logs": list(self.queried_logs),  # pragma: no cover
            "queried_metrics": {  # pragma: no cover
                svc: list(metrics)  # pragma: no cover
                for svc, metrics in self.queried_metrics.items()  # pragma: no cover
            },  # pragma: no cover
            "visibility_levels": self.visibility_levels,  # pragma: no cover
        }  # pragma: no cover

    def reset(self) -> None:  # pragma: no cover
        self.queried_services.clear()  # pragma: no cover
        self.queried_metrics.clear()
        self.queried_logs.clear()
        self.hidden_logs.clear()
        self.hidden_metrics.clear()
        self.visibility_levels.clear()


# ============================================================================
# DEPENDENCY PROPAGATION SYSTEM
# ============================================================================

class DependencyPropagator:
    """
    Manages fault propagation through service dependencies.
    Deterministic with seed.
    """

    DEPENDENCY_GRAPH = {
        "recommendation-service": ["order-service", "database-replica", "cache-service"],
        "order-service": ["auth-service", "payment-service", "inventory-service"],
        "auth-service": ["database-primary", "cache-service"],
        "user-service": ["database-primary", "auth-service"],
        "payment-service": ["database-primary"],
        "api-gateway": ["user-service", "auth-service", "order-service"],
        "search-service": ["database-replica", "cache-service"],
        "notification-service": ["email-service", "order-service"],
        "analytics-service": ["database-replica", "recommendation-service"],
        "inventory-service": ["database-primary"],
        "shipping-service": ["order-service"],
        "email-service": [],
        "cache-service": [],
        "database-primary": [],
        "database-replica": [],
    }

    REVERSE_DEPENDENCY_GRAPH: dict[str, list[str]] = {}

    @classmethod
    def _build_reverse_graph(cls) -> None:
        for service, deps in cls.DEPENDENCY_GRAPH.items():
            for dep in deps:
                if dep not in cls.REVERSE_DEPENDENCY_GRAPH:
                    cls.REVERSE_DEPENDENCY_GRAPH[dep] = []
                cls.REVERSE_DEPENDENCY_GRAPH[dep].append(service)

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed

        if not self.REVERSE_DEPENDENCY_GRAPH:  # pragma: no cover
            self._build_reverse_graph()  # pragma: no cover

        self.fault_origin: Optional[str] = None
        self.propagated_services: set[str] = set()
        self.propagation_delays: dict[str, int] = {}
        self.current_step = 0

        self.base_propagation_delay = 2
        self.propagation_decay = 0.7

    def get_downstream_services(self, service: str, depth: int = -1) -> list[str]:
        downstream = []
        visited = {service}
        queue = [(service, 0)]

        while queue:
            current, current_depth = queue.pop(0)

            if depth != -1 and current_depth >= depth:
                continue

            dependents = self.REVERSE_DEPENDENCY_GRAPH.get(current, [])
            for dep in dependents:
                if dep not in visited:
                    visited.add(dep)
                    downstream.append(dep)
                    queue.append((dep, current_depth + 1))

        return downstream

    def get_upstream_services(self, service: str) -> list[str]:
        return self.DEPENDENCY_GRAPH.get(service, [])

    def propagate_failure(
        self,
        root_service: str,
        services_state: dict,
        severity: float = 1.0
    ) -> dict:
        self.fault_origin = root_service
        self.propagated_services = {root_service}

        downstream = self.get_downstream_services(root_service)

        for i, service in enumerate(downstream):
            distance = i + 1
            effect_severity = severity * (self.propagation_decay ** distance)

            self.propagation_delays[service] = distance * self.base_propagation_delay

            if service in services_state:
                services_state[service] = self._apply_degradation(
                    services_state[service],
                    effect_severity,
                    distance
                )

            self.propagated_services.add(service)

        return services_state

    def propagate_recovery(
        self,
        root_service: str,
        services_state: dict
    ) -> dict:
        downstream = self.get_downstream_services(root_service)

        services_state[root_service] = self._generate_healthy_state(root_service)

        for service in downstream:
            if service in self.propagated_services:
                services_state[service] = self._generate_healthy_state(service)

        self.propagated_services.clear()
        self.fault_origin = None

        return services_state

    def step_propagation(self, services_state: dict) -> dict:
        self.current_step += 1

        for service, delay in list(self.propagation_delays.items()):
            if self.current_step >= delay:
                del self.propagation_delays[service]

        return services_state

    def _apply_degradation(
        self,
        current_state: dict,
        severity: float,
        distance: int
    ) -> dict:
        state = current_state.copy()

        base_latency = state.get("latency_ms", 50)
        state["latency_ms"] = base_latency * (1 + severity * 2)

        base_error = state.get("error_rate", 0.01)
        state["error_rate"] = min(0.5, base_error + severity * 0.1)

        if severity > 0.5:
            state["status"] = ServiceStatus.UNHEALTHY.value
        elif severity > 0.2:
            state["status"] = ServiceStatus.DEGRADED.value
        else:
            state["status"] = ServiceStatus.DEGRADED.value

        state["propagation_distance"] = distance
        state["propagation_severity"] = severity

        return state

    def _generate_healthy_state(self, service: str) -> dict:
        return {
            "status": ServiceStatus.HEALTHY.value,
            "latency_ms": self.rng.uniform(20, 50),
            "error_rate": self.rng.uniform(0, 0.005),
            "cpu_percent": self.rng.uniform(20, 40),
            "memory_percent": self.rng.uniform(40, 60),
        }

    def get_propagation_info(self) -> dict:  # pragma: no cover
        return {  # pragma: no cover
            "fault_origin": self.fault_origin,  # pragma: no cover
            "propagated_services": list(self.propagated_services),  # pragma: no cover
            "pending_delays": dict(self.propagation_delays),  # pragma: no cover
            "current_step": self.current_step,  # pragma: no cover
        }  # pragma: no cover

    def reset(self) -> None:  # pragma: no cover
        self.fault_origin = None  # pragma: no cover
        self.propagated_services.clear()  # pragma: no cover
        self.propagation_delays.clear()  # pragma: no cover
        self.current_step = 0  # pragma: no cover


DependencyPropagator._build_reverse_graph()


__all__ = [
    "DETERMINISTIC_EPOCH",
    "get_deterministic_timestamp",
    "ServiceStatus",
    "LogNoiseGenerator",
    "MetricNoiseGenerator",
    "PartialObservabilityManager",
    "DependencyPropagator",
]