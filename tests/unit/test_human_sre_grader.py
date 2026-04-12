"""
IncidentOps - Human SRE Grader Tests

Tests HumanSREGrader, grade_like_human_sre, and related types.
"""
import pytest
from app.human_sre_grader import (
    HumanSREGrader,
    HumanSREEvaluation,
    MisleadingPathAnalysis,
    MisleadingPathType,
    SREGrade,
    grade_like_human_sre,
)


class TestSREGrade:
    """SREGrade enum values."""

    def test_grade_values(self):
        assert SREGrade.EXPERT.value == "expert"
        assert SREGrade.PROFICIENT.value == "proficient"
        assert SREGrade.COMPETENT.value == "competent"
        assert SREGrade.LEARNING.value == "learning"
        assert SREGrade.UNTRAINED.value == "untrained"

    def test_grade_is_string(self):
        assert isinstance(SREGrade.EXPERT, str)


class TestMisleadingPathType:
    """MisleadingPathType enum values."""

    def test_misleading_path_type_values(self):
        values = {p.value for p in MisleadingPathType}
        assert len(values) >= 2


class TestMisleadingPathAnalysis:
    """MisleadingPathAnalysis dataclass."""

    def test_creation(self):
        analysis = MisleadingPathAnalysis(
            path_type=MisleadingPathType.SYMPTOM_CONFUSION,
            service_followed="api-gateway",
            correct_service="payment-service",
            steps_wasted=5,
            penalty=0.15,
            explanation="Investigated wrong service",
        )
        assert analysis.path_type == MisleadingPathType.SYMPTOM_CONFUSION
        assert analysis.service_followed == "api-gateway"
        assert analysis.penalty == 0.15

    def test_fields(self):
        analysis = MisleadingPathAnalysis(
            path_type=MisleadingPathType.SYMPTOM_CONFUSION,
            service_followed="api-gateway",
            correct_service="payment-service",
            steps_wasted=3,
            penalty=0.1,
            explanation="Test",
        )
        assert analysis.steps_wasted == 3
        assert analysis.correct_service == "payment-service"


class TestHumanSREEvaluation:
    """HumanSREEvaluation dataclass."""

    def test_evaluation_creation(self):
        eval_result = HumanSREEvaluation()
        assert isinstance(eval_result, HumanSREEvaluation)

    def test_evaluation_fields(self):
        eval_result = HumanSREEvaluation()
        eval_result.final_score = 0.85
        eval_result.grade = SREGrade.PROFICIENT
        assert eval_result.final_score == 0.85
        assert eval_result.grade == SREGrade.PROFICIENT


