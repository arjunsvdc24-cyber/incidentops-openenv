"""
IncidentOps - Analyst Agent

Provides pattern matching and memory-based analysis to guide
other agents toward likely root causes.
"""
from typing import Optional, Dict, Any, List
from app.agents.base import BaseAgent, AgentObservation, AgentDecision, AgentRole
from app.models import ActionType


class AnalystAgent(BaseAgent):
    """
    Analyst Agent - pattern matching and memory.

    Behavior:
    1. At step 0, query memory for similar fault types
    2. Suggest most likely fault type based on symptom overlap
    3. After each step, update fault type probability
    4. Provide hints to other agents based on historical success
    """

    role = AgentRole.ANALYST

    # Fault type indicators for quick pattern matching
    FAULT_INDICATORS: Dict[str, List[str]] = {
        "oom": ["OutOfMemory", "heap", "memory", "gc", "java.lang.OutOfMemoryError"],
        "cascade": ["timeout", "connection", "pool", "exhausted", "503", "multiple"],
        "ghost": ["silent", "gradual", "ctr", "metric", "no error", "deploy"],
        "deployment": ["deploy", "version", "new", "after deploy", "rollback"],
        "network": ["timeout", "connection refused", "network", "dns", "unreachable"],
        "cert": ["certificate", "ssl", "tls", "expired", "handshake"],
    }

    def __init__(self) -> None:
        self._seed: int = 42
        self._suggested_fault_type: Optional[str] = None
        self._confidence: float = 0.0
        self._memory_hints: List[str] = []
        self._fault_probabilities: Dict[str, float] = {}
        self._pattern_matches: List[Dict[str, Any]] = []

    def reset(self, seed: int) -> None:
        """Reset agent state for a new episode"""
        self._seed = seed
        self._suggested_fault_type = None
        self._confidence = 0.0
        self._memory_hints = []
        self._fault_probabilities = {
            "oom": 0.0,
            "cascade": 0.0,
            "ghost": 0.0,
            "deployment": 0.0,
            "network": 0.0,
            "cert": 0.0,
        }
        self._pattern_matches = []

    def decide(self, observation: AgentObservation) -> AgentDecision:
        """Provide pattern-based analysis and hints"""
        # Analyze current observation for patterns
        self._analyze_patterns(observation)

        # Try to load memory and match patterns
        hints: List[str] = []
        memory_suggestions: List[Dict[str, Any]] = []

        try:
            from app.memory import IncidentMemory
            memory = IncidentMemory(seed=self._seed)

            # Extract keywords from action history
            keywords = self._extract_keywords(observation)

            if keywords:
                # Search memory for similar incidents
                matches = memory.search(query=" ".join(keywords), limit=3)
                for match in matches:
                    memory_suggestions.append({
                        "fault_type": match.record.fault_type,
                        "service": match.record.root_cause_service,
                        "action": match.record.correct_action,
                        "relevance": match.relevance_score,
                    })
                    hints.append(
                        f"Historical: {match.record.fault_type} in {match.record.root_cause_service}, "
                        f"try {match.record.correct_action} (relevance: {match.relevance_score:.2f})"
                    )
        except Exception:  # pragma: no cover
            # Memory not available or search failed
            pass  # pragma: no cover

        # Update suggestions based on pattern matching
        if self._suggested_fault_type:
            suggested_action = self._get_action_for_fault(self._suggested_fault_type)
            hints.insert(0, f"Analysis suggests: {self._suggested_fault_type} fault, try {suggested_action}")

        self._memory_hints = hints

        # Return query_memory action with findings in reasoning
        return AgentDecision(
            action_type=ActionType.QUERY_MEMORY.value,
            target_service=None,
            parameters={"symptoms": hints, "confidence": self._confidence},
            confidence=min(self._confidence, 0.8),
            reasoning="; ".join(hints) if hints else f"Initial analysis complete, no strong patterns detected (confidence: {self._confidence:.2f})",
        )

    def _analyze_patterns(self, observation: AgentObservation) -> None:
        """Analyze observation for fault patterns"""
        # Reset probabilities
        for key in self._fault_probabilities:
            self._fault_probabilities[key] = 0.0

        # Analyze action history for patterns
        action_text = " ".join([
            str(a.get("action_type", "")) + " " + str(a.get("target_service", ""))
            for a in observation.action_history
        ]).lower()

        # Check each fault type's indicators
        for fault_type, indicators in self.FAULT_INDICATORS.items():
            matches = sum(1 for indicator in indicators if indicator.lower() in action_text)
            if matches > 0:
                self._fault_probabilities[fault_type] = min(matches / len(indicators) + 0.2, 0.9)

        # Get most likely fault type
        if self._fault_probabilities:
            max_prob = max(self._fault_probabilities.values())
            if max_prob > 0.3:
                self._suggested_fault_type = max(
                    self._fault_probabilities, key=self._fault_probabilities.get
                )
                self._confidence = max_prob
            else:
                # No strong pattern - guess based on step number
                if observation.step == 0:  # pragma: no cover
                    self._suggested_fault_type = "cascade"  # Most common  # pragma: no cover
                    self._confidence = 0.2  # pragma: no cover
                else:  # pragma: no cover
                    self._suggested_fault_type = None  # pragma: no cover
                    self._confidence = 0.0  # pragma: no cover

        # Record pattern match
        self._pattern_matches.append({
            "step": observation.step,
            "probabilities": dict(self._fault_probabilities),
            "suggested": self._suggested_fault_type,
            "confidence": self._confidence,
        })

    def _extract_keywords(self, observation: AgentObservation) -> List[str]:
        """Extract keywords from observation for memory search"""
        keywords: List[str] = []

        # From action history
        for action in observation.action_history:
            action_type = action.get("action_type", "")
            target = action.get("target_service", "")
            if target:
                keywords.append(target)
            if action_type:
                keywords.append(action_type.replace("_", " "))

        # From rewards (negative rewards indicate problems)
        if observation.reward_history:
            recent_avg = sum(observation.reward_history[-3:]) / min(len(observation.reward_history), 3)
            if recent_avg < 0:
                keywords.extend(["error", "problem", "issue"])

        return list(set(keywords))

    def _get_action_for_fault(self, fault_type: str) -> str:
        """Get recommended action for a fault type"""
        action_map = {
            "oom": ActionType.RESTART_SERVICE.value,
            "cascade": ActionType.SCALE_SERVICE.value,
            "ghost": ActionType.ROLLBACK_DEPLOYMENT.value,
            "deployment": ActionType.ROLLBACK_DEPLOYMENT.value,
            "network": ActionType.SCALE_SERVICE.value,
            "cert": ActionType.APPLY_FIX.value,
        }
        return action_map.get(fault_type, ActionType.RESTART_SERVICE.value)

    def learn(self, observation: AgentObservation, decision: AgentDecision, reward: float) -> None:
        """Update fault probabilities based on outcome"""
        # If this hint led to positive reward, increase confidence
        if reward > 0.2:
            self._confidence = min(self._confidence + 0.15, 1.0)

            # Update probability for suggested fault type
            if self._suggested_fault_type:
                self._fault_probabilities[self._suggested_fault_type] = min(
                    self._fault_probabilities.get(self._suggested_fault_type, 0) + 0.1,
                    1.0
                )
        elif reward < -0.1:
            self._confidence = max(self._confidence - 0.1, 0.0)

            # Decrease probability for wrong suggestion
            if self._suggested_fault_type:
                self._fault_probabilities[self._suggested_fault_type] = max(
                    self._fault_probabilities.get(self._suggested_fault_type, 0) - 0.2,
                    0.0
                )

    def get_analysis_summary(self) -> Dict[str, Any]:
        """Get summary of analysis"""
        return {
            "suggested_fault_type": self._suggested_fault_type,
            "confidence": self._confidence,
            "fault_probabilities": dict(self._fault_probabilities),
            "memory_hints": list(self._memory_hints),
            "pattern_matches": self._pattern_matches,
        }

    def get_current_hypothesis(self) -> Optional[Dict[str, Any]]:
        """Get the current fault hypothesis with recommended action"""
        if not self._suggested_fault_type:
            return None

        return {
            "fault_type": self._suggested_fault_type,
            "confidence": self._confidence,
            "recommended_action": self._get_action_for_fault(self._suggested_fault_type),
            "reasoning": f"Based on pattern analysis with {self._confidence:.0%} confidence",
        }
