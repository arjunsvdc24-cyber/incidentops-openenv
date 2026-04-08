"""
IncidentOps - Frontier-Level Hard Task v11.0

Designed to challenge frontier AI models.

Features:
1. Dual-layer failure (recommendation bug + db latency spike)
2. Misleading root cause (logs suggest db, actual is recommendation)
3. Temporal dependency (deploy before metric drift)
4. Signal mismatch (metrics show one thing, logs show another)

Requires 6-8 steps minimum.
Deterministic.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import random


@dataclass
class DualLayerFailure:
    """Represents a dual-layer failure scenario"""
    primary_failure_service: str      # Actual root cause
    primary_failure_type: str         # e.g., "deployment_bug"
    secondary_failure_service: str    # Misleading service
    secondary_failure_type: str       # e.g., "latency_spike"
    correlation: str                   # How they're related


@dataclass
class DeceptiveSignal:
    """A deceptive signal designed to mislead"""
    service: str
    signal_type: str  # "log", "metric", "alert"
    content: str
    intended_effect: str  # What we want agent to think
    actual_relevance: str  # "misleading", "partial", "delayed"


@dataclass 
class FrontierScenario:
    """Complete frontier-level scenario"""
    scenario_id: str
    difficulty: int  # Always 5 for frontier
    dual_layer_failure: DualLayerFailure
    deceptive_signals: List[DeceptiveSignal]
    timeline_events: List[dict]
    correct_investigation_path: List[str]
    minimum_steps: int = 6


class FrontierTaskGenerator:
    """
    Generates frontier-level difficulty scenarios.
    
    These scenarios are designed to require true reasoning,
    not pattern matching or brute force.
    """
    
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed
    
    def generate_frontier_scenario(self) -> FrontierScenario:
        """
        Generate a frontier-level scenario.
        
        Key design:
        1. Two apparent failures, only one is root cause
        2. Logs point to wrong service
        3. Metrics show conflicting signals
        4. Requires temporal reasoning
        """
        scenario_id = f"frontier_{self.seed}"
        
        # Create dual-layer failure
        dual_failure = DualLayerFailure(
            primary_failure_service="recommendation-service",
            primary_failure_type="deployment_bug",  # Algorithm bug
            secondary_failure_service="database-primary",
            secondary_failure_type="latency_spike",  # Red herring
            correlation="recommendation queries db, but db latency is symptom not cause"
        )
        
        # Create deceptive signals
        deceptive_signals = self._generate_deceptive_signals()
        
        # Create timeline
        timeline = self._generate_timeline()
        
        # Define correct investigation path
        correct_path = [
            "query_metrics:recommendation-service",      # See CTR decline
            "query_metrics:database-primary",           # See latency (misleading)
            "query_deployments",                        # See timeline
            "query_logs:recommendation-service",        # No errors (clue)
            "query_logs:database-primary",              # See slow queries (misleading)
            "correlate:deploy_time_with_ctr_decline",   # Key reasoning step
            "identify_root_cause:recommendation-service",
            "rollback_deployment:recommendation-service",
        ]
        
        return FrontierScenario(
            scenario_id=scenario_id,
            difficulty=5,
            dual_layer_failure=dual_failure,
            deceptive_signals=deceptive_signals,
            timeline_events=timeline,
            correct_investigation_path=correct_path,
            minimum_steps=6,
        )
    
    def _generate_deceptive_signals(self) -> List[DeceptiveSignal]:
        """Generate deceptive signals"""
        signals = []
        
        # 1. Database latency spike (misleading - appears as root cause)
        signals.append(DeceptiveSignal(
            service="database-primary",
            signal_type="metric",
            content="latency_p99: 850ms (baseline: 50ms)",
            intended_effect="Agent thinks DB is the problem",
            actual_relevance="misleading"  # It's a symptom, not cause
        ))
        
        # 2. Database slow query logs (misleading)
        signals.append(DeceptiveSignal(
            service="database-primary",
            signal_type="log",
            content="WARNING: Slow query detected: 2300ms",
            intended_effect="Reinforce DB as root cause",
            actual_relevance="misleading"
        ))
        
        # 3. Recommendation service appears healthy (deceptive)
        signals.append(DeceptiveSignal(
            service="recommendation-service",
            signal_type="metric",
            content="error_rate: 0.001%, latency_p99: 45ms",
            intended_effect="Agent dismisses recommendation-service",
            actual_relevance="partial"  # No errors, but business metrics bad
        ))
        
        # 4. CTR decline (the real signal, but subtle)
        signals.append(DeceptiveSignal(
            service="recommendation-service",
            signal_type="metric",
            content="ctr: 1.8% (baseline: 3.5%), quality_score: 0.65 (baseline: 0.85)",
            intended_effect="Should trigger deeper investigation",
            actual_relevance="partial"  # Key signal if agent looks
        ))
        
        # 5. Recommendation logs show no errors (actually a clue)
        signals.append(DeceptiveSignal(
            service="recommendation-service",
            signal_type="log",
            content="INFO: Model v2.1.0 loaded, DEBUG: Processing batch",
            intended_effect="Looks normal, but model version is clue",
            actual_relevance="partial"  # Version number is the key
        ))
        
        # 6. Unrelated service warning (noise)
        signals.append(DeceptiveSignal(
            service="notification-service",
            signal_type="alert",
            content="WARNING: Queue depth above threshold",
            intended_effect="Distraction",
            actual_relevance="misleading"
        ))
        
        # 7. Delayed metric (appears after issue resolved in history)
        signals.append(DeceptiveSignal(
            service="cache-service",
            signal_type="metric",
            content="cache_hit_ratio: 78% (was 85% 2 hours ago)",
            intended_effect="Another red herring",
            actual_relevance="delayed"
        ))
        
        return signals
    
    def _generate_timeline(self) -> List[dict]:
        """Generate timeline with temporal dependency"""
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        
        events = [
            # Normal operations
            {
                "timestamp": (base_time - timedelta(hours=4)).isoformat(),
                "service": "database-primary",
                "event": "maintenance_complete",
                "description": "DB index optimization completed",
            },
            {
                "timestamp": (base_time - timedelta(hours=2)).isoformat(),
                "service": "recommendation-service",
                "event": "deployment",
                "version": "v2.0.5",
                "description": "Minor bugfix release",
                "is_problematic": False,
            },
            # The problematic deployment
            {
                "timestamp": (base_time - timedelta(hours=1, minutes=30)).isoformat(),
                "service": "recommendation-service",
                "event": "deployment",
                "version": "v2.1.0",
                "description": "Optimize recommendation algorithm for speed",
                "is_problematic": True,  # This introduced the bug
                "commit": "abc123def",
                "author": "developer_a",
            },
            # Secondary symptom: DB load increases (because recommendations are wrong)
            {
                "timestamp": (base_time - timedelta(hours=1, minutes=15)).isoformat(),
                "service": "database-primary",
                "event": "metric_change",
                "metric": "query_latency",
                "change": "+400ms",
                "description": "Query latency spike observed",
            },
            # Another deployment (red herring)
            {
                "timestamp": (base_time - timedelta(hours=1)).isoformat(),
                "service": "notification-service",
                "event": "deployment",
                "version": "v1.3.0",
                "description": "Update notification templates",
                "is_problematic": False,
            },
            # CTR starts declining (delayed effect)
            {
                "timestamp": (base_time - timedelta(minutes=45)).isoformat(),
                "service": "recommendation-service",
                "event": "metric_change",
                "metric": "ctr",
                "change": "-0.5%",
                "description": "CTR begins gradual decline",
            },
            # More symptoms
            {
                "timestamp": (base_time - timedelta(minutes=30)).isoformat(),
                "service": "analytics-service",
                "event": "alert",
                "description": "User engagement metrics declining",
            },
            {
                "timestamp": (base_time - timedelta(minutes=15)).isoformat(),
                "service": "database-primary",
                "event": "alert",
                "description": "Slow query count elevated",
            },
        ]
        
        return events


class DeceptiveSignalGenerator:
    """
    Generates deceptive signals for various scenarios.
    
    Types of deception:
    1. Unrelated warnings
    2. Error logs after resolution
    3. Delayed metrics
    4. Conflicting signals
    """
    
    # Unrelated warnings that appear random
    UNRELATED_WARNINGS = [
        ("notification-service", "Queue depth above 80%"),
        ("email-service", "SMTP connection slow"),
        ("search-service", "Index rebuild pending"),
        ("analytics-service", "Batch job delayed by 5 minutes"),
        ("cache-service", "Eviction rate elevated"),
        ("shipping-service", "External API timeout"),
    ]
    
    # Post-resolution errors (appear after fix applied)
    POST_RESOLUTION_ERRORS = [
        ("payment-service", "Connection pool exhausted (temporary)"),
        ("order-service", "Retry limit exceeded for upstream"),
        ("user-service", "Session cache miss spike"),
    ]
    
    # Delayed metric patterns
    DELAYED_METRICS = [
        ("cache-service", "hit_ratio", "78%", "2 hours ago: 85%"),
        ("search-service", "index_size", "12GB", "1 hour ago: 10GB"),
        ("analytics-service", "queue_depth", "150", "30 min ago: 50"),
    ]
    
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed
    
    def generate_unrelated_warnings(
        self,
        count: int = 2,
        exclude_services: Optional[List[str]] = None
    ) -> List[dict]:
        """Generate unrelated warning signals"""
        exclude = set(exclude_services or [])
        
        available = [
            (s, m) for s, m in self.UNRELATED_WARNINGS
            if s not in exclude
        ]
        
        selected = self.rng.sample(
            available,
            min(count, len(available))
        )
        
        return [
            {
                "service": svc,
                "level": "WARNING",
                "message": msg,
                "noise_type": "unrelated",
            }
            for svc, msg in selected
        ]
    
    def generate_post_resolution_errors(
        self,
        resolution_step: int,
        delay_steps: int = 2
    ) -> List[dict]:
        """
        Generate errors that appear after resolution.
        
        These appear after the agent has fixed the issue,
        potentially causing confusion.
        """
        errors = []
        
        for svc, msg in self.rng.sample(
            self.POST_RESOLUTION_ERRORS,
            min(1, len(self.POST_RESOLUTION_ERRORS))
        ):
            errors.append({
                "service": svc,
                "level": "ERROR",
                "message": msg,
                "appears_after_step": resolution_step + delay_steps,
                "noise_type": "post_resolution",
            })
        
        return errors
    
    def generate_delayed_metrics(
        self,
        current_step: int,
        delay_steps: int = 3
    ) -> List[dict]:
        """Generate metrics that lag behind reality"""
        metrics = []
        
        for svc, metric, current, previous in self.DELAYED_METRICS:
            metrics.append({
                "service": svc,
                "metric_name": metric,
                "current_value": current,
                "previous_value": previous,
                "delay_steps": delay_steps,
                "noise_type": "delayed",
            })
        
        return metrics
    
    def generate_conflicting_signals(
        self,
        service: str,
        metric_signal: str,
        log_signal: str
    ) -> dict:
        """
        Generate conflicting signals for same service.
        
        Metrics show one thing, logs show another.
        """
        return {
            "service": service,
            "conflict_type": "metric_vs_log",
            "metric_signal": {
                "type": "metric",
                "content": metric_signal,
                "interpretation": "appears healthy",
            },
            "log_signal": {
                "type": "log",
                "content": log_signal,
                "interpretation": "appears problematic",
            },
            "resolution": "Must check business metrics to resolve conflict",
            "noise_type": "conflicting",
        }
    
    def inject_deception_into_logs(
        self,
        real_logs: List[dict],
        scenario_type: str = "frontier"
    ) -> List[dict]:
        """
        Inject deceptive signals into real logs.
        
        Maintains determinism via seed.
        """
        deceptive_logs = []
        
        # Add unrelated warnings
        if scenario_type == "frontier":
            warnings = self.generate_unrelated_warnings(count=2)
            for w in warnings:
                deceptive_logs.append({
                    "timestamp": datetime(2024, 1, 15, 10, 0, 0).isoformat(),
                    "service": w["service"],
                    "level": w["level"],
                    "message": w["message"],
                    "is_deceptive": True,
                })
        
        # Mix with real logs
        combined = real_logs + deceptive_logs
        
        # Sort by timestamp (deterministic)
        combined.sort(key=lambda x: x.get("timestamp", ""))
        
        return combined
    
    def inject_deception_into_metrics(
        self,
        real_metrics: dict,
        service: str
    ) -> dict:
        """Inject deceptive signals into metrics"""
        metrics = real_metrics.copy()
        
        # Add delayed metric indicators
        metrics["_metadata"] = {
            "data_freshness": "may_be_delayed_by_2_steps",
            "last_update": "see_deployment_timeline_for_correlation",
        }
        
        return metrics


def create_frontier_scenario(seed: int = 42) -> FrontierScenario:
    """Factory function to create frontier scenario"""
    generator = FrontierTaskGenerator(seed=seed)
    return generator.generate_frontier_scenario()
