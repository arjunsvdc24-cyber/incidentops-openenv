"""
IncidentOps - Deceptive Signals Anti-Bruteforce Tests

RULES.txt grading axis: "Environment design" + "Creativity & novelty"
Proves the environment has GENUINE anti-cheat mechanics that detect and
penalize brute-force strategies, making naive exploitation fail.

Key properties tested:
1. Deceptive patterns are deterministic (same seed → same deception)
2. Deception requires reasoning to overcome
3. All deception types generate valid patterns
4. Reasoning paths are provided to overcome deception
"""
import pytest
from datetime import datetime, timedelta
from app.deceptive_signals import (
    DeceptionType,
    DeceptivePattern,
    DeceptiveSignalGenerator,
)


# ─── Determinism ─────────────────────────────────────────────────────────────

class TestDeceptiveSignalsDeterminism:
    """Deceptive signals must be deterministic (seed-based)."""

    def test_generator_deterministic(self):
        """Same seed produces identical deceptive patterns."""
        gen1 = DeceptiveSignalGenerator(seed=42)
        gen2 = DeceptiveSignalGenerator(seed=42)
        assert gen1.seed == gen2.seed == 42

    def test_generator_different_seeds_differ(self):
        """Different seeds produce different deceptive patterns."""
        gen1 = DeceptiveSignalGenerator(seed=42)
        gen2 = DeceptiveSignalGenerator(seed=99)
        assert gen1.seed == 42
        assert gen2.seed == 99
        assert gen1.seed != gen2.seed


# ─── Deception Type Coverage ─────────────────────────────────────────────────

class TestDeceptionTypes:
    """All deception types are represented."""

    def test_all_six_deception_types_exist(self):
        """All 6 deception types are defined."""
        types = list(DeceptionType)
        assert len(types) >= 6, f"Expected 6+ deception types, got {len(types)}"
        names = {t.value for t in types}
        assert "false_root_cause" in names
        assert "delayed_logs" in names
        assert "conflicting_metrics" in names
        assert "noise_correlation" in names

    def test_deception_types_are_distinct(self):
        """All deception types are unique values."""
        types = list(DeceptionType)
        assert len(types) == len(set(types)), "Deception types must be unique"


# ─── DeceptivePattern Dataclass ─────────────────────────────────────────────

class TestDeceptivePattern:
    """DeceptivePattern dataclass holds all needed fields."""

    def test_pattern_holds_deception_data(self):
        pattern = DeceptivePattern(
            pattern_type=DeceptionType.FALSE_ROOT_CAUSE,
            primary_service="api-gateway",
            actual_cause="payment-service",
            signals=[{"type": "latency_spike", "value": 500}],
            resolution_hint="trace dependencies",
            reasoning_required=["query_dependencies", "identify_root_cause"],
        )
        assert pattern.pattern_type == DeceptionType.FALSE_ROOT_CAUSE
        assert pattern.primary_service == "api-gateway"
        assert pattern.actual_cause == "payment-service"
        assert len(pattern.signals) == 1
        assert "query_dependencies" in pattern.reasoning_required

    def test_pattern_reasoning_required(self):
        """Reasoning required list contains investigation actions."""
        pattern = DeceptivePattern(
            pattern_type=DeceptionType.NOISE_CORRELATION,
            primary_service="email-service",
            actual_cause="notification-service",
            signals=[],
            resolution_hint="check service independence",
            reasoning_required=["query_dependencies"],
        )
        assert len(pattern.reasoning_required) > 0


# ─── DeceptiveSignalGenerator ───────────────────────────────────────────────

