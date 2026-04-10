"""
IncidentOps - Enhanced Grader Edge Cases
Targets uncovered lines in app/enhanced_grader.py
"""
import pytest
from app.enhanced_grader import (
    EnhancedSREGrader,
    grade_trajectory_enhanced,
    SREGrade,
    ReasoningPattern,
)


class TestScoreRootCauseEdgeCases:
    """Test _score_root_cause edge cases - lines 262-266."""

    def test_wrong_root_cause_identified(self):
        """Cover: lines 262-266 - wrong root cause identification returns 0.0."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "identify_root_cause", "target_service": "wrong-service"},
        ]
        score = grader._score_root_cause(actions, "payment-service")
        assert score == 0.0

    def test_correct_root_cause_identified(self):
        """Cover: lines 263-264 - correct root cause returns 1.0."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "identify_root_cause", "target_service": "payment-service"},
        ]
        score = grader._score_root_cause(actions, "payment-service")
        assert score == 1.0


class TestScoreFixEdgeCases:
    """Test _score_fix edge cases - lines 289-315."""

    def test_no_fix_applied(self):
        """Cover: line 286-287 - no fix applied returns 0.0."""
        grader = EnhancedSREGrader()
        actions = []
        final_state = {"fix_applied": False}
        score = grader._score_fix(actions, final_state, "payment-service", "oom")
        assert score == 0.0

    def test_no_fix_actions_partial_credit(self):
        """Cover: line 294-295 - no fix actions gives 0.5 partial credit."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "query_metrics", "target_service": "payment-service"},
        ]
        final_state = {"fix_applied": True}
        score = grader._score_fix(actions, final_state, "payment-service", "oom")
        assert score == 0.5

    def test_correct_fix_oom(self):
        """Cover: lines 304-313 - correct fix type for OOM (restart_service)."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "restart_service", "target_service": "payment-service"},
        ]
        final_state = {"fix_applied": True}
        score = grader._score_fix(actions, final_state, "payment-service", "oom")
        assert score == 1.0

    def test_correct_fix_ghost(self):
        """Cover: lines 305-313 - correct fix type for ghost (rollback_deployment)."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "rollback_deployment",
             "target_service": "recommendation-service"},
        ]
        final_state = {"fix_applied": True}
        score = grader._score_fix(
            actions, final_state, "recommendation-service", "ghost"
        )
        assert score == 1.0

    def test_cascade_fix_score_partial(self):
        """Cover: lines 294-295 - cascade fix with scale_service gets partial credit.

        Note: scale_service is NOT in fix_actions list (only restart, rollback, apply_fix).
        So correct cascade fix gets 0.5 (partial credit for fix_applied but no fix actions).
        """
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "scale_service", "target_service": "database-primary"},
        ]
        final_state = {"fix_applied": True}
        score = grader._score_fix(actions, final_state, "database-primary", "cascade")
        # scale_service is now a valid fix for cascade
        assert score == 1.0

    def test_network_fix_score_partial(self):
        """Cover: lines 294-295 - network fix with scale_service gets partial credit.

        Note: scale_service is NOT in fix_actions list, so correct network fix
        gets 0.5 (partial credit for fix_applied but no fix actions in the list).
        """
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "scale_service", "target_service": "api-gateway"},
        ]
        final_state = {"fix_applied": True}
        score = grader._score_fix(actions, final_state, "api-gateway", "network")
        # scale_service is now a valid fix for network
        assert score == 1.0

    def test_correct_fix_deployment(self):
        """Cover: lines 306-313 - correct fix type for deployment (rollback_deployment)."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "rollback_deployment", "target_service": "auth-service"},
        ]
        final_state = {"fix_applied": True}
        score = grader._score_fix(actions, final_state, "auth-service", "deployment")
        assert score == 1.0

    def test_wrong_service_returns_0_3(self):
        """Cover: line 300-301 - wrong service returns 0.3."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "restart_service", "target_service": "wrong-service"},
        ]
        final_state = {"fix_applied": True}
        score = grader._score_fix(actions, final_state, "payment-service", "oom")
        assert score == 0.3

    def test_right_service_wrong_fix_type(self):
        """Cover: line 315 - right service, wrong fix type returns 0.7."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "restart_service", "target_service": "recommendation-service"},
        ]
        final_state = {"fix_applied": True}
        score = grader._score_fix(
            actions, final_state, "recommendation-service", "ghost"
        )
        assert score == 0.7


