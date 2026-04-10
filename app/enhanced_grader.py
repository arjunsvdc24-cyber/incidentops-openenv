from typing import Any
"""
IncidentOps - Enhanced SRE Grader v13.0

Scoring breakdown:
- 0.25 → root cause identification
- 0.25 → fix correctness
- 0.20 → efficiency
- 0.15 → minimal disruption
- 0.15 → reasoning quality

Reasoning quality evaluates:
- Did agent follow logical path?
- Did it avoid misleading signals?
- Did it use evidence correctly?

Returns:
{
  score: float,
  breakdown: {...},
  explanation: string
}

Deterministic scoring.
"""
from dataclasses import dataclass, field
from enum import Enum


class SREGrade(str, Enum):
    """SRE expertise grades"""
    EXPERT = "expert"
    PROFICIENT = "proficient"
    COMPETENT = "competent"
    LEARNING = "learning"
    NOVICE = "novice"


class ReasoningPattern(str, Enum):
    """Patterns of reasoning behavior"""
    SYSTEMATIC = "systematic"     # Follows logical order
    HYPOTHESIS_DRIVEN = "hypothesis_driven"  # Tests hypotheses
    EVIDENCE_BASED = "evidence_based"  # Uses evidence correctly
    REACTIVE = "reactive"         # Responds to signals without depth
    RANDOM = "random"             # No clear reasoning


@dataclass
class ScoringBreakdown:
    """Detailed scoring breakdown"""
    # Component scores (0.0-1.0)
    root_cause_score: float = 0.0
    fix_score: float = 0.0
    efficiency_score: float = 0.0
    disruption_score: float = 0.0
    reasoning_score: float = 0.0
    
    # Weighted contributions
    root_cause_weighted: float = 0.0
    fix_weighted: float = 0.0
    efficiency_weighted: float = 0.0
    disruption_weighted: float = 0.0
    reasoning_weighted: float = 0.0
    
    # Final
    raw_total: float = 0.0
    penalties: float = 0.0
    final_score: float = 0.0
    grade: SREGrade = SREGrade.NOVICE


@dataclass
class ReasoningAnalysis:
    """Analysis of reasoning quality"""
    pattern: ReasoningPattern
    followed_logical_path: bool
    avoided_misleading_signals: bool
    used_evidence_correctly: bool
    hypothesis_refinement: bool
    
    # Details
    logical_path_score: float = 0.0
    signal_discrimination_score: float = 0.0
    evidence_usage_score: float = 0.0
    
    # Specific issues
    followed_false_leads: list[str] = field(default_factory=list)
    missed_key_evidence: list[str] = field(default_factory=list)
    reasoning_gaps: list[str] = field(default_factory=list)


@dataclass
class EnhancedEvaluation:
    """Complete enhanced evaluation"""
    # Scores
    breakdown: ScoringBreakdown
    
    # Reasoning analysis
    reasoning_analysis: ReasoningAnalysis
    
    # Narrative
    explanation: str
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]
    
    # Metadata
    trajectory_id: str | None = None
    total_steps: int = 0


