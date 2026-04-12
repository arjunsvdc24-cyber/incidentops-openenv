from typing import Any
"""
IncidentOps - Dense Reward Function for Maximum Learning Signal

This module implements a comprehensive reward system designed to provide
continuous feedback signals at every step, enabling smooth gradient
descent during RL training.

Reward Philosophy:
- Dense rewards at every step (not just at episode end)
- Positive signals for progress toward solution
- Negative signals for inefficient or harmful actions
- Smooth gradients to guide learning
"""
from dataclasses import dataclass, field
from app.models import ActionType, RewardBreakdown


@dataclass
class RewardConfig:
    """Configuration for reward weights"""
    # === Continuous Progress Rewards ===
    # System health improvement: scaled by error reduction
    health_improvement_weight: float = 2.5

    # Latency improvement: direct scale (ms)
    latency_improvement_weight: float = 1.0

    # Correct investigation: querying relevant service (granular by type)
    investigation_service_reward: float = 0.03
    investigation_metrics_reward: float = 0.05
    investigation_logs_reward: float = 0.04
    investigation_dependencies_reward: float = 0.04
    investigation_deployments_reward: float = 0.05  # Valuable for ghost/deployment faults

    # Root cause identification (tiered)
    root_cause_reward: float = 0.3
    root_cause_attempted_reward: float = 0.1  # Investigated correct service

    # Correct fix applied (tiered)
    correct_fix_reward: float = 0.4
    partial_fix_reward: float = 0.2  # Right service, wrong action type
    wrong_service_attempt: float = 0.05  # Made an attempt (for encouragement)

    # Minimal actions bonus (efficiency)
    minimal_actions_bonus: float = 0.15

    # Time bonus: reward for fast resolution
    time_bonus_per_step_saved: float = 0.03  # Bonus per step under SLO budget

    # Investigation thoroughness bonus
    thorough_investigation_bonus: float = 0.1  # For querying both metrics and logs

    # Memory usage bonus
    memory_usage_bonus: float = 0.05

    # === Penalties ===
    # Unnecessary restart (service not actually faulty)
    unnecessary_restart_penalty: float = -0.1

    # Redundant query (asking same thing again)
    redundant_query_penalty: float = -0.05

    # Random/irrelevant action
    random_action_penalty: float = -0.02

    # Wrong service fix penalty
    wrong_service_fix_penalty: float = -0.08

    # === Thresholds ===
    # SLO budget by difficulty (steps)
    slo_budget_by_difficulty: dict = field(default_factory=lambda: {
        1: 5, 2: 8, 3: 12, 4: 18, 5: 25
    })

    # Steps considered "minimal" for bonus
    minimal_steps_threshold: int = 15

    # Error rate considered "healthy"
    healthy_error_rate: float = 0.01

    # Latency considered "acceptable" (ms)
    acceptable_latency_ms: float = 100.0


