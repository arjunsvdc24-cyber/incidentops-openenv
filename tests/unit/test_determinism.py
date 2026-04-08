"""
IncidentOps - Unit Tests: Determinism
"""
import pytest
from app.determinism import (
    DeterministicRNG,
    DeterminismAudit,
    run_reproducibility_test,
    patch_for_determinism,
)


class TestDeterministicRNG:
    def test_same_seed_same_output(self):
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(42)
        assert rng1.random() == rng2.random()
        assert rng1.random() == rng2.random()

    def test_different_seeds_different_output(self):
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(99)
        assert rng1.random() != rng2.random()

    def test_deterministic_id(self):
        rng = DeterministicRNG(42)
        id1 = rng.deterministic_id("prefix1")
        id2 = rng.deterministic_id("prefix1")
        assert id1 == id2
        id3 = rng.deterministic_id("prefix2")
        assert id1 != id3

    def test_choice(self):
        rng = DeterministicRNG(42)
        items = ["a", "b", "c"]
        results = [rng.choice(items) for _ in range(10)]
        rng2 = DeterministicRNG(42)
        results2 = [rng2.choice(items) for _ in range(10)]
        assert results == results2

    def test_shuffle(self):
        rng = DeterministicRNG(42)
        items = list(range(20))
        rng.shuffle(items)
        rng2 = DeterministicRNG(42)
        items2 = list(range(20))
        rng2.shuffle(items2)
        assert items == items2

    def test_seed_property(self):
        rng = DeterministicRNG(42)
        assert rng.seed == 42

    def test_reset_with_seed(self):
        rng = DeterministicRNG(42)
        rng.random()
        rng.reset(seed=99)
        assert rng.seed == 99

    def test_reset_without_seed(self):
        rng = DeterministicRNG(42)
        rng.advance_step()
        rng.random()
        rng.reset()
        # Should use existing seed (42)
        assert rng.seed == 42

    def test_randint(self):
        rng = DeterministicRNG(42)
        val = rng.randint(1, 10)
        assert isinstance(val, int)
        assert 1 <= val <= 10

    def test_randint_deterministic(self):
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(42)
        for _ in range(5):
            assert rng1.randint(1, 100) == rng2.randint(1, 100)

    def test_uniform(self):
        rng = DeterministicRNG(42)
        val = rng.uniform(5.0, 10.0)
        assert isinstance(val, float)
        assert 5.0 <= val <= 10.0

    def test_uniform_deterministic(self):
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(42)
        for _ in range(5):
            assert rng1.uniform(0.0, 1.0) == rng2.uniform(0.0, 1.0)

    def test_choices(self):
        rng = DeterministicRNG(42)
        seq = ["a", "b", "c"]
        result = rng.choices(seq, k=5)
        assert len(result) == 5
        for v in result:
            assert v in seq

    def test_choices_deterministic(self):
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(42)
        seq = ["a", "b", "c"]
        for _ in range(5):
            assert rng1.choices(seq, k=3) == rng2.choices(seq, k=3)

    def test_sample(self):
        rng = DeterministicRNG(42)
        seq = list(range(10))
        result = rng.sample(seq, k=3)
        assert len(result) == 3
        assert len(set(result)) == 3  # unique

    def test_sample_deterministic(self):
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(42)
        seq = list(range(20))
        for _ in range(5):
            assert rng1.sample(seq, k=5) == rng2.sample(seq, k=5)

    def test_advance_step(self):
        rng = DeterministicRNG(42)
        assert rng.advance_step() == 1
        assert rng.advance_step() == 2
        assert rng.advance_step() == 3

    def test_deterministic_timestamp(self):
        rng = DeterministicRNG(42)
        rng.advance_step()
        ts = rng.deterministic_timestamp()
        assert isinstance(ts, str)
        assert "T" in ts  # ISO format

    def test_deterministic_timestamp_deterministic(self):
        rng1 = DeterministicRNG(42)
        rng2 = DeterministicRNG(42)
        for _ in range(3):
            rng1.advance_step()
            rng2.advance_step()
            assert rng1.deterministic_timestamp() == rng2.deterministic_timestamp()

    def test_deterministic_timestamp_with_base(self):
        from datetime import datetime
        rng = DeterministicRNG(42)
        rng.advance_step()
        base = datetime(2024, 6, 15, 12, 0, 0)
        ts = rng.deterministic_timestamp(base_time=base)
        assert isinstance(ts, str)


class TestReproducibility:
    def test_run_reproducibility_test(self):
        result = run_reproducibility_test(seed=42, num_steps=5)
        assert result is not None
        assert "passed" in result
        assert "rewards_match" in result
        assert result["passed"] is True


class TestDeterminismAudit:
    """DeterminismAudit static methods."""

    def test_audit_code_for_violations(self):
        result = DeterminismAudit.audit_code_for_violations("app")
        assert "violations_found" in result
        assert "violations" in result
        assert "passed" in result
        assert isinstance(result["violations"], list)
        assert isinstance(result["passed"], bool)

    def test_audit_code_for_violations_structure(self):
        result = DeterminismAudit.audit_code_for_violations("app/models.py")
        # Single file should be checked
        assert "violations_found" in result


class TestPatchForDeterminism:
    """patch_for_determinism function."""

    def test_patch_for_determinism_returns_dict(self):
        result = patch_for_determinism()
        assert isinstance(result, dict)
        assert "status" in result
        assert "note" in result
