"""
IncidentOps - Unit Tests: Models
"""
import pytest
from pydantic import ValidationError
from app.models import (
    ActionType, StepRequest, StepResponse, VALID_SERVICES, RewardBreakdown
)


class TestActionType:
    def test_all_action_types_exist(self):
        assert ActionType.QUERY_SERVICE.value == "query_service"
        assert ActionType.QUERY_METRICS.value == "query_metrics"
        assert ActionType.QUERY_LOGS.value == "query_logs"
        assert ActionType.QUERY_DEPENDENCIES.value == "query_dependencies"
        assert ActionType.QUERY_DEPLOYMENTS.value == "query_deployments"
        assert ActionType.RESTART_SERVICE.value == "restart_service"
        assert ActionType.SCALE_SERVICE.value == "scale_service"
        assert ActionType.ROLLBACK_DEPLOYMENT.value == "rollback_deployment"
        assert ActionType.QUERY_MEMORY.value == "query_memory"
        assert ActionType.IDENTIFY_ROOT_CAUSE.value == "identify_root_cause"
        assert ActionType.APPLY_FIX.value == "apply_fix"

    def test_action_type_count(self):
        assert len(ActionType) == 11


class TestStepRequest:
    def test_valid_request(self):
        req = StepRequest(action_type="query_service", target_service="api-gateway")
        assert req.action_type == "query_service"
        assert req.target_service == "api-gateway"

    def test_invalid_action_type(self):
        with pytest.raises(ValidationError):
            StepRequest(action_type="invalid_action", target_service="api-gateway")

    def test_invalid_service(self):
        with pytest.raises(ValidationError):
            StepRequest(action_type="query_service", target_service="invalid-service")

    def test_service_required_for_query(self):
        with pytest.raises(ValidationError):
            StepRequest(action_type="query_service")

    def test_service_not_required_for_memory(self):
        req = StepRequest(action_type="query_memory")
        assert req.action_type == "query_memory"

    def test_parameters_optional(self):
        req = StepRequest(action_type="query_service", target_service="api-gateway", parameters={"key": "value"})
        assert req.parameters == {"key": "value"}

    def test_no_service_for_global_action(self):
        req = StepRequest(action_type="query_dependencies")
        assert req.action_type == "query_dependencies"


class TestValidServices:
    def test_all_15_services(self):
        assert len(VALID_SERVICES) == 15
        assert "api-gateway" in VALID_SERVICES
        assert "database-primary" in VALID_SERVICES
        assert "recommendation-service" in VALID_SERVICES

    def test_services_are_strings(self):
        for svc in VALID_SERVICES:
            assert isinstance(svc, str)
            assert len(svc) > 0


class TestRewardBreakdown:
    def test_default_values(self):
        rb = RewardBreakdown()
        assert rb.total == 0.0
        assert rb.health_improvement == 0.0

    def test_custom_values(self):
        rb = RewardBreakdown(
            health_improvement=0.5,
            latency_improvement=0.3,
            correct_investigation=0.2,
            total=1.0,
        )
        assert rb.total == 1.0
        assert rb.health_improvement == 0.5