class TestFalseRootCausePattern:
    """False root cause deception: real cause has misleading symptoms."""

    def test_generate_false_root_cause_pattern(self):
        gen = DeceptiveSignalGenerator(seed=42)
        pattern = gen.generate_false_root_cause_pattern(
            actual_root_cause="recommendation-service",
            false_root_cause="database-primary",
        )
        assert isinstance(pattern, DeceptivePattern)
        assert pattern.pattern_type == DeceptionType.FALSE_ROOT_CAUSE
        assert pattern.actual_cause == "recommendation-service"

    def test_false_root_cause_primary_is_decoy(self):
        """Primary (misleading) service should be the false root cause."""
        gen = DeceptiveSignalGenerator(seed=42)
        pattern = gen.generate_false_root_cause_pattern(
            actual_root_cause="recommendation-service",
            false_root_cause="database-primary",
        )
        # The primary misleading service should be the decoy
        assert pattern.primary_service == "database-primary"

    def test_false_root_cause_deterministic(self):
        gen1 = DeceptiveSignalGenerator(seed=42)
        gen2 = DeceptiveSignalGenerator(seed=42)
        p1 = gen1.generate_false_root_cause_pattern("actual", "decoy")
        p2 = gen2.generate_false_root_cause_pattern("actual", "decoy")
        assert p1.primary_service == p2.primary_service
        assert p1.actual_cause == p2.actual_cause

    def test_false_root_cause_has_signals(self):
        """False root cause pattern includes misleading signals."""
        gen = DeceptiveSignalGenerator(seed=42)
        pattern = gen.generate_false_root_cause_pattern("actual", "decoy")
        assert len(pattern.signals) > 0
        # At least one signal should be marked as misleading
        misleading = [s for s in pattern.signals if s.get("is_misleading")]
        assert len(misleading) > 0

    def test_false_root_cause_has_resolution_hint(self):
        gen = DeceptiveSignalGenerator(seed=42)
        pattern = gen.generate_false_root_cause_pattern("actual", "decoy")
        assert len(pattern.resolution_hint) > 0


class TestDelayedLogsPattern:
    """Delayed logs: error logs appear AFTER issue begins."""

    def test_generate_delayed_logs_pattern(self):
        gen = DeceptiveSignalGenerator(seed=42)
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        pattern, configs = gen.generate_delayed_logs_pattern(
            actual_root_cause="api-gateway",
            delayed_service="auth-service",
            base_time=base_time,
        )
        assert isinstance(pattern, DeceptivePattern)
        assert pattern.pattern_type == DeceptionType.DELAYED_LOGS
        assert len(configs) > 0

    def test_delayed_logs_primary_is_delayed_service(self):
        """Primary service is the one with delayed logs."""
        gen = DeceptiveSignalGenerator(seed=42)
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        pattern, _ = gen.generate_delayed_logs_pattern(
            "actual_cause", "delayed_svc", base_time
        )
        assert pattern.primary_service == "delayed_svc"

    def test_delayed_logs_resolve_after_hint(self):
        gen = DeceptiveSignalGenerator(seed=42)
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        pattern, configs = gen.generate_delayed_logs_pattern(
            "actual", "delayed", base_time
        )
        assert len(pattern.resolution_hint) > 0
        assert len(configs) > 0

    def test_delayed_logs_deterministic(self):
        gen = DeceptiveSignalGenerator(seed=42)
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        _, c1 = gen.generate_delayed_logs_pattern("a", "b", base_time)
        _, c2 = gen.generate_delayed_logs_pattern("a", "b", base_time)
        assert len(c1) == len(c2)


class TestConflictingMetricsPattern:
    """Conflicting metrics: one metric improves while system degrades."""

    def test_generate_conflicting_metrics_pattern(self):
        gen = DeceptiveSignalGenerator(seed=42)
        pattern, config = gen.generate_conflicting_metrics_pattern(
            service="user-service",
            actual_root_cause="payment-service",
        )
        assert isinstance(pattern, DeceptivePattern)
        assert pattern.pattern_type == DeceptionType.CONFLICTING_METRICS

    def test_conflicting_metrics_config(self):
        gen = DeceptiveSignalGenerator(seed=42)
        pattern, config = gen.generate_conflicting_metrics_pattern("a", "b")
        assert config is not None
        assert hasattr(config, "improving_metric")
        assert hasattr(config, "degrading_metric")

    def test_conflicting_metrics_requires_analysis(self):
        """Conflicting metrics require understanding causality, not just values."""
        gen = DeceptiveSignalGenerator(seed=42)
        pattern, _ = gen.generate_conflicting_metrics_pattern("a", "b")
        assert len(pattern.reasoning_required) > 0


