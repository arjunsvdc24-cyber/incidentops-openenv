"""
IncidentOps - Reasoning-Quality Reward Function v12.0

Enhanced to reflect reasoning quality, not just final outcome.

Rewards:
- +0.1 for correct dependency tracing
- +0.1 for identifying misleading signal
- +0.1 for correlating deploy timeline
- +0.05 for querying correct service
- +0.3 for correct root cause
- +0.3 for correct fix
- +0.1 for correct memory usage

Penalties:
- -0.1 incorrect root cause assumption
- -0.05 ignoring key signals
- -0.05 actions without new info
"""
from dataclasses import dataclass, field
from typing import Optional, Set, List, Dict
from enum import Enum


class ReasoningAction(str, Enum):
    """Types of reasoning actions"""
    DEPENDENCY_TRACE = "dependency_trace"
    MISLEADING_SIGNAL_IDENTIFIED = "misleading_signal_identified"
    DEPLOY_CORRELATION = "deploy_correlation"
    CORRECT_SERVICE_QUERY = "correct_service_query"
    KEY_SIGNAL_IGNORED = "key_signal_ignored"
    INCORRECT_ASSUMPTION = "incorrect_assumption"


@dataclass
class ReasoningRewardBreakdown:
    """Complete breakdown of reasoning-based rewards"""
    # Reasoning rewards
    dependency_trace_reward: float = 0.0
    misleading_signal_reward: float = 0.0
    deploy_correlation_reward: float = 0.0
    correct_service_query_reward: float = 0.0
    
    # Outcome rewards
    root_cause_correct: float = 0.0
    fix_correct: float = 0.0
    memory_usage_reward: float = 0.0
    
    # Penalties
    incorrect_assumption_penalty: float = 0.0
    key_signal_ignored_penalty: float = 0.0
    no_new_info_penalty: float = 0.0
    brute_force_penalty: float = 0.0
    
    # Totals
    reasoning_total: float = 0.0
    outcome_total: float = 0.0
    penalty_total: float = 0.0
    final_reward: float = 0.0
    
    # Quality metrics
    reasoning_quality_score: float = 0.0
    decision_quality_score: float = 0.0
    
    # Debug
    reasoning_steps: List[str] = field(default_factory=list)
    decisions_made: List[str] = field(default_factory=list)


@dataclass
class ReasoningWeights:
    """Weights for reasoning rewards"""
    # Reasoning (0.35 total)
    dependency_trace: float = 0.1
    misleading_signal_identified: float = 0.1
    deploy_correlation: float = 0.1
    correct_service_query: float = 0.05
    
    # Outcome (0.65 total)
    root_cause_correct: float = 0.3
    fix_correct: float = 0.3
    memory_usage: float = 0.1
    
    # Penalties
    incorrect_assumption: float = 0.1
    key_signal_ignored: float = 0.05
    no_new_info: float = 0.05