class RewardCalculator:
    """
    Calculates dense rewards for incident response actions.
    
    Design Principles:
    1. Every step produces a reward signal
    2. Rewards form smooth gradients toward solution
    3. Partial credit for progress, not just completion
    4. Penalties guide away from inefficient behaviors
    """
    
    def __init__(self, config: RewardConfig | None = None):
        self.config = config or RewardConfig()

        # Track previous state for improvement calculations
        self.prev_total_error_rate: float = 0.0
        self.prev_avg_latency: float = 0.0

        # Track action history for redundant detection
        self.action_history: list[dict] = []
        self.query_count: dict[str, int] = {}

        # Track investigation progress
        self.queried_services: set[str] = set()
        self.queried_metrics_on_root: bool = False
        self.queried_logs_on_root: bool = False
        self.identified_root_cause: bool = False
        self.applied_correct_fix: bool = False

        # Track time/efficiency
        self.current_step: int = 0
        self.difficulty: int = 3

        # Fault information (set by environment)
        self.fault_root_cause: str | None = None
        self.fault_affected_services: set[str] = set()
        self.fault_type: str | None = None

    def set_fault_info(
        self,
        root_cause: str,
        affected_services: set[str],
        fault_type: str | None = None,
        difficulty: int = 3
    ) -> None:
        """Set fault information for reward calculation"""
        self.fault_root_cause = root_cause
        self.fault_affected_services = affected_services
        self.fault_type = fault_type
        self.difficulty = difficulty

    def reset(self) -> None:
        """Reset state for new episode"""
        self.prev_total_error_rate = 0.0
        self.prev_avg_latency = 0.0
        self.action_history = []
        self.query_count = {}
        self.queried_services = set()
        self.queried_metrics_on_root = False
        self.queried_logs_on_root = False
        self.identified_root_cause = False
        self.applied_correct_fix = False
        self.current_step = 0
        self.difficulty = 3
        self.fault_root_cause = None
        self.fault_affected_services = set()
        self.fault_type = None
    
    def calculate_step_reward(
        self,
        action_type: str,
        target_service: str | None,
        current_services: dict,
        is_terminated: bool = False,
        used_memory: bool = False,
    ) -> RewardBreakdown:
        """
        Calculate reward for a single step with granular signals.

        Args:
            action_type: The action taken
            target_service: Target service for the action
            current_services: Current service states
            is_terminated: Whether episode is ending
            used_memory: Whether memory was consulted

        Returns:
            RewardBreakdown with detailed reward components
        """
        breakdown = RewardBreakdown()

        # 1. Calculate system health improvement
        current_total_error = self._calculate_total_error_rate(current_services)
        health_delta = self.prev_total_error_rate - current_total_error
        breakdown.health_improvement = health_delta * self.config.health_improvement_weight
        self.prev_total_error_rate = current_total_error

        # 2. Calculate latency improvement
        current_avg_latency = self._calculate_avg_latency(current_services)
        latency_delta = self.prev_avg_latency - current_avg_latency
        breakdown.latency_improvement = latency_delta * self.config.latency_improvement_weight / 100.0
        self.prev_avg_latency = current_avg_latency

        # 3. Granular investigation rewards
        if target_service and self._is_relevant_service(target_service):
            query_key = f"{action_type}:{target_service}"
            if query_key not in self.query_count or self.query_count[query_key] == 0:
                # First time querying this service with this action
                if action_type == ActionType.QUERY_METRICS.value:
                    breakdown.correct_investigation = self.config.investigation_metrics_reward
                    if target_service == self.fault_root_cause:
                        self.queried_metrics_on_root = True
                elif action_type == ActionType.QUERY_LOGS.value:
                    breakdown.correct_investigation = self.config.investigation_logs_reward
                    if target_service == self.fault_root_cause:
                        self.queried_logs_on_root = True
                elif action_type == ActionType.QUERY_SERVICE.value:
                    breakdown.correct_investigation = self.config.investigation_service_reward
                elif action_type == ActionType.QUERY_DEPENDENCIES.value:
                    breakdown.correct_investigation = self.config.investigation_dependencies_reward
                elif action_type == ActionType.QUERY_DEPLOYMENTS.value:
                    breakdown.correct_investigation = self.config.investigation_deployments_reward

                self.queried_services.add(target_service)

        # 4. Root cause identification reward (tiered)
        if action_type == ActionType.IDENTIFY_ROOT_CAUSE.value:
            if target_service == self.fault_root_cause and not self.identified_root_cause:
                breakdown.root_cause_identified = self.config.root_cause_reward
                self.identified_root_cause = True
            elif target_service != self.fault_root_cause:
                # Attempted identification but wrong — small negative
                breakdown.root_cause_identified = -0.05
        elif (target_service == self.fault_root_cause and
              action_type.startswith("query_") and
              not self.identified_root_cause):
            # Partial credit: investigated the right service
            breakdown.root_cause_identified = self.config.root_cause_attempted_reward

        # 5. Fix reward (tiered)
        if action_type in (ActionType.RESTART_SERVICE.value, ActionType.SCALE_SERVICE.value,
                           ActionType.ROLLBACK_DEPLOYMENT.value, ActionType.APPLY_FIX.value):
            if self._is_correct_fix(target_service, action_type):
                breakdown.correct_fix = self.config.correct_fix_reward
                self.applied_correct_fix = True
            elif target_service == self.fault_root_cause:
                # Right service, wrong action type
                breakdown.correct_fix = self.config.partial_fix_reward
            else:
                # Wrong service attempt
                breakdown.correct_fix = self.config.wrong_service_attempt

        # 6. Investigation thoroughness bonus
        if (self.queried_metrics_on_root and self.queried_logs_on_root and
                not hasattr(self, '_thorough_bonus_applied')):
            breakdown.correct_investigation += self.config.thorough_investigation_bonus
            self._thorough_bonus_applied = True  # type: ignore[attr-defined]

        # 7. Memory usage bonus
        if used_memory:
            breakdown.memory_usage_bonus = self.config.memory_usage_bonus

        # 8. Apply penalties
        self._apply_penalties(breakdown, action_type, target_service)

        # 9. Time bonus for fast resolution at termination
        if is_terminated and self.applied_correct_fix:
            slo_budget = self.config.slo_budget_by_difficulty.get(self.difficulty, 12)
            steps_taken = len(self.action_history)
            if steps_taken < slo_budget:
                steps_saved = slo_budget - steps_taken
                breakdown.correct_fix += steps_saved * self.config.time_bonus_per_step_saved

        # 10. Minimal actions bonus at termination
        if is_terminated:
            steps = len(self.action_history)
            if steps <= self.config.minimal_steps_threshold:
                efficiency_ratio = 1.0 - (steps / self.config.minimal_steps_threshold)
                breakdown.minimal_actions = self.config.minimal_actions_bonus * efficiency_ratio

        # Calculate total
        breakdown.total = (
            breakdown.health_improvement +
            breakdown.latency_improvement +
            breakdown.correct_investigation +
            breakdown.root_cause_identified +
            breakdown.correct_fix +
            breakdown.minimal_actions +
            breakdown.memory_usage_bonus +
            breakdown.unnecessary_restart_penalty +
            breakdown.redundant_query_penalty +
            breakdown.random_action_penalty
        )

        # Clamp total to reasonable range
        breakdown.total = max(-1.0, min(2.0, breakdown.total))

        # Record action in history
        self._record_action(action_type, target_service)
        self.current_step += 1

        return breakdown
    
    def _calculate_total_error_rate(self, services: dict) -> float:
        """Calculate total error rate across all services"""
        if not services:
            return 0.0
        return sum(s.get("error_rate", 0) for s in services.values())
    
    def _calculate_avg_latency(self, services: dict) -> float:
        """Calculate average latency across all services"""
        if not services:
            return 0.0
        latencies = [s.get("latency_ms", 0) for s in services.values()]
        return sum(latencies) / len(latencies) if latencies else 0.0
    
    def _is_relevant_service(self, service: str) -> bool:
        """Check if service is relevant to the fault"""
        if self.fault_root_cause and service == self.fault_root_cause:
            return True
        if service in self.fault_affected_services:
            return True
        return False
    
    def _is_correct_fix(self, target_service: str | None, action_type: str) -> bool:
        """Check if the fix targets the root cause with the correct action type"""
        if not target_service or not self.fault_root_cause:
            return False
        if target_service != self.fault_root_cause:
            return False
        # Verify action type matches fault type
        if self.fault_type == "ghost":
            return action_type == ActionType.ROLLBACK_DEPLOYMENT.value
        elif self.fault_type in ("cascade", "network"):
            return action_type == ActionType.SCALE_SERVICE.value
        else:
            return action_type == ActionType.RESTART_SERVICE.value
    
    def _apply_penalties(
        self,
        breakdown: RewardBreakdown,
        action_type: str,
        target_service: str | None
    ) -> None:
        """Apply penalties for suboptimal actions"""

        # 1. Unnecessary restart penalty (restarting a healthy service)
        if action_type == ActionType.RESTART_SERVICE.value:
            if target_service and not self._is_relevant_service(target_service):
                breakdown.unnecessary_restart_penalty = self.config.unnecessary_restart_penalty

        # 2. Redundant query penalty
        if action_type in (
            ActionType.QUERY_SERVICE.value,
            ActionType.QUERY_METRICS.value,
            ActionType.QUERY_LOGS.value,
            ActionType.QUERY_DEPENDENCIES.value,
            ActionType.QUERY_DEPLOYMENTS.value,
        ):
            query_key = f"{action_type}:{target_service}"
            self.query_count[query_key] = self.query_count.get(query_key, 0) + 1
            if self.query_count[query_key] > 1:
                breakdown.redundant_query_penalty = self.config.redundant_query_penalty

        # 3. Wrong service fix penalty
        if action_type in (ActionType.RESTART_SERVICE.value, ActionType.SCALE_SERVICE.value,
                           ActionType.ROLLBACK_DEPLOYMENT.value, ActionType.APPLY_FIX.value):
            if target_service and target_service != self.fault_root_cause:
                # Penalize fixing wrong service (unless we already got partial credit)
                if breakdown.correct_fix <= 0.05:  # pragma: no cover
                    breakdown.random_action_penalty = max(
                        breakdown.random_action_penalty,
                        self.config.wrong_service_fix_penalty
                    )

        # 4. Random action penalty (escalation without investigation)
        if self._is_random_action(action_type, target_service):
            breakdown.random_action_penalty = self.config.random_action_penalty
    
    def _is_random_action(self, action_type: str, target_service: str | None) -> bool:
        """Detect if an action appears random or irrelevant"""
        # Scale without reason (service not overloaded)
        if action_type == ActionType.SCALE_SERVICE.value:
            # Could check if service actually needs scaling
            pass  # Requires more context
        
        # Rollback wrong service
        if action_type == ActionType.ROLLBACK_DEPLOYMENT.value:
            if target_service and not self._is_relevant_service(target_service):
                return True
        
        return False
    
    def _record_action(self, action_type: str, target_service: str | None) -> None:
        """Record action in history"""
        self.action_history.append({
            "action_type": action_type,
            "target_service": target_service,
        })


