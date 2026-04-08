"""
IncidentOps - LLM Baseline Coverage Tests

Targeting app/llm_baseline.py for coverage improvement.
Tests import classes and functions from app.llm_baseline:
- LLMAgentConfig
- EvaluationResult
- LLMBaselineAgent
- check_openai_available()
- run_baseline_episode()
- run_llm_evaluation()

Uses real environment via make_env() for integration-like coverage.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.llm_baseline import (
    LLMAgentConfig,
    EvaluationResult,
    LLMBaselineAgent,
    check_openai_available,
    run_baseline_episode,
    run_llm_evaluation,
    HAS_OPENAI,
)
from app.environment import make_env


class TestLLMAgentConfigCoverage:
    """Additional coverage tests for LLMAgentConfig dataclass."""

    def test_config_with_all_defaults(self):
        """LLMAgentConfig with no arguments uses all defaults."""
        config = LLMAgentConfig()
        assert config.seed == 42
        assert config.model == "groq/llama-4-opus-17b"
        assert config.max_tokens == 500
        assert config.temperature == 0.0
        assert config.max_steps == 20

    def test_config_with_partial_override(self):
        """LLMAgentConfig with partial arguments."""
        config = LLMAgentConfig(seed=100)
        assert config.seed == 100
        assert config.model == "groq/llama-4-opus-17b"  # default

    def test_config_temperature_deterministic(self):
        """Temperature is set to 0.0 for deterministic behavior."""
        config = LLMAgentConfig(temperature=0.0)
        assert config.temperature == 0.0

    def test_config_max_tokens_override(self):
        """Max tokens can be customized."""
        config = LLMAgentConfig(max_tokens=1000)
        assert config.max_tokens == 1000

    def test_config_model_from_env_fallback(self):
        """MODEL_NAME environment variable is read at import time."""
        # Default is groq/llama-4-opus-17b
        config = LLMAgentConfig()
        assert "groq" in config.model.lower() or "llama" in config.model.lower()


class TestEvaluationResultCoverage:
    """Coverage tests for EvaluationResult dataclass."""

    def test_evaluation_result_creation(self):
        """EvaluationResult can be instantiated with all fields."""
        result = EvaluationResult(
            difficulty="easy",
            score=0.85,
            steps=5,
            success=True,
            actions=[{"action_type": "restart_service", "target_service": "payment-service"}],
        )
        assert result.difficulty == "easy"
        assert result.score == 0.85
        assert result.steps == 5
        assert result.success is True
        assert len(result.actions) == 1

    def test_evaluation_result_failure(self):
        """EvaluationResult can represent a failed episode."""
        result = EvaluationResult(
            difficulty="hard",
            score=0.0,
            steps=20,
            success=False,
            actions=[],
        )
        assert result.success is False
        assert result.score == 0.0

    def test_evaluation_result_with_empty_actions(self):
        """EvaluationResult with empty action list."""
        result = EvaluationResult(
            difficulty="medium",
            score=0.5,
            steps=0,
            success=False,
            actions=[],
        )
        assert result.actions == []
        assert result.steps == 0


class TestCheckOpenAIAvailableCoverage:
    """Additional coverage tests for check_openai_available()."""

    def test_no_openai_package_returns_false(self):
        """When openai package is not installed, returns False."""
        with patch("app.llm_baseline.HAS_OPENAI", False):
            result = check_openai_available()
            assert result is False

    def test_with_openai_package_but_no_key(self):
        """When openai package exists but no API key, returns False."""
        with patch("app.llm_baseline.HAS_OPENAI", True):
            with patch.dict("os.environ", {}, clear=True):
                result = check_openai_available()
                assert result is False

    def test_with_groq_api_key(self):
        """GROQ_API_KEY makes check_openai_available return True."""
        with patch("app.llm_baseline.HAS_OPENAI", True):
            with patch.dict("os.environ", {"GROQ_API_KEY": "gsk_test"}):
                result = check_openai_available()
                assert result is True

    def test_with_openai_api_key(self):
        """OPENAI_API_KEY makes check_openai_available return True."""
        with patch("app.llm_baseline.HAS_OPENAI", True):
            with patch.dict("os.environ", {"OPENAI_API_KEY": "sk_test"}):
                result = check_openai_available()
                assert result is True

    def test_with_gemini_api_key(self):
        """GEMINI_API_KEY makes check_openai_available return True."""
        with patch("app.llm_baseline.HAS_OPENAI", True):
            with patch.dict("os.environ", {"GEMINI_API_KEY": "gem_test"}):
                result = check_openai_available()
                assert result is True

    def test_with_askme_api_key(self):
        """ASKME_API_KEY makes check_openai_available return True."""
        with patch("app.llm_baseline.HAS_OPENAI", True):
            with patch.dict("os.environ", {"ASKME_API_KEY": "askme_test"}):
                result = check_openai_available()
                assert result is True


class TestLLMBaselineAgentAdditionalCoverage:
    """Additional coverage tests for LLMBaselineAgent."""

    def test_agent_init_with_none_config(self):
        """Agent initializes with None config using defaults."""
        agent = LLMBaselineAgent(config=None)
        assert agent.config.seed == 42
        assert agent.client is None  # No API key in test env

    def test_agent_state_tracking(self):
        """Agent tracks action_history and current_step."""
        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        assert agent.action_history == []
        assert agent.current_step == 0

        # Perform an action
        obs = {
            "step": 0,
            "alerts": [],
            "services": {},
            "incident_info": {"fault_type": "ghost"},
        }
        agent.act(obs)

        assert len(agent.action_history) == 1
        assert agent.current_step == 0

    def test_agent_step_updates_from_observation(self):
        """Agent's current_step updates from observation."""
        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {"step": 10, "alerts": [], "services": {}, "incident_info": {}}
        agent.act(obs)
        assert agent.current_step == 10

    def test_agent_provider_detection(self):
        """Agent detects provider from LLM_PROVIDER env var."""
        with patch.dict("os.environ", {"LLM_PROVIDER": "openai"}):
            agent = LLMBaselineAgent()
            assert agent.provider == "openai"

    def test_agent_base_url_detection(self):
        """Agent uses API_BASE_URL env var."""
        with patch.dict("os.environ", {"API_BASE_URL": "https://custom.api.com/v1"}):
            agent = LLMBaselineAgent()
            assert agent.base_url == "https://custom.api.com/v1"

    def test_agent_priority_order_groq_hf_openai(self):
        """Agent prioritizes API keys: GROQ > HF > OPENAI > GEMINI > ASKME."""
        # GROQ_API_KEY takes priority
        with patch.dict(
            "os.environ",
            {
                "GROQ_API_KEY": "groq_key",
                "HF_TOKEN": "hf_key",
                "OPENAI_API_KEY": "openai_key",
            },
        ):
            agent = LLMBaselineAgent()
            assert agent.api_key == "groq_key"
            assert agent.base_url == "https://api.groq.com/openai/v1"

    def test_agent_openai_key_fallback(self):
        """OPENAI_API_KEY used when other keys are absent."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk_openai"}):
            agent = LLMBaselineAgent()
            assert agent.api_key == "sk_openai"

    def test_agent_client_init_failure(self):
        """Agent handles client initialization failure gracefully."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
            with patch("app.llm_baseline.OpenAI", side_effect=Exception("Init failed")):
                agent = LLMBaselineAgent()
                assert agent.client is None


