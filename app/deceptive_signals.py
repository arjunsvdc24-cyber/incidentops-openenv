"""
IncidentOps - Advanced Deceptive Signals v12.0

Sophisticated deceptive signals that require reasoning to overcome:

1. False root cause: DB shows latency spike, but caused by recommendation overload
2. Delayed logs: Error logs appear AFTER issue begins
3. Conflicting metrics: One metric improves while system degrades
4. Noise correlation trap: Two services show similar symptoms

Deterministic and solvable with reasoning.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from enum import Enum
from datetime import datetime, timedelta
import random


class DeceptionType(str, Enum):
    """Types of deceptive signals"""
    FALSE_ROOT_CAUSE = "false_root_cause"
    DELAYED_LOGS = "delayed_logs"
    CONFLICTING_METRICS = "conflicting_metrics"
    NOISE_CORRELATION = "noise_correlation"
    RED_HERRING_DEPLOY = "red_herring_deploy"
    SYMPTOM_MASKED_AS_CAUSE = "symptom_masked_as_cause"


@dataclass
class DeceptivePattern:
    """A deceptive pattern configuration"""
    pattern_type: DeceptionType
    primary_service: str       # The misleading service
    actual_cause: str          # The actual root cause
    signals: List[dict]        # The deceptive signals
    resolution_hint: str       # How to resolve the deception
    reasoning_required: List[str]  # Steps needed to overcome


@dataclass
class DelayedLogConfig:
    """Configuration for delayed log appearance"""
    service: str
    actual_error_time: datetime
    log_appears_after: timedelta
    log_content: str
    misleads_to: str  # What this misleads agent to think


@dataclass
class ConflictingMetricConfig:
    """Configuration for conflicting metrics"""
    service: str
    improving_metric: str      # Metric that shows improvement
    improving_value: float
    degrading_metric: str      # Metric that shows degradation
    degrading_value: float
    interpretation_hint: str   # How to interpret correctly


class DeceptiveSignalGenerator:
    """
    Generates advanced deceptive signals.
    
    All patterns are deterministic and solvable with proper reasoning.
    The goal is to force agents to think, not react.
    """
    
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed
    
    def generate_false_root_cause_pattern(
        self,
        actual_root_cause: str,
        false_root_cause: str
    ) -> DeceptivePattern:
        """
        Generate false root cause pattern.
        
        Example:
        - DB shows latency spike
        - But caused by recommendation service overload
        - Agent must trace the dependency chain
        """
        signals = [
            # DB shows obvious symptoms
            {
                "service": false_root_cause,
                "type": "metric",
                "name": "query_latency_p99",
                "value": 850,
                "baseline": 50,
                "severity": "high",
                "is_misleading": True,
            },
            {
                "service": false_root_cause,
                "type": "metric",
                "name": "connection_count",
                "value": 150,
                "baseline": 30,
                "severity": "medium",
                "is_misleading": True,
            },
            {
                "service": false_root_cause,
                "type": "log",
                "level": "WARNING",
                "message": f"Slow query detected: high load from {actual_root_cause}",
                "is_misleading": True,
                "contains_hint": True,  # The hint is in the message
            },
            
            # Actual root cause shows subtle signs
            {
                "service": actual_root_cause,
                "type": "metric",
                "name": "request_rate",
                "value": 5000,
                "baseline": 1000,
                "severity": "medium",
                "is_actual_cause": True,
            },
            {
                "service": actual_root_cause,
                "type": "metric",
                "name": "business_metric_ctr",
                "value": 1.5,
                "baseline": 3.5,
                "severity": "high",
                "is_actual_cause": True,
                "requires_business_context": True,
            },
        ]
        
        return DeceptivePattern(
            pattern_type=DeceptionType.FALSE_ROOT_CAUSE,
            primary_service=false_root_cause,
            actual_cause=actual_root_cause,
            signals=signals,
            resolution_hint="Check which service is causing the DB load",
            reasoning_required=[
                "Query DB to see latency spike",
                "Query DB logs to find slow queries",
                "Notice DB logs mention recommendation service",
                "Query recommendation service to find actual issue",
                "Correlate recommendation request rate with DB load",
            ]
        )
    
    def generate_delayed_logs_pattern(
        self,
        actual_root_cause: str,
        delayed_service: str,
        base_time: datetime
    ) -> Tuple[DeceptivePattern, List[DelayedLogConfig]]:
        """
        Generate delayed logs pattern.
        
        Error logs appear AFTER the issue has begun,
        making timing-based reasoning essential.
        """
        delayed_configs = [
            DelayedLogConfig(
                service=delayed_service,
                actual_error_time=base_time - timedelta(minutes=30),
                log_appears_after=timedelta(minutes=15),
                log_content="Connection timeout to upstream",
                misleads_to=f"{delayed_service} is the problem"
            ),
            DelayedLogConfig(
                service=actual_root_cause,
                actual_error_time=base_time - timedelta(minutes=45),
                log_appears_after=timedelta(minutes=5),
                log_content="Model inference degradation detected",
                misleads_to="Check logs timing vs metric changes"
            ),
        ]
        
        signals = [
            # Delayed error appears now
            {
                "service": delayed_service,
                "type": "log",
                "level": "ERROR",
                "message": "Connection timeout to upstream",
                "appears_at": (base_time - timedelta(minutes=15)).isoformat(),
                "actual_event_at": (base_time - timedelta(minutes=30)).isoformat(),
                "is_delayed": True,
            },
            # Earlier subtle sign
            {
                "service": actual_root_cause,
                "type": "log",
                "level": "INFO",
                "message": "Model inference time increased",
                "appears_at": (base_time - timedelta(minutes=40)).isoformat(),
                "is_early_signal": True,
            },
            # Timeline shows deploy before issues
            {
                "service": actual_root_cause,
                "type": "deployment",
                "version": "v2.1.0",
                "timestamp": (base_time - timedelta(minutes=50)).isoformat(),
                "description": "Optimize recommendation algorithm",
                "is_cause": True,
            },
        ]
        
        return DeceptivePattern(
            pattern_type=DeceptionType.DELAYED_LOGS,
            primary_service=delayed_service,
            actual_cause=actual_root_cause,
            signals=signals,
            resolution_hint="Compare log timestamps with metric changes",
            reasoning_required=[
                "Query deployment timeline",
                "Note deploy timestamp",
                "Query metrics over time",
                "Notice metric change before error logs",
                "Correlate timeline to find actual cause",
            ]
        ), delayed_configs
    
    def generate_conflicting_metrics_pattern(
        self,
        service: str,
        actual_root_cause: str
    ) -> Tuple[DeceptivePattern, ConflictingMetricConfig]:
        """
        Generate conflicting metrics pattern.
        
        One metric improves while system degrades,
        requiring deeper analysis.
        """
        config = ConflictingMetricConfig(
            service=service,
            improving_metric="throughput",
            improving_value=5000,  # Higher throughput
            degrading_metric="business_value_per_request",
            degrading_value=0.5,  # But lower value per request
            interpretation_hint="High throughput with low value = bad recommendations"
        )
        
        signals = [
            # Misleading "good" metric
            {
                "service": service,
                "type": "metric",
                "name": "throughput",
                "value": 5000,
                "baseline": 3000,
                "trend": "improving",
                "is_misleading": True,
                "misleading_interpretation": "Service is performing well",
            },
            {
                "service": service,
                "type": "metric",
                "name": "latency_p99",
                "value": 45,
                "baseline": 50,
                "trend": "improving",
                "is_misleading": True,
            },
            
            # Actual problem indicators
            {
                "service": service,
                "type": "metric",
                "name": "recommendation_ctr",
                "value": 1.2,
                "baseline": 3.5,
                "trend": "degrading",
                "is_actual_problem": True,
            },
            {
                "service": service,
                "type": "metric",
                "name": "user_engagement",
                "value": 0.3,
                "baseline": 0.8,
                "trend": "degrading",
                "is_actual_problem": True,
            },
            {
                "service": actual_root_cause,
                "type": "deployment",
                "version": "v2.1.0",
                "description": "Speed optimization - reduced model complexity",
                "contains_hint": True,
            },
        ]
        
        return DeceptivePattern(
            pattern_type=DeceptionType.CONFLICTING_METRICS,
            primary_service=service,
            actual_cause=actual_root_cause,
            signals=signals,
            resolution_hint="Check business metrics, not just technical metrics",
            reasoning_required=[
                "Query service metrics",
                "Notice throughput is high (looks good)",
                "Query business metrics",
                "Notice CTR is low (actual problem)",
                "Check deployment for recent changes",
                "Correlate deploy with metric changes",
            ]
        ), config
    
    def generate_noise_correlation_pattern(
        self,
        service_a: str,
        service_b: str,
        actual_root_cause: str
    ) -> DeceptivePattern:
        """
        Generate noise correlation trap.
        
        Two services show similar symptoms,
        but only one is the root cause.
        """
        signals = [
            # Service A shows symptoms
            {
                "service": service_a,
                "type": "metric",
                "name": "error_rate",
                "value": 0.05,
                "baseline": 0.001,
                "correlated_with": service_b,
            },
            {
                "service": service_a,
                "type": "log",
                "level": "WARNING",
                "message": "Upstream dependency slow",
                "correlated_with": service_b,
            },
            
            # Service B shows similar symptoms
            {
                "service": service_b,
                "type": "metric",
                "name": "error_rate",
                "value": 0.04,
                "baseline": 0.001,
                "correlated_with": service_a,
            },
            {
                "service": service_b,
                "type": "log",
                "level": "WARNING",
                "message": "Upstream dependency slow",
                "correlated_with": service_a,
            },
            
            # Actual root cause
            {
                "service": actual_root_cause,
                "type": "metric",
                "name": "saturation",
                "value": 0.95,
                "baseline": 0.5,
                "is_root_cause": True,
            },
            {
                "service": actual_root_cause,
                "type": "dependency",
                "depends_on": [service_a, service_b],
                "is_upstream": True,
                "hint": "Both affected services depend on this",
            },
        ]
        
        return DeceptivePattern(
            pattern_type=DeceptionType.NOISE_CORRELATION,
            primary_service=f"{service_a}+{service_b}",
            actual_cause=actual_root_cause,
            signals=signals,
            resolution_hint="Check dependency direction - which is upstream?",
            reasoning_required=[
                "Query both affected services",
                "Notice both have similar symptoms",
                "Query dependencies",
                "Find common upstream dependency",
                "Investigate upstream service",
                "Identify as root cause",
            ]
        )
    
    def generate_symptom_masked_as_cause(
        self,
        symptom_service: str,
        actual_cause: str
    ) -> DeceptivePattern:
        """
        Generate symptom masked as cause pattern.
        
        The symptom looks like the cause,
        but is actually a downstream effect.
        """
        signals = [
            # Symptom service shows obvious errors
            {
                "service": symptom_service,
                "type": "metric",
                "name": "error_rate",
                "value": 0.15,
                "baseline": 0.001,
                "is_symptom": True,
                "misleading_interpretation": "This is the root cause",
            },
            {
                "service": symptom_service,
                "type": "log",
                "level": "ERROR",
                "message": "Failed to process request",
                "is_symptom": True,
            },
            
            # Actual cause shows subtle signs
            {
                "service": actual_cause,
                "type": "metric",
                "name": "response_time_anomaly",
                "value": 1.3,  # 30% slower
                "baseline": 1.0,
                "is_actual_cause": True,
                "subtle": True,
            },
            {
                "service": actual_cause,
                "type": "log",
                "level": "INFO",
                "message": "Using fallback model path",
                "is_actual_cause": True,
                "subtle": True,
            },
            {
                "service": symptom_service,
                "type": "dependency",
                "depends_on": [actual_cause],
                "is_downstream": True,
                "hint": f"{symptom_service} depends on {actual_cause}",
            },
        ]
        
        return DeceptivePattern(
            pattern_type=DeceptionType.SYMPTOM_MASKED_AS_CAUSE,
            primary_service=symptom_service,
            actual_cause=actual_cause,
            signals=signals,
            resolution_hint="Check dependencies - error may be downstream effect",
            reasoning_required=[
                "See obvious errors in service A",
                "Check service A dependencies",
                "Find it depends on service B",
                "Query service B metrics",
                "Find subtle anomaly in B",
                "Identify B as root cause",
            ]
        )
    
    def generate_full_deception_suite(
        self,
        actual_root_cause: str = "recommendation-service"
    ) -> Dict:
        """
        Generate a complete deception suite for a scenario.
        
        Returns all deceptive patterns that can be used together.
        """
        false_root = "database-primary"
        delayed_service = "api-gateway"
        correlated_a = "user-service"
        correlated_b = "order-service"
        
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        
        patterns = {}
        
        # False root cause
        patterns["false_root_cause"] = self.generate_false_root_cause_pattern(
            actual_root_cause, false_root
        )
        
        # Delayed logs
        patterns["delayed_logs"], _ = self.generate_delayed_logs_pattern(
            actual_root_cause, delayed_service, base_time
        )
        
        # Conflicting metrics
        patterns["conflicting_metrics"], _ = self.generate_conflicting_metrics_pattern(
            actual_root_cause, actual_root_cause
        )
        
        # Noise correlation
        patterns["noise_correlation"] = self.generate_noise_correlation_pattern(
            correlated_a, correlated_b, actual_root_cause
        )
        
        # Symptom masked as cause
        patterns["symptom_masked"] = self.generate_symptom_masked_as_cause(
            correlated_a, actual_root_cause
        )
        
        return patterns
    
    def inject_deception_into_logs(
        self,
        logs: List[dict],
        deception_type: DeceptionType,
        intensity: float = 0.5
    ) -> List[dict]:
        """
        Inject deceptive signals into logs.
        
        Args:
            logs: Original logs
            deception_type: Type of deception to inject
            intensity: How much deception (0.0-1.0)
            
        Returns:
            Logs with deception injected
        """
        deceptive_logs = []
        
        if deception_type == DeceptionType.FALSE_ROOT_CAUSE:
            # Add misleading DB errors
            deceptive_logs.append({
                "timestamp": datetime(2024, 1, 15, 10, 0, 0).isoformat(),
                "service": "database-primary",
                "level": "ERROR",
                "message": "Connection pool exhausted",
                "is_deceptive": True,
            })
        
        elif deception_type == DeceptionType.DELAYED_LOGS:
            # Add logs that appear late
            deceptive_logs.append({
                "timestamp": (datetime(2024, 1, 15, 10, 0, 0) - timedelta(minutes=5)).isoformat(),
                "service": "api-gateway",
                "level": "WARNING",
                "message": "Timeout waiting for upstream",
                "actual_event_time": (datetime(2024, 1, 15, 10, 0, 0) - timedelta(minutes=20)).isoformat(),
                "is_delayed": True,
                "is_deceptive": True,
            })
        
        # Mix with real logs
        combined = logs + deceptive_logs
        
        # Sort by timestamp (deterministic)
        combined.sort(key=lambda x: x.get("timestamp", ""))
        
        return combined
    
    def get_reasoning_path_for_deception(
        self,
        deception_type: DeceptionType
    ) -> List[str]:
        """Get the correct reasoning path to overcome deception"""
        paths = {
            DeceptionType.FALSE_ROOT_CAUSE: [
                "1. Observe DB latency spike",
                "2. Check DB logs for cause",
                "3. Find DB logs mention recommendation-service",
                "4. Query recommendation-service metrics",
                "5. Find business metric decline",
                "6. Correlate deploy timeline with decline",
                "7. Identify recommendation deploy as root cause",
            ],
            DeceptionType.DELAYED_LOGS: [
                "1. Query deployment timeline",
                "2. Note deploy timestamp",
                "3. Query metrics over time",
                "4. Find metric change before error logs",
                "5. Identify service with earliest change",
                "6. That service is root cause",
            ],
            DeceptionType.CONFLICTING_METRICS: [
                "1. Query technical metrics (look fine)",
                "2. Query business metrics (degraded)",
                "3. Realize technical metrics misleading",
                "4. Check deployment history",
                "5. Find deploy that optimized speed",
                "6. Speed optimization degraded quality",
            ],
            DeceptionType.NOISE_CORRELATION: [
                "1. Query multiple affected services",
                "2. Notice similar symptoms",
                "3. Query dependency graph",
                "4. Find common upstream dependency",
                "5. Investigate upstream",
                "6. Identify upstream as root cause",
            ],
            DeceptionType.SYMPTOM_MASKED_AS_CAUSE: [
                "1. See obvious errors in service",
                "2. Check service dependencies",
                "3. Find upstream dependency",
                "4. Query upstream metrics",
                "5. Find subtle anomaly",
                "6. Identify upstream as root cause",
            ],
            DeceptionType.RED_HERRING_DEPLOY: [
                "1. See recent deployment on unrelated service",
                "2. Check deployment timeline for all services",
                "3. Correlate deploy times with incident start",
                "4. Notice unrelated deploy happened after incident began",
                "5. Dismiss red herring deploy",
                "6. Focus on service with matching timeline",
            ],
        }
        return paths.get(deception_type, [])