class EnhancedSREGrader:
    """
    Enhanced SRE-style grader with reasoning quality.
    
    Weight distribution:
    - Root cause: 25%
    - Fix: 25%
    - Efficiency: 20%
    - Disruption: 15%
    - Reasoning: 15%
    """
    
    # Weights
    WEIGHTS = {
        "root_cause": 0.25,
        "fix": 0.25,
        "efficiency": 0.20,
        "disruption": 0.15,
        "reasoning": 0.15,
    }
    
    # Base optimal steps by fault type (difficulty 3 baseline)
    # Difficulty 1 → multiply by 0.7, Difficulty 5 → multiply by 1.5
    BASE_OPTIMAL_STEPS = {
        "oom": 4,
        "cascade": 5,
        "ghost": 6,
        "deployment": 4,
        "network": 3,
    }

    def _get_optimal_steps(self, fault_type: str, difficulty: int) -> int:
        """Get optimal steps accounting for difficulty"""
        base = self.BASE_OPTIMAL_STEPS.get(fault_type, 5)
        # Scale by difficulty: diff 1→0.7x, diff 3→1.0x, diff 5→1.5x
        multiplier = 0.5 + (difficulty * 0.25)
        return max(2, round(base * multiplier))
    
    # Key evidence by fault type
    KEY_EVIDENCE = {
        "oom": ["memory_metrics", "heap_logs", "gc_logs"],
        "cascade": ["dependency_check", "upstream_metrics", "propagation_path"],
        "ghost": ["business_metrics", "deployment_timeline", "gradual_change"],
        "deployment": ["version_check", "error_timing", "rollback_test"],
        "network": ["latency_metrics", "connection_logs", "timeout_patterns"],
    }
    
    # Common false leads
    FALSE_LEADS = {
        "ghost": ["database_latency", "cache_miss", "unrelated_warnings"],
        "cascade": ["symptom_service", "downstream_errors"],
        "oom": ["network_timeout", "slow_queries"],
    }
    
    def __init__(self, seed: int = 42):
        self.seed = seed
    
    def grade(
        self,
        trajectory: dict,
        scenario: dict,
        reasoning_data: dict | None = None
    ) -> EnhancedEvaluation:
        """
        Grade trajectory with reasoning quality.
        
        Args:
            trajectory: Dict with actions, rewards, final_state
            scenario: Dict with fault_type, root_cause, affected_services
            reasoning_data: Optional reasoning tracking data
            
        Returns:
            EnhancedEvaluation with complete analysis
        """
        actions = trajectory.get("actions", [])
        final_state = trajectory.get("final_state", {})
        
        fault_type = scenario.get("fault_type", "unknown")
        root_cause = scenario.get("root_cause_service", "")
        affected = set(scenario.get("affected_services", []))
        
        # Initialize components
        breakdown = ScoringBreakdown()
        
        # 1. Root cause score (25%)
        breakdown.root_cause_score = self._score_root_cause(actions, root_cause)
        breakdown.root_cause_weighted = breakdown.root_cause_score * self.WEIGHTS["root_cause"]
        
        # 2. Fix score (25%)
        breakdown.fix_score = self._score_fix(actions, final_state, root_cause, fault_type)
        breakdown.fix_weighted = breakdown.fix_score * self.WEIGHTS["fix"]
        
        # 3. Efficiency score (20%) — difficulty-aware
        difficulty = scenario.get("difficulty", 3)
        breakdown.efficiency_score = self._score_efficiency(len(actions), fault_type, difficulty)
        breakdown.efficiency_weighted = breakdown.efficiency_score * self.WEIGHTS["efficiency"]
        
        # 4. Disruption score (15%)
        disruption_result = self._score_disruption(actions, root_cause, affected)
        breakdown.disruption_score = disruption_result["score"]
        breakdown.disruption_weighted = breakdown.disruption_score * self.WEIGHTS["disruption"]
        
        # 5. Reasoning score (15%)
        reasoning_analysis = self._analyze_reasoning(
            actions, fault_type, root_cause, reasoning_data
        )
        breakdown.reasoning_score = self._calculate_reasoning_score(reasoning_analysis)
        breakdown.reasoning_weighted = breakdown.reasoning_score * self.WEIGHTS["reasoning"]
        
        # Calculate totals
        breakdown.raw_total = (
            breakdown.root_cause_weighted +
            breakdown.fix_weighted +
            breakdown.efficiency_weighted +
            breakdown.disruption_weighted +
            breakdown.reasoning_weighted
        )
        
        # Apply penalties
        penalties = self._calculate_penalties(actions, root_cause, affected)
        breakdown.penalties = penalties
        breakdown.final_score = max(0.0, min(1.0, breakdown.raw_total - penalties))
        
        # Assign grade
        breakdown.grade = self._assign_grade(breakdown.final_score)
        
        # Generate explanation
        explanation = self._generate_explanation(
            breakdown, reasoning_analysis, fault_type, root_cause
        )
        
        strengths = self._identify_strengths(breakdown, reasoning_analysis)
        weaknesses = self._identify_weaknesses(breakdown, reasoning_analysis)
        suggestions = self._generate_suggestions(breakdown, reasoning_analysis, fault_type)
        
        return EnhancedEvaluation(
            breakdown=breakdown,
            reasoning_analysis=reasoning_analysis,
            explanation=explanation,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            total_steps=len(actions),
        )
    
    def _score_root_cause(self, actions: list[dict], root_cause: str) -> float:
        """Score root cause identification with tiered partial credit."""
        if not actions or not root_cause:
            return 0.0

        # Tier 1: explicit correct identification
        for action in actions:
            if action.get("action_type") == "identify_root_cause":
                if action.get("target_service") == root_cause:
                    return 1.0
                else:
                    return 0.0   # explicitly wrong identification

        # Tier 2: query_actions on the exact root cause service (investigated it)
        for action in actions:
            target = action.get("target_service", "")
            action_type = action.get("action_type", "")
            if target == root_cause and action_type.startswith("query_"):
                return 0.5

        # Tier 3: queried the dependency graph (systematic approach, still partial)
        queried_deps = any(
            a.get("action_type") == "query_dependencies"
            for a in actions
        )
        if queried_deps:
            # Check if any investigation action targeted a related service
            investigation = [
                a for a in actions
                if a.get("action_type", "").startswith("query_")
            ]
            if investigation:
                # Some investigation done — credit for methodology
                return 0.25

        # Tier 4: any investigation at all (effort, not result)
        if any(a.get("action_type", "").startswith("query_") for a in actions):
            return 0.1

        return 0.0
    
    def _score_fix(
        self,
        actions: list[dict],
        final_state: dict,
        root_cause: str,
        fault_type: str
    ) -> float:
        """Score fix correctness with generous partial credit for partial progress."""
        fix_actions = [
            a for a in actions
            if a.get("action_type") in ("restart_service", "rollback_deployment", "apply_fix", "scale_service")
        ]

        # ── Full fix applied (explicit flag or resolved state) ──────────────
        if final_state.get("fix_applied", False):
            if fix_actions:
                last_fix = fix_actions[-1]
                if last_fix.get("target_service") == root_cause:
                    expected = {
                        "ghost": "rollback_deployment",
                        "deployment": "rollback_deployment",
                        "oom": "restart_service",
                        "network": "scale_service",
                        "cascade": "scale_service",
                    }
                    if expected.get(fault_type) == last_fix.get("action_type"):
                        return 1.0
                    return 0.7  # right service, suboptimal fix method
                return 0.3  # wrong service
            return 0.5  # flagged fixed but no fix action recorded

        # ── Partial credit: fix action attempted on the right service ────────
        if fix_actions:
            last_fix = fix_actions[-1]
            if last_fix.get("target_service") == root_cause:
                # Right service — partial credit even without explicit fix_applied
                expected = {
                    "ghost": "rollback_deployment",
                    "deployment": "rollback_deployment",
                    "oom": "restart_service",
                    "network": "scale_service",
                    "cascade": "scale_service",
                }
                if expected.get(fault_type) == last_fix.get("action_type"):
                    return 0.8   # full method on right service, but state not resolved
                return 0.6       # right service, suboptimal method

            # Wrong service — small credit for attempting something
            return 0.15

        # ── Partial credit: right service queried / investigated but no fix yet ─
        for action in actions:
            if action.get("target_service") == root_cause and action.get("action_type", "").startswith("query_"):
                return 0.2   # investigated correctly but didn't apply a fix

        return 0.0
    
    def _score_efficiency(self, step_count: int, fault_type: str, difficulty: int = 3) -> float:
        """Score efficiency — difficulty-aware"""
        optimal = self._get_optimal_steps(fault_type, difficulty)

        if step_count <= optimal:
            return 1.0
        elif step_count <= optimal + 2:
            return 0.8
        elif step_count <= optimal + 5:
            return 0.6
        elif step_count <= optimal + 10:
            return 0.4
        else:
            return 0.2
    
    def _score_disruption(
        self,
        actions: list[dict],
        root_cause: str,
        affected: set[str]
    ) -> dict:
        """Score minimal disruption"""
        relevant = {root_cause} | affected
        touched = set()
        restart_count = 0
        
        for action in actions:
            action_type = action.get("action_type", "")
            target = action.get("target_service", "")
            
            if action_type in ("restart_service", "rollback_deployment", "apply_fix", "scale_service"):
                touched.add(target)
                if action_type == "restart_service":
                    restart_count += 1
        
        unrelated = touched - relevant
        touched_unrelated = len(unrelated) > 0
        
        if not touched:
            return {"score": 0.0, "touched_unrelated": False}
        
        if not unrelated and restart_count <= 1:
            return {"score": 1.0, "touched_unrelated": False}
        elif not unrelated:
            return {"score": 0.8, "touched_unrelated": False}
        else:
            penalty = len(unrelated) * 0.2
            return {"score": max(0.0, 1.0 - penalty), "touched_unrelated": True}
    
    def _analyze_reasoning(
        self,
        actions: list[dict],
        fault_type: str,
        root_cause: str,
        reasoning_data: dict | None
    ) -> ReasoningAnalysis:
        """Analyze reasoning quality"""
        analysis = ReasoningAnalysis(
            pattern=ReasoningPattern.RANDOM,
            followed_logical_path=False,
            avoided_misleading_signals=False,
            used_evidence_correctly=False,
            hypothesis_refinement=False,
        )
        
        # Check for logical path
        logical_path_score = self._check_logical_path(actions, fault_type, root_cause)
        analysis.logical_path_score = logical_path_score
        analysis.followed_logical_path = logical_path_score >= 0.6
        
        # Check signal discrimination
        signal_score, false_leads = self._check_signal_discrimination(actions, fault_type)
        analysis.signal_discrimination_score = signal_score
        analysis.avoided_misleading_signals = signal_score >= 0.6
        analysis.followed_false_leads = false_leads
        
        # Check evidence usage
        evidence_score, missed = self._check_evidence_usage(actions, fault_type)
        analysis.evidence_usage_score = evidence_score
        analysis.used_evidence_correctly = evidence_score >= 0.5
        analysis.missed_key_evidence = missed
        
        # Determine pattern
        analysis.pattern = self._determine_pattern(
            actions, analysis.followed_logical_path,
            analysis.avoided_misleading_signals
        )
        
        # Check hypothesis refinement
        if reasoning_data:
            analysis.hypothesis_refinement = reasoning_data.get("progression_score", 0) > 0.5
        
        return analysis
    
    def _check_logical_path(
        self,
        actions: list[dict],
        fault_type: str,
        root_cause: str
    ) -> float:
        """Check if agent followed logical investigation path"""
        score = 0.0
        
        # Check if investigation before action
        investigation_actions = [
            a for a in actions
            if a.get("action_type") in ("query_service", "query_metrics", "query_logs")
        ]
        
        intervention_actions = [
            a for a in actions
            if a.get("action_type") in ("restart_service", "rollback_deployment")
        ]
        
        if investigation_actions and intervention_actions:
            # Did investigation come before intervention?
            first_investigation = investigation_actions[0] if investigation_actions else None
            first_intervention = intervention_actions[0] if intervention_actions else None
            
            if first_investigation and first_intervention:
                inv_step = actions.index(first_investigation)
                int_step = actions.index(first_intervention)
                if inv_step < int_step:
                    score += 0.4
        
        # Check if root cause was investigated
        root_cause_investigated = any(
            a.get("target_service") == root_cause
            for a in investigation_actions
        )
        if root_cause_investigated:
            score += 0.3
        
        # Check for appropriate depth
        if len(investigation_actions) >= 3:  # pragma: no cover
            score += 0.3  # pragma: no cover

        return min(1.0, score)
    
    def _check_signal_discrimination(
        self,
        actions: list[dict],
        fault_type: str
    ) -> tuple[float, list[str]]:
        """Check if agent avoided false leads"""
        false_leads = self.FALSE_LEADS.get(fault_type, [])
        followed_false = []
        
        # Check if agent investigated false leads extensively
        for lead in false_leads:  # pragma: no cover
            lead_investigated = any(  # pragma: no cover
                lead in str(a).lower()  # pragma: no cover
                for a in actions  # pragma: no cover
            )  # pragma: no cover
            if lead_investigated:  # pragma: no cover
                followed_false.append(lead)  # pragma: no cover

        if not followed_false:
            return 1.0, []
        elif len(followed_false) == 1:
            return 0.7, followed_false
        else:
            return 0.4, followed_false
    
    def _check_evidence_usage(
        self,
        actions: list[dict],
        fault_type: str
    ) -> tuple[float, list[str]]:
        """Check if agent used key evidence"""
        key_evidence = self.KEY_EVIDENCE.get(fault_type, [])
        used = []
        missed = []
        
        action_str = " ".join(str(a).lower() for a in actions)
        
        for evidence in key_evidence:
            if evidence.replace("_", " ") in action_str:
                used.append(evidence)
            else:
                missed.append(evidence)
        
        if not key_evidence:  # pragma: no cover
            return 1.0, []  # pragma: no cover
        
        return len(used) / len(key_evidence), missed
    
    def _determine_pattern(
        self,
        actions: list[dict],
        logical_path: bool,
        avoided_misleading: bool
    ) -> ReasoningPattern:
        """Determine reasoning pattern"""
        if logical_path and avoided_misleading:
            return ReasoningPattern.HYPOTHESIS_DRIVEN
        elif logical_path:
            return ReasoningPattern.SYSTEMATIC
        elif avoided_misleading:
            return ReasoningPattern.EVIDENCE_BASED
        
        # Check for reactive pattern
        intervention_count = sum(
            1 for a in actions
            if a.get("action_type") in ("restart_service", "rollback_deployment")
        )
        
        if intervention_count > 2:
            return ReasoningPattern.REACTIVE
        
        return ReasoningPattern.RANDOM
    
    def _calculate_reasoning_score(self, analysis: ReasoningAnalysis) -> float:
        """Calculate overall reasoning score"""
        weights = {
            "logical_path": 0.4,
            "signal_discrimination": 0.3,
            "evidence_usage": 0.3,
        }
        
        return (
            analysis.logical_path_score * weights["logical_path"] +
            analysis.signal_discrimination_score * weights["signal_discrimination"] +
            analysis.evidence_usage_score * weights["evidence_usage"]
        )
    
    def _calculate_penalties(
        self,
        actions: list[dict],
        root_cause: str,
        affected: set[str]
    ) -> float:
        """Calculate additional penalties"""
        penalties = 0.0
        
        # Penalty for multiple incorrect root cause attempts
        incorrect_attempts = sum(
            1 for a in actions
            if a.get("action_type") == "identify_root_cause"
            and a.get("target_service") != root_cause
        )
        penalties += incorrect_attempts * 0.05
        
        # Penalty for excessive restarts
        restart_count = sum(
            1 for a in actions
            if a.get("action_type") == "restart_service"
        )
        if restart_count > 2:
            penalties += (restart_count - 2) * 0.05
        
        return penalties
    
    def _assign_grade(self, score: float) -> SREGrade:
        """Assign grade based on score"""
        if score >= 0.9:
            return SREGrade.EXPERT
        elif score >= 0.75:
            return SREGrade.PROFICIENT
        elif score >= 0.6:
            return SREGrade.COMPETENT
        elif score >= 0.4:
            return SREGrade.LEARNING
        else:
            return SREGrade.NOVICE
    
    def _generate_explanation(
        self,
        breakdown: ScoringBreakdown,
        reasoning: ReasoningAnalysis,
        fault_type: str,
        root_cause: str
    ) -> str:
        """Generate explanation text with helpful guidance for all levels."""
        parts = [
            f"Grade: {breakdown.grade.value.upper()} (Score: {breakdown.final_score:.2f})",
            "",
            "Scoring Breakdown:",
            f"  Root Cause: {breakdown.root_cause_score:.0%} × 0.25 = {breakdown.root_cause_weighted:.3f}",
            f"  Fix: {breakdown.fix_score:.0%} × 0.25 = {breakdown.fix_weighted:.3f}",
            f"  Efficiency: {breakdown.efficiency_score:.0%} × 0.20 = {breakdown.efficiency_weighted:.3f}",
            f"  Disruption: {breakdown.disruption_score:.0%} × 0.15 = {breakdown.disruption_weighted:.3f}",
            f"  Reasoning: {breakdown.reasoning_score:.0%} × 0.15 = {breakdown.reasoning_weighted:.3f}",
            "",
            f"Reasoning Pattern: {reasoning.pattern.value}",
        ]

        # ── Helpful guidance for empty / no-action trajectories ─────────────────
        if breakdown.root_cause_score == 0.0 and breakdown.fix_score == 0.0:
            parts.append("")
            parts.append("No investigation or fix actions detected.")
            parts.append("Hint: Start by querying service metrics or logs to observe symptoms,")
            parts.append(f"      then narrow down to the root cause ({root_cause} for {fault_type} faults).")

        # ── Partial progress feedback ──────────────────────────────────────────
        if breakdown.root_cause_score > 0 and breakdown.fix_score == 0:
            parts.append("")
            parts.append("Good investigation — you identified the right service.")
            parts.append("Next: Apply the correct fix (restart_service for OOM, scale_service for cascade, etc.).")

        if breakdown.fix_score > 0 and breakdown.fix_score < 0.6:
            parts.append("")
            parts.append("Fix attempted on the right service — nearly there!")
            parts.append("Tip: Check if the correct fix action type is being used for this fault type.")

        if reasoning.followed_false_leads:
            parts.append(f"  False leads followed: {reasoning.followed_false_leads}")

        if reasoning.missed_key_evidence:
            parts.append(f"  Missed evidence: {reasoning.missed_key_evidence}")

        if breakdown.penalties > 0:
            parts.append(f"  Penalties applied: -{breakdown.penalties:.2f}")

        return "\n".join(parts)
    
    def _identify_strengths(
        self,
        breakdown: ScoringBreakdown,
        reasoning: ReasoningAnalysis
    ) -> list[str]:
        """Identify strengths"""
        strengths = []
        
        if breakdown.root_cause_score >= 0.9:
            strengths.append("Correctly identified root cause")
        
        if breakdown.fix_score >= 0.9:
            strengths.append("Applied optimal fix")
        
        if breakdown.efficiency_score >= 0.9:
            strengths.append("Very efficient resolution")
        
        if reasoning.followed_logical_path:
            strengths.append("Followed logical investigation path")
        
        if reasoning.avoided_misleading_signals:
            strengths.append("Avoided misleading signals")
        
        return strengths
    
    def _identify_weaknesses(
        self,
        breakdown: ScoringBreakdown,
        reasoning: ReasoningAnalysis
    ) -> list[str]:
        """Identify weaknesses"""
        weaknesses = []
        
        if breakdown.root_cause_score < 0.5:
            weaknesses.append("Failed to identify root cause")
        
        if breakdown.fix_score < 0.5:
            weaknesses.append("Incorrect or no fix applied")
        
        if breakdown.efficiency_score < 0.5:
            weaknesses.append("Inefficient resolution")
        
        if reasoning.followed_false_leads:
            weaknesses.append(f"Followed false leads: {reasoning.followed_false_leads}")
        
        if reasoning.missed_key_evidence:
            weaknesses.append(f"Missed key evidence: {reasoning.missed_key_evidence}")
        
        return weaknesses
    
    def _generate_suggestions(
        self,
        breakdown: ScoringBreakdown,
        reasoning: ReasoningAnalysis,
        fault_type: str
    ) -> list[str]:
        """Generate actionable improvement suggestions per fault type"""
        suggestions = []

        # Reasoning pattern suggestions
        if reasoning.pattern in (ReasoningPattern.RANDOM, ReasoningPattern.REACTIVE):
            suggestions.append("Develop a systematic investigation approach: query metrics before taking action")

        if reasoning.followed_false_leads:
            suggestions.append("Verify signal relevance before acting — check if service is upstream or downstream of symptoms")

        if reasoning.missed_key_evidence:
            suggestions.append(f"Key evidence for {fault_type} faults: {self.KEY_EVIDENCE.get(fault_type, [])}")

        if breakdown.efficiency_score < 0.7:
            suggestions.append("Reduce redundant queries — use query_dependencies once to map all services, then focus on suspicious ones")

        # Fault-type-specific actionable suggestions
        fault_actionable: dict[str, list[str]] = {
            "ghost": [
                "Silent faults have no error logs — always check query_metrics for business_metric drift (CTR, conversion)",
                "query_deployments shows recent changes — correlate deploy time with metric degradation time",
                "Silent faults require rollback_deployment, not restart_service",
                "Check recommendation-service / search-service CTR trend across 3+ query_metrics calls",
            ],
            "oom": [
                "OOM faults: check query_metrics for memory_percent > 90% before restarting",
                "payment-service and analytics-service are the most common OOM culprits at difficulty 2",
                "For memory leaks (difficulty 4+), restart_service is correct but track memory growth over time",
            ],
            "cascade": [
                "Cascades start from core services — check database-primary connection_pool_usage first",
                "503 errors on multiple services = shared dependency failure, not service-specific bug",
                "Use query_dependencies to find upstream/downstream relationships",
                "Correct fix for cascade: scale_service on the core service, not on symptom services",
            ],
            "deployment": [
                "Check query_deployments first — look for recent rollback-able deploys",
                "deployment faults: query_logs for error patterns in the recently-deployed version",
                "Rollback is almost always the correct fix — prefer it over restart",
            ],
            "network": [
                "High latency across many services = api-gateway bottleneck, not individual service issue",
                "Use query_metrics to find the service with highest error_rate or latency spike",
                "scale_service on api-gateway usually fixes DDoS/network bottleneck",
            ],
        }

        for fault, msgs in fault_actionable.items():
            if fault_type == fault and breakdown.final_score < 0.7:
                for msg in msgs[:2]:  # Add top 2 per fault type
                    if msg not in suggestions:
                        suggestions.append(msg)

        # Reasoning quality suggestions
        if reasoning.pattern == ReasoningPattern.SYSTEMATIC and breakdown.efficiency_score < 0.5:
            suggestions.append("Investigation was thorough but too slow — SLA countdown matters")

        if breakdown.root_cause_score < 0.3:
            suggestions.append("Root cause identification needs work: always check dependency graph before restarting services")

        return suggestions