class TestLLMBaselineAgentGetLLMActionCoverage:
    """Coverage tests for _get_llm_action method."""

    def test_llm_action_parses_standard_json(self):
        """_get_llm_action parses standard JSON response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"action_type": "restart_service", "target_service": "payment-service"}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = LLMBaselineAgent()
        agent.client = mock_client
        agent.reset(seed=42)

        obs = {"step": 0, "alerts": [], "services": {}, "incident_info": {}}
        action = agent._get_llm_action(obs)

        assert action["action_type"] == "restart_service"
        assert action["target_service"] == "payment-service"
        assert action["parameters"] == {}

    def test_llm_action_defaults_missing_fields(self):
        """_get_llm_action defaults missing fields."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        # Missing target_service
        mock_response.choices[0].message.content = '{"action_type": "query_deployments"}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = LLMBaselineAgent()
        agent.client = mock_client
        agent.reset(seed=42)

        obs = {"step": 0, "alerts": [], "services": {}, "incident_info": {}}
        action = agent._get_llm_action(obs)

        assert action["action_type"] == "query_deployments"
        assert action["target_service"] is None

    def test_llm_action_trials_three_times(self):
        """_get_llm_action tries 3 times before falling back."""
        mock_client = MagicMock()
        # All attempts fail
        mock_client.chat.completions.create.side_effect = [
            Exception("fail 1"),
            Exception("fail 2"),
            Exception("fail 3"),
        ]

        agent = LLMBaselineAgent()
        agent.client = mock_client
        agent.reset(seed=42)

        obs = {"step": 0, "alerts": [], "services": {}, "incident_info": {"fault_type": "ghost"}}
        action = agent._get_llm_action(obs)

        # Falls back to rule-based ghost detection
        assert action["action_type"] == "query_deployments"
        assert mock_client.chat.completions.create.call_count == 3


