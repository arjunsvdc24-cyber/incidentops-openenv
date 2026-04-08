"""
IncidentOps - Base Agent Classes

Provides abstract base class and shared data structures for all agents.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class AgentRole(str, Enum):
    """Roles for multi-agent system"""
    INVESTIGATOR = "investigator"  # Gathers evidence, queries services
    FIXER = "fixer"               # Applies remediations
    ANALYST = "analyst"           # Reads memory, analyzes patterns


@dataclass
class AgentObservation:
    """What an agent can observe from the environment"""
    step: int
    action_history: List[Dict[str, Any]]
    reward_history: List[float]
    information_summary: Dict[str, Any]
    reasoning_score: float
    is_guessing: bool


@dataclass
class AgentDecision:
    """What an agent decides to do"""
    action_type: str
    target_service: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    reasoning: str = ""


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Agents implement:
    - reset(): Initialize for new episode
    - decide(): Choose action based on observation
    - learn(): Update internal state based on outcome
    """
    role: AgentRole

    @abstractmethod
    def reset(self, seed: int) -> None:
        """
        Reset agent state for a new episode.

        Args:
            seed: Random seed for deterministic behavior
        """
        pass

    @abstractmethod
    def decide(self, observation: AgentObservation) -> AgentDecision:
        """
        Given an observation, decide on an action.

        Args:
            observation: Current environment observation

        Returns:
            AgentDecision with chosen action
        """
        pass

    @abstractmethod
    def learn(self, observation: AgentObservation, decision: AgentDecision, reward: float) -> None:
        """
        Learn from the outcome of a decision.

        Args:
            observation: Observation at decision time
            decision: The decision that was made
            reward: The reward received after executing the action
        """
        pass

    def get_stats(self) -> Dict[str, Any]:
        """
        Get agent statistics for monitoring.

        Returns:
            Dict of statistics
        """
        return {"role": self.role.value if self.role else "unknown"}
