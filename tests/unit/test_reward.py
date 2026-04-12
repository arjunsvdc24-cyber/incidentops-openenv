"""
IncidentOps - Unit Tests: Reward System
"""
import pytest
from app.reward import RewardCalculator, RewardConfig, ProgressiveRewardShaping
from app.reasoning_reward import ReasoningRewardCalculator, ReasoningWeights


class TestRewardCalculator:
    def test_initializes(self):
        calc = RewardCalculator()
        assert calc is not None

    def test_calculate_step_reward(self):
        calc = RewardCalculator()
        calc.set_fault_info(
            root_cause="payment-service",
            affected_services={"payment-service", "order-service"},
            fault_type="oom"
        )
        reward = calc.calculate_step_reward(
            action_type="query_service",
            target_service="payment-service",
            current_services={},
            is_terminated=False,
            used_memory=False,
        )
        # Returns RewardBreakdown with a total float field
        assert hasattr(reward, "total")
        assert isinstance(reward.total, float)


class TestProgressiveRewardShaping:
    def test_initializes(self):
        reward_calc = RewardCalculator()
        shaper = ProgressiveRewardShaping(reward_calculator=reward_calc)
        assert shaper is not None

    def test_get_shaped_reward(self):
        reward_calc = RewardCalculator()
        shaper = ProgressiveRewardShaping(reward_calculator=reward_calc)
        # ProgressiveRewardShaping uses get_shaped_reward, not get_stage
        base_reward = 0.5
        from app.models import RewardBreakdown
        breakdown = RewardBreakdown()
        result = shaper.get_shaped_reward(base_reward, breakdown)
        assert isinstance(result, float)


class TestReasoningRewardCalculator:
    def test_initializes(self):
        calc = ReasoningRewardCalculator()
        assert calc is not None

    def test_calculate_step_reward(self):
        calc = ReasoningRewardCalculator()
        calc.set_fault_context(
            root_cause="payment-service",
            affected={"payment-service"},
        )
        # ReasoningRewardCalculator uses calculate_step_reward, not calculate_reasoning_reward
        reward = calc.calculate_step_reward(
            action_type="query_service",
            target_service="payment-service",
            observation={},
            step=1,
            info_gained=True,
        )
        assert isinstance(reward.final_reward, float)
