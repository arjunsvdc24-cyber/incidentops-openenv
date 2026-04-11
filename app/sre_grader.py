"""
IncidentOps - SRE Expert Grader v11.0

Grades trajectories like a human SRE expert.

Evaluation Criteria:
1. Root cause accuracy (0.3)
2. Fix correctness (0.3)
3. Efficiency (0.2)
4. Minimal disruption (0.1)
5. Reasoning quality (0.1)

Penalties:
- Touching unrelated services
- Ignoring key signals

Returns:
- Final score
- Human-readable explanation

Deterministic scoring.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set


class SREGrade(str, Enum):
    """SRE-style grades"""
    EXPERT = "expert"          # Like a senior SRE
    PROFICIENT = "proficient"  # Like a mid-level SRE
    COMPETENT = "competent"    # Like a junior SRE
    LEARNING = "learning"      # Still learning
    UNTRAINED = "untrained"    # Needs training


@dataclass
class SREEvaluation:
    """Complete SRE-style evaluation"""
    # Component scores (0.0-1.0)
    root_cause_accuracy: float = 0.0
    fix_correctness: float = 0.0
    efficiency: float = 0.0
    minimal_disruption: float = 0.0
    reasoning_quality: float = 0.0
    
    # Weighted scores
    root_cause_weighted: float = 0.0
    fix_weighted: float = 0.0
    efficiency_weighted: float = 0.0
    disruption_weighted: float = 0.0
    reasoning_weighted: float = 0.0
    
    # Final
    raw_score: float = 0.0
    final_score: float = 0.0
    grade: SREGrade = SREGrade.UNTRAINED
    
    # Analysis
    touched_unrelated_services: bool = False
    ignored_key_signals: bool = False
    key_signals: List[str] = field(default_factory=list)
    missed_signals: List[str] = field(default_factory=list)
    false_signals_followed: List[str] = field(default_factory=list)
    
    # Explanation
    explanation: str = ""
    reasoning_analysis: str = ""
    improvement_suggestions: List[str] = field(default_factory=list)
    
    # Additional fields for main.py compatibility
    trajectory_id: str | None = None
    total_reward: float = 0.0


@dataclass
class SignalAnalysis:
    """Analysis of signal handling"""
    key_signals: List[str] = field(default_factory=list)
    observed_signals: List[str] = field(default_factory=list)
    missed_signals: List[str] = field(default_factory=list)
    false_leads: List[str] = field(default_factory=list)
    correct_leads: List[str] = field(default_factory=list)


class SREExpertGrader:
    """
    Grades trajectories with SRE expertise.
    
    Evaluates like a human expert would:
    - Did they find the real problem?
    - Did they fix it correctly?
    - Did they do it efficiently?
    - Did they avoid making things worse?
    - Did they reason well?
    """
    
    # Weights for each component
    WEIGHTS = {
        "root_cause": 0.3,
        "fix": 0.3,
        "efficiency": 0.2,
        "disruption": 0.1,
        "reasoning": 0.1,
    }
    
    # Key signal patterns for different fault types
    KEY_SIGNALS = {
        "ghost": [
            "ctr_decline",
            "deployment_timeline",
            "no_explicit_errors",
            "business_metric_decline",
        ],
        "cascade": [
            "multiple_services_affected",
            "dependency_chain",
            "upstream_failure",
        ],
        "oom": [
            "OutOfMemoryError",
            "heap_space",
            "memory_pressure",
        ],
        "deployment": [
            "new_errors",
            "version_change",
            "deployment_timestamp",
        ],
        "network": [
            "timeout",
            "connection_refused",
            "latency_spike",
        ],
    }
    
    # False signal patterns (red herrings)
    FALSE_SIGNALS = {
        "ghost": [
            "database_latency",  # Often appears but is symptom
            "unrelated_warnings",
            "cache_miss_rate",  # May be elevated but not cause
        ],
    }
    
    def __init__(self, seed: int = 42):
        self.seed = seed
    
    def grade(
        self,
        trajectory: Dict,
        scenario: Dict
    ) -> SREEvaluation:
        """
        Grade trajectory like an SRE expert.
        
        Args:
            trajectory: Dict with actions, rewards, final_state
            scenario: Dict with fault_type, root_cause, affected_services
            
        Returns:
            SREEvaluation with complete analysis
        """
        evaluation = SREEvaluation()
        
        actions = trajectory.get("actions", [])
        final_state = trajectory.get("final_state", {})
        
        fault_type = scenario.get("fault_type", "unknown")
        root_cause = scenario.get("root_cause_service", "")
        affected_services = set(scenario.get("affected_services", []))
        
        # 1. Analyze signals
        signal_analysis = self._analyze_signals(actions, fault_type, root_cause)
        evaluation.key_signals = signal_analysis.key_signals
        evaluation.missed_signals = signal_analysis.missed_signals
        evaluation.false_signals_followed = signal_analysis.false_leads
        evaluation.ignored_key_signals = len(signal_analysis.missed_signals) > 0
        
        # 2. Root cause accuracy (0.3)
        evaluation.root_cause_accuracy = self._evaluate_root_cause(
            actions, root_cause
        )
        evaluation.root_cause_weighted = (
            evaluation.root_cause_accuracy * self.WEIGHTS["root_cause"]
        )
        
        # 3. Fix correctness (0.3)
        evaluation.fix_correctness = self._evaluate_fix(
            actions, final_state, root_cause, fault_type
        )
        evaluation.fix_weighted = (
            evaluation.fix_correctness * self.WEIGHTS["fix"]
        )
        
        # 4. Efficiency (0.2)
        evaluation.efficiency = self._evaluate_efficiency(
            len(actions), fault_type
        )
        evaluation.efficiency_weighted = (
            evaluation.efficiency * self.WEIGHTS["efficiency"]
        )
        
        # 5. Minimal disruption (0.1)
        disruption_eval = self._evaluate_disruption(
            actions, root_cause, affected_services
        )
        evaluation.minimal_disruption = disruption_eval["score"]
        evaluation.touched_unrelated_services = disruption_eval["touched_unrelated"]
        evaluation.disruption_weighted = (
            evaluation.minimal_disruption * self.WEIGHTS["disruption"]
        )
        
        # 6. Reasoning quality (0.1)
        evaluation.reasoning_quality = self._evaluate_reasoning(
            actions, signal_analysis, fault_type
        )
        evaluation.reasoning_weighted = (
            evaluation.reasoning_quality * self.WEIGHTS["reasoning"]
        )
        
        # 7. Calculate final score
        evaluation.raw_score = (
            evaluation.root_cause_weighted +
            evaluation.fix_weighted +
            evaluation.efficiency_weighted +
            evaluation.disruption_weighted +
            evaluation.reasoning_weighted
        )
        
        # Apply penalties
        penalty = 0.0
        if evaluation.touched_unrelated_services:
            penalty += 0.1
        if evaluation.ignored_key_signals:
            penalty += 0.05
        
        # Clamp to strictly (0, 1) — validator requires scores > 0.0 and < 1.0
        _EPSILON = 1e-9
        evaluation.final_score = max(_EPSILON, min(1.0 - _EPSILON, evaluation.raw_score - penalty))
        
        # 8. Assign grade
        evaluation.grade = self._assign_grade(evaluation.final_score)
        
        # 9. Generate explanation
        evaluation.explanation = self._generate_explanation(
            evaluation, fault_type, root_cause
        )
        evaluation.reasoning_analysis = self._generate_reasoning_analysis(
            evaluation, signal_analysis
        )
        evaluation.improvement_suggestions = self._generate_suggestions(
            evaluation, signal_analysis
        )
        
        return evaluation
    
    def _analyze_signals(
        self,
        actions: List[Dict],
        fault_type: str,
        root_cause: str
    ) -> SignalAnalysis:
        """Analyze how signals were handled"""
        analysis = SignalAnalysis()
        
        # Get expected key signals
        analysis.key_signals = self.KEY_SIGNALS.get(fault_type, [])
        
        # Analyze observed signals
        for action in actions:
            action_type = action.get("action_type", "")
            target = action.get("target_service", "")
            
            # Check what was investigated
            if action_type in ("query_logs", "query_metrics", "query_service"):
                signal = f"{action_type}:{target}"
                analysis.observed_signals.append(signal)
        
        # Check for missed key signals
        if fault_type == "ghost":
            # For ghost, must check business metrics and timeline
            checked_metrics = any(
                a.get("action_type") == "query_metrics" and
                a.get("target_service") == root_cause
                for a in actions
            )
            checked_timeline = any(
                a.get("action_type") == "query_deployments"
                for a in actions
            )
            
            if not checked_metrics:
                analysis.missed_signals.append("business_metrics")
            if not checked_timeline:
                analysis.missed_signals.append("deployment_timeline")
        
        # Check for false leads
        if fault_type == "ghost":
            # Common false lead: investigating DB when it's a recommendation bug
            db_investigated = any(
                a.get("target_service", "").startswith("database")
                for a in actions
            )
            if db_investigated and root_cause != "database-primary":
                analysis.false_leads.append("database_latency")
        
        # Identify correct leads
        root_cause_investigated = any(
            a.get("target_service") == root_cause
            for a in actions
        )
        if root_cause_investigated:
            analysis.correct_leads.append(f"investigated_{root_cause}")
        
        return analysis
    
    def _evaluate_root_cause(
        self,
        actions: List[Dict],
        actual_root_cause: str
    ) -> float:
        """Evaluate root cause identification accuracy"""
        for action in actions:
            if action.get("action_type") == "identify_root_cause":
                if action.get("target_service") == actual_root_cause:
                    return 1.0
                else:
                    return 0.0
        
        # Never identified
        return 0.0
    
    def _evaluate_fix(
        self,
        actions: List[Dict],
        final_state: Dict,
        root_cause: str,
        fault_type: str
    ) -> float:
        """Evaluate fix correctness"""
        # Check if incident was resolved
        if not final_state.get("fix_applied", False):
            return 0.0
        
        # Check if correct fix was applied
        fix_actions = [
            a for a in actions
            if a.get("action_type") in ("restart_service", "rollback_deployment", "apply_fix")
        ]
        
        if not fix_actions:
            return 0.5  # Fixed but unclear how
        
        last_fix = fix_actions[-1]
        
        # Check target
        if last_fix.get("target_service") != root_cause:
            return 0.3  # Fixed wrong service
        
        # Check action type matches fault
        action_type = last_fix.get("action_type")
        expected_actions = {
            "ghost": "rollback_deployment",
            "deployment": "rollback_deployment",
            "oom": "restart_service",
            "network": "scale_service",
            "cascade": "restart_service",
        }
        
        expected = expected_actions.get(fault_type)
        if expected and action_type == expected:
            return 1.0
        elif expected and action_type != expected:
            return 0.7  # Right service, suboptimal action
        
        return 0.8
    
    def _evaluate_efficiency(
        self,
        step_count: int,
        fault_type: str
    ) -> float:
        """Evaluate efficiency"""
        # Optimal steps by fault type
        optimal = {
            "ghost": 6,
            "cascade": 5,
            "oom": 4,
            "deployment": 4,
            "network": 3,
        }
        
        target = optimal.get(fault_type, 5)
        
        if step_count <= target:
            return 1.0
        elif step_count <= target + 2:
            return 0.8
        elif step_count <= target + 5:
            return 0.6
        elif step_count <= target + 10:
            return 0.4
        else:
            return 0.2
    
    def _evaluate_disruption(
        self,
        actions: List[Dict],
        root_cause: str,
        affected_services: Set[str]
    ) -> Dict:
        """Evaluate minimal disruption"""
        relevant = {root_cause} | affected_services
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
    
    def _evaluate_reasoning(
        self,
        actions: List[Dict],
        signal_analysis: SignalAnalysis,
        fault_type: str
    ) -> float:
        """Evaluate reasoning quality"""
        score = 0.0
        
        # Checked relevant services
        correct_leads = len(signal_analysis.correct_leads)
        score += min(0.3, correct_leads * 0.15)
        
        # Avoided false leads
        if not signal_analysis.false_leads:
            score += 0.3
        
        # Investigated in logical order
        # (e.g., symptoms → dependencies → root cause)
        investigation_actions = [
            a for a in actions
            if a.get("action_type") in ("query_service", "query_metrics", "query_logs")
        ]
        
        if len(investigation_actions) >= 2:
            # Did some investigation before acting
            intervention_actions = [
                a for a in actions
                if a.get("action_type") in ("restart_service", "rollback_deployment")
            ]
            
            if investigation_actions[0].get("step", 0) < intervention_actions[0].get("step", float('inf')):
                score += 0.2
        
        # Used timeline for ghost scenarios
        if fault_type == "ghost":
            used_timeline = any(
                a.get("action_type") == "query_deployments"
                for a in actions
            )
            if used_timeline:
                score += 0.2
        
        return min(1.0, score)
    
    def _assign_grade(self, score: float) -> SREGrade:
        """Assign SRE-style grade"""
        if score >= 0.9:
            return SREGrade.EXPERT
        elif score >= 0.75:
            return SREGrade.PROFICIENT
        elif score >= 0.6:
            return SREGrade.COMPETENT
        elif score >= 0.4:
            return SREGrade.LEARNING
        else:
            return SREGrade.UNTRAINED
    
    def _generate_explanation(
        self,
        evaluation: SREEvaluation,
        fault_type: str,
        root_cause: str
    ) -> str:
        """Generate human-readable explanation"""
        parts = []
        
        # Overall assessment
        parts.append(f"Grade: {evaluation.grade.value.upper()} (Score: {evaluation.final_score:.2f})")
        parts.append("")
        
        # Root cause
        if evaluation.root_cause_accuracy >= 0.9:
            parts.append(f"✓ Correctly identified root cause: {root_cause}")
        elif evaluation.root_cause_accuracy > 0:
            parts.append(f"~ Partially identified root cause")
        else:
            parts.append(f"✗ Failed to identify root cause: {root_cause}")
        
        # Fix
        if evaluation.fix_correctness >= 0.9:
            parts.append(f"✓ Applied correct fix")
        elif evaluation.fix_correctness > 0:
            parts.append(f"~ Applied partial fix")
        else:
            parts.append(f"✗ Failed to apply correct fix")
        
        # False leads
        if evaluation.false_signals_followed:
            parts.append("")
            parts.append(f"⚠ Followed false signals: {evaluation.false_signals_followed}")
        
        # Unrelated services
        if evaluation.touched_unrelated_services:
            parts.append("")
            parts.append(f"⚠ Affected unrelated services")
        
        return "\n".join(parts)
    
    def _generate_reasoning_analysis(
        self,
        evaluation: SREEvaluation,
        signal_analysis: SignalAnalysis
    ) -> str:
        """Generate reasoning analysis"""
        parts = []
        
        parts.append("Reasoning Analysis:")
        parts.append(f"- Key signals identified: {len(signal_analysis.correct_leads)}")
        parts.append(f"- Key signals missed: {len(signal_analysis.missed_signals)}")
        parts.append(f"- False leads followed: {len(signal_analysis.false_leads)}")
        parts.append(f"- Reasoning quality score: {evaluation.reasoning_quality:.2f}")
        
        if evaluation.missed_signals:
            parts.append("")
            parts.append(f"Missed critical signals: {evaluation.missed_signals}")
        
        return "\n".join(parts)
    
    def _generate_suggestions(
        self,
        evaluation: SREEvaluation,
        signal_analysis: SignalAnalysis
    ) -> List[str]:
        """Generate improvement suggestions"""
        suggestions = []
        
        if evaluation.root_cause_accuracy < 0.9:
            suggestions.append(
                "Focus on correlating deployment timeline with metric changes"
            )
        
        if evaluation.false_signals_followed:
            suggestions.append(
                "Verify signals before acting - some may be symptoms, not causes"
            )
        
        if evaluation.missed_signals:
            suggestions.append(
                f"Investigate key signals: {evaluation.missed_signals}"
            )
        
        if evaluation.touched_unrelated_services:
            suggestions.append(
                "Limit interventions to services directly related to the fault"
            )
        
        if evaluation.efficiency < 0.7:
            suggestions.append(
                "Reduce redundant queries - focus on gathering new information"
            )
        
        return suggestions


def grade_like_sre(
    trajectory: Dict,
    scenario: Dict,
    seed: int = 42
) -> SREEvaluation:
    """
    Grade trajectory like an SRE expert.
    
    Quick helper function.
    """
    grader = SREExpertGrader(seed=seed)
    return grader.grade(trajectory, scenario)
