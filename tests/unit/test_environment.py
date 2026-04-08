"""
IncidentOps - Unit Tests: Environment
"""
import pytest
from app.environment import make_env, IncidentEnv, EnvironmentConfig
from app.fault_injector import FaultType


class TestEnvironment:
    def test_make_env_default(self):
        env = make_env()
        assert env is not None
        assert isinstance(env, IncidentEnv)

    def test_make_env_with_seed(self):
        env = make_env(seed=123)
        assert env.config.seed == 123

    def test_reset_returns_observation(self):
        env = make_env(seed=42)
        obs = env.reset(seed=42)
        assert isinstance(obs, dict)
        assert "services" in obs or "step" in obs

    def test_reset_deterministic(self):
        env1 = make_env(seed=42)
        env2 = make_env(seed=42)
        obs1 = env1.reset(seed=42)
        obs2 = env2.reset(seed=42)
        assert obs1 == obs2

    def test_step_executes_action(self):
        env = make_env(seed=42)
        env.reset(seed=42)
        response = env.step({
            "action_type": "query_service",
            "target_service": "api-gateway",
        })
        assert hasattr(response, "reward")
        assert hasattr(response, "observation")
        assert hasattr(response, "terminated")
        assert isinstance(response.reward, float)

    def test_step_invalid_action_raises(self):
        env = make_env(seed=42)
        env.reset(seed=42)
        with pytest.raises(Exception):
            env.step({"action_type": "invalid_action"})

    def test_all_fault_types(self):
        for fault in FaultType:
            env = make_env(seed=42, fault_type=fault)
            obs = env.reset(seed=42)
            assert obs is not None

    def test_difficulty_range(self):
        for difficulty in [1, 2, 3, 4, 5]:
            env = make_env(seed=42, difficulty=difficulty)
            obs = env.reset(seed=42)
            assert obs is not None

    def test_max_steps_limit(self):
        env = make_env(seed=42, max_steps=5)
        env.reset(seed=42)
        for i in range(10):
            response = env.step({
                "action_type": "query_service",
                "target_service": "api-gateway",
            })
            if response.terminated or response.truncated:
                break
            if i >= 4:
                assert response.truncated is True

    def test_episode_rewards_accumulated(self):
        env = make_env(seed=42)
        env.reset(seed=42)
        assert env.episode_rewards == []
        env.step({"action_type": "query_service", "target_service": "api-gateway"})
        assert isinstance(env.episode_rewards, list)


class TestEnvironmentConfig:
    def test_config_defaults(self):
        config = EnvironmentConfig()
        assert config.seed == 42
        assert config.max_steps == 50
        assert config.difficulty == 3
        assert config.enable_memory is True
        assert config.enable_log_noise is True
        assert config.enable_metric_noise is True

    def test_config_custom(self):
        config = EnvironmentConfig(seed=999, max_steps=10, difficulty=5)
        assert config.seed == 999
        assert config.max_steps == 10
        assert config.difficulty == 5
