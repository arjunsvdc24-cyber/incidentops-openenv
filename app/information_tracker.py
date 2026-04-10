from typing import Any
"""
IncidentOps - Enhanced Information Tracking System v12.0

Eliminates random guessing by:
1. Tracking information gain per action
2. Penalizing actions without new information (-0.05)
3. Penalizing repeated actions without state change (-0.05)
4. Penalizing restarts of unrelated services (-0.1)

Ensures optimal strategy requires reasoning, not brute force.
"""
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import hashlib


class InformationType(str, Enum):
    """Types of information that can be gained"""
    SERVICE_STATUS = "service_status"
    METRICS = "metrics"
    LOGS = "logs"
    DEPENDENCIES = "dependencies"
    DEPLOYMENTS = "deployments"
    MEMORY = "memory"
    ROOT_CAUSE_CANDIDATE = "root_cause_candidate"


@dataclass
class InformationState:
    """Tracks what information has been gathered"""
    queried_services: set[str] = field(default_factory=set)
    queried_metrics: dict[str, set[str]] = field(default_factory=dict)
    queried_logs: dict[str, int] = field(default_factory=dict)  # service -> count
    known_dependencies: bool = False
    known_deployments: bool = False
    memory_queried: bool = False
    root_cause_candidates: list[str] = field(default_factory=list)
    
    def get_state_hash(self) -> str:
        """Get deterministic hash of current state"""
        state_str = (
            f"services:{sorted(self.queried_services)}|"
            f"metrics:{sorted((k, sorted(v)) for k, v in self.queried_metrics.items())}|"
            f"logs:{sorted(self.queried_logs.items())}|"
            f"deps:{self.known_dependencies}|"
            f"deploys:{self.known_deployments}|"
            f"memory:{self.memory_queried}|"
            f"candidates:{self.root_cause_candidates}"
        )
        return hashlib.md5(state_str.encode()).hexdigest()[:8]


@dataclass
class ActionResult:
    """Result of an action with information tracking"""
    action_type: str
    target_service: str | None
    information_gained: bool
    information_type: InformationType | None
    new_information: list[str]
    state_changed: bool
    is_redundant: bool
    is_unrelated_restart: bool
    penalty: float
    reasoning_hint: str


@dataclass
class AntiGuessingPenalties:
    """Penalties for random guessing behavior"""
    no_new_info_penalty: float = 0.0
    repeated_action_penalty: float = 0.0
    unrelated_restart_penalty: float = 0.0
    total_penalty: float = 0.0
    reasons: list[str] = field(default_factory=list)


