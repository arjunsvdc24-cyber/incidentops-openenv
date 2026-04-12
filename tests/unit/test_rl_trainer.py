"""
IncidentOps - RL Trainer & DB Model Tests

Tests the GymnasiumWrapper and RLTrainer for SB3 integration,
plus ORM model __repr__ methods.
"""
import pytest
import numpy as np


class TestDBModelsRepr:
    """ORM model __repr__ methods."""

    def test_user_repr(self):
        from app.db.models import User
        user = User(id=1, username="testuser")
        repr_str = repr(user)
        assert "User" in repr_str
        assert "testuser" in repr_str

    def test_episode_repr(self):
        from app.db.models import Episode
        episode = Episode(
            id=1,
            episode_id="ep-001",
            fault_type="oom",
            difficulty=2,
            seed=42,
            agent_type="human",
            actions=[],
            observations=[],
            rewards=[],
            total_reward=5.0,
            final_score=0.85,
            grade="excellent",
            num_steps=10,
            terminated=False,
            truncated=False,
            created_at=None,
        )
        repr_str = repr(episode)
        assert "Episode" in repr_str
        assert "oom" in repr_str

    def test_leaderboard_entry_repr(self):
        from app.db.models import LeaderboardEntry
        entry = LeaderboardEntry(
            id=1,
            user_id=5,
            task_id="oom_2",
            fault_type="oom",
            grader_type="enhanced",
            best_score=0.9,
            avg_score=0.85,
            episode_count=10,
            created_at=None,
            updated_at=None,
        )
        repr_str = repr(entry)
        assert "LeaderboardEntry" in repr_str
        assert "oom_2" in repr_str


class TestRLTrainerInit:
    """RLTrainer initialization and configuration."""

    def test_trainer_initializes_ppo(self):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        assert trainer.model_class == PPO
        assert trainer.total_timesteps == 10

    def test_trainer_initializes_a2c(self):
        from stable_baselines3 import A2C
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=A2C, total_timesteps=10)
        assert trainer.model_class == A2C

    def test_trainer_initializes_dqn(self):
        from stable_baselines3 import DQN
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=DQN, total_timesteps=10)
        assert trainer.model_class == DQN

    def test_trainer_default_values(self):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        assert trainer.learning_rate == 3e-4
        assert trainer.verbose == 1
        assert trainer.normalize_observations is True
        assert trainer.n_envs == 1
        assert trainer.model is None

    def test_trainer_custom_params(self):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(
            model_class=PPO,
            total_timesteps=1000,
            learning_rate=1e-3,
            verbose=0,
            normalize_observations=False,
            n_envs=4,
        )
        assert trainer.learning_rate == 1e-3
        assert trainer.verbose == 0
        assert trainer.normalize_observations is False
        assert trainer.n_envs == 4

    def test_trainer_make_env(self):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        env_fn = trainer.make_env(seed=42)
        assert callable(env_fn)

    def test_trainer_make_env_returns_gym_wrapper(self):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer, GymnasiumWrapper
        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        env_fn = trainer.make_env(seed=42)
        env = env_fn()
        assert isinstance(env, GymnasiumWrapper)
        env.close()

    def test_trainer_get_model_before_train(self):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        assert trainer.get_model() is None

    def test_trainer_save_without_model_raises(self, tmp_path):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        with pytest.raises(ValueError, match="not trained"):
            trainer.save(str(tmp_path / "no_model"))

    def test_trainer_predict_without_model_raises(self):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        with pytest.raises(ValueError, match="not trained"):
            trainer.predict(np.zeros(85))

    def test_trainer_load_method_exists(self):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        assert callable(trainer.load)

    def test_trainer_evaluate_method_exists(self):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        assert callable(trainer.evaluate)

    def test_trainer_save_method_exists(self):
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer
        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        assert callable(trainer.save)


