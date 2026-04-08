"""
IncidentOps - Stable-Baselines3 Integration

Provides Gymnasium wrapper and RL trainer for use with
stable-baselines3 algorithms (PPO, A2C, etc.).
"""
from typing import Tuple, Dict, Any, Optional, Callable, TYPE_CHECKING
import numpy as np

from app.models import ActionType, VALID_SERVICES

if TYPE_CHECKING:
    from app.environment import IncidentEnv

try:
    import gymnasium as gym
    from stable_baselines3 import PPO, A2C, DQN
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    gym = None
    PPO = None
    A2C = None
    DQN = None
    DummyVecEnv = None
    VecNormalize = None


class GymnasiumWrapper(gym.Env):
    """
    Wrap IncidentEnv as a Gymnasium-compatible environment.

    Action space: Discrete(11 * 16) = 176 actions
    Each action is mapped to (action_type, target_service) pair

    Observation space: Box with normalized service metrics + step info
    Features: 75 (15 services * 5 metrics) + 5 step info = 80 total
    """

    metadata = {"render_modes": []}

    def __init__(self, incident_env: "IncidentEnv"):
        """
        Initialize wrapper.

        Args:
            incident_env: The IncidentEnv to wrap
        """
        super().__init__()

        if not SB3_AVAILABLE:
            raise ImportError(
                "stable-baselines3 and gymnasium are required. "
                "Install with: pip install stable-baselines3 gymnasium"
            )

        self.env = incident_env

        # Action space: discrete actions for (action_type, service) combinations
        num_actions = len(ActionType)
        num_services = len(VALID_SERVICES)
        self._action_space_size = num_actions * num_services
        self.action_space = gym.spaces.Discrete(self._action_space_size)

        # Observation space: service metrics + step info
        self._num_services = num_services
        self._metrics_per_service = 5  # latency, error_rate, cpu, memory, status
        self._obs_size = num_services * self._metrics_per_service + 5  # + step info
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self._obs_size,),
            dtype=np.float32
        )

        # Cache for action/service mappings
        self._action_types = [a.value for a in ActionType]
        self._services = sorted(VALID_SERVICES)
        self._service_to_idx = {s: i for i, s in enumerate(self._services)}

    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict]:
        """Reset the environment"""
        if seed is not None:
            obs = self.env.reset(seed=seed)
        else:
            obs = self.env.reset()

        return self._obs_to_array(obs), {}

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Execute one step"""
        # Decode action
        action_type_idx = action // self._num_services
        service_idx = action % self._num_services

        action_type = self._action_types[
            min(action_type_idx, len(self._action_types) - 1)
        ]
        service = self._services[min(service_idx, len(self._services) - 1)]

        # Build action dict
        action_dict = {
            "action_type": action_type,
            "target_service": service,
            "parameters": {},
        }

        # Execute in environment
        response = self.env.step(action_dict)

        # Convert observation
        obs = self._obs_to_array(response.observation)

        return (
            obs,
            response.reward,
            response.terminated,
            response.truncated,
            response.info or {},
        )

    def _obs_to_array(self, obs: Dict) -> np.ndarray:
        """
        Convert dict observation to flat numpy array.

        Features per service (5):
        - latency_ms / 1000 (normalized)
        - error_rate (0-1)
        - cpu_percent / 100 (normalized)
        - memory_percent / 100 (normalized)
        - 1.0 if unhealthy, 0.0 otherwise

        Plus step info (5):
        - step / max_steps (normalized)
        - fix_applied (0 or 1)
        - observed_services / total_services
        - observed_logs / 100
        - observed_metrics / 100
        """
        features = []

        # Service metrics
        services = obs.get("services", {})
        for svc_name in self._services:
            svc = services.get(svc_name, {})
            features.extend([
                svc.get("latency_ms", 0) / 1000.0,  # normalize latency
                svc.get("error_rate", 0.0),           # already 0-1
                svc.get("cpu_percent", 0) / 100.0,    # normalize
                svc.get("memory_percent", 0) / 100.0, # normalize
                1.0 if svc.get("status") in ("unhealthy", "degraded") else 0.0,
            ])

        # Pad if necessary
        while len(features) < self._num_services * self._metrics_per_service:
            features.append(0.0)

        # Step info
        max_steps = self.env.config.max_steps if hasattr(self.env, 'config') else 50
        step_info = [
            self.env.current_step / max_steps,
            1.0 if obs.get("fix_applied", False) else 0.0,
            int(obs.get("observability", {}).get("observed_services", 0)) / self._num_services,
            int(obs.get("observability", {}).get("observed_logs", 0)) / 100.0,
            int(obs.get("observability", {}).get("observed_metrics", 0)) / 100.0,
        ]
        features.extend(step_info)

        return np.array(features[:self._obs_size], dtype=np.float32)

    def close(self) -> None:
        """Clean up environment"""
        self.env.close()

    def render(self, mode: str = "human") -> Optional[str]:
        """Render the environment"""
        return self.env.render(mode=mode)

    def get_action_mapping(self, action: int) -> Tuple[str, str]:
        """Get the (action_type, service) for a discrete action"""
        action_type_idx = action // self._num_services
        service_idx = action % self._num_services
        return (
            self._action_types[action_type_idx],
            self._services[service_idx]
        )


class RLTrainer:
    """
    Train RL agents using Stable-Baselines3 on IncidentEnv.

    Supports: PPO, A2C, DQN

    Usage:
        trainer = RLTrainer(model_class=PPO, total_timesteps=100_000)
        trainer.train(env_fn=lambda: GymnasiumWrapper(make_env(seed=0)))
        trainer.save("./models/ppo_incidentops")

        # Load and predict
        trainer.load("./models/ppo_incidentops")
        action, _ = trainer.predict(obs)
    """

    def __init__(
        self,
        model_class: type = PPO,
        total_timesteps: int = 100_000,
        learning_rate: float = 3e-4,
        verbose: int = 1,
        normalize_observations: bool = True,
        n_envs: int = 1,
    ):
        """
        Initialize trainer.

        Args:
            model_class: Stable-Baselines3 model class (PPO, A2C, DQN)
            total_timesteps: Total training timesteps
            learning_rate: Learning rate
            verbose: Verbosity level
            normalize_observations: Whether to normalize observations
            n_envs: Number of parallel environments
        """
        if not SB3_AVAILABLE:
            raise ImportError(
                "stable-baselines3 and gymnasium are required. "
                "Install with: pip install stable-baselines3 gymnasium"
            )

        self.model_class = model_class
        self.total_timesteps = total_timesteps
        self.learning_rate = learning_rate
        self.verbose = verbose
        self.normalize_observations = normalize_observations
        self.n_envs = n_envs
        self.tensorboard_log = None
        self.model: Optional[Any] = None
        self._vec_env = None

    def make_env(self, seed: int = 42) -> Callable:
        """
        Create environment factory function.

        Args:
            seed: Random seed

        Returns:
            Callable that returns a fresh GymnasiumWrapper
        """
        def _init():
            from app.environment import make_env
            base_env = make_env(seed=seed)
            return GymnasiumWrapper(base_env)
        return _init

    def train(self, env_fn: Optional[Callable] = None) -> Any:
        """
        Train the model.

        Args:
            env_fn: Function that returns a Gymnasium env.
                   If None, creates default IncidentEnv vectorized env.

        Returns:
            Trained model
        """
        if env_fn is None:
            env_fn = self.make_env(0)

        # Create vectorized environment
        if self.n_envs == 1:
            self._vec_env = DummyVecEnv([env_fn])
        else:
            self._vec_env = DummyVecEnv([self.make_env(i) for i in range(self.n_envs)])

        # Optionally normalize observations
        if self.normalize_observations and self._vec_env is not None:
            self._vec_env = VecNormalize(self._vec_env, norm_obs=True, norm_reward=True)

        # Create model
        self.model = self.model_class(
            "MlpPolicy",
            self._vec_env,
            learning_rate=self.learning_rate,
            verbose=self.verbose,
            tensorboard_log=None,
        )

        # Train
        self.model.learn(total_timesteps=self.total_timesteps)

        return self.model

    def save(self, path: str) -> None:
        """
        Save trained model.

        Args:
            path: Path to save model
        """
        if self.model is None:
            raise ValueError("Model not trained or loaded")
        self.model.save(path)

    def load(self, path: str) -> Any:
        """
        Load trained model.

        Args:
            path: Path to load model from

        Returns:
            Loaded model
        """
        if not SB3_AVAILABLE:
            raise ImportError("stable-baselines3 not available")

        self.model = self.model_class.load(path)
        return self.model

    def predict(
        self,
        obs: np.ndarray,
        deterministic: bool = True
    ) -> Tuple[int, float]:
        """
        Predict action for a single observation.

        Args:
            obs: Observation array
            deterministic: Whether to use deterministic policy

        Returns:
            Tuple of (action, state_value)
        """
        if self.model is None:
            raise ValueError("Model not trained or loaded")

        action, state = self.model.predict(obs, deterministic=deterministic)
        return int(action), float(state) if state is not None else 0.0

    def evaluate(
        self,
        env_fn: Callable,
        n_episodes: int = 10,
        deterministic: bool = True,
    ) -> Dict[str, float]:
        """
        Evaluate the model on multiple episodes.

        Args:
            env_fn: Function that returns a fresh Gymnasium env
            n_episodes: Number of episodes to run
            deterministic: Whether to use deterministic policy

        Returns:
            Dict with evaluation metrics
        """
        if self.model is None:
            raise ValueError("Model not trained or loaded")

        rewards = []
        episode_lengths = []
        successes = []

        for _ in range(n_episodes):
            env = env_fn()
            obs, _ = env.reset()
            done = False
            episode_reward = 0.0
            steps = 0

            while not done:
                action, _ = self.predict(obs, deterministic=deterministic)
                obs, reward, terminated, truncated, _ = env.step(action)
                episode_reward += reward
                steps += 1
                done = terminated or truncated

            rewards.append(episode_reward)
            episode_lengths.append(steps)
            successes.append(1.0 if env.env.fix_applied else 0.0)
            env.close()

        return {
            "mean_reward": np.mean(rewards),
            "std_reward": np.std(rewards),
            "mean_episode_length": np.mean(episode_lengths),
            "success_rate": np.mean(successes),
        }

    def get_model(self) -> Optional[Any]:
        """Get the trained model"""
        return self.model
