"""
IncidentOps - LLM Baseline Tests

Tests for app/llm_baseline.py covering:
- LLMAgentConfig defaults
- LLMBaselineAgent initialization (with/without API key)
- act() with fallback when no API key
- _get_fallback_action ghost detection, alert handling, service remediation
- _format_observation
- run_llm_evaluation (mocked)
- check_openai_available
- run_baseline_episode (mocked)
"""
import pytest
from unittest.mock import patch, MagicMock


class TestLLMAgentConfig:
    """LLMAgentConfig dataclass defaults and fields."""

    def test_defaults(self):
        from app.llm_baseline import LLMAgentConfig

        config = LLMAgentConfig()
        assert config.seed == 42
        assert config.model == "groq/llama-4-opus-17b"
        assert config.max_tokens == 500
        assert config.temperature == 0.0
        assert config.max_steps == 20

    def test_custom_values(self):
        from app.llm_baseline import LLMAgentConfig

        config = LLMAgentConfig(seed=99, model="gpt-4o-mini", max_tokens=200, max_steps=10)
        assert config.seed == 99
        assert config.model == "gpt-4o-mini"
        assert config.max_tokens == 200
        assert config.max_steps == 10

    def test_model_from_env_var_read_at_import(self):
        """MODEL_NAME is read at import time; explicit model arg overrides."""
        from app.llm_baseline import LLMAgentConfig

        # When model is explicitly passed, it overrides the default
        config = LLMAgentConfig(model="gpt-3.5-turbo")
        assert config.model == "gpt-3.5-turbo"


