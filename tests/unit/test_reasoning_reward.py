"""
IncidentOps - Reasoning Reward Tests

Tests ReasoningRewardCalculator and related classes for evaluating
agent reasoning quality.
"""
import pytest
from app.reasoning_reward import (
    ReasoningAction,
    ReasoningRewardBreakdown,
    ReasoningWeights,
    ReasoningRewardCalculator,
    create_reasoning_reward,
)


class TestReasoningAction:
    """ReasoningAction enum."""

    def test_reasoning_action_values(self):
        names = {a.value for a in ReasoningAction}
        assert len(names) >= 3


class TestReasoningRewardBreakdown:
    """ReasoningRewardBreakdown dataclass."""

    def test_breakdown_defaults(self):
        b = ReasoningRewardBreakdown()
        assert b.final_reward == 0.0
        assert b.correct_service_query_reward == 0.0

    def test_breakdown_non_zero(self):
        b = ReasoningRewardBreakdown(
            correct_service_query_reward=0.2,
            reasoning_total=0.3,
            final_reward=0.5,
        )
        assert b.final_reward == 0.5
        assert b.correct_service_query_reward == 0.2


class TestReasoningWeights:
    """ReasoningWeights dataclass."""

    def test_weights_defaults(self):
        w = ReasoningWeights()
        assert hasattr(w, "correct_service_query")
        assert hasattr(w, "dependency_trace")


class TestReasoningRewardCalculator:
    """ReasoningRewardCalculator evaluates reasoning quality."""

    def test_calculator_creation(self):
        calc = ReasoningRewardCalculator(seed=42)
        assert calc is not None

    def test_reset(self):
        calc = ReasoningRewardCalculator(seed=42)
        calc.set_fault_context("payment-service", {"order-service"})
        calc.record_service_query("payment-service", "metrics")
        calc.reset()
        assert len(calc.correct_queries) == 0

    def test_set_fault_context(self):
        calc = ReasoningRewardCalculator(seed=42)
        calc.set_fault_context(
            root_cause="payment-service",
            affected={"order-service", "user-service"},
        )
        assert calc.actual_root_cause == "payment-service"

    def test_set_key_signals(self):
        calc = ReasoningRewardCalculator(seed=42)
        calc.set_key_signals(["high_memory", "OOM_error", "GC_pause"])
        assert len(calc.key_signals) == 3

    def test_record_dependency_trace(self):
        calc = ReasoningRewardCalculator(seed=42)
        reward = calc.record_dependency_trace(
            from_service="payment-service",
            to_service="database-primary",
            is_correct=True,
        )
        assert len(calc.dependency_traces) == 1
        assert isinstance(reward, float)

    def test_record_misleading_signal_identified(self):
        calc = ReasoningRewardCalculator(seed=42)
        reward = calc.record_misleading_signal_identified(
            signal_description="latency_spike",
            correct_interpretation="not root cause",
        )
        assert len(calc.misleading_signals_identified) == 1
        assert isinstance(reward, float)

    def test_record_deploy_correlation(self):
        calc = ReasoningRewardCalculator(seed=42)
        reward = calc.record_deploy_correlation(
            deploy_id="deploy-001",
            metric_change="latency_spike",
            is_correct=True,
        )
        assert len(calc.deploy_correlations) == 1
        assert isinstance(reward, float)

    def test_record_service_query(self):
        calc = ReasoningRewardCalculator(seed=42)
        calc.set_fault_context("payment-service", set())
        reward = calc.record_service_query("payment-service", "metrics")
        assert isinstance(reward, float)

    def test_record_incorrect_assumption(self):
        calc = ReasoningRewardCalculator(seed=42)
        calc.record_incorrect_assumption(
            assumed_root_cause="api-gateway",
            actual_root_cause="payment-service",
        )
        assert len(calc.incorrect_assumptions) == 1

    def test_record_ignored_signal(self):
        calc = ReasoningRewardCalculator(seed=42)
        reward = calc.record_ignored_signal("OutOfMemoryError")
        assert isinstance(reward, float)
        assert reward <= 0.0  # Should be a penalty (negative)

    def test_calculate_step_reward(self):
        calc = ReasoningRewardCalculator(seed=42)
        calc.set_fault_context("payment-service", set())
        breakdown = calc.calculate_step_reward(
            action_type="query_service",
            target_service="payment-service",
            observation=None,
            step=1,
        )
        assert isinstance(breakdown, ReasoningRewardBreakdown)

    def test_get_summary(self):
        calc = ReasoningRewardCalculator(seed=42)
        calc.set_fault_context("payment-service", set())
        calc.record_service_query("payment-service", "metrics")
        summary = calc.get_summary()
        assert isinstance(summary, dict)

    def test_multiple_traces_accumulate(self):
        calc = ReasoningRewardCalculator(seed=42)
        calc.record_dependency_trace("payment-service", "database-primary", True)
        calc.record_dependency_trace("order-service", "database-primary", True)
        assert len(calc.dependency_traces) == 2


