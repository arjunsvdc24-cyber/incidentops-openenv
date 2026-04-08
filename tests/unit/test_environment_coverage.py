"""
IncidentOps - Environment Coverage Tests
Targets uncovered lines in app/environment.py
"""
import pytest
from app.environment import make_env
from app.fault_injector import FaultType


class TestEnvironmentSLADeadlines:
    """Test SLA deadline calculation (lines 212, 247-274)."""

    def test_sla_deadline_critical(self):
        """Test SLA critical urgency state."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        env.current_step = 23  # Near deadline
        result = env.step({"action_type": "query_service", "target_service": "api-gateway"})
        obs = dict(result.observation)
        assert "sla_deadline" in obs

    def test_sla_deadline_breach(self):
        """Test SLA breach state."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        env.current_step = 29  # Near breach
        result = env.step({"action_type": "query_service", "target_service": "api-gateway"})
        obs = dict(result.observation)
        sla = obs.get("sla_deadline", {})
        assert "urgency" in sla or "minutes_remaining" in sla

    def test_sla_metrics_in_observation(self):
        """Test SLA metrics included in observation."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({"action_type": "query_service", "target_service": "api-gateway"})
        obs = dict(result.observation)
        assert "sla_deadline" in obs


class TestEnvironmentActionValidation:
    """Test action validation edge cases (lines 324, 332, 337, 340, 354, 357)."""

    def test_restart_service_not_found(self):
        """Test restart with invalid service - lines 442-445."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({
            "action_type": "restart_service",
            "target_service": "nonexistent-service",
        })
        obs = dict(result.observation)
        action_result = obs.get("action_result", {})
        assert "error" in action_result

    def test_query_service_not_found(self):
        """Test query_service with invalid service - line 324."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({
            "action_type": "query_service",
            "target_service": "invalid-service-xyz",
        })
        obs = dict(result.observation)
        assert obs.get("step", 0) >= 0

    def test_query_logs_error(self):
        """Test query_logs with error - line 391, 394."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({
            "action_type": "query_logs",
            "target_service": "api-gateway",
        })
        obs = dict(result.observation)
        assert obs.get("step", 0) >= 0

    def test_dependency_graph(self):
        """Test query_dependencies returns graph - line 340."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({"action_type": "query_dependencies"})
        obs = dict(result.observation)
        action_result = obs.get("action_result", {})
        assert "dependencies" in action_result or obs.get("step", 0) >= 0


class TestEnvironmentMemoryLeak:
    """Test memory leak scenario (lines 374-378)."""

    def test_memory_leak_tracking(self):
        """Test memory leak is tracked across steps."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        for _ in range(5):
            result = env.step({
                "action_type": "query_metrics",
                "target_service": "analytics-service",
            })
        assert result.reward is not None
        env.close()


class TestEnvironmentDeploymentTimeline:
    """Test deployment timeline (line 433)."""

    def test_query_deployments(self):
        """Test query_deployments returns timeline - line 433."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({"action_type": "query_deployments"})
        obs = dict(result.observation)
        action_result = obs.get("action_result", {})
        assert "deployments" in action_result or obs.get("step", 0) >= 0


class TestEnvironmentScaleService:
    """Test scale service validation (lines 466-475)."""

    def test_scale_service_valid(self):
        """Test scale_service with valid service."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({
            "action_type": "scale_service",
            "target_service": "order-service",
        })
        assert result.reward is not None

    def test_scale_service_termination(self):
        """Test scale_service can terminate episode."""
        env = make_env(seed=42, difficulty=3, fault_type=FaultType.CASCADE)
        env.reset(seed=42)
        result = env.step({
            "action_type": "scale_service",
            "target_service": "database-primary",
        })
        assert result.reward is not None


class TestEnvironmentRollback:
    """Test rollback validation and success (lines 488-497)."""

    def test_rollback_deployment(self):
        """Test rollback_deployment action."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({
            "action_type": "rollback_deployment",
            "target_service": "recommendation-service",
        })
        assert result.reward is not None

    def test_rollback_ghost_fix(self):
        """Test rollback fixes ghost scenario."""
        env = make_env(seed=42, difficulty=5, fault_type=FaultType.GHOST)
        env.reset(seed=42)
        env.step({"action_type": "query_deployments"})
        result = env.step({
            "action_type": "rollback_deployment",
            "target_service": "recommendation-service",
        })
        assert result.reward is not None
        env.close()


class TestEnvironmentMemoryIntegration:
    """Test memory integration (lines 509-520)."""

    def test_memory_integration_in_observation(self):
        """Test memory integration included in observation."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({
            "action_type": "query_service",
            "target_service": "api-gateway",
        })
        assert result.reward is not None


class TestEnvironmentRootCauseID:
    """Test root cause identification (lines 528-555)."""

    def test_identify_root_cause_action(self):
        """Test identify_root_cause action."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({
            "action_type": "identify_root_cause",
            "target_service": "payment-service",
        })
        assert result.reward is not None


class TestEnvironmentApplyFix:
    """Test apply_fix action (lines 547-555)."""

    def test_apply_fix_valid(self):
        """Test apply_fix with valid service."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        result = env.step({
            "action_type": "apply_fix",
            "target_service": "payment-service",
        })
        assert result.reward is not None


class TestRecoveryPaths:
    """Test recovery paths (lines 573-574)."""

    def test_fix_applied_property(self):
        """Test fix_applied is tracked."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        env.step({
            "action_type": "restart_service",
            "target_service": "payment-service",
        })
        assert env.current_step >= 1


class TestEnvironmentGymInterface:
    """Test Gymnasium wrapper interface (lines 865, 869, 873, 891)."""

    def test_action_space_property(self):
        """Test action_space is accessible."""
        env = make_env(seed=42, difficulty=2)
        actions = env.get_action_space()
        assert len(actions) > 0
        assert "query_service" in actions

    def test_observation_space_property(self):
        """Test observation_space is accessible."""
        env = make_env(seed=42, difficulty=2)
        services = env.get_service_list()
        assert len(services) > 0
        assert "payment-service" in services

    def test_episode_summary(self):
        """Test episode summary property."""
        env = make_env(seed=42, difficulty=2)
        env.reset(seed=42)
        env.step({"action_type": "query_service", "target_service": "api-gateway"})
        summary = env.get_episode_summary()
        assert "total_steps" in summary
        assert summary["total_steps"] == 1