class TestRLTrainerSB3Availability:
    """SB3 availability flag."""

    def test_sb3_available_flag(self):
        from app.agents.rl.trainer import SB3_AVAILABLE
        assert SB3_AVAILABLE is True

    def test_sb3_modules_imported(self):
        from app.agents.rl.trainer import PPO, A2C, DQN, gym
        assert PPO is not None
        assert A2C is not None
        assert DQN is not None
        assert gym is not None


class TestGymnasiumWrapperCoverage:
    """Target uncovered GymnasiumWrapper methods (reset, step, _obs_to_array, get_action_mapping)."""

    def test_wrapper_reset_with_seed(self):
        """Cover GymnasiumWrapper.reset() with seed - lines 82-89."""
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer, GymnasiumWrapper
        from app.environment import make_env

        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        env_fn = trainer.make_env(seed=42)
        wrapper = env_fn()

        obs, info = wrapper.reset(seed=42)
        assert isinstance(obs, np.ndarray)
        assert obs.shape[0] == wrapper._obs_size
        wrapper.close()

    def test_wrapper_reset_without_seed(self):
        """Cover GymnasiumWrapper.reset() without seed - lines 84-89."""
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer, GymnasiumWrapper
        from app.environment import make_env

        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        env_fn = trainer.make_env(seed=99)
        wrapper = env_fn()

        obs, info = wrapper.reset()
        assert isinstance(obs, np.ndarray)
        wrapper.close()

    def test_wrapper_step_execution(self):
        """Cover GymnasiumWrapper.step() - lines 91-120."""
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer, GymnasiumWrapper

        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        env_fn = trainer.make_env(seed=42)
        wrapper = env_fn()

        obs, _ = wrapper.reset(seed=42)
        # Take action 0 (query_service + first service)
        obs, reward, term, term2, info = wrapper.step(0)
        assert isinstance(obs, np.ndarray)
        assert isinstance(reward, float)
        assert isinstance(term, bool)
        assert isinstance(term2, bool)
        wrapper.close()

    def test_wrapper_obs_to_array(self):
        """Cover GymnasiumWrapper._obs_to_array() - lines 130-170."""
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer, GymnasiumWrapper

        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        env_fn = trainer.make_env(seed=42)
        wrapper = env_fn()

        obs, _ = wrapper.reset(seed=42)
        # _obs_to_array is called internally by reset/step
        assert obs.shape[0] == wrapper._obs_size
        assert obs.dtype == np.float32
        wrapper.close()

    def test_wrapper_get_action_mapping(self):
        """Cover GymnasiumWrapper.get_action_mapping() - lines 180-187."""
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer, GymnasiumWrapper

        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        env_fn = trainer.make_env(seed=42)
        wrapper = env_fn()

        wrapper.reset(seed=42)
        action_type, service = wrapper.get_action_mapping(0)
        assert isinstance(action_type, str)
        assert isinstance(service, str)
        wrapper.close()

    def test_wrapper_action_space(self):
        """Cover GymnasiumWrapper action_space property."""
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer, GymnasiumWrapper

        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        env_fn = trainer.make_env(seed=42)
        wrapper = env_fn()

        assert wrapper.action_space is not None
        assert wrapper.observation_space is not None
        wrapper.close()

    def test_wrapper_render(self):
        """Cover GymnasiumWrapper.render() - lines 176-178."""
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer, GymnasiumWrapper

        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        env_fn = trainer.make_env(seed=42)
        wrapper = env_fn()
        wrapper.reset(seed=42)

        result = wrapper.render()
        assert result is None  # env.render returns None
        wrapper.close()

    def test_wrapper_obs_padding(self):
        """Cover _obs_to_array padding path - lines 155-157."""
        from stable_baselines3 import PPO
        from app.agents.rl.trainer import RLTrainer, GymnasiumWrapper

        trainer = RLTrainer(model_class=PPO, total_timesteps=10)
        env_fn = trainer.make_env(seed=42)
        wrapper = env_fn()
        # Force padding by setting services to empty
        wrapper.reset(seed=42)
        wrapper.env.services = {}  # Force empty for padding test
        obs, _ = wrapper.reset(seed=99)
        assert obs.shape[0] == wrapper._obs_size
        wrapper.close()