class TestReasoningRewardEdgeCases:
    """Coverage for uncovered lines in reasoning_reward.py."""

    def test_duplicate_dependency_trace_returns_zero(self):
        """Cover: reasoning_reward.py line 162 - duplicate trace."""
        calc = ReasoningRewardCalculator(seed=42)
        calc.record_dependency_trace("db", "order", True)
        reward = calc.record_dependency_trace("db", "order", True)  # duplicate
        assert reward == 0.0

    def test_duplicate_misleading_signal_returns_zero(self):
        """Cover: reasoning_reward.py line 180 - duplicate misleading signal."""
        calc = ReasoningRewardCalculator(seed=42)
        calc.record_misleading_signal_identified("high_cpu", "normal")
        reward = calc.record_misleading_signal_identified("high_cpu", "normal")
        assert reward == 0.0

    def test_duplicate_deploy_correlation_returns_zero(self):
        """Cover: reasoning_reward.py lines 200-202 - duplicate correlation."""
        calc = ReasoningRewardCalculator(seed=42)
        calc.record_deploy_correlation("deploy-1", "latency", True)
        reward = calc.record_deploy_correlation("deploy-1", "latency", False)
        assert reward == 0.0

    def test_deploy_correlation_incorrect(self):
        """Cover: reasoning_reward.py line 209 - is_correct=False."""
        calc = ReasoningRewardCalculator(seed=42)
        reward = calc.record_deploy_correlation("deploy-bad", "error", False)
        assert reward == 0.0

    def test_correct_assumption_no_penalty(self):
        """Cover: reasoning_reward.py line 246 - correct guess = no penalty."""
        calc = ReasoningRewardCalculator(seed=42)
        calc.set_fault_context("payment-service", set())
        reward = calc.record_incorrect_assumption("payment-service", "payment-service")
        assert reward == 0.0

    def test_query_dependencies_with_empty_key_signals(self):
        """Cover: reasoning_reward.py line 290 - empty key_signals."""
        calc = ReasoningRewardCalculator(seed=42)
        # key_signals is empty by default
        breakdown = calc.calculate_step_reward(
            action_type="query_dependencies",
            target_service="payment-service",
            observation={},
            step=1,
        )
        assert breakdown.dependency_trace_reward == 0.0

    def test_query_deployments_action(self):
        """Cover: reasoning_reward.py line 303 - query_deployments."""
        calc = ReasoningRewardCalculator(seed=42)
        breakdown = calc.calculate_step_reward(
            action_type="query_deployments",
            target_service=None,
            observation={},
            step=2,
        )
        assert "Queried deployment timeline" in breakdown.reasoning_steps

    def test_incorrect_root_cause_penalty(self):
        """Cover: reasoning_reward.py lines 307-323 - wrong root cause."""
        calc = ReasoningRewardCalculator(seed=42)
        calc.set_fault_context("payment-service", set())
        breakdown = calc.calculate_step_reward(
            action_type="identify_root_cause",
            target_service="wrong-service",
            observation={},
            step=3,
        )
        assert breakdown.incorrect_assumption_penalty < 0
        assert len(breakdown.decisions_made) > 0

    def test_query_memory_step(self):
        """Cover: reasoning_reward.py line 339 - query_memory."""
        calc = ReasoningRewardCalculator(seed=42)
        breakdown = calc.calculate_step_reward(
            action_type="query_memory",
            target_service=None,
            observation={},
            step=2,
        )
        assert "Consulted incident memory" in breakdown.reasoning_steps

    def test_no_new_info_penalty(self):
        """Cover: reasoning_reward.py lines 342-344 - no info penalty."""
        calc = ReasoningRewardCalculator(seed=42)
        breakdown = calc.calculate_step_reward(
            action_type="query_service",
            target_service="api-gateway",
            observation={},
            step=5,
            info_gained=False,
        )
        assert breakdown.no_new_info_penalty < 0

    def test_reasoning_quality_empty_queries(self):
        """Cover: reasoning_reward.py line 382 - empty correct_queries."""
        calc = ReasoningRewardCalculator(seed=42)
        # No queries recorded
        score = calc._calculate_reasoning_quality()
        assert score == 0.0

    def test_reasoning_quality_empty_key_signals(self):
        """Cover: reasoning_reward.py line 389 - empty key_signals."""
        calc = ReasoningRewardCalculator(seed=42)
        calc.record_service_query("any-service", "metrics")
        # key_signals still empty
        score = calc._calculate_reasoning_quality()
        assert score == 0.5

    def test_decision_quality_with_decisions(self):
        """Cover: reasoning_reward.py lines 411-416 - decisions made."""
        calc = ReasoningRewardCalculator(seed=42)
        calc.set_fault_context("payment-service", set())
        # Correct root cause
        calc.calculate_step_reward(
            action_type="identify_root_cause",
            target_service="payment-service",
            observation={},
            step=1,
        )
        score = calc._calculate_decision_quality()
        assert score >= 0.0

    def test_decision_quality_no_decisions(self):
        """Cover: reasoning_reward.py lines 408-409 - no decisions."""
        calc = ReasoningRewardCalculator(seed=42)
        score = calc._calculate_decision_quality()
        assert score == 0.5


class TestCreateReasoningReward:
    """Factory function for creating calculator."""

    def test_create_reasoning_reward(self):
        calc = create_reasoning_reward(seed=42)
        assert isinstance(calc, ReasoningRewardCalculator)
