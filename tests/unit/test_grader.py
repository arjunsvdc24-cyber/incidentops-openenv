"""
IncidentOps - Unit Tests: Graders
"""
import pytest
from app.grader import grade_trajectory, DeepTrajectoryGrader, DetailedScore
from app.enhanced_grader import grade_trajectory_enhanced, EnhancedSREGrader
from app.human_sre_grader import grade_like_human_sre


def make_trajectory(fault_type="oom", root_cause="payment-service", correct_fix="restart_service:payment-service"):
    return {
        "id": "test_trajectory",
        "actions": [
            {"action_type": "query_service", "target_service": "api-gateway"},
            {"action_type": "query_logs", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
        ],
        "rewards": [0.1, 0.2, 0.5],
        "final_state": {"terminated": True},
        "scenario": {
            "fault_type": fault_type,
            "difficulty": 2,
            "root_cause_service": root_cause,
            "correct_fix": correct_fix,
        },
    }


class TestBasicGrader:
    def test_grade_returns_score(self):
        traj = make_trajectory()
        result = grade_trajectory(traj, seed=42)
        assert hasattr(result, "final_score")
        assert 0.0 <= result.final_score <= 1.0

    def test_grade_is_deterministic(self):
        traj = make_trajectory()
        r1 = grade_trajectory(traj, seed=42)
        r2 = grade_trajectory(traj, seed=42)
        assert r1.final_score == r2.final_score

    def test_empty_trajectory_grades(self):
        traj = {
            "actions": [],
            "rewards": [],
            "final_state": {},
            "scenario": {"fault_type": "oom", "difficulty": 2},
        }
        result = grade_trajectory(traj, seed=42)
        assert 0.0 <= result.final_score <= 1.0

    def test_detailed_score_fields(self):
        grader = DeepTrajectoryGrader(seed=42)
        traj = make_trajectory()
        detailed = grader.grade(traj)
        assert hasattr(detailed, "root_cause_score")
        assert hasattr(detailed, "fix_score")
        assert hasattr(detailed, "efficiency_score")


class TestExtendedScoringDimensions:
    """Tests for new extended scoring dimensions (v11.0)"""

    def test_new_score_fields_exist(self):
        """All new score fields should exist with default values"""
        grader = DeepTrajectoryGrader(seed=42)
        traj = make_trajectory()
        detailed = grader.grade(traj)
        assert hasattr(detailed, "reasoning_chain_score")
        assert hasattr(detailed, "mttr_score")
        assert hasattr(detailed, "action_ordering_score")
        assert hasattr(detailed, "slo_preservation_score")

    def test_reasoning_chain_full_credit(self):
        """Full reasoning chain should get high score"""
        traj = {
            "actions": [
                {"action_type": "query_metrics", "target_service": "payment-service"},
                {"action_type": "query_logs", "target_service": "payment-service"},
                {"action_type": "identify_root_cause", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": True},
            "scenario": {
                "fault_type": "oom",
                "root_cause_service": "payment-service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(traj)
        assert result.reasoning_chain_score > 0.5

    def test_reasoning_chain_cascade_fault(self):
        """Cascade faults should require dependency tracing"""
        traj = {
            "actions": [
                {"action_type": "query_dependencies", "target_service": "payment-service"},
                {"action_type": "identify_root_cause", "target_service": "database-primary"},
                {"action_type": "scale_service", "target_service": "database-primary"},
            ],
            "final_state": {"fix_applied": True},
            "scenario": {
                "fault_type": "cascade",
                "root_cause_service": "database-primary",
                "affected_services": ["payment-service"],
            },
        }
        result = grade_trajectory(traj)
        # Should get credit for tracing dependencies
        assert result.reasoning_chain_score >= 0.5

    def test_reasoning_chain_ghost_fault(self):
        """Ghost faults should check deployment history"""
        traj = {
            "actions": [
                {"action_type": "query_deployments", "target_service": "recommendation-service"},
                {"action_type": "query_metrics", "target_service": "recommendation-service"},
                {"action_type": "identify_root_cause", "target_service": "recommendation-service"},
                {"action_type": "rollback_deployment", "target_service": "recommendation-service"},
            ],
            "final_state": {"fix_applied": True},
            "scenario": {
                "fault_type": "ghost",
                "root_cause_service": "recommendation-service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(traj)
        # Should get credit for checking deployment history
        assert result.reasoning_chain_score >= 0.5

    def test_mttr_excellent_speed(self):
        """Fast resolution should get high MTTR score"""
        traj = {
            "actions": [
                {"action_type": "query_logs", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": True},
            "scenario": {
                "fault_type": "oom",
                "root_cause_service": "payment-service",
                "difficulty": 2,
            },
        }
        result = grade_trajectory(traj)
        assert result.mttr_score >= 0.8

    def test_mttr_unresolved(self):
        """Unresolved incidents should have low MTTR score"""
        traj = {
            "actions": [
                {"action_type": "query_logs", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": False},
            "scenario": {
                "fault_type": "oom",
                "root_cause_service": "payment-service",
                "difficulty": 2,
            },
        }
        result = grade_trajectory(traj)
        assert result.mttr_score < 0.3

    def test_action_ordering_relevant_first(self):
        """Investigating relevant services first should get high score"""
        traj = {
            "actions": [
                {"action_type": "query_logs", "target_service": "payment-service"},  # relevant first
                {"action_type": "query_logs", "target_service": "api-gateway"},  # then irrelevant
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": True},
            "scenario": {
                "fault_type": "oom",
                "root_cause_service": "payment-service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(traj)
        assert result.action_ordering_score >= 0.6

    def test_action_ordering_no_premature_actions(self):
        """No intervention before investigation should get high score"""
        traj = {
            "actions": [
                {"action_type": "query_logs", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": True},
            "scenario": {
                "fault_type": "oom",
                "root_cause_service": "payment-service",
            },
        }
        result = grade_trajectory(traj)
        assert result.action_ordering_score >= 0.5

    def test_action_ordering_premature_action(self):
        """Intervention before investigation should reduce score"""
        traj = {
            "actions": [
                {"action_type": "restart_service", "target_service": "payment-service"},  # premature
            ],
            "final_state": {"fix_applied": True},
            "scenario": {
                "fault_type": "oom",
                "root_cause_service": "payment-service",
            },
        }
        result = grade_trajectory(traj)
        assert result.action_ordering_score < 0.5

    def test_slo_preservation_critical_within_slo(self):
        """Critical incidents resolved quickly should get high SLO score"""
        traj = {
            "actions": [
                {"action_type": "query_logs", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": True},
            "scenario": {
                "fault_type": "ghost",
                "root_cause_service": "payment-service",
                "severity": "critical",
            },
        }
        result = grade_trajectory(traj)
        assert result.slo_preservation_score >= 0.8

    def test_slo_preservation_low_priority(self):
        """Low priority incidents have more time"""
        traj = {
            "actions": [
                {"action_type": "query_logs", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": True},
            "scenario": {
                "fault_type": "oom",
                "root_cause_service": "payment-service",
                "priority": "low",
            },
        }
        result = grade_trajectory(traj)
        assert result.slo_preservation_score >= 0.8

    def test_total_score_still_in_range(self):
        """Final score should always be between 0.0 and 1.0"""
        traj = make_trajectory()
        result = grade_trajectory(traj)
        assert 0.0 <= result.final_score <= 1.0

    def test_score_breakdown_sums_correctly(self):
        """Score breakdown should sum to final score"""
        traj = {
            "actions": [
                {"action_type": "query_metrics", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": True},
            "scenario": {
                "fault_type": "oom",
                "root_cause_service": "payment-service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(traj)
        # Raw score should equal the weighted sum (all sum to 1.00 exactly)
        expected_raw = (
            0.25 * result.root_cause_score +
            0.25 * result.fix_score +
            0.14 * result.efficiency_score +
            0.14 * result.minimal_disruption_score +
            0.06 * result.reasoning_chain_score +
            0.06 * result.mttr_score +
            0.06 * result.action_ordering_score +
            0.04 * result.slo_preservation_score
        )
        assert abs(result.raw_score - expected_raw) < 0.001


class TestEnhancedGrader:
    def test_enhanced_grade_returns_evaluation(self):
        traj = make_trajectory()
        result = grade_trajectory_enhanced(traj, traj["scenario"], seed=42)
        assert result is not None
        assert hasattr(result.breakdown, "final_score")

    def test_enhanced_score_range(self):
        traj = make_trajectory()
        result = grade_trajectory_enhanced(traj, traj["scenario"], seed=42)
        assert 0.0 <= result.breakdown.final_score <= 1.0

    def test_enhanced_has_reasoning_analysis(self):
        traj = make_trajectory()
        result = grade_trajectory_enhanced(traj, traj["scenario"], seed=42)
        assert hasattr(result, "reasoning_analysis")


class TestHumanSREGrader:
    def test_human_grader_returns_grade(self):
        traj = make_trajectory()
        result = grade_like_human_sre(traj, traj["scenario"], seed=42)
        assert result is not None
        assert 0.0 <= result.final_score <= 1.0

    def test_all_fault_types(self):
        for fault in ["oom", "cascade", "ghost"]:
            traj = make_trajectory(fault_type=fault)
            result = grade_like_human_sre(traj, traj["scenario"], seed=42)
            assert 0.0 <= result.final_score <= 1.0