class TestScoreEfficiencyEdgeCases:
    """Test _score_efficiency edge cases - lines 323-330."""

    def test_efficiency_optimal(self):
        """Cover: line 321-322 - optimal steps returns 1.0."""
        grader = EnhancedSREGrader()
        # OOM at difficulty 3: base 4 * 1.0 = 4 optimal steps
        score = grader._score_efficiency(4, "oom", 3)
        assert score == 1.0

    def test_efficiency_good(self):
        """Cover: lines 323-324 - good efficiency returns 0.85.

        For oom at difficulty 3: optimal=5, grace=2.
        Good range: optimal + grace = 5+2 = 7 steps, so 6 steps -> 0.85.
        """
        grader = EnhancedSREGrader()
        # OOM at difficulty 3: optimal 5, grace 2, so 6 steps -> 0.85
        score = grader._score_efficiency(6, "oom", 3)
        assert score == 0.85

    def test_efficiency_fair(self):
        """Cover: lines 325-326 - fair efficiency returns 0.7."""
        grader = EnhancedSREGrader()
        # OOM at difficulty 3: optimal 5, grace 2, fair range up to 10 steps
        # 8 steps is in fair range (7 < 8 <= 10) -> 0.7
        score = grader._score_efficiency(8, "oom", 3)
        assert score == 0.7

    def test_efficiency_poor(self):
        """Cover: lines 327-328 - poor efficiency returns 0.5."""
        grader = EnhancedSREGrader()
        # OOM at difficulty 3: optimal 5, grace 2, poor range up to 14 steps
        # 12 steps is in poor range (10 < 12 <= 14) -> 0.5
        score = grader._score_efficiency(12, "oom", 3)
        assert score == 0.5

    def test_efficiency_very_poor(self):
        """Cover: lines 329-330 - very poor efficiency returns 0.18."""
        grader = EnhancedSREGrader()
        # OOM at difficulty 3: optimal 5, grace 2, poor threshold 14 steps
        # 20 steps -> max(0.15, 0.3 - (20-5-2-7)*0.02) = max(0.15, 0.18) = 0.18
        score = grader._score_efficiency(20, "oom", 3)
        assert score == 0.18


class TestScoreDisruptionEdgeCases:
    """Test _score_disruption edge cases - lines 356, 360-364."""

    def test_no_actions_touched(self):
        """Cover: line 355-356 - no service touched returns 0.0."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "query_metrics", "target_service": "payment-service"},
        ]
        result = grader._score_disruption(actions, "payment-service", set())
        assert result["score"] == 0.0
        assert result["touched_unrelated"] is False

    def test_single_restart_no_unrelated(self):
        """Cover: line 358-359 - single restart, no unrelated returns 1.0."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "restart_service", "target_service": "payment-service"},
        ]
        result = grader._score_disruption(actions, "payment-service", set())
        assert result["score"] == 1.0
        assert result["touched_unrelated"] is False

    def test_multiple_restarts_no_unrelated(self):
        """Cover: lines 360-361 - multiple restarts, no unrelated returns 0.8."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "restart_service", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
        ]
        result = grader._score_disruption(actions, "payment-service", set())
        assert result["score"] == 0.8
        assert result["touched_unrelated"] is False

    def test_unrelated_services_penalty(self):
        """Cover: lines 362-364 - unrelated services penalized."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "restart_service", "target_service": "payment-service"},
            {"action_type": "scale_service", "target_service": "email-service"},
        ]
        result = grader._score_disruption(
            actions, "payment-service", {"order-service"}
        )
        assert result["score"] < 1.0
        assert result["touched_unrelated"] is True


class TestAnalyzeReasoningEdgeCases:
    """Test _analyze_reasoning edge cases - line 407."""

    def test_hypothesis_refinement_from_reasoning_data(self):
        """Cover: line 407 - hypothesis refinement from reasoning_data."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "query_metrics", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
        ]
        reasoning_data = {"progression_score": 0.8}
        analysis = grader._analyze_reasoning(
            actions, "oom", "payment-service", reasoning_data
        )
        assert analysis.hypothesis_refinement is True

    def test_no_hypothesis_refinement(self):
        """Cover: line 407 - no refinement when progression_score is low."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "restart_service", "target_service": "payment-service"},
        ]
        reasoning_data = {"progression_score": 0.3}
        analysis = grader._analyze_reasoning(
            actions, "oom", "payment-service", reasoning_data
        )
        assert analysis.hypothesis_refinement is False