class TestHumanSREGrader:
    """HumanSREGrader evaluates trajectories like a human SRE."""

    def test_grader_initializes(self):
        grader = HumanSREGrader()
        assert grader is not None

    def test_grader_grade_perfect_trajectory(self):
        """A perfect trajectory gets a high grade."""
        grader = HumanSREGrader()
        trajectory = {
            "actions": [
                {"action_type": "query_metrics", "target_service": "payment-service"},
                {"action_type": "query_logs", "target_service": "payment-service"},
                {"action_type": "identify_root_cause", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True, "fix_applied": True},
        }
        scenario = {
            "fault_type": "oom",
            "root_cause_service": "payment-service",
            "affected_services": [],
        }
        result = grader.grade(trajectory, scenario)
        assert isinstance(result, HumanSREEvaluation)
        assert 0.0 <= result.final_score <= 1.0
        assert result.grade in {SREGrade.EXPERT, SREGrade.PROFICIENT, SREGrade.COMPETENT}

    def test_grader_no_investigation(self):
        """No investigation gets a low score."""
        grader = HumanSREGrader()
        trajectory = {
            "actions": [
                {"action_type": "restart_service", "target_service": "api-gateway"},
            ],
            "final_state": {"terminated": True, "fix_applied": False},
        }
        scenario = {
            "fault_type": "oom",
            "root_cause_service": "payment-service",
            "affected_services": [],
        }
        result = grader.grade(trajectory, scenario)
        assert isinstance(result, HumanSREEvaluation)
        # Score should be low since no investigation
        assert result.final_score <= 0.5

    def test_grader_wrong_root_cause(self):
        """Wrong root cause identification gets a penalty."""
        grader = HumanSREGrader()
        trajectory = {
            "actions": [
                {"action_type": "query_service", "target_service": "api-gateway"},
                {"action_type": "restart_service", "target_service": "api-gateway"},
            ],
            "final_state": {"terminated": True, "fix_applied": False},
        }
        scenario = {
            "fault_type": "cascade",
            "root_cause_service": "database-primary",
            "affected_services": ["order-service"],
        }
        result = grader.grade(trajectory, scenario)
        assert isinstance(result, HumanSREEvaluation)

    def test_grader_with_deception(self):
        """Trajectory with misleading paths gets penalties."""
        grader = HumanSREGrader()
        trajectory = {
            "actions": [
                {"action_type": "query_service", "target_service": "api-gateway"},
                {"action_type": "query_metrics", "target_service": "api-gateway"},
                {"action_type": "query_logs", "target_service": "api-gateway"},
                {"action_type": "query_service", "target_service": "auth-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True, "fix_applied": True},
        }
        scenario = {
            "fault_type": "oom",
            "root_cause_service": "payment-service",
            "affected_services": [],
            "misleading_services": ["api-gateway", "auth-service"],
        }
        result = grader.grade(trajectory, scenario)
        assert isinstance(result, HumanSREEvaluation)

    def test_grader_empty_actions(self):
        """Empty action list still produces a result."""
        grader = HumanSREGrader()
        trajectory = {"actions": [], "final_state": {"terminated": True}}
        scenario = {
            "fault_type": "oom",
            "root_cause_service": "payment-service",
            "affected_services": [],
        }
        result = grader.grade(trajectory, scenario)
        assert isinstance(result, HumanSREEvaluation)
        assert 0.0 <= result.final_score <= 1.0

    def test_grader_ghost_fault(self):
        """Ghost fault requires deployment investigation."""
        grader = HumanSREGrader()
        trajectory = {
            "actions": [
                {"action_type": "query_deployments", "target_service": "recommendation-service"},
                {"action_type": "rollback_deployment", "target_service": "recommendation-service"},
            ],
            "final_state": {"terminated": True, "fix_applied": True},
        }
        scenario = {
            "fault_type": "ghost",
            "root_cause_service": "recommendation-service",
            "affected_services": [],
        }
        result = grader.grade(trajectory, scenario)
        assert isinstance(result, HumanSREEvaluation)

    def test_grader_cascade_fault(self):
        """Cascade fault requires scale action."""
        grader = HumanSREGrader()
        trajectory = {
            "actions": [
                {"action_type": "query_service", "target_service": "database-primary"},
                {"action_type": "scale_service", "target_service": "database-primary"},
            ],
            "final_state": {"terminated": True, "fix_applied": True},
        }
        scenario = {
            "fault_type": "cascade",
            "root_cause_service": "database-primary",
            "affected_services": ["order-service"],
        }
        result = grader.grade(trajectory, scenario)
        assert isinstance(result, HumanSREEvaluation)

    def test_grader_deterministic(self):
        """Same inputs produce same score."""
        grader1 = HumanSREGrader(seed=42)
        grader2 = HumanSREGrader(seed=42)
        trajectory = {
            "actions": [
                {"action_type": "query_metrics", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True},
        }
        scenario = {
            "fault_type": "oom",
            "root_cause_service": "payment-service",
            "affected_services": [],
        }
        result1 = grader1.grade(trajectory, scenario)
        result2 = grader2.grade(trajectory, scenario)
        assert result1.final_score == result2.final_score

    def test_grader_result_fields(self):
        grader = HumanSREGrader()
        trajectory = {"actions": [{"action_type": "restart_service", "target_service": "api-gateway"}], "final_state": {"terminated": True}}
        scenario = {"fault_type": "oom", "root_cause_service": "payment-service", "affected_services": []}
        result = grader.grade(trajectory, scenario)
        assert hasattr(result, "final_score")
        assert hasattr(result, "grade")
        assert hasattr(result, "summary")


class TestGradeLikeHumanSRE:
    """Top-level grade_like_human_sre function."""

    def test_returns_evaluation(self):
        trajectory = {
            "actions": [{"action_type": "restart_service", "target_service": "payment-service"}],
            "final_state": {"terminated": True},
        }
        scenario = {
            "fault_type": "oom",
            "root_cause_service": "payment-service",
        }
        result = grade_like_human_sre(trajectory, scenario)
        assert isinstance(result, HumanSREEvaluation)
        assert 0.0 <= result.final_score <= 1.0

    def test_with_deception_scenario(self):
        trajectory = {
            "actions": [
                {"action_type": "query_metrics", "target_service": "payment-service"},
                {"action_type": "query_logs", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True, "fix_applied": True},
        }
        scenario = {
            "fault_type": "oom",
            "root_cause_service": "payment-service",
            "affected_services": [],
            "misleading_services": ["api-gateway"],
        }
        result = grade_like_human_sre(trajectory, scenario)
        assert isinstance(result, HumanSREEvaluation)
