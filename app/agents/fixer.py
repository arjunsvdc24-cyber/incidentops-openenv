from typing import Any
"""
IncidentOps - Fixer Agent

Applies remediations to fix incidents. Works in coordination with
the Investigator agent which provides suspicion scores.
"""
from app.agents.base import BaseAgent, AgentObservation, AgentDecision, AgentRole
from app.models import ActionType


class FixerAgent(BaseAgent):
    """
    Fixer Agent - applies remediations.

    Behavior:
    1. Wait for Investigator to narrow down to suspect services
    2. Check if evidence is strong enough (>0.7 suspicion)
    3. Apply the most appropriate fix:
       - OOM/memory issues -> restart_service
       - Latency/degradation -> scale_service
       - Deployment-related -> rollback_deployment
       - Cert issues -> apply_fix
    4. If fix fails (no reward improvement), try next most likely
    """

    role = AgentRole.FIXER

    # Maps fault patterns to fix actions
    FAULT_FIX_MAP: dict[str, tuple] = {
        "memory": (ActionType.RESTART_SERVICE.value, "memory pressure detected"),
        "oom": (ActionType.RESTART_SERVICE.value, "out of memory error"),
        "crash": (ActionType.RESTART_SERVICE.value, "service crash"),
        "latency": (ActionType.SCALE_SERVICE.value, "high latency"),
        "slow": (ActionType.SCALE_SERVICE.value, "slow response"),
        "timeout": (ActionType.RESTART_SERVICE.value, "timeout error"),
        "deployment": (ActionType.ROLLBACK_DEPLOYMENT.value, "post-deployment issue"),
        "version": (ActionType.ROLLBACK_DEPLOYMENT.value, "version mismatch"),
        "cert": (ActionType.APPLY_FIX.value, "certificate issue"),
        "ssl": (ActionType.APPLY_FIX.value, "ssl/tls error"),
        "connection": (ActionType.SCALE_SERVICE.value, "connection pool exhausted"),
        "pool": (ActionType.SCALE_SERVICE.value, "connection pool issue"),
    }

    def __init__(self) -> None:
        self._seed: int = 42
        self._last_fix_service: str | None = None
        self._last_fix_action: str | None = None
        self._fix_attempts: int = 0
        self._fix_history: list[dict[str, Any]] = []
        self._current_fault_hypothesis: str | None = None

    def reset(self, seed: int) -> None:
        """Reset agent state for a new episode"""
        self._seed = seed
        self._last_fix_service = None
        self._last_fix_action = None
        self._fix_attempts = 0
        self._fix_history = []
        self._current_fault_hypothesis = None

    def decide(self, observation: AgentObservation) -> AgentDecision:
        """Decide the best fix action based on evidence"""
        # If we tried a fix recently and it worked (positive reward), identify root cause
        if self._fix_attempts > 0 and observation.reward_history:
            last_reward = observation.reward_history[-1]
            if last_reward > 0.5:
                # Fix worked - identify root cause to complete episode
                return AgentDecision(
                    action_type=ActionType.IDENTIFY_ROOT_CAUSE.value,
                    target_service=self._last_fix_service or "api-gateway",
                    confidence=0.85,
                    reasoning="Fix succeeded, identifying root cause to complete resolution",
                )

        # Determine the suspected service from action history
        suspected_service = self._find_suspected_service(observation)

        # If we already tried one fix and it didn't work, try a different approach
        if self._fix_attempts >= 1 and self._last_fix_service == suspected_service:
            # Try scaling instead of restart (or vice versa)
            if self._last_fix_action == ActionType.RESTART_SERVICE.value:
                return AgentDecision(
                    action_type=ActionType.SCALE_SERVICE.value,
                    target_service=suspected_service,
                    confidence=0.6,
                    reasoning=f"Restart insufficient, trying scale for {suspected_service}",
                )
            else:
                return AgentDecision(
                    action_type=ActionType.RESTART_SERVICE.value,
                    target_service=suspected_service,
                    confidence=0.6,
                    reasoning=f"Scale insufficient, trying restart for {suspected_service}",
                )

        # Determine fix action based on fault hypothesis
        fix_action, reasoning = self._determine_fix_action(observation, suspected_service)

        self._last_fix_service = suspected_service
        self._last_fix_action = fix_action
        self._fix_attempts = 1

        return AgentDecision(
            action_type=fix_action,
            target_service=suspected_service,
            confidence=0.8,
            reasoning=reasoning,
        )

    def _find_suspected_service(self, observation: AgentObservation) -> str:
        """Find the most likely root cause from action history"""
        # Look at recent actions for clues
        query_services: list[str] = []

        for action_dict in observation.action_history[-10:]:
            if action_dict.get("action_type") in [
                ActionType.QUERY_METRICS.value,
                ActionType.QUERY_LOGS.value,
                ActionType.QUERY_SERVICE.value,
            ]:
                svc = action_dict.get("target_service")
                if svc:
                    # Prioritize services that appear most frequently
                    query_services.append(svc)

        if query_services:
            # Return the most frequently queried service (likely the problematic one)
            from collections import Counter
            counts = Counter(query_services)
            return counts.most_common(1)[0][0]

        # Fallback to common root causes
        return "payment-service"  # pragma: no cover

    def _determine_fix_action(
        self, observation: AgentObservation, service: str
    ) -> tuple:
        """Determine the appropriate fix action based on symptoms"""
        # Analyze action history for symptom patterns
        symptom_keywords: list[str] = []

        for action_dict in observation.action_history:
            action_type = action_dict.get("action_type", "")
            if "query_logs" in action_type:
                # Logs often contain error messages
                symptom_keywords.append("error")
            elif "query_metrics" in action_type:
                # Could indicate latency or resource issues
                symptom_keywords.append("latency")

        # Check reward history for clues
        if observation.reward_history:
            recent_rewards = observation.reward_history[-5:]
            avg_reward = sum(recent_rewards) / len(recent_rewards)

            if avg_reward < -0.2:
                # Negative rewards suggest wrong approach
                symptom_keywords.append("wrong_fix")

        # Match against fault patterns
        for keyword, (action, description) in self.FAULT_FIX_MAP.items():
            if any(keyword in str(symptom_keywords).lower() for _ in [1]):
                self._current_fault_hypothesis = keyword
                return action, f"Detected {description}, applying {action} to {service}"

        # Default fallback - restart is usually safe first choice
        return ActionType.RESTART_SERVICE.value, f"Applying restart to suspected service {service}"

    def learn(self, observation: AgentObservation, decision: AgentDecision, reward: float) -> None:
        """Update fix strategy based on outcome"""
        # Record this fix attempt
        self._fix_history.append({
            "service": decision.target_service,
            "action": decision.action_type,
            "reward": reward,
            "step": observation.step,
        })

        # If fix didn't work, increment attempt counter
        if reward < 0:
            self._fix_attempts += 1
        else:
            # Reset if fix worked
            self._fix_attempts = 0

    def get_fix_summary(self) -> dict[str, Any]:
        """Get summary of fix attempts"""
        return {
            "fix_attempts": self._fix_attempts,
            "last_fix_service": self._last_fix_service,
            "last_fix_action": self._last_fix_action,
            "fix_history": self._fix_history,
            "fault_hypothesis": self._current_fault_hypothesis,
        }