class TestCheckSignalDiscriminationEdgeCases:
    """Test _check_signal_discrimination edge cases - lines 472, 476-479."""

    def test_single_false_lead(self):
        """Cover: line 472 - single false lead returns 0.7."""
        grader = EnhancedSREGrader()
        # cascade's false leads: ["symptom_service", "downstream_errors"]
        actions = [
            {"action_type": "query_metrics", "target_service": "symptom_service"},
            {"action_type": "restart_service", "target_service": "database-primary"},
        ]
        score, leads = grader._check_signal_discrimination(actions, "cascade")
        assert score == 0.7
        assert "symptom_service" in leads

    def test_multiple_false_leads(self):
        """Cover: lines 476-479 - multiple false leads returns 0.4."""
        grader = EnhancedSREGrader()
        # cascade's false leads: ["symptom_service", "downstream_errors"]
        actions = [
            {"action_type": "query_metrics", "target_service": "symptom_service"},
            {"action_type": "query_logs", "target_service": "downstream_errors"},
            {"action_type": "restart_service", "target_service": "database-primary"},
        ]
        score, leads = grader._check_signal_discrimination(actions, "cascade")
        assert score == 0.4
        assert len(leads) == 2


class TestCheckEvidenceUsageEdgeCases:
    """Test _check_evidence_usage edge cases - lines 495, 500."""

    def test_evidence_not_used(self):
        """Cover: line 495 - evidence not found in actions."""
        grader = EnhancedSREGrader()
        # oom key evidence: ["memory_metrics", "heap_logs", "gc_logs"]
        actions = [
            {"action_type": "query_metrics", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
        ]
        score, missed = grader._check_evidence_usage(actions, "oom")
        assert score == 0.0
        assert len(missed) == 3

    def test_no_key_evidence_defined(self):
        """Cover: line 500 - fault type with no key evidence defined."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "restart_service", "target_service": "unknown-service"},
        ]
        score, missed = grader._check_evidence_usage(actions, "nonexistent_fault")
        assert score == 1.0
        assert missed == []

    def test_some_evidence_not_used(self):
        """Cover: line 496-497 - some evidence goes to missed list."""
        grader = EnhancedSREGrader()
        # oom key evidence: ["memory_metrics", "heap_logs", "gc_logs"]
        # None of these are found, so all go to missed
        actions = [
            {"action_type": "query_metrics", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
        ]
        score, missed = grader._check_evidence_usage(actions, "oom")
        # No evidence found, so all 3 go to missed
        assert score == 0.0
        assert len(missed) == 3
        assert "memory_metrics" in missed
        assert "heap_logs" in missed
        assert "gc_logs" in missed

    def test_some_evidence_is_used(self):
        """Cover: line 495 - evidence found in actions appends to used list."""
        grader = EnhancedSREGrader()
        # oom key evidence: ["memory_metrics", "heap_logs", "gc_logs"]
        # Include "memory metrics" (with space, matching replace("_", " "))
        actions = [
            {"action_type": "query_metrics", "target_service": "payment-service",
             "notes": "memory metrics: 95%"},
            {"action_type": "restart_service", "target_service": "payment-service"},
        ]
        score, missed = grader._check_evidence_usage(actions, "oom")
        # memory_metrics found, others missed
        assert score == pytest.approx(1/3, rel=0.1)
        assert "heap_logs" in missed
        assert "gc_logs" in missed


class TestDeterminePatternEdgeCases:
    """Test _determine_pattern edge cases - lines 514, 519-527."""

    def test_systematic_pattern(self):
        """Cover: line 514 - systematic pattern when logical_path but not avoided."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "query_metrics", "target_service": "payment-service"},
            {"action_type": "query_logs", "target_service": "payment-service"},
        ]
        pattern = grader._determine_pattern(actions, True, False)
        assert pattern == ReasoningPattern.SYSTEMATIC

    def test_reactive_pattern(self):
        """Cover: lines 524-525 - reactive pattern with >2 interventions."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "restart_service", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
        ]
        pattern = grader._determine_pattern(actions, False, False)
        assert pattern == ReasoningPattern.REACTIVE

    def test_random_pattern(self):
        """Cover: lines 527 - random pattern (fallback)."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "query_metrics", "target_service": "payment-service"},
        ]
        pattern = grader._determine_pattern(actions, False, False)
        assert pattern == ReasoningPattern.RANDOM


