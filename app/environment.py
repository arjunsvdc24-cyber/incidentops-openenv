"""
IncidentOps - Core Environment (OpenEnv Specification) v9.0

Enhanced with:
- Log noise (irrelevant warnings, duplicates, misleading traces)
- Metric noise (fluctuations, delayed updates)
- Partial observability (hidden logs, lagging metrics)
- Full dependency propagation

A Gym-style environment for incident response RL training.
"""
from dataclasses import dataclass, field
from typing import Optional
import random
from datetime import datetime

from app.models import (
    ActionType,
    ServiceStatus,
    StepResponse,
    RewardBreakdown,
    VALID_SERVICES,
)
from app.reward import RewardCalculator, RewardConfig, create_default_reward_calculator
from app.memory import IncidentMemory
from app.fault_injector import (
    FaultInjector,
    FaultSimulator,
    FaultScenario,
    FaultType,
    LogNoiseGenerator,
    MetricNoiseGenerator,
    PartialObservabilityManager,
    DependencyPropagator,
)


# === SLA & Business Constants ===

# Simulation time: 5 steps = 1 minute
STEPS_PER_MINUTE = 5

# SLA time limits per fault type (in minutes)
SLA_MINUTES = {
    "oom": 5,
    "cascade": 8,
    "ghost": 15,
    "deployment": 8,
    "network": 5,
    "network_partition": 5,
    "data_corruption": 5,
    "config_drift": 10,
    "ddos": 3,
    "slow_downstream": 8,
    "version_mismatch": 10,
    "cert_expiry": 15,
    "memory_leak": 10,
    "zombie_process": 5,
    "thundering_herd": 5,
}

# Revenue per minute for each service (based on criticality, in USD)
SERVICE_REVENUE_MAP = {
    "payment-service": 5000,
    "order-service": 4000,
    "user-service": 3000,
    "api-gateway": 5000,
    "auth-service": 4500,
    "inventory-service": 2000,
    "recommendation-service": 1500,
    "cache-service": 1000,
    "notification-service": 500,
    "email-service": 300,
    "shipping-service": 2000,
    "search-service": 1000,
    "analytics-service": 500,
    "database-primary": 8000,
    "database-replica": 0,
}


@dataclass
class EnvironmentConfig:
    """Configuration for the environment"""
    seed: int = 42
    max_steps: int = 50
    fault_type: Optional[FaultType] = None
    difficulty: int = 3
    enable_memory: bool = True
    
    # Noise configuration
    enable_log_noise: bool = True
    enable_metric_noise: bool = True
    enable_partial_observability: bool = True
    enable_propagation: bool = True
    
    # Noise levels
    log_noise_ratio: float = 0.3
    metric_fluctuation_amplitude: float = 0.05
    metric_lag_steps: int = 2
    
    # Reward configuration
    reward_config: RewardConfig = field(default_factory=RewardConfig)


@dataclass
class AgentAction:
    """Parsed agent action"""
    action_type: ActionType
    target_service: Optional[str] = None
    parameters: dict = field(default_factory=dict)