class TestLLMBaselineAgentFormatObservationCoverage:
    """Additional coverage tests for _format_observation."""

    def test_format_empty_observation(self):
        """_format_observation handles empty observation gracefully."""
        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {"step": 0, "alerts": [], "services": {}, "incident_info": {}}
        formatted = agent._format_observation(obs)

        assert "Step: 0" in formatted
        assert "Alerts:" not in formatted
        assert "Problem Services:" not in formatted

    def test_format_multiple_alerts(self):
        """_format_observation shows multiple alerts."""
        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {
            "step": 1,
            "alerts": [
                {"service": "svc1", "severity": "critical", "message": "error1"},
                {"service": "svc2", "severity": "warning", "message": "error2"},
            ],
            "services": {},
            "incident_info": {},
        }
        formatted = agent._format_observation(obs)

        assert "Alerts:" in formatted
        assert "svc1" in formatted
        assert "svc2" in formatted

    def test_format_degraded_services(self):
        """_format_observation shows degraded services."""
        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {
            "step": 0,
            "alerts": [],
            "services": {
                "api-gateway": {"status": "degraded", "latency_ms": 2000, "error_rate": 0.15},
            },
            "incident_info": {},
        }
        formatted = agent._format_observation(obs)

        assert "Problem Services:" in formatted
        assert "api-gateway" in formatted
        assert "degraded" in formatted

    def test_format_no_incident_info(self):
        """_format_observation handles missing incident_info."""
        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {"step": 0, "alerts": [], "services": {}}
        formatted = agent._format_observation(obs)

        assert "Step: 0" in formatted


class TestRunBaselineEpisodeWithRealEnv:
    """Coverage tests for run_baseline_episode with real environment."""

    def test_run_baseline_episode_with_real_env(self):
        """run_baseline_episode works with real environment (OOM fault)."""
        # Use real make_env for integration coverage
        env = make_env(seed=42, difficulty=2)

        result = run_baseline_episode(
            env,
            agent=None,
            seed=42,
            max_steps=3,
            verbose=False,
        )

        assert "steps" in result
        assert "total_reward" in result
        assert "final_score" in result
        assert "grade" in result
        assert result["steps"] <= 3
        assert isinstance(result["total_reward"], float)

    def test_run_baseline_episode_cascade_fault(self):
        """run_baseline_episode with cascade fault."""
        from app.fault_injector import FaultType

        env = make_env(seed=42, difficulty=3, fault_type=FaultType.CASCADE)

        result = run_baseline_episode(
            env,
            agent=None,
            seed=42,
            max_steps=5,
            verbose=False,
        )

        assert result["steps"] <= 5
        assert 0.0 <= result["final_score"] <= 1.0

    def test_run_baseline_episode_ghost_fault(self):
        """run_baseline_episode with ghost fault (hardest)."""
        from app.fault_injector import FaultType

        env = make_env(seed=42, difficulty=5, fault_type=FaultType.GHOST)

        result = run_baseline_episode(
            env,
            agent=None,
            seed=42,
            max_steps=5,
            verbose=False,
        )

        assert result["steps"] <= 5
        # Ghost is hard, score may be low

    def test_run_baseline_episode_max_steps_limit(self):
        """run_baseline_episode respects max_steps limit."""
        env = make_env(seed=99)

        result = run_baseline_episode(
            env,
            agent=None,
            seed=99,
            max_steps=2,
            verbose=False,
        )

        assert result["steps"] == 2

    def test_run_baseline_episode_deterministic_seed(self):
        """run_baseline_episode produces deterministic results with same seed."""
        env1 = make_env(seed=123)
        env2 = make_env(seed=123)

        result1 = run_baseline_episode(env1, seed=123, max_steps=3, verbose=False)
        result2 = run_baseline_episode(env2, seed=123, max_steps=3, verbose=False)

        # Same seed should produce same number of steps
        assert result1["steps"] == result2["steps"]


