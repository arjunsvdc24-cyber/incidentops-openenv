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