# ── Task → scenario inference ──────────────────────────────────────────────

# Canonical task → (fault_type, root_cause_service, affected_services, difficulty)
_TASK_SCENARIOS: dict[str, dict] = {
    "oom_crash": {
        "fault_type": "oom",
        "root_cause_service": "payment-service",
        "affected_services": {"payment-service"},
        "difficulty": 2,
    },
    "cascade_failure": {
        "fault_type": "cascade",
        "root_cause_service": "database-primary",
        "affected_services": {"order-service", "user-service", "payment-service"},
        "difficulty": 3,
    },
    "ghost_corruption": {
        "fault_type": "ghost",
        "root_cause_service": "recommendation-service",
        "affected_services": {"recommendation-service"},
        "difficulty": 5,
    },
    "ddos_flood": {
        "fault_type": "network",
        "root_cause_service": "api-gateway",
        "affected_services": {"api-gateway", "auth-service", "order-service"},
        "difficulty": 3,
    },
    "memory_spiral": {
        "fault_type": "oom",
        "root_cause_service": "analytics-service",
        "affected_services": {"analytics-service", "database-replica"},
        "difficulty": 4,
    },
    # Generic aliases
    "oom": {
        "fault_type": "oom",
        "root_cause_service": "payment-service",
        "affected_services": {"payment-service"},
        "difficulty": 2,
    },
    "cascade": {
        "fault_type": "cascade",
        "root_cause_service": "database-primary",
        "affected_services": {"order-service", "user-service", "payment-service"},
        "difficulty": 3,
    },
    "ghost": {
        "fault_type": "ghost",
        "root_cause_service": "recommendation-service",
        "affected_services": {"recommendation-service"},
        "difficulty": 5,
    },
    "network": {
        "fault_type": "network",
        "root_cause_service": "api-gateway",
        "affected_services": {"api-gateway", "auth-service", "order-service"},
        "difficulty": 3,
    },
}


