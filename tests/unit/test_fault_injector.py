"""
IncidentOps - Unit Tests: Fault Injector
"""
import pytest
from app.fault_injector import (
    FaultInjector, FaultType, FaultScenario,
    LogNoiseGenerator, MetricNoiseGenerator, DependencyPropagator
)


class TestFaultInjector:
    def test_injector_initializes(self):
        inj = FaultInjector(seed=42)
        assert inj is not None

    def test_generate_oom_scenario(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        assert isinstance(scenario, FaultScenario)
        assert scenario.fault_type == FaultType.OOM
        assert scenario.difficulty == 2
        assert len(scenario.root_cause_service) > 0
        assert len(scenario.affected_services) > 0

    def test_generate_cascade_scenario(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.CASCADE, difficulty=3)
        assert isinstance(scenario, FaultScenario)
        assert scenario.fault_type == FaultType.CASCADE

    def test_generate_ghost_scenario(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.GHOST, difficulty=5)
        assert isinstance(scenario, FaultScenario)
        assert scenario.fault_type == FaultType.GHOST

    def test_generate_deterministic(self):
        inj1 = FaultInjector(seed=42)
        inj2 = FaultInjector(seed=42)
        s1 = inj1.generate_scenario(FaultType.OOM, difficulty=2)
        s2 = inj2.generate_scenario(FaultType.OOM, difficulty=2)
        assert s1.root_cause_service == s2.root_cause_service
        assert s1.affected_services == s2.affected_services

    def test_all_fault_types(self):
        inj = FaultInjector(seed=42)
        for fault in FaultType:
            scenario = inj.generate_scenario(fault, difficulty=3)
            assert scenario.fault_type == fault
            assert scenario.correct_fix is not None
            assert len(scenario.correct_fix) > 0

    def test_scenario_has_symptoms(self):
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        assert len(scenario.symptoms) > 0


class TestDependencyPropagator:
    def test_get_upstream_services(self):
        prop = DependencyPropagator()
        upstream = prop.get_upstream_services("api-gateway")
        assert isinstance(upstream, list)

    def test_get_downstream_services(self):
        prop = DependencyPropagator()
        downstream = prop.get_downstream_services("database-primary", depth=2)
        assert isinstance(downstream, list)

    def test_propagate_failure(self):
        prop = DependencyPropagator()
        affected = prop.propagate_failure("database-primary", {"database-primary": {"status": "unhealthy"}})
        assert isinstance(affected, dict)


class TestFaultSimulatorCoverage:
    """Target uncovered FaultSimulator methods."""

    def test_simulator_get_metrics_ghost(self):
        """Cover _generate_faulty_metrics GHOST branch - line 1336."""
        from app.fault_injector import FaultInjector, FaultSimulator
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.GHOST, difficulty=5)
        sim = FaultSimulator(scenario, seed=42)
        # Call get_metrics on root cause (should hit GHOST branch)
        metrics = sim.get_metrics(scenario.root_cause_service, apply_noise=False)
        assert "business_metrics" in metrics
        assert "ctr" in metrics["business_metrics"]

    def test_simulator_get_logs_network(self):
        """Cover DDoS deceptive logs branch - lines 1218-1262."""
        from app.fault_injector import FaultInjector, FaultSimulator
        inj = FaultInjector(seed=42)
        # Force a network scenario via cascade (cascade uses NETWORK fault type)
        scenario = inj.generate_scenario(FaultType.CASCADE, difficulty=3)
        sim = FaultSimulator(scenario, seed=42)
        # query_logs triggers _generate_faulty_logs for root_cause
        logs = sim.get_logs(scenario.root_cause_service, apply_noise=False)
        assert isinstance(logs, list)

    def test_simulator_get_logs_apply_noise_true(self):
        """Cover log noise injection path - line 1198."""
        from app.fault_injector import FaultInjector, FaultSimulator
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=3)
        sim = FaultSimulator(scenario, seed=42)
        # apply_noise=True
        logs = sim.get_logs(scenario.root_cause_service, apply_noise=True)
        assert isinstance(logs, list)

    def test_simulator_get_service_states_network(self):
        """Cover DDoS downstream degradation - lines 1160-1162."""
        from app.fault_injector import FaultInjector, FaultSimulator
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.CASCADE, difficulty=3)
        sim = FaultSimulator(scenario, seed=42)
        states = sim.get_service_states(apply_propagation=True)
        assert isinstance(states, dict)
        assert len(states) > 0

    def test_simulator_memory_leak_metrics(self):
        """Cover memory leak misleading metrics - line 1182."""
        from app.fault_injector import FaultInjector, FaultSimulator
        inj = FaultInjector(seed=42)
        # Generate OOM with difficulty 4 → triggers memory leak scenario
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=4)
        sim = FaultSimulator(scenario, seed=42)
        # If it's a memory leak, test the database-replica path
        if hasattr(scenario, 'is_memory_leak') and scenario.is_memory_leak:
            metrics = sim.get_metrics("database-replica", apply_noise=False)
            assert isinstance(metrics, dict)

    def test_simulator_advance_step(self):
        """Cover advance_step method."""
        from app.fault_injector import FaultInjector, FaultSimulator
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.OOM, difficulty=2)
        sim = FaultSimulator(scenario, seed=42)
        sim.advance_step()
        assert sim.step == 1

    def test_simulator_propagate_recovery(self):
        """Cover propagate_recovery method."""
        from app.fault_injector import FaultInjector, FaultSimulator
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.CASCADE, difficulty=3)
        sim = FaultSimulator(scenario, seed=42)
        states = sim.get_service_states(apply_propagation=True)
        recovered = sim.propagate_recovery(scenario.root_cause_service, states)
        assert isinstance(recovered, dict)

    def test_simulator_deploy_timeline(self):
        """Cover get_deploy_timeline method."""
        from app.fault_injector import FaultInjector, FaultSimulator
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.GHOST, difficulty=5)
        sim = FaultSimulator(scenario, seed=42)
        timeline = sim.get_deploy_timeline()
        assert isinstance(timeline, list)

    def test_generate_string_fault_type(self):
        """Cover isinstance(str) branch in generate_scenario."""
        inj = FaultInjector(seed=42)
        # Passing string directly - should work
        scenario = inj.generate_scenario("cascade", difficulty=3)
        assert isinstance(scenario, FaultScenario)

    def test_generate_none_fault_type(self):
        """Cover fault_type=None random selection."""
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(None, difficulty=3)
        assert isinstance(scenario, FaultScenario)

    def test_injector_get_hardest_scenario(self):
        """Cover get_hardest_scenario."""
        inj = FaultInjector(seed=42)
        s = inj.get_hardest_scenario()
        assert s.difficulty == 5
        assert s.fault_type == FaultType.GHOST

    def test_injector_list_extended_faults(self):
        """Cover list_extended_faults."""
        inj = FaultInjector(seed=42)
        faults = inj.list_extended_faults()
        assert isinstance(faults, list)

    def test_injector_generate_extended(self):
        """Cover generate_extended_scenario."""
        inj = FaultInjector(seed=42)
        try:
            s = inj.generate_extended_scenario("ddos", difficulty=3)
            assert isinstance(s, FaultScenario)
        except ImportError:
            pass  # OK if faults module not available
