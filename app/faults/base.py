"""
IncidentOps - Base Fault Class

Abstract base class for all fault generators.
All faults must implement this interface for consistent behavior.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.determinism import DeterministicRNG
    from app.fault_injector import FaultScenario


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


class BaseFault(ABC):
    """
    Abstract base class for all fault generators.

    Each fault must:
    1. Define a unique name
    2. Set a difficulty range (min/max)
    3. List affected services hint
    4. Implement generate() to create FaultScenario
    5. Implement get_symptoms() to list characteristic symptoms
    """

    name: str
    difficulty_range: tuple[int, int]  # (min, max)
    affected_services_hint: list[str]

    @abstractmethod
    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> "FaultScenario":
        """
        Generate a deterministic fault scenario.

        Args:
            rng: Deterministic random number generator
            difficulty: Difficulty level (1-5)
            services: List of available service names

        Returns:
            FaultScenario with all fault details
        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def get_symptoms(self) -> list[str]:
        """Get characteristic symptoms for this fault type."""
        raise NotImplementedError  # pragma: no cover

    def validate_difficulty(self, difficulty: int) -> int:
        """Clamp difficulty only when outside the fault's valid range"""
        min_diff, max_diff = self.difficulty_range
        if difficulty < min_diff:
            return min_diff
        if difficulty > max_diff:
            return max_diff
        return difficulty

    def get_log_noise_patterns(self) -> list[str]:  # pragma: no cover
        """Get characteristic log noise patterns for this fault"""
        return []  # pragma: no cover

    def get_metric_noise_patterns(self) -> list[str]:  # pragma: no cover
        """Get characteristic metric noise patterns for this fault"""
        return []  # pragma: no cover
