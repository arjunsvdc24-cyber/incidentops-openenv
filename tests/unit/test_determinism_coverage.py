"""
IncidentOps - Determinism Coverage Tests
Targets uncovered lines in app/determinism.py
"""
import pytest
from app.determinism import (
    DeterministicRNG,
    DeterminismAudit,
    run_reproducibility_test,
)


class TestDeterministicRNG:
    def test_basic_functionality(self):
        """Cover: DeterministicRNG basic usage"""
        rng = DeterministicRNG(seed=42)
        vals = [rng.random() for _ in range(5)]
        assert len(vals) == 5
        assert 0 <= vals[0] <= 1

    def test_reproducibility(self):
        """Cover: DeterministicRNG reproducibility"""
        rng1 = DeterministicRNG(seed=123)
        rng2 = DeterministicRNG(seed=123)
        vals1 = [rng1.random() for _ in range(10)]
        vals2 = [rng2.random() for _ in range(10)]
        assert vals1 == vals2

    def test_different_seeds_different_results(self):
        """Cover: DeterministicRNG different seeds"""
        rng1 = DeterministicRNG(seed=1)
        rng2 = DeterministicRNG(seed=2)
        assert rng1.random() != rng2.random()


class TestDeterminismAudit:
    def test_check_environment_determinism_passes(self):
        """Cover: DeterminismAudit.check_environment_determinism()"""
        from app.environment import IncidentEnv, EnvironmentConfig
        result = DeterminismAudit.check_environment_determinism(
            IncidentEnv, EnvironmentConfig, seed=42
        )
        assert result["passed"] is True

    def test_check_environment_determinism_with_seed(self):
        """Cover: DeterminismAudit.check_environment_determinism() with different seed"""
        from app.environment import IncidentEnv, EnvironmentConfig
        result = DeterminismAudit.check_environment_determinism(
            IncidentEnv, EnvironmentConfig, seed=99
        )
        assert result["passed"] is True


class TestRunReproducibilityTest:
    def test_reproducibility_test_passes(self):
        """Cover: run_reproducibility_test()"""
        result = run_reproducibility_test(seed=42, num_steps=5)
        assert result["passed"] is True
        assert result["seed"] == 42

    def test_reproducibility_test_with_num_steps(self):
        """Cover: run_reproducibility_test() with different num_steps"""
        result = run_reproducibility_test(seed=555, num_steps=3)
        assert result["passed"] is True

    def test_reproducibility_test_result_structure(self):
        """Cover: run_reproducibility_test() result keys"""
        result = run_reproducibility_test(seed=777, num_steps=5)
        assert result["passed"] is True
        assert "rewards_match" in result
        assert "total_rewards_match" in result
        assert "initial_obs_match" in result
        assert "seed" in result
        assert "errors" in result

    def test_reproducibility_test_deterministic_keys(self):
        """Cover: run_reproducibility_test() deterministic keys"""
        result = run_reproducibility_test(seed=888, num_steps=2)
        assert result["passed"] is True
        # Results should be deterministic
        result2 = run_reproducibility_test(seed=888, num_steps=2)
        assert result == result2
