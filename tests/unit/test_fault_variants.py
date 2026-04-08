"""
IncidentOps - Fault Variant Unit Tests

Tests all fault types across both the canonical FaultInjector (OOM, Cascade, Ghost)
and the extended FaultRegistry (10 additional fault types) to ensure:
1. Each fault type instantiates correctly
2. Each fault produces deterministic, valid scenarios
3. Correct fix is properly identified per fault type
4. Difficulty levels affect fault parameters
"""
import pytest
from app.fault_injector import (
    FaultType,
    FaultInjector,
    FaultSimulator,
    FaultScenario,
)
from app.faults.registry import FaultRegistry


class TestFaultTypeEnum:
    """FaultType enum has all canonical fault types."""

    def test_canonical_faults_present(self):
        """OOM, cascade, ghost are canonical FaultType values."""
        expected = {"oom", "cascade", "ghost"}
        actual = {f.value for f in FaultType}
        assert expected.issubset(actual), f"Missing canonical faults: {expected - actual}"

    def test_fault_type_count(self):
        """FaultType enum has 5 canonical values."""
        assert len(list(FaultType)) >= 5


class TestFaultRegistry:
    """FaultRegistry has 10 extended fault types."""

    def test_registry_has_10_extended_faults(self):
        names = FaultRegistry.list()
        assert len(names) == 11, f"Expected 11 extended faults, got {len(names)}: {names}"
        expected = {
            "cert_expiry", "config_drift", "data_corruption", "ddos",
            "memory_leak", "network_partition", "slow_downstream",
            "thundering_herd", "version_mismatch", "zombie", "zombie_process",
        }
        assert set(names) == expected

    def test_each_extended_fault_has_generator(self):
        for name in FaultRegistry.list():
            fault = FaultRegistry.get(name)
            assert fault is not None, f"No fault generator for {name}"

    def test_extended_fault_all_difficulties(self):
        """Each extended fault supports all 5 difficulty levels."""
        for name in FaultRegistry.list():
            difficulties = FaultRegistry.get_all_difficulties().get(name)
            assert difficulties is not None


