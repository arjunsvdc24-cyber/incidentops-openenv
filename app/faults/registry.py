"""
IncidentOps - Fault Registry

Central registry for all fault generators.
Provides fault discovery, listing, and generation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.determinism import DeterministicRNG
    from app.fault_injector import FaultScenario
    from app.faults.base import BaseFault


class FaultRegistry:
    """
    Central registry for all fault generators.

    Usage:
        # List all faults
        FaultRegistry.list()

        # Get a specific fault instance
        fault = FaultRegistry.get("network_partition")

        # Generate a scenario
        scenario = FaultRegistry.generate("network_partition", rng, 3, services)
    """

    _faults: dict[str, type["BaseFault"]] = {}

    @classmethod
    def register(cls, fault: type["BaseFault"]) -> None:
        """
        Register a fault class.

        Args:
            fault: Fault class to register
        """
        fault_instance = fault()
        cls._faults[fault_instance.name] = fault

    @classmethod
    def list(cls) -> list[str]:
        """
        List all registered fault names.

        Returns:
            Sorted list of fault names
        """
        return sorted(cls._faults.keys())

    @classmethod
    def get(cls, name: str) -> "BaseFault":
        """
        Get a fault instance by name.

        Args:
            name: Fault name

        Returns:
            Fault instance

        Raises:
            KeyError: If fault not found
        """
        if name not in cls._faults:
            available = ", ".join(cls.list())  # pragma: no cover
            raise KeyError(  # pragma: no cover
                f"Fault '{name}' not found. Available faults: {available}"  # pragma: no cover
            )  # pragma: no cover
        return cls._faults[name]()

    @classmethod
    def generate(
        cls,
        name: str,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> "FaultScenario":
        """
        Generate a scenario for a specific fault.

        Args:
            name: Fault name
            rng: Deterministic RNG
            difficulty: Difficulty level (1-5)
            services: List of available services

        Returns:
            Generated FaultScenario with fault_type set to the requested name
        """
        fault = cls.get(name)
        scenario = fault.generate(rng, difficulty, services)
        # Override fault_type so the scenario reflects the caller's requested name
        # (supports aliases: "zombie" and "zombie_process" both use ZombieProcessFault)
        from app.fault_injector import FaultType
        try:
            scenario.fault_type = FaultType(name)
        except ValueError:  # pragma: no cover
            pass  # Use whatever the fault class set  # pragma: no cover
        return scenario

    @classmethod
    def get_all_difficulties(cls) -> dict[str, tuple[int, int]]:
        """Get difficulty ranges for all registered faults"""
        result = {}
        for name in cls._faults:
            fault = cls.get(name)
            result[name] = fault.difficulty_range
        return result

    @classmethod
    def get_affected_services_hints(cls) -> dict[str, list[str]]:
        """Get affected services hints for all registered faults"""
        result = {}
        for name in cls._faults:
            fault = cls.get(name)
            result[name] = fault.affected_services_hint
        return result