def infer_scenario_from_task(task: str | None, scenario: dict | None) -> dict:
    """Return a valid scenario dict, inferring from task if scenario is sparse/absent."""
    if scenario is None:
        scenario = {}
    # If scenario already has the essentials, use it
    if scenario.get("fault_type") and scenario.get("root_cause_service"):
        return scenario
    # If a task name was given, look it up
    if task:
        task_lower = task.lower().replace("-", "_").replace(" ", "_")
        for key in (task_lower, task_lower.replace("_failure", "").replace("_corruption", "")):
            if key in _TASK_SCENARIOS:
                merged = dict(scenario)
                merged.update(_TASK_SCENARIOS[key])
                return merged
        # Fallback: try to match by fault_type substring in task
        for known_key, known_val in _TASK_SCENARIOS.items():
            if known_key in task_lower:
                merged = dict(scenario)
                merged.update(known_val)
                return merged
    return scenario


def grade_trajectory_enhanced(
    trajectory: dict,
    scenario: dict | None = None,
    seed: int = 42,
    task: str | None = None,
) -> EnhancedEvaluation:
    """Quick helper for enhanced grading.

    Args:
        trajectory: Dict with actions, rewards, final_state
        scenario: Optional scenario dict (fault_type, root_cause_service, affected_services, difficulty)
        seed: Random seed for determinism
        task: Optional task name (e.g. "oom_crash") to infer scenario when scenario is absent
    """
    # Infer scenario from task if not fully specified
    resolved = infer_scenario_from_task(task, scenario)
    grader = EnhancedSREGrader(seed=seed)
    return grader.grade(trajectory, resolved)
