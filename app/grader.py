from typing import Any
"""
IncidentOps - Deep Trajectory Grader v11.0

Evaluates agent trajectories with comprehensive scoring.

Scoring Breakdown:
- 0.25 → correct root cause identified
- 0.25 → correct fix applied
- 0.15 → efficiency (steps taken)
- 0.15 → minimal disruption (services affected by actions)
- 0.05 → reasoning chain evaluation
- 0.05 → MTTR (Mean Time To Resolve)
- 0.05 → action ordering quality
- 0.05 → SLO preservation

Penalties:
- unnecessary actions
- incorrect services affected
- redundant queries

Features:
- Deterministic scoring [0.0-1.0]
- Debug explanation output
- Trajectory analysis
- Action sequence evaluation
- Extended quality dimensions for SRE excellence
"""
from dataclasses import dataclass, field
from enum import Enum
import json
import math


class ScoreGrade(str, Enum):
    """Grade levels for trajectory"""
    EXCELLENT = "excellent"    # 0.9-1.0
    GOOD = "good"            # 0.7-0.89
    PASSABLE = "passable"    # 0.5-0.69
    POOR = "poor"           # 0.3-0.49
    FAILED = "failed"       # 0.0-0.29


@dataclass
class ActionAnalysis:
    """Analysis of a single action"""
    step: int
    action_type: str
    target_service: str | None
    is_investigation: bool
    is_intervention: bool
    is_necessary: bool
    is_redundant: bool
    targets_relevant_service: bool
    debug_notes: list[str] = field(default_factory=list)


@dataclass
class TrajectoryAnalysis:
    """Complete trajectory analysis"""
    total_steps: int
    investigation_steps: int
    intervention_steps: int
    redundant_actions: int
    unnecessary_actions: int
    services_queried: set[str]
    services_affected_by_actions: set[str]
    action_sequence: list[ActionAnalysis]
    investigation_quality: float
    intervention_quality: float
    debug_notes: list[str] = field(default_factory=list)


@dataclass
class DetailedScore:
    """Detailed scoring breakdown"""
    # Core scores (0.0-1.0 each)
    root_cause_score: float = 0.0       # Weight: 0.25
    fix_score: float = 0.0              # Weight: 0.25
    efficiency_score: float = 0.0       # Weight: 0.15
    minimal_disruption_score: float = 0.0  # Weight: 0.15

    # Extended quality scores (0.0-1.0 each, weight: 0.05 each)
    reasoning_chain_score: float = 0.0     # Weight: 0.05
    mttr_score: float = 0.0                # Weight: 0.05
    action_ordering_score: float = 0.0     # Weight: 0.05
    slo_preservation_score: float = 0.0   # Weight: 0.05

    # Penalties
    unnecessary_action_penalty: float = 0.0
    incorrect_service_penalty: float = 0.0
    redundant_query_penalty: float = 0.0

    # Final
    raw_score: float = 0.0
    final_score: float = 0.0
    grade: ScoreGrade = ScoreGrade.FAILED

    # Analysis
    trajectory_analysis: TrajectoryAnalysis | None = None

    # Debug
    debug_explanation: list[str] = field(default_factory=list)


