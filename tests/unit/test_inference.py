"""
IncidentOps - Inference Script Tests
"""
import os
import pytest
import io
import sys
from unittest.mock import patch, MagicMock

# Set mock API key before importing inference module
os.environ["OPENAI_API_KEY"] = "test-key-for-unit-tests"

# Now import after env is set
from inference import log_start, log_step, log_end, parse_action, TASKS, run_task, BENCHMARK, MODEL_NAME

# Restore original environment after import to avoid polluting other tests
_original_openai_key = os.environ.pop("OPENAI_API_KEY", None)


class TestInferenceFormat:
    """Verify stdout format matches rules spec."""

    def test_log_start_format(self):
        old = sys.stdout
        out = io.StringIO()
        sys.stdout = out
        try:
            log_start("oom_crash", "gpt-4o")
        finally:
            sys.stdout = old
        line = out.getvalue().strip()
        assert line == "[START] task=oom_crash env=incidentops model=gpt-4o", f"Got: {repr(line)}"

    def test_log_step_format(self):
        old = sys.stdout
        out = io.StringIO()
        sys.stdout = out
        try:
            log_step(1, "restart payment-service", 0.5, False, None)
        finally:
            sys.stdout = old
        line = out.getvalue().strip()
        # Should be ONE space after [STEP], not two
        assert line == "[STEP] step=1 action=restart payment-service reward=0.50 done=false error=null", f"Got: {repr(line)}"

    def test_log_step_with_error(self):
        old = sys.stdout
        out = io.StringIO()
        sys.stdout = out
        try:
            log_step(2, "restart api-gateway", 0.0, False, "Service not found")
        finally:
            sys.stdout = old
        line = out.getvalue().strip()
        assert "error=Service not found" in line
        assert "step=2" in line

    def test_log_end_format(self):
        old = sys.stdout
        out = io.StringIO()
        sys.stdout = out
        try:
            log_end(True, 5, 0.85, [0.1, 0.2, 0.5, 0.5, 0.5])
        finally:
            sys.stdout = old
        line = out.getvalue().strip()
        # Should be THREE spaces after [END]
        assert line == "[END] success=true steps=5 score=0.850 rewards=0.10,0.20,0.50,0.50,0.50", f"Got: {repr(line)}"


class TestParseAction:
    """parse_action utility function."""

    def test_parse_query_service(self):
        result = parse_action("query_metrics payment-service")
        assert result["action_type"] == "query_metrics"
        assert result["target_service"] == "payment-service"

    def test_parse_restart(self):
        result = parse_action("restart payment-service")
        assert result["action_type"] == "restart_service"

    def test_parse_done(self):
        result = parse_action("DONE")
        assert result["action_type"] == "DONE"

    def test_parse_rollback(self):
        result = parse_action("rollback recommendation-service")
        assert result["action_type"] == "rollback_deployment"


class TestInferenceIntegration:
    """Full inference run with mocked LLM."""

    @patch("inference.make_env")
    @patch("inference.FaultType", return_value="oom")
    def test_run_task_mocked_llm(self, mock_fault_type, mock_make_env):
        import asyncio

        # Create a mock environment
        mock_env = MagicMock()
        mock_env.reset.return_value = {
            "incident_info": {"fault_type": "oom", "difficulty": 2},
            "services": {"payment-service": {"status": "unhealthy"}},
            "alerts": [],
            "action_result": {},
            "business_impact": {},
            "sla_deadline": {},
            "fix_applied": False,
        }
        mock_result = MagicMock()
        mock_result.observation = mock_env.reset.return_value
        mock_result.reward = 0.5
        mock_result.terminated = False
        mock_result.truncated = False
        mock_env.step.return_value = mock_result
        mock_make_env.return_value = mock_env

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "restart payment-service"
        mock_client.chat.completions.create.return_value = mock_response

        task = {"task_id": "oom_crash", "fault_type": "oom", "difficulty": 2}

        async def run():
            result = await run_task(mock_client, task, seed=42)
            return result

        result = asyncio.run(run())
        assert "task_id" in result
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0
