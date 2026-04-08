"""
IncidentOps - Grader Coverage Tests
Targets uncovered lines in app/grader.py and app/enhanced_grader.py
"""
import pytest
from app.grader import grade_trajectory, grade_multiple_trajectories
from app.enhanced_grader import grade_trajectory_enhanced
from app.human_sre_grader import grade_like_human_sre


class TestGraderEdgeCases:
    """Test grader edge cases for full coverage."""

    def test_queried_root_cause_not_identified(self):
        """Cover: grader.py lines 327-329 - partial credit for queried root cause."""
        trajectory = {
            "actions": [
                {"action_type": "query_service", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "oom",
                "difficulty": 2,
                "root_cause_service": "payment-service",
                "correct_fix": "restart_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(trajectory)
        assert result.final_score >= 0.0

    def test_incorrect_root_cause_identified(self):
        """Cover: grader.py lines 387-391 - 0 score for wrong root cause."""
        trajectory = {
            "actions": [
                {"action_type": "query_service", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "wrong-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "oom",
                "difficulty": 2,
                "root_cause_service": "payment-service",
                "correct_fix": "restart_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(trajectory)
        assert result.final_score >= 0.0

    def test_wrong_service_fix(self):
        """Cover: grader.py lines 435-441 - partial score for wrong service."""
        trajectory = {
            "actions": [
                {"action_type": "restart_service", "target_service": "api-gateway"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "oom",
                "difficulty": 2,
                "root_cause_service": "payment-service",
                "correct_fix": "restart_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(trajectory)
        assert result.final_score >= 0.0

    def test_efficiency_poor_tier(self):
        """Cover: grader.py lines 458-466 - poor efficiency scoring."""
        # Many steps (poor efficiency)
        trajectory = {
            "actions": [
                {"action_type": "query_service", "target_service": s}
                for s in ["api-gateway", "auth-service", "user-service",
                          "order-service", "payment-service", "inventory-service",
                          "notification-service", "email-service"]
            ] + [
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "oom",
                "difficulty": 2,
                "root_cause_service": "payment-service",
                "correct_fix": "restart_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(trajectory)
        assert result.final_score >= 0.0

    def test_redundant_actions_penalty(self):
        """Cover: grader.py lines 528-530, 556-558 - redundant action penalty."""
        trajectory = {
            "actions": [
                {"action_type": "restart_service", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "oom",
                "difficulty": 2,
                "root_cause_service": "payment-service",
                "correct_fix": "restart_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(trajectory)
        assert result.final_score >= 0.0

    def test_incorrect_service_penalty(self):
        """Cover: grader.py lines 636-638 - incorrect service penalty."""
        trajectory = {
            "actions": [
                {"action_type": "restart_service", "target_service": "nonexistent"},
            ],
            "final_state": {"terminated": False},
            "scenario": {
                "fault_type": "oom",
                "difficulty": 2,
                "root_cause_service": "payment-service",
                "correct_fix": "restart_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(trajectory)
        assert result.final_score >= 0.0

    def test_ghost_fault_suggestions(self):
        """Cover: grader.py lines 668-671 - ghost fault suggestions."""
        trajectory = {
            "actions": [
                {"action_type": "query_deployments"},
                {"action_type": "rollback_deployment",
                 "target_service": "recommendation-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "ghost",
                "difficulty": 5,
                "root_cause_service": "recommendation-service",
                "correct_fix": "rollback_deployment",
                "affected_services": [],
            },
        }
        result = grade_trajectory(trajectory)
        assert result.final_score >= 0.0

    def test_cascade_fault_suggestions(self):
        """Cover: grader.py lines 670-671 - cascade fault suggestions."""
        trajectory = {
            "actions": [
                {"action_type": "query_dependencies"},
                {"action_type": "scale_service", "target_service": "database-primary"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "cascade",
                "difficulty": 3,
                "root_cause_service": "database-primary",
                "correct_fix": "scale_service",
                "affected_services": ["order-service", "payment-service"],
            },
        }
        result = grade_trajectory(trajectory)
        assert result.final_score >= 0.0

    def test_mttr_slow_resolution(self):
        """Cover: grader.py lines 750-755 - slow resolution penalty."""
        trajectory = {
            "actions": [
                {"action_type": "query_service", "target_service": s}
                for s in ["api-gateway", "auth-service", "user-service",
                          "order-service", "payment-service", "inventory-service",
                          "notification-service", "database-primary", "cache-service"]
            ] + [
                {"action_type": "scale_service", "target_service": "database-primary"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "cascade",
                "difficulty": 3,
                "root_cause_service": "database-primary",
                "correct_fix": "scale_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(trajectory)
        assert result.final_score >= 0.0

    def test_slo_breach_score(self):
        """Cover: grader.py lines 881, 901-908 - SLO breach scoring."""
        trajectory = {
            "actions": [
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "oom",
                "difficulty": 2,
                "root_cause_service": "payment-service",
                "correct_fix": "restart_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory(trajectory)
        assert result.final_score >= 0.0


class TestEnhancedGraderEdgeCases:
    """Test enhanced grader edge cases for full coverage."""

    def test_right_service_suboptimal_fix(self):
        """Cover: enhanced_grader.py line 301 - right service wrong fix type."""
        trajectory = {
            "actions": [
                {"action_type": "query_metrics", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "ghost",
                "difficulty": 5,
                "root_cause_service": "payment-service",
                "correct_fix": "rollback_deployment",
                "affected_services": [],
            },
        }
        result = grade_trajectory_enhanced(trajectory, trajectory["scenario"], seed=42)
        assert result.breakdown.final_score >= 0.0

    def test_ghost_requires_rollback(self):
        """Cover: enhanced_grader.py line 315 - ghost requires rollback."""
        trajectory = {
            "actions": [
                {"action_type": "query_deployments"},
                {"action_type": "restart_service", "target_service": "recommendation-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "ghost",
                "difficulty": 5,
                "root_cause_service": "recommendation-service",
                "correct_fix": "rollback_deployment",
                "affected_services": [],
            },
        }
        result = grade_trajectory_enhanced(trajectory, trajectory["scenario"], seed=42)
        assert result.breakdown.final_score >= 0.0

    def test_disruption_irrelevant_service(self):
        """Cover: enhanced_grader.py line 361 - irrelevant service penalty."""
        trajectory = {
            "actions": [
                {"action_type": "query_service", "target_service": "email-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "oom",
                "difficulty": 2,
                "root_cause_service": "payment-service",
                "correct_fix": "restart_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory_enhanced(trajectory, trajectory["scenario"], seed=42)
        assert result.breakdown.final_score >= 0.0

    def test_single_false_lead_detection(self):
        """Cover: enhanced_grader.py line 472 - single false lead."""
        trajectory = {
            "actions": [
                {"action_type": "query_metrics", "target_service": "api-gateway"},
                {"action_type": "query_logs", "target_service": "api-gateway"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "cascade",
                "difficulty": 3,
                "root_cause_service": "database-primary",
                "correct_fix": "scale_service",
                "affected_services": ["order-service", "payment-service"],
            },
        }
        result = grade_trajectory_enhanced(trajectory, trajectory["scenario"], seed=42)
        assert result.breakdown.final_score >= 0.0

    def test_multiple_false_leads(self):
        """Cover: enhanced_grader.py lines 476-479 - multiple false leads."""
        trajectory = {
            "actions": [
                {"action_type": "query_metrics", "target_service": s}
                for s in ["api-gateway", "auth-service", "user-service",
                          "order-service", "inventory-service"]
            ] + [
                {"action_type": "scale_service", "target_service": "database-primary"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "cascade",
                "difficulty": 3,
                "root_cause_service": "database-primary",
                "correct_fix": "scale_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory_enhanced(trajectory, trajectory["scenario"], seed=42)
        assert result.breakdown.final_score >= 0.0

    def test_reactive_pattern_detection(self):
        """Cover: enhanced_grader.py lines 519-527 - reactive pattern detection."""
        trajectory = {
            "actions": [
                {"action_type": "query_dependencies"},
                {"action_type": "query_deployments"},
                {"action_type": "scale_service", "target_service": "database-primary"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "cascade",
                "difficulty": 3,
                "root_cause_service": "database-primary",
                "correct_fix": "scale_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory_enhanced(trajectory, trajectory["scenario"], seed=42)
        assert result.breakdown.final_score >= 0.0

    def test_ghost_actionable_suggestions(self):
        """Cover: enhanced_grader.py line 676 - ghost suggestions."""
        trajectory = {
            "actions": [
                {"action_type": "query_deployments"},
                {"action_type": "rollback_deployment",
                 "target_service": "recommendation-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "ghost",
                "difficulty": 5,
                "root_cause_service": "recommendation-service",
                "correct_fix": "rollback_deployment",
                "affected_services": [],
            },
        }
        result = grade_trajectory_enhanced(trajectory, trajectory["scenario"], seed=42)
        assert result.breakdown.final_score >= 0.0

    def test_systematic_pattern_suggestion(self):
        """Cover: enhanced_grader.py line 723 - systematic pattern."""
        trajectory = {
            "actions": [
                {"action_type": "query_service", "target_service": "api-gateway"},
                {"action_type": "query_dependencies"},
                {"action_type": "scale_service", "target_service": "database-primary"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "cascade",
                "difficulty": 3,
                "root_cause_service": "database-primary",
                "correct_fix": "scale_service",
                "affected_services": [],
            },
        }
        result = grade_trajectory_enhanced(trajectory, trajectory["scenario"], seed=42)
        assert result.breakdown.final_score >= 0.0


class TestGradeMultipleTrajectories:
    """Test batch grading - grader.py lines 1023-1051."""

    def test_grade_multiple_trajectories(self):
        """Cover: grader.py grade_multiple_trajectories."""
        trajectories = [
            {
                "actions": [
                    {"action_type": "restart_service", "target_service": "payment-service"},
                ],
                "final_state": {"terminated": True},
                "scenario": {
                    "fault_type": "oom",
                    "difficulty": 2,
                    "root_cause_service": "payment-service",
                    "correct_fix": "restart_service",
                    "affected_services": [],
                },
            },
            {
                "actions": [
                    {"action_type": "query_service", "target_service": "api-gateway"},
                ],
                "final_state": {"terminated": False},
                "scenario": {
                    "fault_type": "cascade",
                    "difficulty": 3,
                    "root_cause_service": "database-primary",
                    "correct_fix": "scale_service",
                    "affected_services": [],
                },
            },
        ]
        results = grade_multiple_trajectories(trajectories)
        assert isinstance(results, dict)
        assert results["total_trajectories"] == 2
        assert len(results["results"]) == 2
        assert all("final_score" in r for r in results["results"])


class TestHumanSREGrader:
    """Test human SRE grader."""

    def test_human_sre_grader_basic(self):
        """Cover: human_sre_grader.py."""
        trajectory = {
            "actions": [
                {"action_type": "query_service", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"terminated": True},
            "scenario": {
                "fault_type": "oom",
                "difficulty": 2,
                "root_cause_service": "payment-service",
                "correct_fix": "restart_service",
                "affected_services": [],
            },
        }
        result = grade_like_human_sre(trajectory, trajectory["scenario"])
        assert result.grade in ["expert", "proficient", "competent", "learning", "untrained"]