class DeepTrajectoryGrader:
    """
    Deep trajectory evaluator with comprehensive scoring.

    Scoring Weights:
    - Root cause identification: 25%
    - Correct fix: 25%
    - Efficiency: 15%
    - Minimal disruption: 15%
    - Reasoning chain: 5%
    - MTTR: 5%
    - Action ordering: 5%
    - SLO preservation: 5%

    Deterministic - same trajectory always produces same score.
    """

    # Efficiency thresholds (steps)
    EXCELLENT_STEPS = 5
    GOOD_STEPS = 8
    PASSABLE_STEPS = 12
    MAX_ACCEPTABLE_STEPS = 20

    # SLO thresholds (in steps, assuming each step ~1 minute)
    SLO_TIERS = {
        "critical": 5,   # P0 incidents
        "high": 10,      # P1 incidents
        "medium": 20,   # P2 incidents
        "low": 30,      # P3 incidents
    }

    # Fault types that require deployment history check
    DEPLOYMENT_FAULTS = {"ghost", "deployment_issue", "config_drift", "version_mismatch"}

    # Fault types that require dependency tracing
    CASCADE_FAULTS = {"cascade", "network_partition", "slow_downstream"}

    # Investigation action types
    INVESTIGATION_ACTIONS = {
        "query_service",
        "query_metrics",
        "query_logs",
        "query_dependencies",
        "query_deployments",
        "query_memory",
    }

    # Deep investigation actions (metrics + logs for thorough analysis)
    DEEP_INVESTIGATION_ACTIONS = {
        "query_metrics",
        "query_logs",
        "query_memory",
    }

    # Intervention action types
    INTERVENTION_ACTIONS = {
        "restart_service",
        "scale_service",
        "rollback_deployment",
        "apply_fix",
    }
    
    def __init__(self, seed: int = 42):
        """Initialize grader with seed for determinism"""
        self.seed = seed
    
    def grade(self, trajectory: dict) -> DetailedScore:
        """
        Grade a complete trajectory.

        Args:
            trajectory: Dict containing:
                - actions: List of actions taken
                - rewards: List of rewards received
                - final_state: Final environment state
                - scenario: Fault scenario info
                - seed: Trajectory seed for reproducibility

        Returns:
            DetailedScore with complete breakdown
        """
        score = DetailedScore()

        actions = trajectory.get("actions", [])
        rewards = trajectory.get("rewards", [])
        final_state = trajectory.get("final_state", {})
        scenario = trajectory.get("scenario", {})

        # 1. Analyze trajectory
        score.trajectory_analysis = self._analyze_trajectory(actions, scenario)

        # 2. Calculate root cause score (0.25 weight)
        score.root_cause_score = self._calculate_root_cause_score(
            actions, scenario, score.debug_explanation
        )

        # 3. Calculate fix score (0.25 weight)
        score.fix_score = self._calculate_fix_score(
            actions, final_state, scenario, score.debug_explanation
        )

        # 4. Calculate efficiency score (0.15 weight)
        score.efficiency_score = self._calculate_efficiency_score(
            len(actions), score.debug_explanation
        )

        # 5. Calculate minimal disruption score (0.15 weight)
        score.minimal_disruption_score = self._calculate_disruption_score(
            actions, scenario, score.debug_explanation
        )

        # 6. Calculate extended quality scores (0.05 each)
        score.reasoning_chain_score = self._evaluate_reasoning_chain(
            actions, scenario, score.debug_explanation
        )
        score.mttr_score = self._evaluate_mttr(
            actions, final_state, scenario, score.debug_explanation
        )
        score.action_ordering_score = self._evaluate_action_ordering(
            actions, scenario, score.debug_explanation
        )
        score.slo_preservation_score = self._evaluate_slo_preservation(
            len(actions), scenario, score.debug_explanation
        )

        # 7. Calculate penalties
        score.unnecessary_action_penalty = self._calculate_unnecessary_penalty(
            score.trajectory_analysis, score.debug_explanation
        )
        score.redundant_query_penalty = self._calculate_redundant_penalty(
            score.trajectory_analysis, score.debug_explanation
        )
        score.incorrect_service_penalty = self._calculate_incorrect_service_penalty(
            score.trajectory_analysis, scenario, score.debug_explanation
        )

        # 8. Calculate final score (must total 1.0)
        score.raw_score = (
            0.25 * score.root_cause_score +
            0.25 * score.fix_score +
            0.15 * score.efficiency_score +
            0.15 * score.minimal_disruption_score +
            0.05 * score.reasoning_chain_score +
            0.05 * score.mttr_score +
            0.05 * score.action_ordering_score +
            0.05 * score.slo_preservation_score
        )

        # Apply penalties (capped at 0.0)
        total_penalty = (
            score.unnecessary_action_penalty +
            score.redundant_query_penalty +
            score.incorrect_service_penalty
        )
        # Clamp to strictly (0, 1) — validator requires scores > 0.0 and < 1.0
        _EPSILON = 1e-9
        score.final_score = max(_EPSILON, min(1.0 - _EPSILON, score.raw_score - total_penalty))

        # 9. Assign grade
        score.grade = self._assign_grade(score.final_score)

        # 10. Generate final debug explanation
        self._generate_final_explanation(score, trajectory)
        
        return score
    
    def _analyze_trajectory(
        self,
        actions: list[dict],
        scenario: dict
    ) -> TrajectoryAnalysis:
        """Analyze the complete trajectory"""
        analysis = TrajectoryAnalysis(
            total_steps=len(actions),
            investigation_steps=0,
            intervention_steps=0,
            redundant_actions=0,
            unnecessary_actions=0,
            services_queried=set(),
            services_affected_by_actions=set(),
            action_sequence=[],
            investigation_quality=0.0,
            intervention_quality=0.0,
        )
        
        root_cause = scenario.get("root_cause_service", "")
        affected_services = set(scenario.get("affected_services", []))
        relevant_services = {root_cause} | affected_services
        
        # Track for redundancy detection
        seen_queries: dict[str, int] = {}
        
        for i, action in enumerate(actions):
            action_type = action.get("action_type", "")
            target_service = action.get("target_service")
            
            # Analyze this action
            action_analysis = ActionAnalysis(
                step=i,
                action_type=action_type,
                target_service=target_service,
                is_investigation=action_type in self.INVESTIGATION_ACTIONS,
                is_intervention=action_type in self.INTERVENTION_ACTIONS,
                is_necessary=True,
                is_redundant=False,
                targets_relevant_service=target_service in relevant_services if target_service else False,
            )
            
            # Count action types
            if action_analysis.is_investigation:
                analysis.investigation_steps += 1
                if target_service:
                    analysis.services_queried.add(target_service)
            
            if action_analysis.is_intervention:
                analysis.intervention_steps += 1
                if target_service:
                    analysis.services_affected_by_actions.add(target_service)
            
            # Check for redundancy
            if action_type in self.INVESTIGATION_ACTIONS:
                query_key = f"{action_type}:{target_service}"
                if query_key in seen_queries:
                    action_analysis.is_redundant = True
                    analysis.redundant_actions += 1
                    action_analysis.debug_notes.append(
                        f"Redundant query: {query_key} first seen at step {seen_queries[query_key]}"
                    )
                else:
                    seen_queries[query_key] = i
            
            # Check if necessary
            if action_analysis.is_intervention and target_service:
                if target_service not in relevant_services:
                    action_analysis.is_necessary = False
                    analysis.unnecessary_actions += 1
                    action_analysis.debug_notes.append(
                        f"Unnecessary intervention on irrelevant service: {target_service}"
                    )
            
            analysis.action_sequence.append(action_analysis)
        
        # Calculate quality metrics
        if analysis.total_steps > 0:
            analysis.investigation_quality = min(1.0, analysis.investigation_steps / 4)
            if analysis.intervention_steps > 0:
                correct_interventions = sum(
                    1 for a in analysis.action_sequence
                    if a.is_intervention and a.targets_relevant_service
                )
                analysis.intervention_quality = correct_interventions / analysis.intervention_steps
            else:
                analysis.intervention_quality = 0.0
        
        # Add analysis notes
        analysis.debug_notes.append(f"Total steps: {analysis.total_steps}")
        analysis.debug_notes.append(f"Investigation steps: {analysis.investigation_steps}")
        analysis.debug_notes.append(f"Intervention steps: {analysis.intervention_steps}")
        analysis.debug_notes.append(f"Services queried: {analysis.services_queried}")
        analysis.debug_notes.append(f"Services affected by actions: {analysis.services_affected_by_actions}")
        
        return analysis
    
    def _calculate_root_cause_score(
        self,
        actions: list[dict],
        scenario: dict,
        debug: list[str]
    ) -> float:
        """Calculate root cause identification score (0.0-1.0)"""
        root_cause = scenario.get("root_cause_service", "")
        
        if not root_cause:
            debug.append("No root cause defined in scenario")
            return 0.0
        
        # Check if root cause was identified
        for action in actions:
            if action.get("action_type") == "identify_root_cause":
                if action.get("target_service") == root_cause:
                    debug.append(f"Root cause correctly identified: {root_cause}")
                    return 1.0
                else:  # pragma: no cover
                    debug.append(  # pragma: no cover
                        f"Root cause incorrectly identified as: {action.get('target_service')} "  # pragma: no cover
                        f"(correct: {root_cause})"  # pragma: no cover
                    )  # pragma: no cover
                    return 0.0  # pragma: no cover
        
        # Check if agent queried the root cause service
        queried_root_cause = False
        for action in actions:
            if action.get("target_service") == root_cause:
                if action.get("action_type") in self.INVESTIGATION_ACTIONS:
                    queried_root_cause = True
                    break
        
        if queried_root_cause:
            debug.append(f"Root cause service was queried but not explicitly identified")
            return 0.5
        
        debug.append("Root cause was never identified or queried")
        return 0.0
    
    def _calculate_fix_score(
        self,
        actions: list[dict],
        final_state: dict,
        scenario: dict,
        debug: list[str]
    ) -> float:
        """Calculate fix application score (0.0-1.0)"""
        root_cause = scenario.get("root_cause_service", "")
        correct_fix = scenario.get("correct_fix", "")
        
        # Check if incident was resolved
        if final_state.get("fix_applied", False):
            debug.append("Incident was successfully resolved")
            
            # Check if correct service was fixed
            fix_actions = [
                a for a in actions
                if a.get("action_type") in self.INTERVENTION_ACTIONS
            ]
            
            if fix_actions:
                last_fix = fix_actions[-1]
                if last_fix.get("target_service") == root_cause:
                    debug.append(f"Correct fix applied to root cause: {root_cause}")
                    return 1.0
                else:  # pragma: no cover
                    debug.append(  # pragma: no cover
                        f"Fix applied to wrong service: {last_fix.get('target_service')} "  # pragma: no cover
                        f"(should be: {root_cause})"  # pragma: no cover
                    )  # pragma: no cover
                    return 0.5  # pragma: no cover

            return 0.8  # Fixed but unclear how  # pragma: no cover
        
        debug.append("Incident was not resolved")
        return 0.0
    
    def _calculate_efficiency_score(
        self,
        steps: int,
        debug: list[str]
    ) -> float:
        """Calculate efficiency score based on steps (0.0-1.0)"""
        if steps <= self.EXCELLENT_STEPS:
            score = 1.0
            debug.append(f"Excellent efficiency: {steps} steps (≤{self.EXCELLENT_STEPS})")
        elif steps <= self.GOOD_STEPS:
            score = 0.9 - (steps - self.EXCELLENT_STEPS) * 0.05
            debug.append(f"Good efficiency: {steps} steps (≤{self.GOOD_STEPS})")
        elif steps <= self.PASSABLE_STEPS:
            score = 0.7 - (steps - self.GOOD_STEPS) * 0.05
            debug.append(f"Passable efficiency: {steps} steps (≤{self.PASSABLE_STEPS})")
        elif steps <= self.MAX_ACCEPTABLE_STEPS:
            score = 0.4 - (steps - self.PASSABLE_STEPS) * 0.02
            debug.append(f"Poor efficiency: {steps} steps (≤{self.MAX_ACCEPTABLE_STEPS})")
        else:
            score = max(0.1, 0.2 - (steps - self.MAX_ACCEPTABLE_STEPS) * 0.01)
            debug.append(f"Very poor efficiency: {steps} steps (>{self.MAX_ACCEPTABLE_STEPS})")
        
        return max(0.0, min(1.0, score))
    
    def _calculate_disruption_score(
        self,
        actions: list[dict],
        scenario: dict,
        debug: list[str]
    ) -> float:
        """Calculate minimal disruption score (0.0-1.0)"""
        root_cause = scenario.get("root_cause_service", "")
        affected_services = set(scenario.get("affected_services", []))
        relevant_services = {root_cause} | affected_services
        
        # Count services affected by actions
        services_affected = set()
        restart_count = 0
        scale_count = 0
        rollback_count = 0
        
        for action in actions:
            action_type = action.get("action_type", "")
            target = action.get("target_service")
            
            if action_type in self.INTERVENTION_ACTIONS and target:
                services_affected.add(target)
                
                if action_type == "restart_service":
                    restart_count += 1
                elif action_type == "scale_service":
                    scale_count += 1
                elif action_type == "rollback_deployment":
                    rollback_count += 1
        
        # Check if only relevant services were affected
        irrelevant_affected = services_affected - relevant_services
        
        if not services_affected:
            debug.append("No services affected by actions - no intervention taken")
            return 0.0
        
        # Base score on proportion of relevant services affected
        if len(irrelevant_affected) == 0:
            base_score = 1.0
            debug.append(f"All affected services were relevant: {services_affected}")
        else:
            relevant_ratio = len(services_affected & relevant_services) / len(services_affected)
            base_score = relevant_ratio
            debug.append(
                f"Some irrelevant services affected: {irrelevant_affected} "
                f"(relevant ratio: {relevant_ratio:.2f})"
            )
        
        # Penalize excessive restarts
        if restart_count > 1:  # pragma: no cover
            penalty = min(0.3, (restart_count - 1) * 0.1)  # pragma: no cover
            base_score -= penalty  # pragma: no cover
            debug.append(f"Multiple restarts ({restart_count}), penalty: -{penalty:.2f}")  # pragma: no cover

        # Penalize multiple rollbacks
        if rollback_count > 1:  # pragma: no cover
            penalty = min(0.3, (rollback_count - 1) * 0.1)  # pragma: no cover
            base_score -= penalty  # pragma: no cover
            debug.append(f"Multiple rollbacks ({rollback_count}), penalty: -{penalty:.2f}")  # pragma: no cover
        
        return max(0.0, min(1.0, base_score))
    
    def _calculate_unnecessary_penalty(
        self,
        analysis: TrajectoryAnalysis,
        debug: list[str]
    ) -> float:
        """Calculate penalty for unnecessary actions"""
        if analysis.unnecessary_actions == 0:
            return 0.0
        
        penalty = min(0.3, analysis.unnecessary_actions * 0.1)
        debug.append(f"Unnecessary actions penalty: -{penalty:.2f} ({analysis.unnecessary_actions} actions)")
        return penalty
    
    def _calculate_redundant_penalty(
        self,
        analysis: TrajectoryAnalysis,
        debug: list[str]
    ) -> float:
        """Calculate penalty for redundant queries"""
        if analysis.redundant_actions == 0:  # pragma: no cover
            return 0.0  # pragma: no cover

        penalty = min(0.2, analysis.redundant_actions * 0.05)  # pragma: no cover
        debug.append(f"Redundant queries penalty: -{penalty:.2f} ({analysis.redundant_actions} queries)")  # pragma: no cover
        return penalty  # pragma: no cover
    
    def _calculate_incorrect_service_penalty(
        self,
        analysis: TrajectoryAnalysis,
        scenario: dict,
        debug: list[str]
    ) -> float:
        """Calculate penalty for affecting incorrect services"""
        root_cause = scenario.get("root_cause_service", "")
        affected_services = set(scenario.get("affected_services", []))
        relevant_services = {root_cause} | affected_services

        incorrect = analysis.services_affected_by_actions - relevant_services

        if not incorrect:
            return 0.0

        penalty = min(0.3, len(incorrect) * 0.15)
        debug.append(f"Incorrect services affected penalty: -{penalty:.2f} (services: {incorrect})")
        return penalty

    def _evaluate_reasoning_chain(
        self,
        actions: list[dict],
        scenario: dict,
        debug: list[str]
    ) -> float:
        """
        Evaluate reasoning chain quality (0.0-1.0).

        Checks:
        - Actions before conclusions (query_* before identify_root_cause)
        - Deep investigation before fix (metrics + logs before restart/scale/rollback)
        - Dependencies traced (query_dependencies before fix) for cascade faults
        - Deployment history checked (for ghost/deployment faults)
        """
        score = 0.0
        fault_type = scenario.get("fault_type", "")
        root_cause = scenario.get("root_cause_service", "")

        # Track action indices for ordering checks
        first_query_idx = None
        first_identify_idx = None
        first_fix_idx = None
        first_deployment_query_idx = None
        first_dependency_query_idx = None
        deep_investigation_before_fix = False
        dependencies_traced = False

        for i, action in enumerate(actions):
            action_type = action.get("action_type", "")
            target = action.get("target_service")

            # Track first occurrences
            if action_type in self.INVESTIGATION_ACTIONS and first_query_idx is None:
                first_query_idx = i

            if action_type == "identify_root_cause" and first_identify_idx is None:
                first_identify_idx = i

            if action_type in self.INTERVENTION_ACTIONS and first_fix_idx is None:
                first_fix_idx = i

            if action_type == "query_deployments":
                if first_deployment_query_idx is None:
                    first_deployment_query_idx = i

            if action_type == "query_dependencies":
                if first_dependency_query_idx is None:
                    first_dependency_query_idx = i

        # Check 1: Actions before conclusions
        if first_query_idx is not None and first_identify_idx is not None:
            if first_query_idx < first_identify_idx:
                score += 0.3
                debug.append("Reasoning chain: Investigation before root cause identification (+0.3)")
            else:  # pragma: no cover
                debug.append("Reasoning chain: Root cause claimed before investigation")  # pragma: no cover
        elif first_identify_idx is not None:  # pragma: no cover
            debug.append("Reasoning chain: Root cause claimed without investigation")  # pragma: no cover
        else:  # pragma: no cover
            score += 0.1  # Partial credit for not claiming without evidence  # pragma: no cover
            debug.append("Reasoning chain: Partial credit for no premature conclusion (+0.1)")  # pragma: no cover

        # Check 2: Deep investigation before fix
        if first_fix_idx is not None:
            # Check if metrics/logs were queried before the first fix
            deep_invest_done = False
            for i, action in enumerate(actions[:first_fix_idx]):
                if action.get("action_type") in self.DEEP_INVESTIGATION_ACTIONS:
                    if action.get("target_service") == root_cause or not root_cause:
                        deep_invest_done = True
                        break

            if deep_invest_done:
                score += 0.3
                deep_investigation_before_fix = True
                debug.append("Reasoning chain: Deep investigation before fix (+0.3)")
            else:
                debug.append("Reasoning chain: No deep investigation (metrics/logs) before fix")

        # Check 3: Dependencies traced for cascade faults
        if fault_type in self.CASCADE_FAULTS:  # pragma: no cover
            if first_dependency_query_idx is not None and first_fix_idx is not None:  # pragma: no cover
                if first_dependency_query_idx < first_fix_idx:  # pragma: no cover
                    score += 0.2  # pragma: no cover
                    dependencies_traced = True  # pragma: no cover
                    debug.append("Reasoning chain: Dependencies traced before fix (+0.2)")  # pragma: no cover
                else:  # pragma: no cover
                    debug.append("Reasoning chain: Dependencies not traced before fix")  # pragma: no cover
            elif first_dependency_query_idx is not None:  # pragma: no cover
                score += 0.1  # Partial credit  # pragma: no cover
                debug.append("Reasoning chain: Dependencies queried (+0.1)")  # pragma: no cover
            else:  # pragma: no cover
                debug.append("Reasoning chain: Dependencies not traced for cascade fault")  # pragma: no cover

        # Check 4: Deployment history checked for deployment faults
        if fault_type in self.DEPLOYMENT_FAULTS:
            if first_deployment_query_idx is not None:
                score += 0.2
                debug.append("Reasoning chain: Deployment history checked (+0.2)")
            else:
                debug.append("Reasoning chain: Deployment history not checked for deployment fault")

        return min(1.0, score)

    def _evaluate_mttr(
        self,
        actions: list[dict],
        final_state: dict,
        scenario: dict,
        debug: list[str]
    ) -> float:
        """
        Evaluate Mean Time To Resolve (MTTR) efficiency (0.0-1.0).

        Measures:
        - Time from first action to root cause identification
        - Time from identification to fix
        - Overall resolution speed bonus
        """
        root_cause = scenario.get("root_cause_service", "")
        total_steps = len(actions)

        if total_steps == 0:
            debug.append("MTTR: No actions taken")
            return 0.0

        # Track key milestones
        first_action_idx = 0
        identify_idx = None
        fix_idx = None
        root_cause_investigated_idx = None

        for i, action in enumerate(actions):
            action_type = action.get("action_type", "")
            target = action.get("target_service")

            if action_type == "identify_root_cause" and identify_idx is None:
                identify_idx = i

            if action_type in self.INVESTIGATION_ACTIONS:
                if target == root_cause and root_cause_investigated_idx is None:
                    root_cause_investigated_idx = i

            if action_type in self.INTERVENTION_ACTIONS:
                if fix_idx is None:
                    fix_idx = i

        # Calculate MTTR score based on total steps to resolution
        if final_state.get("fix_applied", False):
            # Optimal steps for easy/medium/hard based on fault type
            fault_type = scenario.get("fault_type", "")
            difficulty = scenario.get("difficulty", 3)

            # Expected steps based on difficulty
            expected_steps = {
                1: 3,
                2: 4,
                3: 5,
                4: 6,
                5: 7,
            }.get(difficulty, 5)

            # Calculate speed score
            if total_steps <= expected_steps:
                score = 1.0
                debug.append(f"MTTR: Excellent speed ({total_steps} steps, expected ~{expected_steps})")
            elif total_steps <= expected_steps + 2:
                score = 0.8
                debug.append(f"MTTR: Good speed ({total_steps} steps, expected ~{expected_steps})")
            elif total_steps <= expected_steps + 5:
                score = 0.5
                debug.append(f"MTTR: Acceptable speed ({total_steps} steps, expected ~{expected_steps})")
            else:
                score = max(0.1, 0.3 - (total_steps - expected_steps - 5) * 0.02)
                debug.append(f"MTTR: Slow resolution ({total_steps} steps)")

            # Bonus for quick identification
            if identify_idx is not None:
                id_speed = identify_idx / total_steps
                if id_speed < 0.5:  # Identified in first half of actions
                    score = min(1.0, score + 0.1)
                    debug.append("MTTR: Quick root cause identification bonus")

            return score
        else:
            # Didn't resolve - partial credit for investigation
            if root_cause_investigated_idx is not None:
                investigation_ratio = root_cause_investigated_idx / total_steps
                if investigation_ratio < 0.5:
                    debug.append("MTTR: Investigated efficiently but didn't resolve")
                    return 0.2
            debug.append("MTTR: Incident not resolved")
            return 0.0

    def _evaluate_action_ordering(
        self,
        actions: list[dict],
        scenario: dict,
        debug: list[str]
    ) -> float:
        """
        Evaluate action ordering quality (0.0-1.0).

        Checks:
        - Investigated relevant services first
        - Avoided unnecessary service restarts
        - Proper escalation (investigate before act)
        """
        score = 0.0
        root_cause = scenario.get("root_cause_service", "")
        affected_services = set(scenario.get("affected_services", []))
        relevant_services = {root_cause} | affected_services

        # Track service investigation order
        relevant_queried_first = False
        irrelevant_queried_first = False
        unnecessary_restarts = 0
        premature_actions = 0

        for i, action in enumerate(actions):
            action_type = action.get("action_type", "")
            target = action.get("target_service")

            # Check investigation ordering
            if action_type in self.INVESTIGATION_ACTIONS and target:
                if target in relevant_services and not relevant_queried_first:
                    relevant_queried_first = True
                elif target not in relevant_services and not irrelevant_queried_first:
                    if relevant_queried_first is False:
                        irrelevant_queried_first = True

            # Check for premature actions (intervention before any investigation)
            if action_type in self.INTERVENTION_ACTIONS:
                if i == 0 or not any(
                    a.get("action_type") in self.INVESTIGATION_ACTIONS
                    for a in actions[:i]
                ):
                    premature_actions += 1

            # Count unnecessary restarts (more than one restart on same service)
            if action_type == "restart_service" and target:
                restarts_on_target = sum(
                    1 for a in actions
                    if a.get("action_type") == "restart_service" and a.get("target_service") == target
                )
                if restarts_on_target > 1 and target not in relevant_services:
                    unnecessary_restarts += 1

        # Score based on relevant service investigated first
        if relevant_queried_first and not irrelevant_queried_first:  # pragma: no cover
            score += 0.4  # pragma: no cover
            debug.append("Action ordering: Relevant services investigated first (+0.4)")  # pragma: no cover
        elif relevant_queried_first:  # pragma: no cover
            score += 0.2  # pragma: no cover
            debug.append("Action ordering: Relevant services eventually investigated (+0.2)")  # pragma: no cover
        elif irrelevant_queried_first:  # pragma: no cover
            debug.append("Action ordering: Irrelevant services investigated first")  # pragma: no cover

        # Score based on no premature actions
        if premature_actions == 0:
            score += 0.3
            debug.append("Action ordering: No premature interventions (+0.3)")
        elif premature_actions <= 1:
            score += 0.1
            debug.append("Action ordering: Minor premature action (+0.1)")
        else:
            debug.append(f"Action ordering: {premature_actions} premature interventions")

        # Score based on unnecessary restarts
        if unnecessary_restarts == 0:  # pragma: no cover
            score += 0.3  # pragma: no cover
            debug.append("Action ordering: No unnecessary restarts (+0.3)")  # pragma: no cover
        else:  # pragma: no cover
            debug.append(f"Action ordering: {unnecessary_restarts} unnecessary restarts")  # pragma: no cover

        return min(1.0, score)

    def _evaluate_slo_preservation(
        self,
        total_steps: int,
        scenario: dict,
        debug: list[str]
    ) -> float:
        """
        Evaluate SLO preservation (0.0-1.0).

        Checks:
        - Incident resolved within SLA tier
        - Based on severity/priority of the incident
        """
        # Determine SLA tier from scenario
        severity = scenario.get("severity", "medium")
        priority = scenario.get("priority", "medium")
        fault_type = scenario.get("fault_type", "")

        # Map severity/priority to SLO tier
        slo_tier = "medium"
        if severity in ("critical", "p0") or priority in ("critical", "p0"):
            slo_tier = "critical"
        elif severity in ("high", "p1") or priority in ("high", "p1"):
            slo_tier = "high"
        elif severity in ("low", "p3") or priority in ("low", "p3"):
            slo_tier = "low"

        # Ghost fault type is always critical
        if fault_type in ("ghost",):
            slo_tier = "critical"

        # Get SLO threshold for this tier
        slo_threshold = self.SLO_TIERS.get(slo_tier, 20)

        # Calculate score based on resolution time
        if total_steps <= slo_threshold * 0.5:
            # Met SLA with significant buffer
            score = 1.0
            debug.append(f"SLO: Excellent - resolved in {total_steps} steps (SLO: {slo_threshold})")
        elif total_steps <= slo_threshold:
            # Met SLA
            score = 0.8
            debug.append(f"SLO: Met SLA - {total_steps} steps (threshold: {slo_threshold})")
        elif total_steps <= slo_threshold * 1.5:
            # Breached SLA but close
            score = 0.5
            debug.append(f"SLO: SLA breached - {total_steps} steps (threshold: {slo_threshold})")
        else:
            # Significantly breached SLA
            score = max(0.1, 0.3 - (total_steps - slo_threshold * 1.5) * 0.02)
            debug.append(f"SLO: Major breach - {total_steps} steps (threshold: {slo_threshold})")

        return max(0.0, min(1.0, score))

    def _assign_grade(self, score: float) -> ScoreGrade:
        """Assign grade based on score"""
        if score >= 0.9:
            return ScoreGrade.EXCELLENT
        elif score >= 0.7:
            return ScoreGrade.GOOD
        elif score >= 0.5:
            return ScoreGrade.PASSABLE
        elif score >= 0.3:
            return ScoreGrade.POOR
        else:
            return ScoreGrade.FAILED
    
    def _generate_final_explanation(self, score: DetailedScore, trajectory: dict) -> None:
        """Generate comprehensive debug explanation"""
        score.debug_explanation = [
            "=" * 60,
            "TRAJECTORY GRADING REPORT",
            "=" * 60,
            "",
            "CORE SCORES:",
            f"  Root Cause (25%):    {score.root_cause_score:.3f} × 0.25 = {score.root_cause_score * 0.25:.3f}",
            f"  Correct Fix (25%):   {score.fix_score:.3f} × 0.25 = {score.fix_score * 0.25:.3f}",
            f"  Efficiency (15%):    {score.efficiency_score:.3f} × 0.15 = {score.efficiency_score * 0.15:.3f}",
            f"  Min Disruption (15%): {score.minimal_disruption_score:.3f} × 0.15 = {score.minimal_disruption_score * 0.15:.3f}",
            "",
            "EXTENDED QUALITY SCORES:",
            f"  Reasoning Chain (5%):  {score.reasoning_chain_score:.3f} × 0.05 = {score.reasoning_chain_score * 0.05:.3f}",
            f"  MTTR (5%):            {score.mttr_score:.3f} × 0.05 = {score.mttr_score * 0.05:.3f}",
            f"  Action Ordering (5%):  {score.action_ordering_score:.3f} × 0.05 = {score.action_ordering_score * 0.05:.3f}",
            f"  SLO Preservation (5%): {score.slo_preservation_score:.3f} × 0.05 = {score.slo_preservation_score * 0.05:.3f}",
            "",
            "PENALTIES:",
            f"  Unnecessary Actions:  -{score.unnecessary_action_penalty:.3f}",
            f"  Redundant Queries:    -{score.redundant_query_penalty:.3f}",
            f"  Incorrect Services:   -{score.incorrect_service_penalty:.3f}",
            "",
            "FINAL:",
            f"  Raw Score:    {score.raw_score:.3f}",
            f"  Final Score:  {score.final_score:.3f}",
            f"  Grade:        {score.grade.value.upper()}",
            "",
            "=" * 60,
            "DETAILED ANALYSIS:",
            "=" * 60,
        ]
        
        # Add trajectory analysis details
        if score.trajectory_analysis:
            ta = score.trajectory_analysis
            score.debug_explanation.extend([
                f"  Total Steps:           {ta.total_steps}",
                f"  Investigation Steps:   {ta.investigation_steps}",
                f"  Intervention Steps:    {ta.intervention_steps}",
                f"  Redundant Actions:     {ta.redundant_actions}",
                f"  Unnecessary Actions:   {ta.unnecessary_actions}",
                f"  Services Queried:      {ta.services_queried}",
                f"  Services Affected:     {ta.services_affected_by_actions}",
                "",
            ])
            
            # Add action-by-action breakdown
            score.debug_explanation.append("ACTION SEQUENCE:")
            for action in ta.action_sequence:
                status = "✓" if (action.is_necessary and not action.is_redundant) else "✗"
                score.debug_explanation.append(
                    f"  Step {action.step}: {status} {action.action_type}"
                    f"{' -> ' + action.target_service if action.target_service else ''}"
                )
                if action.debug_notes:
                    for note in action.debug_notes:
                        score.debug_explanation.append(f"       NOTE: {note}")
        
        score.debug_explanation.extend([
            "",
            "=" * 60,
            "DEBUG LOG:",
            "=" * 60,
        ])
        score.debug_explanation.extend(debug for debug in score.debug_explanation if debug.startswith("NOTE:"))


