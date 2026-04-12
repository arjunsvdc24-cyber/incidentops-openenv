"""
IncidentOps - Zombie Process Fault

Child processes not being reaped.
Resource exhaustion, "Too many open files" errors.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.faults.base import BaseFault
from app.fault_injector import DependencyPropagator, FaultScenario, FaultType

if TYPE_CHECKING:
    from app.determinism import DeterministicRNG


class ZombieProcessFault(BaseFault):
    """
    Zombie/orphaned process fault.

    Child processes not being reaped.
    Resource exhaustion, "Too many open files" errors.

    Symptoms:
    - Zombie process warnings
    - "Too many open files" errors
    - File descriptor exhaustion
    - Resource leaks

    Correct fix: restart_service
    """

    name = "zombie_process"
    difficulty_range = (2, 4)
    affected_services_hint = [
        "order-service",
        "payment-service",
        "notification-service",
        "analytics-service",
    ]

    def generate(
        self,
        rng: "DeterministicRNG",
        difficulty: int,
        services: list[str]
    ) -> FaultScenario:
        """Generate a zombie process scenario"""
        difficulty = self.validate_difficulty(difficulty)

        # Root cause is typically a service that spawns workers
        root_candidates = [
            s for s in services
            if any(keyword in s for keyword in ["order", "payment", "notification", "analytics"])
        ]
        if not root_candidates:
            root_candidates = [s for s in services if "service" in s]

        root_cause = rng.choice(root_candidates)

        # Affected includes downstream
        affected = [root_cause]
        downstream = DependencyPropagator.DEPENDENCY_GRAPH.get(root_cause, [])
        affected.extend(rng.sample(downstream, min(difficulty, len(downstream))))

        # Symptoms
        symptoms = self.get_symptoms()

        # Misleading signals
        misleading_signals = [
            f"{rng.choice(services)}: WARNING: System resource usage high",
            f"{rng.choice(services)}: ERROR: Operation failed",
        ]

        if difficulty >= 3:
            misleading_signals.extend([
                f"{rng.choice(services)}: WARNING: Process count unusual",
                f"{rng.choice(services)}: ERROR: Cannot allocate memory",
            ])

        return FaultScenario(
            fault_type=FaultType.ZOMBIE_PROCESS,
            root_cause_service=root_cause,
            affected_services=affected[:difficulty + 2],
            symptoms=symptoms,
            misleading_signals=misleading_signals,
            required_investigation_steps=[
                "query_processes",
                "query_logs:zombie",
                "identify_zombie_processes",
                "kill_zombies",
            ],
            correct_fix=f"restart_service:{root_cause}",
            difficulty=difficulty,
        )

    def get_symptoms(self) -> list[str]:
        """Get zombie process symptoms"""
        return [
            "Zombie process warnings in logs",
            "Too many open files errors",
            "File descriptor exhaustion",
            "Process table filling up",
            "Cannot spawn new processes",
        ]

    def get_log_noise_patterns(self) -> list[str]:
        """Get characteristic log patterns"""
        return [
            "WARNING: Zombie child process detected: PID 12345",
            "ERROR: Too many open files: ulimit exceeded",
            "WARNING: File descriptor count: 65535",
            "ERROR: Cannot open new file: too many open files",
            "WARNING: Process table nearly full",
            "ERROR: Failed to fork: Cannot allocate memory",
        ]

    def get_metric_noise_patterns(self) -> list[str]:
        """Get characteristic metric patterns"""
        return [
            "open_files_count increases rapidly",
            "process_count increases",
            "zombie_count > 0",
            "CPU steady but errors spike",
        ]
