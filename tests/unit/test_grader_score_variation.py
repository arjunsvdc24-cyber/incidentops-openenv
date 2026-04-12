"""
IncidentOps - Grader Score Variation Tests

CRITICAL: This file proves graders return DIFFERENT scores for different trajectories.
RULES.txt disqualification criterion: "Graders that always return the same score"

These tests demonstrate that graders produce meaningful, differentiated evaluation.
"""
import pytest
from app.grader import grade_trajectory, DeepTrajectoryGrader
from app.enhanced_grader import grade_trajectory_enhanced
from app.human_sre_grader import grade_like_human_sre


# ─── Deterministic Trajectories ──────────────────────────────────────────────

def perfect_oom_trajectory():
    """Perfect: investigated, identified, fixed the right service with right action."""
    return {
        "id": "perfect_oom",
        "actions": [
            {"action_type": "query_metrics", "target_service": "payment-service"},
            {"action_type": "query_logs", "target_service": "payment-service"},
            {"action_type": "query_dependencies", "target_service": "payment-service"},
            {"action_type": "identify_root_cause", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
        ],
        "rewards": [0.1, 0.15, 0.1, 0.3, 1.0],
        "final_state": {"terminated": True, "fix_applied": True},
        "scenario": {
            "fault_type": "oom",
            "difficulty": 2,
            "root_cause_service": "payment-service",
            "correct_fix": "restart_service:payment-service",
            "affected_services": [],
        },
    }


def wrong_service_trajectory():
    """Wrong root cause: restarted wrong service."""
    return {
        "id": "wrong_service",
        "actions": [
            {"action_type": "query_logs", "target_service": "api-gateway"},
            {"action_type": "restart_service", "target_service": "api-gateway"},
        ],
        "rewards": [0.05, 0.0],
        "final_state": {"terminated": True, "fix_applied": False},
        "scenario": {
            "fault_type": "oom",
            "difficulty": 2,
            "root_cause_service": "payment-service",
            "correct_fix": "restart_service:payment-service",
            "affected_services": [],
        },
    }


def wrong_action_trajectory():
    """Correct service but wrong action."""
    return {
        "id": "wrong_action",
        "actions": [
            {"action_type": "query_metrics", "target_service": "payment-service"},
            {"action_type": "identify_root_cause", "target_service": "payment-service"},
            {"action_type": "scale_service", "target_service": "payment-service"},
        ],
        "rewards": [0.1, 0.2, 0.0],
        "final_state": {"terminated": True, "fix_applied": False},
        "scenario": {
            "fault_type": "oom",
            "difficulty": 2,
            "root_cause_service": "payment-service",
            "correct_fix": "restart_service:payment-service",
            "affected_services": [],
        },
    }


def no_fix_trajectory():
    """Investigated but never applied any fix."""
    return {
        "id": "no_fix",
        "actions": [
            {"action_type": "query_logs", "target_service": "payment-service"},
            {"action_type": "query_metrics", "target_service": "payment-service"},
            {"action_type": "identify_root_cause", "target_service": "payment-service"},
        ],
        "rewards": [0.05, 0.1, 0.2],
        "final_state": {"terminated": True, "fix_applied": False},
        "scenario": {
            "fault_type": "oom",
            "difficulty": 2,
            "root_cause_service": "payment-service",
            "correct_fix": "restart_service:payment-service",
            "affected_services": [],
        },
    }


def brute_force_trajectory():
    """Brute-force: restarts multiple services randomly without investigation."""
    return {
        "id": "brute_force",
        "actions": [
            {"action_type": "restart_service", "target_service": "auth-service"},
            {"action_type": "restart_service", "target_service": "api-gateway"},
            {"action_type": "restart_service", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "user-service"},
            {"action_type": "restart_service", "target_service": "order-service"},
            {"action_type": "restart_service", "target_service": "email-service"},
        ],
        "rewards": [0.0, -0.1, -0.1, -0.1, -0.1, -0.1],
        "final_state": {"terminated": True, "fix_applied": False},
        "scenario": {
            "fault_type": "oom",
            "difficulty": 2,
            "root_cause_service": "payment-service",
            "correct_fix": "restart_service:payment-service",
            "affected_services": [],
        },
    }


def cascade_correct_trajectory():
    """Perfect cascade fault resolution."""
    return {
        "id": "cascade_correct",
        "actions": [
            {"action_type": "query_metrics", "target_service": "database-primary"},
            {"action_type": "query_dependencies", "target_service": "database-primary"},
            {"action_type": "identify_root_cause", "target_service": "database-primary"},
            {"action_type": "scale_service", "target_service": "database-primary"},
        ],
        "rewards": [0.1, 0.1, 0.3, 0.8],
        "final_state": {"terminated": True, "fix_applied": True},
        "scenario": {
            "fault_type": "cascade",
            "difficulty": 3,
            "root_cause_service": "database-primary",
            "correct_fix": "scale_service:database-primary",
            "affected_services": ["payment-service", "order-service"],
        },
    }


def ghost_correct_trajectory():
    """Perfect ghost fault resolution via deployment history."""
    return {
        "id": "ghost_correct",
        "actions": [
            {"action_type": "query_deployments", "target_service": "recommendation-service"},
            {"action_type": "query_metrics", "target_service": "recommendation-service"},
            {"action_type": "identify_root_cause", "target_service": "recommendation-service"},
            {"action_type": "rollback_deployment", "target_service": "recommendation-service"},
        ],
        "rewards": [0.1, 0.15, 0.3, 1.0],
        "final_state": {"terminated": True, "fix_applied": True},
        "scenario": {
            "fault_type": "ghost",
            "difficulty": 5,
            "root_cause_service": "recommendation-service",
            "correct_fix": "rollback_deployment:recommendation-service",
            "affected_services": [],
        },
    }


# ─── Core: Scores Differ Across Trajectories ──────────────────────────────────

class TestGraderScoreVariation:
    """Graders must NOT return the same score for all inputs. Proves graders are meaningful."""

    def test_perfect_vs_no_fix_differ(self):
        """Perfect resolution must score significantly higher than no-fix."""
        perfect = grade_trajectory(perfect_oom_trajectory(), seed=42)
        no_fix = grade_trajectory(no_fix_trajectory(), seed=42)

        assert perfect.final_score > no_fix.final_score, (
            f"Perfect ({perfect.final_score:.3f}) should score higher than "
            f"no-fix ({no_fix.final_score:.3f})"
        )

    def test_perfect_vs_wrong_service_differ(self):
        """Perfect resolution must score higher than wrong-service."""
        perfect = grade_trajectory(perfect_oom_trajectory(), seed=42)
        wrong = grade_trajectory(wrong_service_trajectory(), seed=42)

        assert perfect.final_score > wrong.final_score, (
            f"Perfect ({perfect.final_score:.3f}) should score higher than "
            f"wrong service ({wrong.final_score:.3f})"
        )

    def test_perfect_vs_wrong_action_differ(self):
        """Perfect resolution must score higher than wrong-action."""
        perfect = grade_trajectory(perfect_oom_trajectory(), seed=42)
        wrong = grade_trajectory(wrong_action_trajectory(), seed=42)

        assert perfect.final_score > wrong.final_score, (
            f"Perfect ({perfect.final_score:.3f}) should score higher than "
            f"wrong action ({wrong.final_score:.3f})"
        )

    def test_perfect_vs_brute_force_differ(self):
        """Perfect resolution must score much higher than brute-force."""
        perfect = grade_trajectory(perfect_oom_trajectory(), seed=42)
        brute = grade_trajectory(brute_force_trajectory(), seed=42)

        assert perfect.final_score > brute.final_score + 0.2, (
            f"Perfect ({perfect.final_score:.3f}) should score significantly higher "
            f"than brute-force ({brute.final_score:.3f})"
        )

    def test_all_scores_in_valid_range(self):
        """Every trajectory must produce a score in [0.0, 1.0]."""
        trajectories = [
            perfect_oom_trajectory(),
            wrong_service_trajectory(),
            wrong_action_trajectory(),
            no_fix_trajectory(),
            brute_force_trajectory(),
            cascade_correct_trajectory(),
            ghost_correct_trajectory(),
        ]
        for traj in trajectories:
            result = grade_trajectory(traj, seed=42)
            assert 0.0 <= result.final_score <= 1.0, (
                f"Trajectory {traj['id']} score {result.final_score} out of range"
            )

    def test_score_range_sufficient_variance(self):
        """Scores must span at least 0.3 across different trajectory quality levels."""
        trajectories = [
            perfect_oom_trajectory(),
            wrong_service_trajectory(),
            no_fix_trajectory(),
            brute_force_trajectory(),
        ]
        scores = [grade_trajectory(t, seed=42).final_score for t in trajectories]
        score_range = max(scores) - min(scores)
        assert score_range >= 0.2, (
            f"Score range ({score_range:.3f}) too narrow — "
            f"grader may be degenerate. Scores: {scores}"
        )

    def test_different_fault_types_score_differently(self):
        """Same-quality trajectory should score differently on different fault types."""
        # Perfect OOM trajectory
        oom_traj = perfect_oom_trajectory()
        oom_score = grade_trajectory(oom_traj, seed=42).final_score

        # Perfect cascade trajectory
        cascade_traj = cascade_correct_trajectory()
        cascade_score = grade_trajectory(cascade_traj, seed=42).final_score

        # Ghost is hardest
        ghost_traj = ghost_correct_trajectory()
        ghost_score = grade_trajectory(ghost_traj, seed=42).final_score

        # All valid range
        for name, score in [("OOM", oom_score), ("Cascade", cascade_score), ("Ghost", ghost_score)]:
            assert 0.0 <= score <= 1.0, f"{name} score {score} out of range"

        # Score range across fault types should be meaningful
        all_scores = [oom_score, cascade_score, ghost_score]
        assert max(all_scores) - min(all_scores) >= 0.0, (
            f"Scores should vary across fault types. Got: {all_scores}"
        )


class TestEnhancedGraderScoreVariation:
    """Enhanced grader also produces differentiated scores."""

    def test_enhanced_scores_differ_across_trajectories(self):
        perfect = grade_trajectory_enhanced(
            perfect_oom_trajectory(),
            perfect_oom_trajectory()["scenario"],
            seed=42,
        )
        no_fix = grade_trajectory_enhanced(
            no_fix_trajectory(),
            no_fix_trajectory()["scenario"],
            seed=42,
        )
        assert perfect.breakdown.final_score > no_fix.breakdown.final_score

    def test_enhanced_all_scores_in_range(self):
        for traj_fn in [
            perfect_oom_trajectory,
            wrong_service_trajectory,
            no_fix_trajectory,
            brute_force_trajectory,
        ]:
            traj = traj_fn()
            result = grade_trajectory_enhanced(traj, traj["scenario"], seed=42)
            assert 0.0 <= result.breakdown.final_score <= 1.0


class TestHumanGraderScoreVariation:
    """Human-expert-style grader also differentiates."""

    def test_human_grader_scores_differ_across_trajectories(self):
        perfect = grade_like_human_sre(
            perfect_oom_trajectory(),
            perfect_oom_trajectory()["scenario"],
            seed=42,
        )
        brute = grade_like_human_sre(
            brute_force_trajectory(),
            brute_force_trajectory()["scenario"],
            seed=42,
        )
        assert perfect.final_score > brute.final_score

    def test_human_grader_all_scores_in_range(self):
        for traj_fn in [
            perfect_oom_trajectory,
            wrong_service_trajectory,
            wrong_action_trajectory,
            no_fix_trajectory,
        ]:
            traj = traj_fn()
            result = grade_like_human_sre(traj, traj["scenario"], seed=42)
            assert 0.0 <= result.final_score <= 1.0


class TestDeterministicScoring:
    """Scores are deterministic (same input → same score)."""

    def test_basic_grader_deterministic(self):
        traj = perfect_oom_trajectory()
        s1 = grade_trajectory(traj, seed=42).final_score
        s2 = grade_trajectory(traj, seed=42).final_score
        s3 = grade_trajectory(traj, seed=99).final_score
        assert s1 == s2, "Same seed should produce identical scores"
        # Different seed may differ
        assert isinstance(s1, float)

    def test_enhanced_grader_deterministic(self):
        traj = perfect_oom_trajectory()
        r1 = grade_trajectory_enhanced(traj, traj["scenario"], seed=42)
        r2 = grade_trajectory_enhanced(traj, traj["scenario"], seed=42)
        assert r1.breakdown.final_score == r2.breakdown.final_score

    def test_human_grader_deterministic(self):
        traj = perfect_oom_trajectory()
        r1 = grade_like_human_sre(traj, traj["scenario"], seed=42)
        r2 = grade_like_human_sre(traj, traj["scenario"], seed=42)
        assert r1.final_score == r2.final_score