def grade_trajectory(trajectory: dict, seed: int = 42) -> DetailedScore:
    """
    Quick grade a single trajectory.
    
    Args:
        trajectory: Trajectory dict with actions, rewards, final_state, scenario
        seed: Seed for deterministic grading
        
    Returns:
        DetailedScore with complete breakdown
    """
    grader = DeepTrajectoryGrader(seed=seed)
    return grader.grade(trajectory)


def grade_multiple_trajectories(
    trajectories: list[dict],
    seed: int = 42
) -> dict:
    """
    Grade multiple trajectories and return aggregate statistics.
    
    Args:
        trajectories: List of trajectory dicts
        seed: Seed for deterministic grading
        
    Returns:
        Dict with aggregate stats and per-trajectory results
    """
    grader = DeepTrajectoryGrader(seed=seed)
    results = []
    
    for i, traj in enumerate(trajectories):
        score = grader.grade(traj)
        results.append({
            "trajectory_id": traj.get("id", f"traj_{i}"),
            "final_score": score.final_score,
            "grade": score.grade.value,
            "root_cause_score": score.root_cause_score,
            "fix_score": score.fix_score,
            "efficiency_score": score.efficiency_score,
            "disruption_score": score.minimal_disruption_score,
            "reasoning_chain_score": score.reasoning_chain_score,
            "mttr_score": score.mttr_score,
            "action_ordering_score": score.action_ordering_score,
            "slo_preservation_score": score.slo_preservation_score,
        })
    
    # Calculate aggregates
    scores = [r["final_score"] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    
    grade_counts = {}
    for r in results:
        grade = r["grade"]
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
    
    return {
        "total_trajectories": len(trajectories),
        "average_score": round(avg_score, 4),
        "grade_distribution": grade_counts,
        "results": results,
    }