class ProgressiveRewardShaping:
    """
    Curriculum-style reward shaping for progressive learning.
    
    As the agent improves, the reward function can be adjusted:
    - Early training: More guidance, larger partial rewards
    - Later training: Sparser rewards, focus on efficiency
    """
    
    def __init__(
        self,
        reward_calculator: RewardCalculator,
        curriculum_stage: int = 0
    ):
        self.calculator = reward_calculator
        self.curriculum_stage = curriculum_stage
        self.stage_thresholds = [0, 10, 50, 100, 200]
    
    def advance_stage(self, episode_count: int) -> None:
        """Advance curriculum stage based on episode count"""
        for i, threshold in enumerate(self.stage_thresholds):
            if episode_count >= threshold:
                self.curriculum_stage = i
    
    def get_shaped_reward(
        self,
        base_reward: float,
        breakdown: RewardBreakdown
    ) -> float:
        """
        Apply curriculum-based shaping to the reward.
        
        Stage 0: Full guidance (all rewards visible)
        Stage 1: Reduce partial rewards by 10%
        Stage 2: Reduce partial rewards by 25%
        Stage 3: Reduce partial rewards by 50%
        Stage 4: Sparse rewards (only termination rewards)
        """
        if self.curriculum_stage == 0:
            return base_reward
        
        reduction_factors = [0.0, 0.1, 0.25, 0.5, 0.75]
        reduction = reduction_factors[min(self.curriculum_stage, len(reduction_factors) - 1)]
        
        # Reduce partial credit rewards
        partial_rewards = (
            breakdown.health_improvement +
            breakdown.latency_improvement +
            breakdown.correct_investigation
        )
        
        shaped_partial = partial_rewards * (1.0 - reduction)
        
        # Keep full rewards for achievements
        achievement_rewards = (
            breakdown.root_cause_identified +
            breakdown.correct_fix +
            breakdown.minimal_actions
        )
        
        # Full penalties
        penalties = (
            breakdown.unnecessary_restart_penalty +
            breakdown.redundant_query_penalty +
            breakdown.random_action_penalty
        )
        
        return shaped_partial + achievement_rewards + penalties


def create_default_reward_calculator() -> RewardCalculator:
    """Factory function to create a reward calculator with defaults"""
    return RewardCalculator(RewardConfig())