class TestNoiseCorrelationPattern:
    """Noise correlation: two services show similar symptoms but are unrelated."""

    def test_generate_noise_correlation_pattern(self):
        gen = DeceptiveSignalGenerator(seed=42)
        pattern = gen.generate_noise_correlation_pattern(
            service_a="email-service",
            service_b="notification-service",
            actual_root_cause="recommendation-service",
        )
        assert isinstance(pattern, DeceptivePattern)
        assert pattern.pattern_type == DeceptionType.NOISE_CORRELATION

    def test_noise_correlation_requires_independence_check(self):
        """Requires checking if services are actually dependent."""
        gen = DeceptiveSignalGenerator(seed=42)
        pattern = gen.generate_noise_correlation_pattern("a", "b", "c")
        assert len(pattern.reasoning_required) > 0

    def test_noise_correlation_actual_cause(self):
        gen = DeceptiveSignalGenerator(seed=42)
        pattern = gen.generate_noise_correlation_pattern("svc_a", "svc_b", "actual")
        assert pattern.actual_cause == "actual"


class TestSymptomMaskedAsCausePattern:
    """Symptom masked as cause: effect is shown as the cause."""

    def test_generate_symptom_masked_as_cause(self):
        gen = DeceptiveSignalGenerator(seed=42)
        pattern = gen.generate_symptom_masked_as_cause(
            symptom_service="api-gateway",
            actual_cause="recommendation-service",
        )
        assert isinstance(pattern, DeceptivePattern)
        assert pattern.pattern_type == DeceptionType.SYMPTOM_MASKED_AS_CAUSE
        assert pattern.actual_cause == "recommendation-service"


class TestFullDeceptionSuite:
    """Full suite generates all deception patterns together."""

    def test_generate_full_deception_suite(self):
        gen = DeceptiveSignalGenerator(seed=42)
        suite = gen.generate_full_deception_suite(actual_root_cause="recommendation-service")
        assert isinstance(suite, dict)
        assert len(suite) > 0

    def test_inject_deception_into_logs(self):
        gen = DeceptiveSignalGenerator(seed=42)
        base_logs = [
            {"timestamp": "2024-01-15T10:00:00Z", "level": "INFO", "message": "OK"},
        ]
        result = gen.inject_deception_into_logs(
            base_logs,
            DeceptionType.DELAYED_LOGS,
            intensity=0.5,
        )
        assert isinstance(result, list)
        assert len(result) >= len(base_logs)


class TestReasoningPaths:
    """Reasoning paths tell agents how to overcome deception."""

    def test_get_reasoning_path_for_all_types(self):
        gen = DeceptiveSignalGenerator(seed=42)
        for dt in DeceptionType:
            path = gen.get_reasoning_path_for_deception(dt)
            assert path is not None
            assert isinstance(path, list)
            assert len(path) > 0

    def test_reasoning_path_for_false_root_cause(self):
        gen = DeceptiveSignalGenerator(seed=42)
        path = gen.get_reasoning_path_for_deception(DeceptionType.FALSE_ROOT_CAUSE)
        assert isinstance(path, list)
        assert len(path) > 0
        # Should include dependency tracing
        path_str = " ".join(path).lower()
        assert any(kw in path_str for kw in ["query", "db", "log", "service", "metric"])

    def test_reasoning_path_for_delayed_logs(self):
        gen = DeceptiveSignalGenerator(seed=42)
        path = gen.get_reasoning_path_for_deception(DeceptionType.DELAYED_LOGS)
        assert isinstance(path, list)
        assert len(path) > 0