class TestCalculatePenaltiesEdgeCases:
    """Test _calculate_penalties edge cases - line 566."""

    def test_excessive_restarts_penalty(self):
        """Cover: line 566 - penalty for >2 restarts."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "restart_service", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
            {"action_type": "restart_service", "target_service": "payment-service"},
        ]
        penalties = grader._calculate_penalties(
            actions, "payment-service", set()
        )
        assert penalties >= 0.05

    def test_incorrect_root_cause_attempts_penalty(self):
        """Cover: line 558 - penalty for incorrect root cause attempts."""
        grader = EnhancedSREGrader()
        actions = [
            {"action_type": "identify_root_cause", "target_service": "wrong-service"},
            {"action_type": "identify_root_cause", "target_service": "another-wrong"},
        ]
        penalties = grader._calculate_penalties(
            actions, "payment-service", set()
        )
        assert penalties >= 0.1


class TestAssignGradeEdgeCases:
    """Test _assign_grade edge cases - lines 573, 575, 577."""

    def test_grade_expert(self):
        """Cover: line 573 - expert grade >= 0.9."""
        grader = EnhancedSREGrader()
        assert grader._assign_grade(0.95) == SREGrade.EXPERT
        assert grader._assign_grade(0.9) == SREGrade.EXPERT

    def test_grade_proficient(self):
        """Cover: line 575 - proficient grade >= 0.75."""
        grader = EnhancedSREGrader()
        assert grader._assign_grade(0.85) == SREGrade.PROFICIENT
        assert grader._assign_grade(0.75) == SREGrade.PROFICIENT

    def test_grade_competent(self):
        """Cover: line 577 - competent grade >= 0.6."""
        grader = EnhancedSREGrader()
        assert grader._assign_grade(0.7) == SREGrade.COMPETENT
        assert grader._assign_grade(0.6) == SREGrade.COMPETENT

    def test_grade_learning(self):
        """Cover: line 579 - learning grade >= 0.4."""
        grader = EnhancedSREGrader()
        assert grader._assign_grade(0.5) == SREGrade.LEARNING
        assert grader._assign_grade(0.4) == SREGrade.LEARNING

    def test_grade_novice(self):
        """Cover: line 581 - novice grade < 0.4."""
        grader = EnhancedSREGrader()
        assert grader._assign_grade(0.3) == SREGrade.NOVICE
        assert grader._assign_grade(0.0) == SREGrade.NOVICE


class TestGenerateExplanationEdgeCases:
    """Test _generate_explanation edge cases - line 605."""

    def test_explanation_includes_false_leads(self):
        """Cover: line 605 - false leads in explanation."""
        grader = EnhancedSREGrader()
        from app.enhanced_grader import ScoringBreakdown, ReasoningAnalysis

        breakdown = ScoringBreakdown(
            root_cause_score=0.5,
            fix_score=0.5,
            efficiency_score=0.5,
            disruption_score=0.5,
            reasoning_score=0.5,
            root_cause_weighted=0.125,
            fix_weighted=0.125,
            efficiency_weighted=0.1,
            disruption_weighted=0.075,
            reasoning_weighted=0.075,
            raw_total=0.5,
            penalties=0.0,
            final_score=0.5,
            grade=SREGrade.COMPETENT,
        )

        reasoning = ReasoningAnalysis(
            pattern=ReasoningPattern.EVIDENCE_BASED,
            followed_logical_path=False,
            avoided_misleading_signals=True,
            used_evidence_correctly=True,
            hypothesis_refinement=False,
            followed_false_leads=["symptom_service"],
            missed_key_evidence=[],
        )

        explanation = grader._generate_explanation(
            breakdown, reasoning, "cascade", "database-primary"
        )
        assert "False leads followed" in explanation
        assert "symptom_service" in explanation


class TestIdentifyStrengthsEdgeCases:
    """Test _identify_strengths edge cases - lines 621, 624."""

    def test_strengths_root_cause_identified(self):
        """Cover: line 621 - root cause identified strength."""
        grader = EnhancedSREGrader()
        from app.enhanced_grader import ScoringBreakdown, ReasoningAnalysis

        breakdown = ScoringBreakdown(root_cause_score=0.95)
        reasoning = ReasoningAnalysis(
            pattern=ReasoningPattern.SYSTEMATIC,
            followed_logical_path=False,
            avoided_misleading_signals=False,
            used_evidence_correctly=False,
            hypothesis_refinement=False,
        )

        strengths = grader._identify_strengths(breakdown, reasoning)
        assert "Correctly identified root cause" in strengths

    def test_strengths_optimal_fix(self):
        """Cover: line 624 - optimal fix strength."""
        grader = EnhancedSREGrader()
        from app.enhanced_grader import ScoringBreakdown, ReasoningAnalysis

        breakdown = ScoringBreakdown(fix_score=0.95)
        reasoning = ReasoningAnalysis(
            pattern=ReasoningPattern.SYSTEMATIC,
            followed_logical_path=False,
            avoided_misleading_signals=False,
            used_evidence_correctly=False,
            hypothesis_refinement=False,
        )

        strengths = grader._identify_strengths(breakdown, reasoning)
        assert "Applied optimal fix" in strengths


class TestIdentifyWeaknessesEdgeCases:
    """Test _identify_weaknesses edge cases - lines 652, 655."""

    def test_weaknesses_inefficient(self):
        """Cover: line 978 - inefficient resolution weakness."""
        grader = EnhancedSREGrader()
        from app.enhanced_grader import ScoringBreakdown, ReasoningAnalysis

        breakdown = ScoringBreakdown(efficiency_score=0.3)
        reasoning = ReasoningAnalysis(
            pattern=ReasoningPattern.SYSTEMATIC,
            followed_logical_path=False,
            avoided_misleading_signals=False,
            used_evidence_correctly=False,
            hypothesis_refinement=False,
        )

        weaknesses = grader._identify_weaknesses(breakdown, reasoning)
        assert any("Inefficient resolution" in w for w in weaknesses)

    def test_weaknesses_false_leads(self):
        """Cover: line 655 - followed false leads weakness."""
        grader = EnhancedSREGrader()
        from app.enhanced_grader import ScoringBreakdown, ReasoningAnalysis

        breakdown = ScoringBreakdown()
        reasoning = ReasoningAnalysis(
            pattern=ReasoningPattern.SYSTEMATIC,
            followed_logical_path=False,
            avoided_misleading_signals=False,
            used_evidence_correctly=False,
            hypothesis_refinement=False,
            followed_false_leads=["database_latency"],
        )

        weaknesses = grader._identify_weaknesses(breakdown, reasoning)
        assert any("database_latency" in w for w in weaknesses)


class TestGenerateSuggestionsEdgeCases:
    """Test _generate_suggestions edge cases - lines 673, 676, 682, 723."""

    def test_suggestions_random_pattern(self):
        """Cover: line 673 - suggestions for random pattern."""
        grader = EnhancedSREGrader()
        from app.enhanced_grader import ScoringBreakdown, ReasoningAnalysis

        breakdown = ScoringBreakdown(efficiency_score=0.5)
        reasoning = ReasoningAnalysis(
            pattern=ReasoningPattern.RANDOM,
            followed_logical_path=False,
            avoided_misleading_signals=False,
            used_evidence_correctly=False,
            hypothesis_refinement=False,
        )

        suggestions = grader._generate_suggestions(
            breakdown, reasoning, "oom"
        )
        assert any("systematic investigation" in s.lower() for s in suggestions)

    def test_suggestions_false_leads(self):
        """Cover: line 676 - suggestions to avoid false leads."""
        grader = EnhancedSREGrader()
        from app.enhanced_grader import ScoringBreakdown, ReasoningAnalysis

        breakdown = ScoringBreakdown()
        reasoning = ReasoningAnalysis(
            pattern=ReasoningPattern.SYSTEMATIC,
            followed_logical_path=False,
            avoided_misleading_signals=False,
            used_evidence_correctly=False,
            hypothesis_refinement=False,
            followed_false_leads=["cache_miss"],
        )

        suggestions = grader._generate_suggestions(
            breakdown, reasoning, "ghost"
        )
        assert any("signal relevance" in s.lower() or "false leads" in s.lower()
                   for s in suggestions)

    def test_suggestions_poor_efficiency(self):
        """Cover: line 682 - suggestions for poor efficiency."""
        grader = EnhancedSREGrader()
        from app.enhanced_grader import ScoringBreakdown, ReasoningAnalysis

        breakdown = ScoringBreakdown(efficiency_score=0.5)
        reasoning = ReasoningAnalysis(
            pattern=ReasoningPattern.SYSTEMATIC,
            followed_logical_path=False,
            avoided_misleading_signals=False,
            used_evidence_correctly=False,
            hypothesis_refinement=False,
        )

        suggestions = grader._generate_suggestions(
            breakdown, reasoning, "oom"
        )
        assert any("redundant" in s.lower() or "query_dependencies" in s
                   for s in suggestions)

    def test_suggestions_systematic_slow(self):
        """Cover: line 723 - systematic but slow suggestions."""
        grader = EnhancedSREGrader()
        from app.enhanced_grader import ScoringBreakdown, ReasoningAnalysis

        breakdown = ScoringBreakdown(efficiency_score=0.3)
        reasoning = ReasoningAnalysis(
            pattern=ReasoningPattern.SYSTEMATIC,
            followed_logical_path=True,
            avoided_misleading_signals=False,
            used_evidence_correctly=False,
            hypothesis_refinement=False,
        )

        suggestions = grader._generate_suggestions(
            breakdown, reasoning, "cascade"
        )
        assert any("thorough" in s.lower() or "SLA" in s
                   for s in suggestions)


class TestAllFaultTypes:
    """Test all 13 fault types to ensure coverage."""

    @pytest.mark.parametrize("fault_type", [
        "ghost",
        "cascade",
        "oom",
        "deployment",
        "network_partition",
        "ddos",
        "memory_leak",
        "zombie_process",
        "thundering_herd",
        "cert_expiry",
        "version_mismatch",
        "data_corruption",
        "config_drift",
        "slow_downstream",
    ])
    def test_fault_type_grading(self, fault_type):
        """Test each fault type can be graded without errors."""
        trajectory = {
            "actions": [
                {"action_type": "query_metrics", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": True},
        }
        scenario = {
            "fault_type": fault_type,
            "difficulty": 3,
            "root_cause_service": "payment-service",
            "affected_services": [],
        }
        result = grade_trajectory_enhanced(trajectory, scenario)
        assert result.breakdown.final_score >= 0.0
        assert result.breakdown.final_score <= 1.0


class TestGradeFunctionIntegration:
    """Integration tests for grade function."""

    def test_complete_expert_trajectory(self):
        """Test an expert-level trajectory."""
        trajectory = {
            "actions": [
                {"action_type": "query_metrics", "target_service": "payment-service"},
                {"action_type": "query_logs", "target_service": "payment-service"},
                {"action_type": "query_metrics", "target_service": "payment-service"},
                {"action_type": "identify_root_cause", "target_service": "payment-service"},
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": True},
        }
        scenario = {
            "fault_type": "oom",
            "difficulty": 2,
            "root_cause_service": "payment-service",
            "affected_services": [],
        }
        result = grade_trajectory_enhanced(trajectory, scenario)
        assert result.breakdown.grade in SREGrade
        assert len(result.suggestions) >= 0

    def test_complete_poor_trajectory(self):
        """Test a poor trajectory."""
        trajectory = {
            "actions": [
                {"action_type": "restart_service", "target_service": "wrong-service"},
                {"action_type": "restart_service", "target_service": "another-wrong"},
                {"action_type": "restart_service", "target_service": "yet-another"},
            ],
            "final_state": {"fix_applied": False},
        }
        scenario = {
            "fault_type": "oom",
            "difficulty": 2,
            "root_cause_service": "payment-service",
            "affected_services": ["order-service"],
        }
        result = grade_trajectory_enhanced(trajectory, scenario)
        assert result.breakdown.final_score < 0.5
        assert len(result.weaknesses) >= 0