class ReasoningRewardCalculator:
    """
    Calculates rewards based on reasoning quality.
    
    Philosophy: Good reasoning should be rewarded even if
    the final outcome is not perfect. Conversely, correct
    outcomes without proper reasoning should be discounted.
    """
    
    def __init__(self, weights: Optional[ReasoningWeights] = None, seed: int = 42):
        self.weights = weights or ReasoningWeights()
        self.seed = seed
        self.reset()
    
    def reset(self) -> None:
        """Reset for new episode"""
        self.dependency_traces: List[tuple] = []
        self.misleading_signals_identified: List[str] = []
        self.deploy_correlations: List[dict] = []
        self.correct_queries: List[str] = []
        self.incorrect_assumptions: List[str] = []
        self.ignored_signals: List[str] = []
        self.key_signals: Set[str] = set()
        
        self.root_cause_attempts: List[str] = []
        self.fix_attempts: List[tuple] = []
        
        self.memory_used_correctly: bool = False
        self.correct_root_cause_identified: bool = False
        self.correct_fix_applied: bool = False
        
        # Fault context
        self.actual_root_cause: Optional[str] = None
        self.affected_services: Set[str] = set()
        self.misleading_services: Set[str] = set()
    
    def set_fault_context(
        self,
        root_cause: str,
        affected: Set[str],
        misleading: Optional[Set[str]] = None
    ) -> None:
        """Set fault context"""
        self.actual_root_cause = root_cause
        self.affected_services = affected
        self.misleading_services = misleading or set()
        self.key_signals = {root_cause} | affected
    
    def set_key_signals(self, signals: List[str]) -> None:
        """Set signals that should not be ignored"""
        self.key_signals = set(signals)
    
    def record_dependency_trace(
        self,
        from_service: str,
        to_service: str,
        is_correct: bool
    ) -> float:
        """
        Record a dependency trace action.
        
        Returns reward for this action.
        """
        trace = (from_service, to_service, is_correct)
        
        # Check if this is a new trace
        if trace not in self.dependency_traces:
            self.dependency_traces.append(trace)
            
            if is_correct:
                return self.weights.dependency_trace
        
        return 0.0
    
    def record_misleading_signal_identified(
        self,
        signal_description: str,
        correct_interpretation: str
    ) -> float:
        """
        Record identification of a misleading signal.
        
        Agent must correctly identify that a signal is misleading.
        """
        key = f"{signal_description}:{correct_interpretation}"
        
        if key not in self.misleading_signals_identified:
            self.misleading_signals_identified.append(key)
            return self.weights.misleading_signal_identified
        
        return 0.0
    
    def record_deploy_correlation(
        self,
        deploy_id: str,
        metric_change: str,
        is_correct: bool
    ) -> float:
        """
        Record a deployment-metric correlation.
        
        Agent identifies that a deploy caused metric change.
        """
        correlation = {
            "deploy": deploy_id,
            "metric": metric_change,
            "correct": is_correct,
        }
        
        # Check if similar correlation already made
        for c in self.deploy_correlations:
            if c["deploy"] == deploy_id and c["metric"] == metric_change:
                return 0.0
        
        self.deploy_correlations.append(correlation)
        
        if is_correct:
            return self.weights.deploy_correlation
        
        return 0.0
    
    def record_service_query(
        self,
        service: str,
        query_type: str
    ) -> float:
        """
        Record a service query.
        
        Reward if querying relevant service.
        """
        key = f"{query_type}:{service}"
        
        if key not in self.correct_queries:
            self.correct_queries.append(key)
            
            # Check if this is a relevant service
            if service in self.key_signals:
                return self.weights.correct_service_query
        
        return 0.0
    
    def record_incorrect_assumption(
        self,
        assumed_root_cause: str,
        actual_root_cause: str
    ) -> float:
        """
        Record an incorrect root cause assumption.
        
        Returns negative reward (penalty).
        """
        if assumed_root_cause != actual_root_cause:
            self.incorrect_assumptions.append(assumed_root_cause)
            return -self.weights.incorrect_assumption
        
        return 0.0
    
    def record_ignored_signal(
        self,
        signal: str
    ) -> float:
        """
        Record that a key signal was ignored.
        
        Returns negative reward (penalty).
        """
        if signal in self.key_signals:
            self.ignored_signals.append(signal)
            return -self.weights.key_signal_ignored
        
        return 0.0
    
    def calculate_step_reward(
        self,
        action_type: str,
        target_service: Optional[str],
        observation: Optional[dict],
        step: int,
        info_gained: bool = True
    ) -> ReasoningRewardBreakdown:
        """
        Calculate reward for a single step.
        
        Returns complete breakdown of reasoning-based rewards.
        """
        breakdown = ReasoningRewardBreakdown()
        
        # 1. Check for correct service query
        if target_service and action_type in ("query_service", "query_metrics", "query_logs"):
            reward = self.record_service_query(target_service, action_type)
            breakdown.correct_service_query_reward = reward
            if reward > 0:
                breakdown.reasoning_steps.append(
                    f"Queried relevant service: {target_service}"
                )
        
        # 2. Check for dependency trace
        if action_type == "query_dependencies" and target_service:
            # Check if this trace is relevant
            is_correct = target_service in self.key_signals
            reward = self.record_dependency_trace(
                "agent", target_service, is_correct
            )
            breakdown.dependency_trace_reward = reward
            if reward > 0:
                breakdown.reasoning_steps.append(
                    f"Traced correct dependency to: {target_service}"
                )
        
        # 3. Check for deployment correlation
        if action_type == "query_deployments":
            # Agent is attempting deploy correlation
            breakdown.reasoning_steps.append("Queried deployment timeline")
        
        # 4. Check for root cause identification
        if action_type == "identify_root_cause" and target_service:
            self.root_cause_attempts.append(target_service)
            
            if target_service == self.actual_root_cause:
                breakdown.root_cause_correct = self.weights.root_cause_correct
                self.correct_root_cause_identified = True
                breakdown.decisions_made.append(
                    f"Correctly identified root cause: {target_service}"
                )
            else:
                # Incorrect assumption
                penalty = self.record_incorrect_assumption(
                    target_service, self.actual_root_cause
                )
                breakdown.incorrect_assumption_penalty = penalty
                breakdown.decisions_made.append(
                    f"Incorrectly assumed root cause: {target_service}"
                )
        
        # 5. Check for fix application
        if action_type in ("restart_service", "rollback_deployment", "apply_fix") and target_service:
            self.fix_attempts.append((target_service, action_type))
            
            if target_service == self.actual_root_cause:
                breakdown.fix_correct = self.weights.fix_correct
                self.correct_fix_applied = True
                breakdown.decisions_made.append(
                    f"Correct fix applied to: {target_service}"
                )
        
        # 6. Check for memory usage
        if action_type == "query_memory":
            # Memory used correctly if it led to correct action
            breakdown.reasoning_steps.append("Consulted incident memory")
        
        # 7. Penalty for no new information
        if not info_gained and step > 3:
            breakdown.no_new_info_penalty = -self.weights.no_new_info
            breakdown.decisions_made.append("Action provided no new information")
        
        # Calculate totals
        breakdown.reasoning_total = (
            breakdown.dependency_trace_reward +
            breakdown.misleading_signal_reward +
            breakdown.deploy_correlation_reward +
            breakdown.correct_service_query_reward
        )
        
        breakdown.outcome_total = (
            breakdown.root_cause_correct +
            breakdown.fix_correct +
            breakdown.memory_usage_reward
        )
        
        breakdown.penalty_total = (
            breakdown.incorrect_assumption_penalty +
            breakdown.key_signal_ignored_penalty +
            breakdown.no_new_info_penalty +
            breakdown.brute_force_penalty
        )
        
        breakdown.final_reward = (
            breakdown.reasoning_total +
            breakdown.outcome_total +
            breakdown.penalty_total
        )
        
        # Calculate quality scores
        breakdown.reasoning_quality_score = self._calculate_reasoning_quality()
        breakdown.decision_quality_score = self._calculate_decision_quality()
        
        return breakdown
    
    def _calculate_reasoning_quality(self) -> float:
        """Calculate overall reasoning quality"""
        if not self.correct_queries:
            return 0.0
        
        # Ratio of correct queries to total relevant services
        relevant_queried = len([q for q in self.correct_queries 
                               if any(s in q for s in self.key_signals)])
        
        if not self.key_signals:
            return 0.5
        
        base_score = relevant_queried / len(self.key_signals)
        
        # Bonus for dependency tracing
        dep_bonus = min(0.2, len(self.dependency_traces) * 0.1)
        
        # Bonus for misleading signal identification
        mislead_bonus = min(0.2, len(self.misleading_signals_identified) * 0.1)
        
        return min(1.0, base_score + dep_bonus + mislead_bonus)
    
    def _calculate_decision_quality(self) -> float:
        """Calculate decision quality based on accuracy"""
        total_decisions = (
            len(self.root_cause_attempts) +
            len(self.fix_attempts)
        )
        
        if total_decisions == 0:
            return 0.5  # No decisions yet
        
        correct_decisions = (
            1 if self.correct_root_cause_identified else 0 +
            1 if self.correct_fix_applied else 0
        )
        
        return correct_decisions / total_decisions
    
    def get_summary(self) -> dict:
        """Get summary of reasoning state"""
        return {
            "dependency_traces": len(self.dependency_traces),
            "misleading_signals_found": len(self.misleading_signals_identified),
            "deploy_correlations": len(self.deploy_correlations),
            "correct_queries": len(self.correct_queries),
            "incorrect_assumptions": len(self.incorrect_assumptions),
            "ignored_signals": len(self.ignored_signals),
            "root_cause_identified": self.correct_root_cause_identified,
            "fix_applied": self.correct_fix_applied,
            "reasoning_quality": self._calculate_reasoning_quality(),
            "decision_quality": self._calculate_decision_quality(),
        }


def create_reasoning_reward(seed: int = 42) -> ReasoningRewardCalculator:
    """Factory function"""
    return ReasoningRewardCalculator(ReasoningWeights(), seed)