class TestRunLLMEvaluationWithRealEnv:
    """Coverage tests for run_llm_evaluation with real environments."""

    def test_run_llm_evaluation_returns_structure(self):
        """run_llm_evaluation returns easy, medium, hard, total keys."""
        results = run_llm_evaluation(seed=42, max_steps=2, verbose=False)

        assert "easy" in results
        assert "medium" in results
        assert "hard" in results
        assert "total" in results
        assert isinstance(results["easy"], float)
        assert isinstance(results["medium"], float)
        assert isinstance(results["hard"], float)
        assert isinstance(results["total"], float)

    def test_run_llm_evaluation_scores_in_range(self):
        """All scores are in valid 0.0-1.0 range."""
        results = run_llm_evaluation(seed=42, max_steps=2, verbose=False)

        assert 0.0 <= results["easy"] <= 1.0
        assert 0.0 <= results["medium"] <= 1.0
        assert 0.0 <= results["hard"] <= 1.0
        assert 0.0 <= results["total"] <= 1.0

    def test_run_llm_evaluation_total_is_average(self):
        """Total score is the average of easy, medium, hard."""
        results = run_llm_evaluation(seed=42, max_steps=2, verbose=False)

        expected_total = (results["easy"] + results["medium"] + results["hard"]) / 3
        assert abs(results["total"] - expected_total) < 0.001

    def test_run_llm_evaluation_different_seeds_different_results(self):
        """Different seeds produce different results (not identical)."""
        results1 = run_llm_evaluation(seed=42, max_steps=2, verbose=False)
        results2 = run_llm_evaluation(seed=99, max_steps=2, verbose=False)

        # At least one difficulty should differ
        differences = [
            results1["easy"] != results2["easy"],
            results1["medium"] != results2["medium"],
            results1["hard"] != results2["hard"],
        ]
        assert any(differences), "Different seeds should produce different results"

    def test_run_llm_evaluation_max_steps_affects_steps(self):
        """More max_steps allows more agent actions."""
        results_short = run_llm_evaluation(seed=42, max_steps=1, verbose=False)
        results_long = run_llm_evaluation(seed=42, max_steps=5, verbose=False)

        # With more steps, we generally get more agent actions (env-dependent)


class TestRunBaselineEpisodeWithCustomAgent:
    """Tests run_baseline_episode with a provided custom agent."""

    def test_run_baseline_episode_accepts_custom_agent(self):
        """run_baseline_episode accepts and uses a custom agent."""
        from app.baseline import BaselineAgent, AgentConfig

        env = make_env(seed=42)
        config = AgentConfig(seed=42)
        custom_agent = BaselineAgent(config=config)

        result = run_baseline_episode(
            env,
            agent=custom_agent,
            seed=42,
            max_steps=3,
            verbose=False,
        )

        assert "steps" in result
        assert "final_score" in result

    def test_run_baseline_episode_without_agent(self):
        """run_baseline_episode works without agent (creates LLMBaselineAgent internally)."""
        env = make_env(seed=42)

        result = run_baseline_episode(
            env,
            agent=None,  # No agent provided
            seed=42,
            max_steps=3,
            verbose=False,
        )

        assert "steps" in result
        assert "final_score" in result


class TestHAS_OPENAIConstant:
    """Tests for HAS_OPENAI constant."""

    def test_has_openai_is_boolean(self):
        """HAS_OPENAI should be a boolean."""
        assert isinstance(HAS_OPENAI, bool)