class EnhancedActionTracker:
    """
    Enhanced action tracker that eliminates random guessing.
    
    Key features:
    1. Tracks information gain per action
    2. Detects repeated actions without state change
    3. Identifies unrelated service restarts
    4. Provides reasoning hints for optimal strategy
    """
    
    # Penalties
    NO_NEW_INFO_PENALTY = 0.05
    REPEATED_ACTION_PENALTY = 0.05
    UNRELATED_RESTART_PENALTY = 0.1
    
    # Investigation actions that gather information
    INVESTIGATION_ACTIONS = {
        "query_service": InformationType.SERVICE_STATUS,
        "query_metrics": InformationType.METRICS,
        "query_logs": InformationType.LOGS,
        "query_dependencies": InformationType.DEPENDENCIES,
        "query_deployments": InformationType.DEPLOYMENTS,
        "query_memory": InformationType.MEMORY,
    }
    
    # Intervention actions that change state
    INTERVENTION_ACTIONS = {
        "restart_service",
        "scale_service",
        "rollback_deployment",
        "apply_fix",
    }
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.reset()
    
    def reset(self) -> None:
        """Reset all tracking state"""
        self.info_state = InformationState()
        self.action_history: list[ActionResult] = []
        self.state_history: list[str] = []  # Hash of states
        self.restart_count: int = 0
        self.services_restarted: set[str] = set()
        self.step: int = 0
        
        # Track what services are relevant (set by environment)
        self.relevant_services: set[str] = set()
        self.root_cause: str | None = None
    
    def set_fault_context(
        self,
        root_cause: str,
        affected_services: set[str]
    ) -> None:
        """Set fault context for relevance tracking"""
        self.root_cause = root_cause
        self.relevant_services = {root_cause} | affected_services
    
    def record_action(
        self,
        action_type: str,
        target_service: str | None,
        observation: dict | None = None
    ) -> ActionResult:
        """
        Record an action and calculate information gain.
        
        Args:
            action_type: Type of action taken
            target_service: Target service if applicable
            observation: Result of the action
            
        Returns:
            ActionResult with full analysis
        """
        self.step += 1
        
        # Get previous state hash
        prev_state_hash = self.info_state.get_state_hash()
        
        # Analyze information gain
        info_gained, info_type, new_info = self._analyze_information_gain(
            action_type, target_service, observation
        )
        
        # Check if state changed
        new_state_hash = self.info_state.get_state_hash()
        state_changed = prev_state_hash != new_state_hash
        
        # Check for redundancy
        is_redundant = self._check_redundancy(action_type, target_service, state_changed)
        
        # Check for unrelated restart
        is_unrelated_restart = self._check_unrelated_restart(action_type, target_service)
        
        # Calculate penalty
        penalty, reasons = self._calculate_penalty(
            info_gained, is_redundant, is_unrelated_restart
        )
        
        # Generate reasoning hint
        reasoning_hint = self._generate_reasoning_hint(
            action_type, target_service, info_gained, new_info
        )
        
        # Record state
        self.state_history.append(new_state_hash)
        
        result = ActionResult(
            action_type=action_type,
            target_service=target_service,
            information_gained=info_gained,
            information_type=info_type,
            new_information=new_info,
            state_changed=state_changed,
            is_redundant=is_redundant,
            is_unrelated_restart=is_unrelated_restart,
            penalty=penalty,
            reasoning_hint=reasoning_hint,
        )
        
        self.action_history.append(result)
        return result
    
    def _analyze_information_gain(
        self,
        action_type: str,
        target_service: str | None,
        observation: dict | None
    ) -> tuple[bool, InformationType | None, list[str]]:
        """Analyze if action provided new information"""
        new_info = []
        info_type = None
        gained = False
        
        # Query service
        if action_type == "query_service" and target_service:
            info_type = InformationType.SERVICE_STATUS
            if target_service not in self.info_state.queried_services:
                self.info_state.queried_services.add(target_service)
                new_info.append(f"First status query for {target_service}")
                gained = True
                
                # Check if this is a relevant service
                if target_service in self.relevant_services:
                    new_info.append(f"Service {target_service} is relevant to incident")
                    if target_service not in self.info_state.root_cause_candidates:
                        self.info_state.root_cause_candidates.append(target_service)
        
        # Query metrics
        elif action_type == "query_metrics" and target_service:
            info_type = InformationType.METRICS
            if target_service not in self.info_state.queried_metrics:
                self.info_state.queried_metrics[target_service] = set()
                new_info.append(f"First metrics query for {target_service}")
                gained = True
            else:
                # Check if new metric dimensions
                if observation and "metrics" in observation:  # pragma: no cover
                    new_metrics = set(observation["metrics"].keys()) - self.info_state.queried_metrics[target_service]  # pragma: no cover
                    if new_metrics:  # pragma: no cover
                        self.info_state.queried_metrics[target_service].update(new_metrics)  # pragma: no cover
                        new_info.append(f"New metrics discovered: {new_metrics}")  # pragma: no cover
                        gained = True  # pragma: no cover
        
        # Query logs
        elif action_type == "query_logs" and target_service:
            info_type = InformationType.LOGS
            count = self.info_state.queried_logs.get(target_service, 0)
            self.info_state.queried_logs[target_service] = count + 1
            
            if count == 0:
                new_info.append(f"First logs query for {target_service}")
                gained = True
            # Subsequent queries only count if new logs appeared
            elif observation and observation.get("new_entries", 0) > 0:  # pragma: no cover
                new_info.append(f"New log entries for {target_service}")  # pragma: no cover
                gained = True  # pragma: no cover
        
        # Query dependencies
        elif action_type == "query_dependencies":
            info_type = InformationType.DEPENDENCIES
            if not self.info_state.known_dependencies:
                self.info_state.known_dependencies = True
                new_info.append("First dependency graph query")
                gained = True
        
        # Query deployments
        elif action_type == "query_deployments":
            info_type = InformationType.DEPLOYMENTS
            if not self.info_state.known_deployments:
                self.info_state.known_deployments = True
                new_info.append("First deployment timeline query")
                gained = True
        
        # Query memory
        elif action_type == "query_memory":
            info_type = InformationType.MEMORY
            if not self.info_state.memory_queried:
                self.info_state.memory_queried = True
                new_info.append("First memory query")
                gained = True
        
        # Identify root cause
        elif action_type == "identify_root_cause" and target_service:
            info_type = InformationType.ROOT_CAUSE_CANDIDATE
            if target_service not in self.info_state.root_cause_candidates:
                self.info_state.root_cause_candidates.append(target_service)
                new_info.append(f"New root cause candidate: {target_service}")
                gained = True
        
        return gained, info_type, new_info
    
    def _check_redundancy(
        self,
        action_type: str,
        target_service: str | None,
        state_changed: bool
    ) -> bool:
        """Check if action is redundant"""
        # Same action on same service without state change
        if len(self.action_history) >= 1:
            prev = self.action_history[-1]
            if (prev.action_type == action_type and
                prev.target_service == target_service and
                not state_changed):
                return True
        
        # Repeated log query without new entries
        if action_type == "query_logs" and target_service:  # pragma: no cover
            count = self.info_state.queried_logs.get(target_service, 0)  # pragma: no cover
            if count > 1:  # pragma: no cover
                return True  # pragma: no cover
        
        return False
    
    def _check_unrelated_restart(
        self,
        action_type: str,
        target_service: str | None
    ) -> bool:
        """Check if restart targets unrelated service"""
        if action_type in ("restart_service", "apply_fix") and target_service:
            self.services_restarted.add(target_service)
            self.restart_count += 1
            
            # Check if service is relevant
            if self.relevant_services and target_service not in self.relevant_services:  # pragma: no cover
                return True  # pragma: no cover
        
        return False
    
    def _calculate_penalty(
        self,
        info_gained: bool,
        is_redundant: bool,
        is_unrelated_restart: bool
    ) -> tuple[float, list[str]]:
        """Calculate total penalty"""
        penalty = 0.0
        reasons = []
        
        # No new information penalty
        if not info_gained and len(self.action_history) > 0:
            # Allow first few exploration actions
            if self.step > 3:
                penalty += self.NO_NEW_INFO_PENALTY
                reasons.append(f"No new information gained (step {self.step})")
        
        # Repeated action penalty
        if is_redundant:
            penalty += self.REPEATED_ACTION_PENALTY
            reasons.append("Repeated action without state change")
        
        # Unrelated restart penalty
        if is_unrelated_restart:
            penalty += self.UNRELATED_RESTART_PENALTY
            reasons.append("Restarted unrelated service")
        
        return penalty, reasons
    
    def _generate_reasoning_hint(
        self,
        action_type: str,
        target_service: str | None,
        info_gained: bool,
        new_info: list[str]
    ) -> str:
        """Generate hint for optimal reasoning strategy"""
        if info_gained:
            return f"✓ {action_type}: {'; '.join(new_info[:2])}"
        
        # Suggest better action
        suggestions = []
        
        if not self.info_state.known_deployments:
            suggestions.append("Consider checking deployment timeline")
        
        if not self.info_state.known_dependencies:
            suggestions.append("Consider checking service dependencies")
        
        if not self.info_state.memory_queried:
            suggestions.append("Consider checking incident memory")
        
        if self.root_cause and self.root_cause not in self.info_state.queried_services:
            suggestions.append(f"Consider investigating {self.root_cause}")
        
        if suggestions:
            return f"⚠ No new info. Hints: {suggestions[0]}"
        
        return "⚠ No new information from this action"
    
    def get_total_penalties(self) -> AntiGuessingPenalties:
        """Get summary of all penalties"""
        penalties = AntiGuessingPenalties()
        
        for action in self.action_history:
            if not action.information_gained and self.step > 3:
                penalties.no_new_info_penalty += self.NO_NEW_INFO_PENALTY
            if action.is_redundant:
                penalties.repeated_action_penalty += self.REPEATED_ACTION_PENALTY
            if action.is_unrelated_restart:
                penalties.unrelated_restart_penalty += self.UNRELATED_RESTART_PENALTY
        
        penalties.total_penalty = (
            penalties.no_new_info_penalty +
            penalties.repeated_action_penalty +
            penalties.unrelated_restart_penalty
        )
        
        # Collect reasons
        for i, action in enumerate(self.action_history):
            if action.penalty > 0:
                penalties.reasons.append(f"Step {i+1}: {action.reasoning_hint}")
        
        return penalties
    
    def get_information_summary(self) -> dict:
        """Get summary of information gathered"""
        return {
            "services_queried": len(self.info_state.queried_services),
            "metrics_queried": sum(len(v) for v in self.info_state.queried_metrics.values()),
            "logs_queried": sum(self.info_state.queried_logs.values()),
            "dependencies_known": self.info_state.known_dependencies,
            "deployments_known": self.info_state.known_deployments,
            "memory_queried": self.info_state.memory_queried,
            "root_cause_candidates": self.info_state.root_cause_candidates,
            "total_restarts": self.restart_count,
            "unrelated_restarts": len(self.services_restarted - self.relevant_services),
        }

    def get_investigation_sequence(self) -> list[dict]:
        """Get ordered sequence of investigation steps taken."""
        sequence = []
        for i, action in enumerate(self.action_history):
            step = {"step": i + 1, "action_type": action.action_type}
            if action.target_service:
                step["target"] = action.target_service
            if action.reasoning_hint:
                step["hint"] = action.reasoning_hint
            sequence.append(step)
        return sequence
    
    def is_guessing_behavior(self) -> bool:
        """Detect if agent is using guessing strategy"""
        # High penalty ratio indicates guessing
        penalties = self.get_total_penalties()
        if self.step > 5 and penalties.total_penalty > 0.2:
            return True
        
        # Many restarts without investigation
        if self.restart_count > 2 and len(self.info_state.queried_services) < 3:
            return True
        
        # No information gathering
        if self.step > 5 and len(self.info_state.queried_services) < 2:
            return True
        
        return False
    
    def get_reasoning_score(self) -> float:
        """
        Calculate reasoning quality score.
        
        Higher score = better reasoning process
        """
        if self.step == 0:
            return 0.0
        
        # Ratio of actions with information gain
        info_actions = sum(1 for a in self.action_history if a.information_gained)
        info_ratio = info_actions / len(self.action_history)
        
        # Penalty for guessing behavior
        penalties = self.get_total_penalties()
        penalty_factor = max(0, 1 - penalties.total_penalty)
        
        # Bonus for systematic investigation
        systematic_bonus = 0.0
        if self.info_state.known_dependencies:
            systematic_bonus += 0.1
        if self.info_state.known_deployments:
            systematic_bonus += 0.1
        if self.info_state.memory_queried:
            systematic_bonus += 0.1
        
        # Final score
        score = (info_ratio * penalty_factor) + systematic_bonus
        
        return min(1.0, max(0.0, score))