class IncidentEnv:
    """
    Incident Response Environment with Enhanced Realism.
    
    OpenEnv Specification Compliance:
    - Deterministic with seed
    - Gym-style step interface
    - Rich observation space
    - Dense reward signal
    
    Enhanced Features:
    - Realistic log noise
    - Metric fluctuations and lag
    - Partial observability
    - Dependency propagation
    """
    
    def __init__(self, config: Optional[EnvironmentConfig] = None):
        self.config = config or EnvironmentConfig()
        self.rng = random.Random(self.config.seed)
        
        # Core components
        self.fault_injector = FaultInjector(seed=self.config.seed)
        self.memory = IncidentMemory(seed=self.config.seed) if self.config.enable_memory else None
        self.reward_calculator = create_default_reward_calculator()
        
        # Current episode state
        self.current_step = 0
        self.current_scenario: Optional[FaultScenario] = None
        self.simulator: Optional[FaultSimulator] = None
        
        # State tracking
        self.services: dict = {}
        self.terminated = False
        self.truncated = False
        self.episode_rewards: list[float] = []
        self.episode_actions: list[dict] = []
        
        # Fix tracking
        self.fix_applied = False
        self.root_cause_identified = False
        self.memory_used_this_step = False
        
        # Track what has been observed (for partial observability)
        self._observed_services: set[str] = set()
        self._observed_logs: set[str] = set()
        self._observed_metrics: set[str] = set()

        # Memory spiral tracking (Task 5)
        self._memory_leak_step: int = 0
    
    # === OpenEnv Core Methods ===
    
    def reset(self, seed: Optional[int] = None) -> dict:
        """Reset the environment for a new episode"""
        if seed is not None:
            self.rng = random.Random(seed)
            self.config.seed = seed
        
        # Reset episode state
        self.current_step = 0
        self.terminated = False
        self.truncated = False
        self.episode_rewards = []
        self.episode_actions = []
        self.fix_applied = False
        self.root_cause_identified = False
        self.memory_used_this_step = False
        self._observed_services.clear()
        self._observed_logs.clear()
        self._observed_metrics.clear()
        self._memory_leak_step = 0
        
        # Generate new fault scenario
        self.current_scenario = self.fault_injector.generate_scenario(
            fault_type=self.config.fault_type,
            difficulty=self.config.difficulty
        )
        
        # Create simulator with enhanced features
        self.simulator = FaultSimulator(
            self.current_scenario,
            seed=self.config.seed
        )
        
        # Initialize services with propagation
        self.services = self.simulator.get_service_states(
            apply_propagation=self.config.enable_propagation
        )
        
        # Reset reward calculator
        self.reward_calculator.reset()
        self.reward_calculator.set_fault_info(
            root_cause=self.current_scenario.root_cause_service,
            affected_services=set(self.current_scenario.affected_services),
            fault_type=self.current_scenario.fault_type.value
        )
        
        return self._get_observation()
    
    def step(self, action: dict) -> StepResponse:
        """Execute one step in the environment"""
        # Parse and validate action
        parsed_action = self._parse_action(action)
        
        # Reset memory flag
        self.memory_used_this_step = False
        
        # Execute action and get result
        action_result = self._execute_action(parsed_action)
        
        # Advance simulator step (for metric lag)
        if self.simulator:
            self.simulator.advance_step()
        
        # Calculate reward
        reward_breakdown = self.reward_calculator.calculate_step_reward(
            action_type=parsed_action.action_type.value,
            target_service=parsed_action.target_service,
            current_services=self.services,
            is_terminated=self.terminated,
            used_memory=self.memory_used_this_step,
        )
        
        reward = reward_breakdown.total

        # SLA urgency penalty — time pressure for real-world stakes
        sla = self._get_sla_deadline()
        if sla.get("urgency") == "critical":
            reward -= 0.1  # Penalty for operating in SLA breach zone
        elif sla.get("urgency") == "elevated":
            reward -= 0.05  # Warning zone

        self.episode_rewards.append(reward)

        # Increment step first so SLA math works correctly
        self.current_step += 1

        # Track memory spiral progress (Task 5)
        if (self.current_scenario and
                self.current_scenario.is_memory_leak and
                not self.fix_applied):
            self._memory_leak_step += 1

        # Check truncation: use SLA-based max_steps (minimum of configured max_steps and SLA limit)
        effective_max_steps = self._get_sla_max_steps()
        if self.current_step >= effective_max_steps:
            self.truncated = True

        # Check termination: fix applied
        self._check_termination(parsed_action)
        
        # Record action
        self.episode_actions.append({
            "step": self.current_step,
            "action": action,
            "reward": reward,
            "terminated": self.terminated,
        })
        
        # Build info
        info = self._build_info(reward_breakdown)
        
        # Build observation: merge action result with full state
        observation = self._get_observation()
        observation["action_result"] = action_result
        
        return StepResponse(
            observation=observation,
            reward=reward,
            terminated=self.terminated,
            truncated=self.truncated,
            info=info,
        )
    
    def render(self, mode: str = "human") -> Optional[str]:
        """Render the current state"""
        if mode == "ansi":
            lines = [
                f"=== Step {self.current_step} ===",
                f"Fault Type: {self.current_scenario.fault_type.value if self.current_scenario else 'N/A'}",
                f"Root Cause: {self.current_scenario.root_cause_service if self.current_scenario else 'N/A'}",
                "",
                "Service States:",
            ]
            for svc, state in self.services.items():
                status = state.get("status", "unknown")
                latency = state.get("latency_ms", 0)
                error = state.get("error_rate", 0)
                propagation = state.get("propagation_distance", "-")
                lines.append(f"  {svc}: {status} (latency: {latency:.1f}ms, error: {error:.2%}, prop_dist: {propagation})")
            
            lines.extend([
                "",
                "Observability:",
                f"  Observed services: {len(self._observed_services)}",
                f"  Observed logs: {len(self._observed_logs)}",
                f"  Observed metrics: {len(self._observed_metrics)}",
                "",
                f"Total Reward: {sum(self.episode_rewards):.4f}",
            ])
            
            return "\n".join(lines)
        
        return None
    
    def close(self) -> None:
        """Clean up environment resources"""
        self.services = {}
        self.current_scenario = None
        self.simulator = None
    
    # === Action Execution ===
    
    def _parse_action(self, action: dict) -> AgentAction:
        """Parse and validate action dict"""
        action_type = ActionType(action["action_type"])
        target_service = action.get("target_service")
        parameters = action.get("parameters", {})
        
        return AgentAction(
            action_type=action_type,
            target_service=target_service,
            parameters=parameters,
        )
    
    def _execute_action(self, action: AgentAction) -> dict:
        """Execute action and return observation"""
        
        if action.action_type == ActionType.QUERY_SERVICE:
            return self._query_service(action.target_service)
        
        elif action.action_type == ActionType.QUERY_METRICS:
            return self._query_metrics(action.target_service)
        
        elif action.action_type == ActionType.QUERY_LOGS:
            return self._query_logs(action.target_service)
        
        elif action.action_type == ActionType.QUERY_DEPENDENCIES:
            return self._query_dependencies(action.target_service)
        
        elif action.action_type == ActionType.QUERY_DEPLOYMENTS:
            return self._query_deployments()
        
        elif action.action_type == ActionType.RESTART_SERVICE:
            return self._restart_service(action.target_service)
        
        elif action.action_type == ActionType.SCALE_SERVICE:
            return self._scale_service(action.target_service)
        
        elif action.action_type == ActionType.ROLLBACK_DEPLOYMENT:
            return self._rollback_deployment(action.target_service)
        
        elif action.action_type == ActionType.QUERY_MEMORY:
            return self._query_memory(action.parameters)
        
        elif action.action_type == ActionType.IDENTIFY_ROOT_CAUSE:
            return self._identify_root_cause(action.target_service)
        
        elif action.action_type == ActionType.APPLY_FIX:
            return self._apply_fix(action.target_service)
        
        return {"error": f"Unknown action type: {action.action_type}"}  # pragma: no cover
    
    def _query_service(self, service: Optional[str]) -> dict:
        """Query service status"""
        if not service:
            return {"error": "target_service required"}  # pragma: no cover

        if service not in self.services:
            return {"error": f"Service {service} not found"}  # pragma: no cover
        
        first_observation = service not in self._observed_services
        self._observed_services.add(service)

        return {
            "service": service,
            "state": self.services[service],
            "first_observation": first_observation,
        }
    
    def _query_metrics(self, service: Optional[str]) -> dict:
        """Query service metrics with noise"""
        if not service:
            return {"error": "target_service required"}  # pragma: no cover

        if not self.simulator:
            return {"error": "No active scenario"}  # pragma: no cover
        
        # Mark as observed
        self._observed_metrics.add(service)
        
        # Get metrics with noise enabled
        metrics = self.simulator.get_metrics(
            service,
            apply_noise=self.config.enable_metric_noise
        )

        # Task 5 memory spiral: inject step-dependent memory growth for analytics-service.
        # The leak is ~4% per step starting at 45%, OOM at ~step 18.
        # Only obvious after 3+ queries — reward calculator handles trend detection.
        if (service == "analytics-service" and
                self.current_scenario and
                self.current_scenario.is_memory_leak):
            leak_progress = self._memory_leak_step
            memory_pct = min(45.0 + leak_progress * 4.0, 99.0)
            metrics["memory_percent"] = round(memory_pct, 2)
            if memory_pct >= 90.0:
                metrics["memory_percent"] = 99.0
        
        # Add metadata about lag
        return {
            "service": service,
            "metrics": metrics,
            "metric_lag_applied": self.config.enable_metric_noise,
            "current_step": self.current_step,
        }
    
    def _query_logs(self, service: Optional[str]) -> dict:
        """Query service logs with noise and partial observability"""
        if not service:
            return {"error": "target_service required"}  # pragma: no cover

        if not self.simulator:
            return {"error": "No active scenario"}  # pragma: no cover
        
        # Mark as observed
        was_hidden = service not in self._observed_logs
        self._observed_logs.add(service)
        
        # Get logs with noise enabled
        logs = self.simulator.get_logs(
            service,
            apply_noise=self.config.enable_log_noise
        )
        
        return {
            "service": service,
            "logs": logs,
            "was_hidden": was_hidden,
            "noise_applied": self.config.enable_log_noise,
        }
    
    def _query_dependencies(self, service: Optional[str]) -> dict:
        """Query service dependencies"""
        deps = DependencyPropagator.DEPENDENCY_GRAPH
        reverse_deps = DependencyPropagator.REVERSE_DEPENDENCY_GRAPH
        
        if service:
            return {
                "service": service,
                "depends_on": deps.get(service, []),
                "depended_by": reverse_deps.get(service, []),
            }
        
        return {
            "dependencies": deps,
            "reverse_dependencies": reverse_deps,
        }
    
    def _query_deployments(self) -> dict:
        """Query deployment timeline"""
        if not self.simulator:
            return {"error": "No active scenario"}  # pragma: no cover
        
        return {
            "deployments": self.simulator.get_deploy_timeline(),
        }
    
    def _restart_service(self, service: Optional[str]) -> dict:
        """Restart a service"""
        if not service:
            return {"error": "target_service required"}  # pragma: no cover

        if service not in self.services:
            return {"error": f"Service {service} not found"}  # pragma: no cover
        
        is_correct = (
            self.current_scenario and
            service == self.current_scenario.root_cause_service and
            self.current_scenario.correct_fix.startswith("restart_service")
        )
        
        if is_correct:
            self._apply_correct_fix(service)
        
        return {
            "action": "restart",
            "service": service,
            "success": True,
            "fix_correct": is_correct,
        }
    
    def _scale_service(self, service: Optional[str]) -> dict:
        """Scale a service"""
        if not service:
            return {"error": "target_service required"}  # pragma: no cover

        is_correct = (
            self.current_scenario and
            service == self.current_scenario.root_cause_service and
            "scale_service" in self.current_scenario.correct_fix
        )

        if is_correct:
            self._apply_correct_fix(service)

        return {
            "action": "scale",
            "service": service,
            "success": True,
            "new_replicas": 3,
            "fix_correct": is_correct,
        }
    
    def _rollback_deployment(self, service: Optional[str]) -> dict:
        """Rollback a service deployment"""
        if not service:
            return {"error": "target_service required"}  # pragma: no cover
        
        is_correct = (
            self.current_scenario and
            service == self.current_scenario.root_cause_service and
            "rollback" in self.current_scenario.correct_fix
        )
        
        if is_correct:
            self._apply_correct_fix(service)
        
        return {
            "action": "rollback",
            "service": service,
            "success": True,
            "previous_version": "v2.0.0",
            "fix_correct": is_correct,
        }
    
    def _query_memory(self, parameters: dict) -> dict:
        """Query incident memory"""
        if not self.memory:
            return {"error": "Memory system disabled"}  # pragma: no cover
        
        self.memory_used_this_step = True
        
        symptoms = parameters.get("symptoms", [])
        services = parameters.get("services", [])
        query = parameters.get("query", "")
        
        matches = self.memory.get_similar_incidents(symptoms, services)
        
        return {
            "similar_incidents": matches,
            "query": query,
        }
    
    def _identify_root_cause(self, service: Optional[str]) -> dict:
        """Identify root cause service"""
        if not service:
            return {"error": "target_service required"}  # pragma: no cover
        
        is_correct = (
            self.current_scenario and
            service == self.current_scenario.root_cause_service
        )
        
        if is_correct:
            self.root_cause_identified = True
        
        return {
            "action": "identify_root_cause",
            "service": service,
            "correct": is_correct,
        }
    
    def _apply_fix(self, service: Optional[str]) -> dict:
        """Apply fix to service"""
        if not service:
            return {"error": "target_service required"}  # pragma: no cover
        
        is_correct = (
            self.current_scenario and
            service == self.current_scenario.root_cause_service
        )
        
        if is_correct:
            self._apply_correct_fix(service)
        
        return {
            "action": "apply_fix",
            "service": service,
            "success": True,
            "fix_correct": is_correct,
        }
    
    def _apply_correct_fix(self, service: str) -> None:
        """Apply correct fix with propagation recovery"""
        self.fix_applied = True
        
        # Use propagation system for recovery
        if self.simulator and self.config.enable_propagation:
            self.services = self.simulator.propagate_recovery(service, self.services)
        else:
            # Simple recovery without propagation
            for svc in self.services:
                self.services[svc] = {
                    "status": ServiceStatus.HEALTHY.value,
                    "latency_ms": 30,
                    "error_rate": 0.001,
                    "cpu_percent": 30,
                    "memory_percent": 50,
                }
    
    # === Helper Methods ===
    
    def _get_observation(self) -> dict:
        """Build observation dict with SLO/SLI metrics and business impact"""
        slo_metrics = self._calculate_slo_metrics()
        business_impact = self._calculate_business_impact()
        sla_deadline = self._get_sla_deadline()
        return {
            "step": self.current_step,
            "services": self.services,
            "alerts": self._get_alerts(),
            "incident_info": {
                "fault_type": self.current_scenario.fault_type.value if self.current_scenario else None,
                "difficulty": self.current_scenario.difficulty if self.current_scenario else None,
            },
            "fix_applied": self.fix_applied,
            "observability": {
                "observed_services": len(self._observed_services),
                "observed_logs": len(self._observed_logs),
                "observed_metrics": len(self._observed_metrics),
            },
            # SLO/SLI metrics — new in v14 for real-world utility scoring
            "slo_metrics": slo_metrics,
            "business_impact": business_impact,
            "sla_deadline": sla_deadline,
        }

    def _calculate_slo_metrics(self) -> dict:
        """Calculate current SLO/SLI metrics based on service health"""
        total_services = len(self.services)
        healthy = sum(1 for s in self.services.values() if s.get("status") == "healthy")
        degraded = sum(1 for s in self.services.values() if s.get("status") == "degraded")
        unhealthy = sum(1 for s in self.services.values() if s.get("status") == "unhealthy")

        # Availability SLI (percentage of healthy services)
        availability = (healthy / total_services * 100) if total_services > 0 else 100.0

        # Latency SLI (p99 latency across all services)
        latencies = [s.get("latency_ms", 30) for s in self.services.values()]
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 30.0
        latency_slo_threshold = 500.0  # 500ms p99 SLA target
        latency_slo_met = p99_latency <= latency_slo_threshold

        # Error rate SLI
        error_rates = [s.get("error_rate", 0.001) for s in self.services.values()]
        avg_error_rate = sum(error_rates) / len(error_rates) if error_rates else 0.001
        error_slo_threshold = 0.01  # 1% error rate SLA
        error_slo_met = avg_error_rate <= error_slo_threshold

        # Error budget (monthly, per SLO: 99.9% availability = 43.8min downtime)
        monthly_error_budget = 43.8  # minutes
        # Burn rate proportional to steps taken / max steps with degraded health
        burn_rate = (degraded * 0.1 + unhealthy * 0.5) / total_services
        steps_elapsed = self.current_step
        max_steps = 50
        elapsed_pct = steps_elapsed / max_steps
        error_budget_burned = burn_rate * elapsed_pct * 100  # percentage of budget
        error_budget_remaining = max(0, 100 - error_budget_burned)

        return {
            "availability_percent": round(availability, 2),
            "latency_p99_ms": round(p99_latency, 1),
            "latency_slo_met": latency_slo_met,
            "error_rate_percent": round(avg_error_rate * 100, 3),
            "error_slo_met": error_slo_met,
            "error_budget_remaining_percent": round(error_budget_remaining, 1),
            "healthy_services": healthy,
            "degraded_services": degraded,
            "unhealthy_services": unhealthy,
        }

    def _calculate_business_impact(self) -> dict:
        """Calculate business impact metrics based on service health and fault"""
        total_revenue_loss = 0.0
        affected_users = 0
        impacted_services = []

        for svc, state in self.services.items():
            status = state.get("status", "healthy")
            revenue_per_min = SERVICE_REVENUE_MAP.get(svc, 500)

            if status == "unhealthy":
                # Complete outage: lose all revenue
                total_revenue_loss += revenue_per_min
                affected_users += self.rng.randint(1000, 5000) if svc != "database-replica" else 0
                impacted_services.append(svc)
            elif status == "degraded":
                # Degraded: lose 50% revenue
                total_revenue_loss += revenue_per_min * 0.5
                affected_users += self.rng.randint(200, 1000) if svc != "database-replica" else 0
                impacted_services.append(svc)

        # Cumulative loss based on steps elapsed
        steps_elapsed = self.current_step
        minutes_elapsed = steps_elapsed / STEPS_PER_MINUTE
        cumulative_revenue_loss = total_revenue_loss * minutes_elapsed

        return {
            "revenue_loss_per_minute_usd": total_revenue_loss,
            "cumulative_revenue_loss_usd": round(cumulative_revenue_loss, 2),
            "affected_users_estimate": affected_users,
            "impacted_services": impacted_services,
            "severity": "critical" if any(self.services.get(s, {}).get("status") == "unhealthy" for s in impacted_services) else "warning",
        }

    def _get_sla_deadline(self) -> dict:
        """Calculate SLA deadline countdown"""
        fault_type = self.current_scenario.fault_type.value if self.current_scenario else "oom"
        sla_minutes = SLA_MINUTES.get(fault_type, 10)

        steps_elapsed = self.current_step
        minutes_elapsed = steps_elapsed / STEPS_PER_MINUTE
        minutes_remaining = max(0, sla_minutes - minutes_elapsed)
        urgency = "normal" if minutes_remaining > sla_minutes * 0.5 else "elevated" if minutes_remaining > sla_minutes * 0.2 else "critical"
        breached = minutes_remaining <= 0

        return {
            "sla_minutes": sla_minutes,
            "minutes_remaining": round(minutes_remaining, 1),
            "urgency": urgency,
            "sla_breached": breached,
            "sla_target_minutes": sla_minutes,
        }

    def _get_sla_max_steps(self) -> int:
        """Get effective max_steps based on SLA for the current fault type.

        Each fault type has a SLA time limit (in minutes). We convert to steps:
        5 steps per minute of simulation time. The effective max_steps is the
        MINIMUM of the configured max_steps and the SLA-based max_steps,
        ensuring SLA deadlines are enforced even when max_steps is generous.
        """
        fault_type = self.current_scenario.fault_type.value if self.current_scenario else "oom"
        sla_minutes = SLA_MINUTES.get(fault_type, 10)
        sla_max_steps = sla_minutes * STEPS_PER_MINUTE

        # Use the tighter of the two constraints
        return min(self.config.max_steps, sla_max_steps)

    def _get_alerts(self) -> list[dict]:
        """Generate alerts based on current state + decoy alerts for misleading."""
        alerts = []

        # Ghost scenario alert
        if self.current_scenario and self.current_scenario.fault_type.value == "ghost":
            alerts.append({
                "service": self.current_scenario.root_cause_service,
                "severity": "info",
                "message": "Business metric degradation detected: CTR dropping across user-facing services"
            })

        for service, state in self.services.items():
            status = state.get("status", "healthy")
            if status == "unhealthy":
                alerts.append({
                    "service": service,
                    "severity": "critical",
                    "message": f"Service {service} is unhealthy",
                })
            elif status == "degraded":
                alerts.append({
                    "service": service,
                    "severity": "warning",
                    "message": f"Service {service} is degraded",
                })

        # Inject decoy alerts (difficulty-aware misleading signals).
        # These are NOT backed by actual service state — they mislead rule-based agents.
        if self.current_scenario and self.current_scenario.decoy_alerts:
            for decoy in self.current_scenario.decoy_alerts:
                # Only inject decoy alerts if difficulty >= 3 (easy/medium keep it cleaner)
                if self.current_scenario.difficulty >= 3:
                    alerts.append(decoy)

        return alerts
    
    def _check_termination(self, action: AgentAction) -> None:
        """Check if episode should terminate"""
        if self.fix_applied:
            self.terminated = True
        # SLA breach — time ran out before fixing
        sla = self._get_sla_deadline()
        if sla.get("sla_breached"):
            self.truncated = True
    
    def _build_info(self, reward_breakdown: RewardBreakdown) -> dict:
        """Build info dict for step response"""
        info = {
            "reward_breakdown": {
                "health_improvement": reward_breakdown.health_improvement,
                "latency_improvement": reward_breakdown.latency_improvement,
                "correct_investigation": reward_breakdown.correct_investigation,
                "root_cause_identified": reward_breakdown.root_cause_identified,
                "correct_fix": reward_breakdown.correct_fix,
                "minimal_actions": reward_breakdown.minimal_actions,
                "unnecessary_restart_penalty": reward_breakdown.unnecessary_restart_penalty,
                "redundant_query_penalty": reward_breakdown.redundant_query_penalty,
                "random_action_penalty": reward_breakdown.random_action_penalty,
                "memory_usage_bonus": reward_breakdown.memory_usage_bonus,
                "total": reward_breakdown.total,
            },
            "episode": {
                "total_steps": self.current_step,
                "total_reward": sum(self.episode_rewards),
            },
            "noise_applied": {
                "log_noise": self.config.enable_log_noise,
                "metric_noise": self.config.enable_metric_noise,
                "partial_observability": self.config.enable_partial_observability,
                "propagation": self.config.enable_propagation,
            },
            "slo_metrics": self._calculate_slo_metrics(),
            "business_impact": self._calculate_business_impact(),
            "sla_deadline": self._get_sla_deadline(),
        }
        
        if self.current_scenario:
            info["scenario"] = {
                "fault_type": self.current_scenario.fault_type.value,
                "root_cause": self.current_scenario.root_cause_service,
                "difficulty": self.current_scenario.difficulty,
            }
            
            # Add propagation info
            if self.simulator:
                info["propagation"] = self.simulator.propagator.get_propagation_info()
        
        return info
    
    # === Utility Methods ===
    
    def get_action_space(self) -> list[str]:
        """Get list of valid actions"""
        return [a.value for a in ActionType]
    
    def get_service_list(self) -> list[str]:
        """Get list of valid services"""
        return list(VALID_SERVICES)
    
    def get_episode_summary(self) -> dict:
        """Get summary of completed episode"""
        return {
            "total_steps": self.current_step,
            "total_reward": sum(self.episode_rewards),
            "avg_reward": sum(self.episode_rewards) / max(len(self.episode_rewards), 1),
            "terminated": self.terminated,
            "truncated": self.truncated,
            "fix_applied": self.fix_applied,
            "root_cause_identified": self.root_cause_identified,
            "actions": self.episode_actions,
            "observability": {
                "services_observed": len(self._observed_services),
                "logs_observed": len(self._observed_logs),
                "metrics_observed": len(self._observed_metrics),
            },
        }
    
    def get_dependency_graph(self) -> dict:
        """Get the full dependency graph"""
        return {
            "dependencies": DependencyPropagator.DEPENDENCY_GRAPH,
            "reverse_dependencies": DependencyPropagator.REVERSE_DEPENDENCY_GRAPH,
        }


# Factory function
def make_env(
    seed: int = 42,
    fault_type: Optional[FaultType] = None,
    difficulty: int = 3,
    max_steps: int = 50,
    enable_noise: bool = True,
) -> IncidentEnv:
    """Create an incident response environment"""
    config = EnvironmentConfig(
        seed=seed,
        fault_type=fault_type,
        difficulty=difficulty,
        max_steps=max_steps,
        enable_log_noise=enable_noise,
        enable_metric_noise=enable_noise,
        enable_partial_observability=enable_noise,
        enable_propagation=True,
    )
    return IncidentEnv(config)