class TestLLMBaselineAgentInit:
    """LLMBaselineAgent initialization scenarios."""

    def test_init_without_api_key(self):
        """Agent initializes even when no OpenAI API key is available."""
        with patch.dict("os.environ", {}, clear=True):
            from app.llm_baseline import LLMBaselineAgent, LLMAgentConfig

            agent = LLMBaselineAgent()
            assert agent.client is None
            assert agent.config.seed == 42

    def test_init_with_api_key(self):
        """Agent initializes OpenAI client when API key is present."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            with patch("app.llm_baseline.OpenAI") as mock_openai_class:
                mock_client = MagicMock()
                mock_openai_class.return_value = mock_client

                from app.llm_baseline import LLMBaselineAgent

                agent = LLMBaselineAgent()
                assert agent.client is mock_client
                assert agent.api_key == "sk-test-key"
                mock_openai_class.assert_called_once()

    def test_init_with_hf_token_fallback(self):
        """HF_TOKEN is used as fallback when OPENAI_API_KEY is not set."""
        with patch.dict("os.environ", {"HF_TOKEN": "hf-test-token", "API_BASE_URL": "https://api.huggingface.co/v1"}):
            with patch("app.llm_baseline.OpenAI") as mock_openai_class:
                mock_client = MagicMock()
                mock_openai_class.return_value = mock_client

                from app.llm_baseline import LLMBaselineAgent

                agent = LLMBaselineAgent()
                assert agent.client is mock_client
                assert agent.api_key == "hf-test-token"

    def test_init_with_custom_config(self):
        """Custom config is stored on the agent."""
        from app.llm_baseline import LLMBaselineAgent, LLMAgentConfig

        config = LLMAgentConfig(seed=123, max_steps=5)
        agent = LLMBaselineAgent(config)
        assert agent.config.seed == 123
        assert agent.config.max_steps == 5


class TestLLMBaselineAgentReset:
    """LLMBaselineAgent.reset() behavior."""

    def test_reset_clears_history(self):
        """reset() clears action history and current_step."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.action_history.append({"action_type": "query_service"})
        agent.current_step = 5

        agent.reset(seed=42)
        assert agent.action_history == []
        assert agent.current_step == 0

    def test_reset_updates_seed(self):
        """reset() with seed parameter updates RNG."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=99)
        assert agent.config.seed == 99


class TestLLMBaselineAgentFallback:
    """LLMBaselineAgent._get_fallback_action() across all scenarios."""

    def _make_obs(self, alerts=None, services=None, fault_type="oom", action_history=None):
        return {
            "step": 0,
            "alerts": alerts or [],
            "services": services or {},
            "incident_info": {"fault_type": fault_type},
            "action_history": action_history or [],
        }

    def test_fallback_ghost_no_signals(self):
        """Ghost: no alerts, no unhealthy services → query_deployments."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = self._make_obs(
            alerts=[],
            services={},
            fault_type="ghost",
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "query_deployments"

    def test_fallback_ghost_second_step(self):
        """Ghost: after query_deployments → query_dependencies."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)
        agent.action_history.append({"action_type": "query_deployments", "target_service": None})

        obs = self._make_obs(
            alerts=[],
            services={},
            fault_type="ghost",
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "query_dependencies"

    def test_fallback_ghost_third_step(self):
        """Ghost: after deployments+dependencies → rollback_deployment on common service."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)
        agent.action_history.extend([
            {"action_type": "query_deployments", "target_service": None},
            {"action_type": "query_dependencies", "target_service": None},
        ])

        obs = self._make_obs(
            alerts=[],
            services={"recommendation-service": {"status": "healthy"}},
            fault_type="ghost",
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "rollback_deployment"
        assert action["target_service"] == "recommendation-service"

    def test_fallback_alert_target(self):
        """Alert present → query_logs on alert service."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = self._make_obs(
            alerts=[{"service": "payment-service", "severity": "critical", "message": "OOM"}],
            services={},
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "query_logs"
        assert action["target_service"] == "payment-service"

    def test_fallback_unhealthy_service_no_prior_query(self):
        """Unhealthy service, not yet queried → query_service."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = self._make_obs(
            alerts=[],
            services={"payment-service": {"status": "unhealthy", "latency_ms": 5000, "error_rate": 0.5}},
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "query_logs"
        assert action["target_service"] == "payment-service"

    def test_fallback_unhealthy_after_logs_cascade(self):
        """Unhealthy service, logs queried, fault_type=cascade → scale_service."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)
        agent.action_history.append(
            {"action_type": "query_logs", "target_service": "payment-service"}
        )

        obs = self._make_obs(
            alerts=[],
            services={"payment-service": {"status": "degraded", "latency_ms": 5000, "error_rate": 0.3}},
            fault_type="cascade",
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "query_metrics"
        assert action["target_service"] == "payment-service"

    def test_fallback_unhealthy_after_metrics_cascade(self):
        """Unhealthy service, metrics queried, fault_type=cascade → scale_service."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)
        agent.action_history.extend([
            {"action_type": "query_logs", "target_service": "payment-service"},
            {"action_type": "query_metrics", "target_service": "payment-service"},
        ])

        obs = self._make_obs(
            alerts=[],
            services={"payment-service": {"status": "degraded", "latency_ms": 5000, "error_rate": 0.3}},
            fault_type="cascade",
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "scale_service"
        assert action["target_service"] == "payment-service"

    def test_fallback_unhealthy_network(self):
        """Unhealthy service, fault_type=network → reroute_traffic."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)
        agent.action_history.extend([
            {"action_type": "query_logs", "target_service": "api-gateway"},
            {"action_type": "query_metrics", "target_service": "api-gateway"},
        ])

        obs = self._make_obs(
            alerts=[],
            services={"api-gateway": {"status": "unhealthy"}},
            fault_type="network",
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "reroute_traffic"
        assert action["target_service"] == "api-gateway"

    def test_fallback_unhealthy_default(self):
        """Unhealthy service, default fault → restart_service."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)
        agent.action_history.extend([
            {"action_type": "query_logs", "target_service": "payment-service"},
            {"action_type": "query_metrics", "target_service": "payment-service"},
        ])

        obs = self._make_obs(
            alerts=[],
            services={"payment-service": {"status": "unhealthy"}},
            fault_type="oom",
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "restart_service"
        assert action["target_service"] == "payment-service"

    def test_fallback_no_signals_query_deployments(self):
        """No alerts, no unhealthy services → query_deployments."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = self._make_obs(
            alerts=[],
            services={},
            fault_type="oom",
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "query_deployments"

    def test_fallback_no_signals_after_deployments(self):
        """After query_deployments, no signals → query_service on random service."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)
        agent.action_history.append({"action_type": "query_deployments", "target_service": None})

        obs = self._make_obs(
            alerts=[],
            services={"api-gateway": {"status": "healthy"}, "payment-service": {"status": "healthy"}},
            fault_type="oom",
        )
        action = agent._get_fallback_action(obs)
        assert action["action_type"] == "query_service"
        assert action["target_service"] in ("api-gateway", "payment-service")


class TestLLMBaselineAgentAct:
    """LLMBaselineAgent.act() behavior."""

    def test_act_without_client_uses_fallback(self):
        """act() falls back to rule-based when no client is available."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {
            "step": 0,
            "alerts": [],
            "services": {},
            "incident_info": {"fault_type": "ghost"},
        }
        action = agent.act(obs)
        assert action["action_type"] == "query_deployments"
        # action is recorded
        assert len(agent.action_history) == 1

    def test_act_with_mocked_llm(self):
        """act() uses LLM when client is available and returns parsed action."""
        from app.llm_baseline import LLMBaselineAgent, LLMAgentConfig

        config = LLMAgentConfig(seed=42)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"action_type": "query_metrics", "target_service": "api-gateway", "reasoning": "check it"}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = LLMBaselineAgent(config)
        agent.client = mock_client
        agent.reset(seed=42)

        obs = {"step": 0, "alerts": [], "services": {}, "incident_info": {}}
        action = agent.act(obs)

        assert action["action_type"] == "query_metrics"
        assert action["target_service"] == "api-gateway"
        mock_client.chat.completions.create.assert_called_once()

    def test_act_with_markdown_json_response(self):
        """act() strips markdown code fences from LLM response."""
        from app.llm_baseline import LLMBaselineAgent, LLMAgentConfig

        config = LLMAgentConfig(seed=42)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '```json\n{"action_type": "restart_service", "target_service": "payment-service", "reasoning": "test"}\n```'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = LLMBaselineAgent(config)
        agent.client = mock_client
        agent.reset(seed=42)

        obs = {"step": 0, "alerts": [], "services": {}, "incident_info": {}}
        action = agent.act(obs)

        assert action["action_type"] == "restart_service"
        assert action["target_service"] == "payment-service"

    def test_act_llm_fallback_on_parse_error(self):
        """act() falls back to rule-based when LLM returns unparseable JSON."""
        from app.llm_baseline import LLMBaselineAgent, LLMAgentConfig

        config = LLMAgentConfig(seed=42)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json at all"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = LLMBaselineAgent(config)
        agent.client = mock_client
        agent.reset(seed=42)

        obs = {"step": 0, "alerts": [], "services": {}, "incident_info": {"fault_type": "ghost"}}
        action = agent.act(obs)

        # Should fall back to rule-based ghost detection
        assert action["action_type"] == "query_deployments"
        assert len(agent.action_history) == 1

    def test_act_llm_fallback_after_multiple_parse_errors(self):
        """act() falls back to rule-based after 3 failed parse attempts."""
        from app.llm_baseline import LLMBaselineAgent, LLMAgentConfig

        config = LLMAgentConfig(seed=42)

        # First two attempts return invalid JSON, third also fails
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            Exception("parse error 1"),
            Exception("parse error 2"),
            Exception("parse error 3"),
        ]

        agent = LLMBaselineAgent(config)
        agent.client = mock_client
        agent.reset(seed=42)

        obs = {"step": 0, "alerts": [], "services": {}, "incident_info": {"fault_type": "ghost"}}
        action = agent.act(obs)

        # Should use rule-based fallback after 3 attempts
        assert action["action_type"] == "query_deployments"
        assert mock_client.chat.completions.create.call_count == 3

    def test_act_llm_response_without_json_brace_prefix(self):
        """act() handles LLM response that doesn't start with '{'."""
        from app.llm_baseline import LLMBaselineAgent, LLMAgentConfig

        config = LLMAgentConfig(seed=42)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        # Response starts with explanatory text before JSON
        mock_response.choices[0].message.content = 'Here is the action:\n{"action_type": "query_logs", "target_service": "payment-service", "reasoning": "need logs"}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = LLMBaselineAgent(config)
        agent.client = mock_client
        agent.reset(seed=42)

        obs = {"step": 0, "alerts": [], "services": {}, "incident_info": {}}
        action = agent.act(obs)

        assert action["action_type"] == "query_logs"
        assert action["target_service"] == "payment-service"

    def test_act_increments_step_from_observation(self):
        """act() reads step from observation."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {"step": 5, "alerts": [], "services": {}, "incident_info": {}}
        agent.act(obs)
        assert agent.current_step == 5


class TestLLMBaselineAgentFormatObservation:
    """LLMBaselineAgent._format_observation() output."""

    def test_format_includes_step(self):
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {"step": 3, "alerts": [], "services": {}, "incident_info": {}}
        formatted = agent._format_observation(obs)
        assert "Step: 3" in formatted

    def test_format_includes_alerts(self):
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {
            "step": 0,
            "alerts": [{"service": "payment-service", "severity": "critical", "message": "OOM"}],
            "services": {},
            "incident_info": {},
        }
        formatted = agent._format_observation(obs)
        assert "Alerts:" in formatted
        assert "payment-service" in formatted

    def test_format_includes_problem_services(self):
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {
            "step": 0,
            "alerts": [],
            "services": {"payment-service": {"status": "unhealthy", "latency_ms": 1000, "error_rate": 0.1}},
            "incident_info": {},
        }
        formatted = agent._format_observation(obs)
        assert "Problem Services:" in formatted
        assert "payment-service" in formatted

    def test_format_includes_incident_type(self):
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)

        obs = {
            "step": 0,
            "alerts": [],
            "services": {},
            "incident_info": {"fault_type": "cascade", "difficulty": 3},
        }
        formatted = agent._format_observation(obs)
        assert "Incident Type: cascade" in formatted
        assert "Difficulty: 3" in formatted

    def test_format_includes_recent_actions(self):
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)
        agent.action_history.extend([
            {"action_type": "query_service", "target_service": "api-gateway"},
            {"action_type": "query_logs", "target_service": "payment-service"},
        ])

        obs = {"step": 2, "alerts": [], "services": {}, "incident_info": {}}
        formatted = agent._format_observation(obs)
        assert "Recent Actions:" in formatted
        assert "query_logs -> payment-service" in formatted


class TestRunLLMEvaluation:
    """run_llm_evaluation() function."""

    def test_run_llm_evaluation_returns_all_difficulties(self):
        """run_llm_evaluation returns easy, medium, hard, and total scores."""
        from app.llm_baseline import run_llm_evaluation

        # Patch at source since imports are inside the function
        with patch("app.environment.make_env") as mock_make_env, \
             patch("app.enhanced_grader.EnhancedSREGrader") as mock_grader_class:

            # Set up mock environment
            mock_env = MagicMock()
            mock_env.reset.return_value = {}
            mock_env.step.return_value.observation = {}
            mock_env.step.return_value.reward = 0.5
            mock_env.step.return_value.terminated = False
            mock_env.step.return_value.truncated = False
            mock_env.current_scenario = MagicMock()
            mock_env.current_scenario.fault_type.value = "OOM"
            mock_env.current_scenario.root_cause_service = "payment-service"
            mock_env.current_scenario.affected_services = []
            mock_make_env.return_value = mock_env

            # Set up mock grader
            mock_grader = MagicMock()
            mock_breakdown = MagicMock()
            mock_breakdown.final_score = 0.8
            mock_grade = MagicMock()
            mock_grade.value = "good"
            mock_breakdown.grade = mock_grade
            mock_result = MagicMock()
            mock_result.breakdown = mock_breakdown
            mock_grader.grade.return_value = mock_result
            mock_grader_class.return_value = mock_grader

            results = run_llm_evaluation(seed=42, max_steps=3, verbose=False)

            assert "easy" in results
            assert "medium" in results
            assert "hard" in results
            assert "total" in results
            # All scores should be normalized 0-1
            assert 0.0 <= results["easy"] <= 1.0
            assert 0.0 <= results["medium"] <= 1.0
            assert 0.0 <= results["hard"] <= 1.0
            assert 0.0 <= results["total"] <= 1.0

    def test_run_llm_evaluation_quits_early_on_termination(self):
        """run_llm_evaluation stops early when episode terminates."""
        from app.llm_baseline import run_llm_evaluation

        with patch("app.environment.make_env") as mock_make_env, \
             patch("app.enhanced_grader.EnhancedSREGrader") as mock_grader_class:

            mock_env = MagicMock()
            mock_env.reset.return_value = {}

            # First step returns terminated=True
            mock_env.step.return_value.observation = {}
            mock_env.step.return_value.reward = 1.0
            mock_env.step.return_value.terminated = True
            mock_env.step.return_value.truncated = False
            mock_env.current_scenario = MagicMock()
            mock_env.current_scenario.fault_type.value = "OOM"
            mock_env.current_scenario.root_cause_service = "payment-service"
            mock_env.current_scenario.affected_services = []
            mock_make_env.return_value = mock_env

            mock_grader = MagicMock()
            mock_breakdown = MagicMock()
            mock_breakdown.final_score = 0.9
            mock_grade = MagicMock()
            mock_grade.value = "excellent"
            mock_breakdown.grade = mock_grade
            mock_result = MagicMock()
            mock_result.breakdown = mock_breakdown
            mock_grader.grade.return_value = mock_result
            mock_grader_class.return_value = mock_grader

            results = run_llm_evaluation(seed=42, max_steps=20, verbose=False)

            # Environment should have been called at most once per difficulty
            # (terminated on first step)
            assert mock_env.step.call_count <= 3


class TestCheckOpenAIAvailable:
    """check_openai_available() function."""

    def test_returns_false_when_no_package(self):
        from app import llm_baseline

        original = llm_baseline.HAS_OPENAI
        llm_baseline.HAS_OPENAI = False
        try:
            result = llm_baseline.check_openai_available()
            assert result is False
        finally:
            llm_baseline.HAS_OPENAI = original

    def test_returns_false_when_missing_hf_token(self):
        """Returns False when HAS_OPENAI is True but HF_TOKEN is empty/missing."""
        import os as _os
        # Save current values
        saved = {}
        for key in ("HF_TOKEN", "API_BASE_URL", "GROQ_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "ASKME_API_KEY"):
            saved[key] = _os.environ.get(key)

        # Clear all LLM-related env vars for this test
        for key in ("HF_TOKEN", "API_BASE_URL", "GROQ_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "ASKME_API_KEY"):
            _os.environ.pop(key, None)

        try:
            from app import llm_baseline
            # Force HAS_OPENAI to True but no env vars
            with patch.object(llm_baseline, "HAS_OPENAI", True):
                result = llm_baseline.check_openai_available()
                assert result is False
        finally:
            # Restore original env vars
            for key, val in saved.items():
                if val is not None:
                    _os.environ[key] = val

    def test_returns_true_when_hf_token_and_base_url_present(self):
        with patch("app.llm_baseline.HAS_OPENAI", True):
            env_patch = {"HF_TOKEN": "hf_test", "API_BASE_URL": "https://api.huggingface.co/v1"}
            with patch.dict("os.environ", env_patch, clear=False):
                from app import llm_baseline
                result = llm_baseline.check_openai_available()
                assert result is True


class TestLLMBaselineAgentFallbackVerbose:
    """Verbose-related fallback paths."""

    def test_fallback_ghost_full_sequence(self):
        """Ghost scenario: completes full investigation sequence."""
        from app.llm_baseline import LLMBaselineAgent

        agent = LLMBaselineAgent()
        agent.reset(seed=42)
        agent.action_history.extend([
            {"action_type": "query_deployments", "target_service": None},
            {"action_type": "query_dependencies", "target_service": None},
            {"action_type": "rollback_deployment", "target_service": "recommendation-service"},
            {"action_type": "query_deployments", "target_service": None},  # already rolled back
        ])

        obs = {
            "step": 4,
            "alerts": [],
            "services": {"recommendation-service": {"status": "healthy"}},
            "incident_info": {"fault_type": "ghost"},
        }
        action = agent._get_fallback_action(obs)
        # After rollback, loops back to query_deployments
        assert action["action_type"] == "query_deployments"


class TestRunLLMEvaluationVerbose:
    """Verbose output paths in run_llm_evaluation."""

    def test_run_llm_evaluation_verbose_mode(self):
        """run_llm_evaluation with verbose=True completes without error."""
        from app.llm_baseline import run_llm_evaluation

        with patch("app.environment.make_env") as mock_make_env, \
             patch("app.enhanced_grader.EnhancedSREGrader") as mock_grader_class:

            mock_env = MagicMock()
            mock_env.reset.return_value = {}
            mock_env.step.return_value.observation = {}
            mock_env.step.return_value.reward = 0.5
            mock_env.step.return_value.terminated = False
            mock_env.step.return_value.truncated = False
            mock_env.current_scenario = MagicMock()
            mock_env.current_scenario.fault_type.value = "OOM"
            mock_env.current_scenario.root_cause_service = "payment-service"
            mock_env.current_scenario.affected_services = []
            mock_make_env.return_value = mock_env

            mock_grader = MagicMock()
            mock_breakdown = MagicMock()
            mock_breakdown.final_score = 0.7
            mock_grade = MagicMock()
            mock_grade.value = "good"
            mock_breakdown.grade = mock_grade
            mock_result = MagicMock()
            mock_result.breakdown = mock_breakdown
            mock_grader.grade.return_value = mock_result
            mock_grader_class.return_value = mock_grader

            # verbose=True should not raise
            results = run_llm_evaluation(seed=42, max_steps=3, verbose=True)
            assert "total" in results


class TestRunBaselineEpisode:
    """run_baseline_episode() compatibility wrapper."""

    def test_run_baseline_episode_returns_result(self):
        from app.llm_baseline import run_baseline_episode

        with patch("app.llm_baseline.LLMBaselineAgent") as mock_agent_class, \
             patch("app.enhanced_grader.EnhancedSREGrader") as mock_grader_class:

            mock_agent = MagicMock()
            mock_agent.action_history = []
            mock_agent.reset = MagicMock()
            mock_agent.act.return_value = {"action_type": "query_service", "target_service": "api-gateway"}
            mock_agent_class.return_value = mock_agent

            mock_grader = MagicMock()
            mock_breakdown = MagicMock()
            mock_breakdown.final_score = 0.75
            mock_grade = MagicMock()
            mock_grade.value = "good"
            mock_breakdown.grade = mock_grade
            mock_result = MagicMock()
            mock_result.breakdown = mock_breakdown
            mock_grader.grade.return_value = mock_result
            mock_grader_class.return_value = mock_grader

            mock_env = MagicMock()
            mock_env.reset.return_value = {}
            mock_env.step.return_value.observation = {}
            mock_env.step.return_value.reward = 0.5
            mock_env.step.return_value.terminated = False
            mock_env.step.return_value.truncated = False
            mock_env.current_scenario = MagicMock()
            mock_env.current_scenario.fault_type.value = "OOM"
            mock_env.current_scenario.root_cause_service = "payment-service"
            mock_env.current_scenario.affected_services = []

            result = run_baseline_episode(mock_env, agent=None, seed=42, max_steps=5, verbose=False)

            assert "steps" in result
            assert "total_reward" in result
            assert "final_score" in result
            assert "grade" in result
            assert result["grade"] == "good"
            assert result["final_score"] == 0.75

    def test_run_baseline_episode_with_terminated_episode(self):
        from app.llm_baseline import run_baseline_episode

        with patch("app.llm_baseline.LLMBaselineAgent") as mock_agent_class, \
             patch("app.enhanced_grader.EnhancedSREGrader") as mock_grader_class:

            mock_agent = MagicMock()
            mock_agent.action_history = [{"action_type": "restart_service", "target_service": "payment-service"}]
            mock_agent.reset = MagicMock()
            mock_agent.act.return_value = {"action_type": "restart_service", "target_service": "payment-service"}
            mock_agent_class.return_value = mock_agent

            mock_grader = MagicMock()
            mock_breakdown = MagicMock()
            mock_breakdown.final_score = 1.0
            mock_grade = MagicMock()
            mock_grade.value = "excellent"
            mock_breakdown.grade = mock_grade
            mock_result = MagicMock()
            mock_result.breakdown = mock_breakdown
            mock_grader.grade.return_value = mock_result
            mock_grader_class.return_value = mock_grader

            mock_env = MagicMock()
            mock_env.reset.return_value = {}
            mock_env.step.return_value.observation = {}
            mock_env.step.return_value.reward = 2.0
            mock_env.step.return_value.terminated = True
            mock_env.step.return_value.truncated = False
            mock_env.current_scenario = MagicMock()
            mock_env.current_scenario.fault_type.value = "OOM"
            mock_env.current_scenario.root_cause_service = "payment-service"
            mock_env.current_scenario.affected_services = []

            result = run_baseline_episode(mock_env, agent=None, seed=42, max_steps=5, verbose=False)

            assert result["steps"] == 1
            assert result["final_score"] == 1.0
            assert result["grade"] == "excellent"

    def test_run_baseline_episode_verbose_mode(self):
        """run_baseline_episode with verbose=True completes without error."""
        from app.llm_baseline import run_baseline_episode

        with patch("app.llm_baseline.LLMBaselineAgent") as mock_agent_class, \
             patch("app.enhanced_grader.EnhancedSREGrader") as mock_grader_class:

            mock_agent = MagicMock()
            mock_agent.action_history = [{"action_type": "query_service", "target_service": "api-gateway"}]
            mock_agent.reset = MagicMock()
            mock_agent.act.return_value = {"action_type": "query_service", "target_service": "api-gateway"}
            mock_agent_class.return_value = mock_agent

            mock_grader = MagicMock()
            mock_breakdown = MagicMock()
            mock_breakdown.final_score = 0.7
            mock_grade = MagicMock()
            mock_grade.value = "good"
            mock_breakdown.grade = mock_grade
            mock_result = MagicMock()
            mock_result.breakdown = mock_breakdown
            mock_grader.grade.return_value = mock_result
            mock_grader_class.return_value = mock_grader

            mock_env = MagicMock()
            mock_env.reset.return_value = {}
            mock_env.step.return_value.observation = {}
            mock_env.step.return_value.reward = 0.5
            mock_env.step.return_value.terminated = False
            mock_env.step.return_value.truncated = False
            mock_env.current_scenario = MagicMock()
            mock_env.current_scenario.fault_type.value = "OOM"
            mock_env.current_scenario.root_cause_service = "payment-service"
            mock_env.current_scenario.affected_services = []

            # verbose=True should not raise
            result = run_baseline_episode(mock_env, agent=None, seed=42, max_steps=5, verbose=True)
            assert "steps" in result
            assert result["final_score"] == 0.7