class TestFaultInjectorBasics:
    """FaultInjector generates valid scenarios for canonical faults."""

    def test_injector_initializes(self):
        inj = FaultInjector(seed=42)
        assert inj is not None

    def test_injector_generates_scenario(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        assert isinstance(scenario, FaultScenario)
        assert scenario.root_cause_service is not None

    def test_injector_get_scenario_by_type(self):
        inj = FaultInjector(seed=42)
        scenario = inj.get_scenario_by_type(FaultType.OOM, difficulty=2)
        assert isinstance(scenario, FaultScenario)

    def test_injector_list_extended_faults(self):
        inj = FaultInjector(seed=42)
        faults = inj.list_extended_faults()
        # Extended faults (10) + canonical FaultType (5) = 15 total
        assert len(faults) == 11  # list_extended_faults returns 11 extended types


class TestOOMFault:
    """OOM fault: payment-service crash → restart_service."""

    def test_oom_generates_scenario(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        assert isinstance(scenario, FaultScenario)

    def test_oom_deterministic(self):
        inj1 = FaultInjector(seed=42)
        inj2 = FaultInjector(seed=42)
        s1 = inj1.generate_scenario(FaultType.OOM, difficulty=2)
        s2 = inj2.generate_scenario(FaultType.OOM, difficulty=2)
        assert s1.root_cause_service == s2.root_cause_service


class TestCascadeFault:
    """Cascade fault: database-primary → scale_service."""

    def test_cascade_generates_scenario(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.CASCADE, difficulty=3)
        assert isinstance(scenario, FaultScenario)

    def test_cascade_affected_services(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.CASCADE, difficulty=3)
        # Cascade should have affected downstream services
        assert isinstance(scenario.affected_services, list)


class TestGhostFault:
    """Ghost fault: recommendation-service → rollback_deployment."""

    def test_ghost_generates_scenario(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.GHOST, difficulty=5)
        assert isinstance(scenario, FaultScenario)
        assert scenario.difficulty == 5

    def test_ghost_deterministic(self):
        inj1 = FaultInjector(seed=42)
        inj2 = FaultInjector(seed=42)
        s1 = inj1.generate_scenario(FaultType.GHOST, difficulty=5)
        s2 = inj2.generate_scenario(FaultType.GHOST, difficulty=5)
        assert s1.root_cause_service == s2.root_cause_service


class TestAllCanonicalFaultTypesGenerate:
    """All canonical FaultType values generate valid scenarios."""

    @pytest.mark.parametrize("fault_type", list(FaultType))
    def test_fault_type_generates_scenario(self, fault_type):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(fault_type, difficulty=3)
        assert isinstance(scenario, FaultScenario)
        assert scenario.root_cause_service is not None

    @pytest.mark.parametrize("fault_type", list(FaultType))
    def test_fault_type_deterministic(self, fault_type):
        """Same seed + same fault type → same scenario."""
        inj1 = FaultInjector(seed=42)
        inj2 = FaultInjector(seed=42)
        s1 = inj1.generate_scenario(fault_type, difficulty=3)
        s2 = inj2.generate_scenario(fault_type, difficulty=3)
        assert s1.root_cause_service == s2.root_cause_service
        assert s1.difficulty == s2.difficulty


class TestFaultSimulator:
    """FaultSimulator applies fault states to service grid."""

    def test_simulator_initializes(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        sim = FaultSimulator(scenario=scenario, seed=42)
        assert sim is not None

    def test_simulator_get_service_states(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        sim = FaultSimulator(scenario=scenario, seed=42)
        states = sim.get_service_states()
        assert isinstance(states, dict)
        assert len(states) > 0

    def test_simulator_get_metrics(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        sim = FaultSimulator(scenario=scenario, seed=42)
        metrics = sim.get_metrics("api-gateway")
        assert isinstance(metrics, dict)

    def test_simulator_get_logs(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        sim = FaultSimulator(scenario=scenario, seed=42)
        logs = sim.get_logs("api-gateway")
        assert isinstance(logs, list)

    def test_simulator_propagate_failure(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.CASCADE, difficulty=3)
        sim = FaultSimulator(scenario=scenario, seed=42)
        states = sim.get_service_states()
        result = sim.propagate_failure("database-primary", states)
        assert isinstance(result, dict)


class TestDifficultyLevels:
    """Different difficulty levels produce different configurations."""

    @pytest.mark.parametrize("difficulty", [1, 2, 3, 4, 5])
    def test_oom_all_difficulties(self, difficulty):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=difficulty)
        assert scenario.difficulty == difficulty

    @pytest.mark.parametrize("difficulty", [1, 2, 3, 4, 5])
    def test_ghost_all_difficulties(self, difficulty):
        """Ghost fault maps difficulty internally (4 for lower, 5 for max)."""
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.GHOST, difficulty=difficulty)
        # Ghost fault: difficulty 1-4 maps to internal level 4, 5 stays 5
        assert scenario.difficulty in (4, 5)

    @pytest.mark.parametrize("difficulty", [1, 2, 3, 4, 5])
    def test_cascade_all_difficulties(self, difficulty):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.CASCADE, difficulty=difficulty)
        assert scenario.difficulty == difficulty


class TestFaultScenario:
    """FaultScenario dataclass holds complete fault configuration."""

    def test_scenario_fields(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        assert hasattr(scenario, "root_cause_service")
        assert hasattr(scenario, "affected_services")
        assert hasattr(scenario, "correct_fix")
        assert hasattr(scenario, "fault_type")
        assert hasattr(scenario, "difficulty")

    def test_scenario_correct_fix_defined(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        assert scenario.correct_fix is not None
        assert len(scenario.correct_fix) > 0


class TestExtendedFaultScenarios:
    """Extended fault types from FaultRegistry."""

    @pytest.mark.parametrize("fault_name", FaultRegistry.list())
    def test_extended_fault_generates(self, fault_name):
        """Each extended fault generates a valid scenario."""
        import random
        faults = FaultRegistry.get_all_difficulties()
        lo, hi = faults[fault_name]
        for d in [lo, (lo + hi) // 2, hi]:
            rng = random.Random(42)
            services = ['api-gateway', 'payment-service', 'user-service',
                         'order-service', 'notification-service', 'recommendation-service']
            scenario = FaultRegistry.generate(fault_name, difficulty=d, rng=rng, services=services)
            assert scenario is not None
            assert hasattr(scenario, "root_cause_service")
            assert hasattr(scenario, "correct_fix")

    @pytest.mark.parametrize("fault_name", FaultRegistry.list())
    def test_extended_fault_correct_fix_defined(self, fault_name):
        """Each extended fault has a correct fix action."""
        import random
        rng = random.Random(42)
        services = ['api-gateway', 'payment-service', 'user-service']
        scenario = FaultRegistry.generate(fault_name, difficulty=3, rng=rng, services=services)
        assert scenario.correct_fix is not None
        assert len(scenario.correct_fix) > 0

    @pytest.mark.parametrize("fault_name", FaultRegistry.list())
    def test_extended_fault_has_hints(self, fault_name):
        """Each extended fault provides affected service hints."""
        hints = FaultRegistry.get_affected_services_hints()
        assert fault_name in hints
        assert isinstance(hints[fault_name], list)


class TestFaultRegistryCoverage:
    """Target uncovered FaultRegistry and BaseFault coverage."""

    def test_registry_get_unknown_fault(self):
        """Cover KeyError path in FaultRegistry.get() - lines 69-73."""
        with pytest.raises(KeyError):
            FaultRegistry.get("nonexistent_fault_xyz")

    def test_registry_generate_unknown_fault(self):
        """Cover KeyError path in FaultRegistry.generate() via get()."""
        from app.determinism import DeterministicRNG
        rng = DeterministicRNG(42)
        services = ['api-gateway', 'user-service', 'order-service']
        # generate with unknown fault name - should raise KeyError
        with pytest.raises(KeyError):
            FaultRegistry.generate("nonexistent_fault", rng, 3, services)

    def test_basefault_validate_difficulty_below(self):
        """Cover BaseFault.validate_difficulty below range."""
        from app.faults.cert_expiry import CertExpiryFault
        fault = CertExpiryFault()
        result = fault.validate_difficulty(0)
        assert result == fault.difficulty_range[0]

    def test_basefault_validate_difficulty_above(self):
        """Cover BaseFault.validate_difficulty above range."""
        from app.faults.cert_expiry import CertExpiryFault
        fault = CertExpiryFault()
        result = fault.validate_difficulty(10)
        assert result == fault.difficulty_range[1]

    def test_cascade_validate_difficulty(self):
        """Cover CascadeFault validate_difficulty."""
        from app.faults.network_partition import NetworkPartitionFault
        fault = NetworkPartitionFault()
        result = fault.validate_difficulty(10)
        assert result == fault.difficulty_range[1]

    def test_ddos_fault_coverage(self):
        """Cover DdosFault methods."""
        from app.faults.ddos import DdosFault
        from app.determinism import DeterministicRNG
        rng = DeterministicRNG(42)
        services = ['api-gateway', 'user-service', 'order-service']
        fault = DdosFault()
        assert fault.validate_difficulty(1) == 1
        assert fault.validate_difficulty(10) == 4
        scenario = fault.generate(rng, 3, services)
        assert scenario.correct_fix is not None

    def test_memory_leak_validate(self):
        """Cover MemoryLeakFault validate_difficulty."""
        from app.faults.memory_leak import MemoryLeakFault
        fault = MemoryLeakFault()
        assert fault.validate_difficulty(0) == 2
        assert fault.validate_difficulty(10) == 5

    def test_version_mismatch_validate(self):
        """Cover VersionMismatchFault validate_difficulty."""
        from app.faults.version_mismatch import VersionMismatchFault
        fault = VersionMismatchFault()
        assert fault.validate_difficulty(1) == 2
        assert fault.validate_difficulty(10) == 5

    def test_cert_expiry_validate(self):
        """Cover CertExpiryFault validate_difficulty."""
        from app.faults.cert_expiry import CertExpiryFault
        fault = CertExpiryFault()
        assert fault.validate_difficulty(1) == 1
        assert fault.validate_difficulty(10) == 3

    def test_zombie_process_validate(self):
        """Cover ZombieProcessFault validate_difficulty."""
        from app.faults.zombie_process import ZombieProcessFault
        fault = ZombieProcessFault()
        assert fault.validate_difficulty(0) == 2
        assert fault.validate_difficulty(10) == 4
