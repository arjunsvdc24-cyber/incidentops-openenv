"""
IncidentOps - Reward System Coverage Tests
Targets uncovered lines in app/reward.py
"""
import pytest
from app.reward import RewardCalculator, ProgressiveRewardShaping
from app.reasoning_reward import ReasoningRewardCalculator
from app.environment import make_env
from app.fault_injector import FaultType


class TestRewardCalculatorEdgeCases:
    """Test reward calculator edge cases."""

    def test_memory_usage_bonus(self):
        """Cover: reward.py line 176 - memory usage bonus."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        # Query service multiple times
        for _ in range(3):
            result = env.step({"action_type": "query_service", "target_service": "api-gateway"})
            assert result.reward is not None
        env.close()

    def test_minimal_actions_bonus(self):
        """Cover: reward.py lines 183-187 - minimal actions bonus."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        env.step({"action_type": "query_service", "target_service": "payment-service"})
        result = env.step({
            "action_type": "restart_service",
            "target_service": "payment-service",
        })
        assert isinstance(result.reward, (int, float))
        env.close()

    def test_partial_fix_reward(self):
        """Cover: reward.py line 232 - partial fix."""
        env = make_env(seed=42, difficulty=3, fault_type=FaultType.CASCADE)
        env.reset(seed=42)
        env.step({"action_type": "query_service", "target_service": "database-primary"})
        result = env.step({
            "action_type": "restart_service",
            "target_service": "database-primary",
        })
        assert isinstance(result.reward, (int, float))
        env.close()

    def test_ghost_fix_reward(self):
        """Cover: reward.py line 237 - ghost requires rollback."""
        env = make_env(seed=42, difficulty=5, fault_type=FaultType.GHOST)
        env.reset(seed=42)
        env.step({"action_type": "query_deployments"})
        result = env.step({
            "action_type": "rollback_deployment",
            "target_service": "recommendation-service",
        })
        assert result.reward is not None
        env.close()


class TestProgressiveRewardShaping:
    """Test progressive reward shaping stages."""

    def test_stage_advancement(self):
        """Cover: reward.py lines 311-315 - stage advancement."""
        from app.reward import RewardCalculator, RewardConfig
        calc = RewardCalculator(RewardConfig())
        calculator = ProgressiveRewardShaping(calc, curriculum_stage=0)
        calculator.advance_stage(5)
        assert calculator.curriculum_stage == 0

    def test_stage_0_full_rewards(self):
        """Cover: reward.py line 331-332 - stage 0 full rewards."""
        from app.reward import RewardCalculator, RewardConfig
        from app.models import RewardBreakdown
        calc = RewardCalculator(RewardConfig())
        calculator = ProgressiveRewardShaping(calc, curriculum_stage=0)
        breakdown = RewardBreakdown()
        reward = calculator.get_shaped_reward(base_reward=1.0, breakdown=breakdown)
        assert reward == 1.0

    def test_stage_4_sparse_rewards(self):
        """Cover: reward.py line 334-360 - high-stage sparse rewards."""
        from app.reward import RewardCalculator, RewardConfig
        from app.models import RewardBreakdown
        calc = RewardCalculator(RewardConfig())
        calculator = ProgressiveRewardShaping(calc, curriculum_stage=4)
        breakdown = RewardBreakdown(
            health_improvement=0.5,
            latency_improvement=0.2,
            correct_investigation=0.1,
            root_cause_identified=0.3,
            correct_fix=0.3,
            minimal_actions=0.1,
        )
        reward = calculator.get_shaped_reward(base_reward=1.0, breakdown=breakdown)
        assert isinstance(reward, (int, float))


class TestReasoningRewardCalculator:
    """Test reasoning reward calculator."""

    def test_calculator_creation(self):
        """Cover: reasoning_reward.py basic creation."""
        calc = ReasoningRewardCalculator()
        assert calc is not None

    def test_record_dependency_trace(self):
        """Cover: reasoning_reward.py dependency tracking."""
        calc = ReasoningRewardCalculator()
        reward = calc.record_dependency_trace(
            from_service="database-primary",
            to_service="order-service",
            is_correct=True,
        )
        assert reward == 0.1

    def test_record_misleading_signal(self):
        """Cover: reasoning_reward.py misleading signal tracking."""
        calc = ReasoningRewardCalculator()
        reward = calc.record_misleading_signal_identified(
            signal_description="high_cpu",
            correct_interpretation="normal under load",
        )
        assert reward == 0.1

    def test_record_deploy_correlation(self):
        """Cover: reasoning_reward.py deployment correlation."""
        calc = ReasoningRewardCalculator()
        reward = calc.record_deploy_correlation(
            deploy_id="recommendation-v2",
            metric_change="latency_spike",
            is_correct=True,
        )
        assert reward == 0.1

    def test_record_service_query(self):
        """Cover: reasoning_reward.py service query."""
        calc = ReasoningRewardCalculator()
        calc.set_key_signals(["api-gateway"])
        reward = calc.record_service_query(
            service="api-gateway",
            query_type="metrics",
        )
        assert reward == 0.05

    def test_record_incorrect_assumption(self):
        """Cover: reasoning_reward.py incorrect assumption."""
        calc = ReasoningRewardCalculator()
        reward = calc.record_incorrect_assumption(
            assumed_root_cause="payment-service",
            actual_root_cause="database-primary",
        )
        assert reward == -0.1

    def test_record_ignored_signal(self):
        """Cover: reasoning_reward.py ignored signal."""
        calc = ReasoningRewardCalculator()
        calc.set_key_signals(["business_metric_drift"])
        reward = calc.record_ignored_signal(signal="business_metric_drift")
        assert reward == -0.05

    def test_calculate_step_reward_with_reasoning(self):
        """Cover: reasoning_reward.py step reward calculation."""
        calc = ReasoningRewardCalculator()
        breakdown = calc.calculate_step_reward(
            action_type="query_metrics",
            target_service="api-gateway",
            observation={},
            step=1,
            info_gained=True,
        )
        assert hasattr(breakdown, "final_reward")

    def test_multiple_traces_accumulate(self):
        """Cover: reasoning_reward.py multiple traces."""
        calc = ReasoningRewardCalculator()
        for svc in ["api-gateway", "auth-service", "user-service"]:
            calc.record_service_query(service=svc, query_type="metrics")
        summary = calc.get_summary()
        assert summary is not None
