"""
IncidentOps - Anti-Brute-Force Detection System v11.0

Prevents agents from solving problems via brute force.

Penalties:
- Restarting >2 services without justification: -0.2
- Querying logs repeatedly for same service: -0.05 per repeat
- Taking actions without new information: -0.02

Tracks action history and detects redundant behavior.
"""
from dataclasses import dataclass, field
from typing import Optional, Set, Dict, List
from enum import Enum
from collections import defaultdict


class ActionType(str, Enum):
    """Action types for tracking"""
    QUERY_SERVICE = "query_service"
    QUERY_METRICS = "query_metrics"
    QUERY_LOGS = "query_logs"
    QUERY_DEPENDENCIES = "query_dependencies"
    QUERY_DEPLOYMENTS = "query_deployments"
    RESTART_SERVICE = "restart_service"
    SCALE_SERVICE = "scale_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    QUERY_MEMORY = "query_memory"
    IDENTIFY_ROOT_CAUSE = "identify_root_cause"
    APPLY_FIX = "apply_fix"


@dataclass
class ActionRecord:
    """Record of a single action"""
    step: int
    action_type: str
    target_service: Optional[str]
    new_information: bool = False
    information_gained: List[str] = field(default_factory=list)


@dataclass
class BruteForcePenalties:
    """Calculated penalties for brute-force behavior"""
    excessive_restart_penalty: float = 0.0
    repeated_log_query_penalty: float = 0.0
    no_new_info_penalty: float = 0.0
    redundant_action_penalty: float = 0.0
    total_penalty: float = 0.0
    reasons: List[str] = field(default_factory=list)


class ActionTracker:
    """
    Tracks action history and detects brute-force patterns.
    
    Detects:
    - Excessive service restarts
    - Repeated log queries
    - Actions without new information
    - Redundant investigation patterns
    """
    
    # Maximum allowed restarts without justification
    MAX_UNJUSTIFIED_RESTARTS = 2
    
    # Penalty for excessive restarts
    EXCESSIVE_RESTART_PENALTY = 0.2
    
    # Penalty per repeated log query
    REPEATED_LOG_QUERY_PENALTY = 0.05
    
    # Penalty for action without new info
    NO_NEW_INFO_PENALTY = 0.02
    
    # Investigation actions that gather information
    INVESTIGATION_ACTIONS = {
        "query_service",
        "query_metrics",
        "query_logs",
        "query_dependencies",
        "query_deployments",
        "query_memory",
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
        self.action_history: List[ActionRecord] = []
        self.services_restarted: Set[str] = set()
        self.restart_count: int = 0
        self.log_query_counts: Dict[str, int] = defaultdict(int)
        self.metrics_query_counts: Dict[str, int] = defaultdict(int)
        self.services_discovered: Set[str] = set()
        self.information_state: Dict[str, Set[str]] = defaultdict(set)
        self.last_action_had_new_info: bool = True
        self.consecutive_no_info_actions: int = 0
    
    def record_action(
        self,
        step: int,
        action_type: str,
        target_service: Optional[str],
        observation_result: Optional[dict] = None
    ) -> ActionRecord:
        """
        Record an action and track its information value.
        
        Args:
            step: Current step number
            action_type: Type of action taken
            target_service: Target service if applicable
            observation_result: Result of the action (for info tracking)
            
        Returns:
            ActionRecord with tracking info
        """
        # Determine if this action provides new information
        new_info, info_gained = self._check_new_information(
            action_type, target_service, observation_result
        )
        
        record = ActionRecord(
            step=step,
            action_type=action_type,
            target_service=target_service,
            new_information=new_info,
            information_gained=info_gained,
        )
        
        # Update tracking state
        self._update_tracking(action_type, target_service, new_info)
        
        self.action_history.append(record)
        
        return record
    
    def _check_new_information(
        self,
        action_type: str,
        target_service: Optional[str],
        observation_result: Optional[dict]
    ) -> tuple[bool, List[str]]:
        """Check if action provides new information"""
        new_info = False
        info_gained = []
        
        if action_type in self.INVESTIGATION_ACTIONS:
            if target_service:
                key = f"{action_type}:{target_service}"
                if key not in self.information_state["queries"]:
                    new_info = True
                    info_gained.append(f"First {action_type} for {target_service}")
                    self.information_state["queries"].add(key)
                
                # Check for new service discovery
                if target_service not in self.services_discovered:
                    new_info = True
                    info_gained.append(f"Discovered service: {target_service}")
                    self.services_discovered.add(target_service)
            
            elif action_type == "query_dependencies":  # pragma: no cover
                if "dependencies" not in self.information_state["global"]:  # pragma: no cover
                    new_info = True  # pragma: no cover
                    info_gained.append("First dependency query")  # pragma: no cover
                    self.information_state["global"].add("dependencies")  # pragma: no cover

            elif action_type == "query_deployments":  # pragma: no cover
                if "deployments" not in self.information_state["global"]:  # pragma: no cover
                    new_info = True  # pragma: no cover
                    info_gained.append("First deployment query")  # pragma: no cover
                    self.information_state["global"].add("deployments")  # pragma: no cover

        elif action_type == "query_memory":  # pragma: no cover
            if "memory" not in self.information_state["global"]:  # pragma: no cover
                new_info = True  # pragma: no cover
                info_gained.append("First memory query")  # pragma: no cover
                self.information_state["global"].add("memory")  # pragma: no cover
        
        return new_info, info_gained
    
    def _update_tracking(
        self,
        action_type: str,
        target_service: Optional[str],
        had_new_info: bool
    ) -> None:
        """Update tracking state after action"""
        if action_type == "restart_service" and target_service:
            self.services_restarted.add(target_service)
            self.restart_count += 1
        
        if action_type == "query_logs" and target_service:
            self.log_query_counts[target_service] += 1
        
        if action_type == "query_metrics" and target_service:
            self.metrics_query_counts[target_service] += 1
        
        # Track consecutive no-info actions
        if not had_new_info and action_type in self.INVESTIGATION_ACTIONS:
            self.consecutive_no_info_actions += 1
            self.last_action_had_new_info = False
        else:
            self.consecutive_no_info_actions = 0
            self.last_action_had_new_info = True
    
    def calculate_penalties(
        self,
        root_cause: Optional[str] = None,
        affected_services: Optional[Set[str]] = None
    ) -> BruteForcePenalties:
        """
        Calculate penalties for brute-force behavior.
        
        Args:
            root_cause: Actual root cause service (for justification check)
            affected_services: Actually affected services
            
        Returns:
            BruteForcePenalties with detailed breakdown
        """
        penalties = BruteForcePenalties()
        
        affected = affected_services or set()
        if root_cause:
            affected.add(root_cause)
        
        # 1. Check excessive restarts
        unjustified_restarts = self.services_restarted - affected
        if len(self.services_restarted) > self.MAX_UNJUSTIFIED_RESTARTS:
            penalties.excessive_restart_penalty = self.EXCESSIVE_RESTART_PENALTY
            penalties.reasons.append(
                f"Restarted {len(self.services_restarted)} services "
                f"(max allowed without justification: {self.MAX_UNJUSTIFIED_RESTARTS})"
            )
        elif unjustified_restarts:
            penalties.excessive_restart_penalty = len(unjustified_restarts) * 0.05
            penalties.reasons.append(
                f"Restarted unrelated services: {unjustified_restarts}"
            )
        
        # 2. Check repeated log queries
        repeated_queries = {
            svc: count for svc, count in self.log_query_counts.items()
            if count > 1
        }
        if repeated_queries:
            for svc, count in repeated_queries.items():
                penalty = (count - 1) * self.REPEATED_LOG_QUERY_PENALTY
                penalties.repeated_log_query_penalty += penalty
            penalties.reasons.append(
                f"Repeated log queries: {repeated_queries}"
            )
        
        # 3. Check actions without new information
        no_info_count = sum(1 for a in self.action_history if not a.new_information)
        if no_info_count > 2:  # Allow some exploration
            penalties.no_new_info_penalty = (no_info_count - 2) * self.NO_NEW_INFO_PENALTY
            penalties.reasons.append(
                f"{no_info_count} actions provided no new information"
            )
        
        # 4. Check redundant patterns (e.g., query → query same thing)
        redundant_count = self._count_redundant_patterns()
        if redundant_count > 0:
            penalties.redundant_action_penalty = redundant_count * 0.03
            penalties.reasons.append(
                f"{redundant_count} redundant action patterns detected"
            )
        
        # Calculate total
        penalties.total_penalty = (
            penalties.excessive_restart_penalty +
            penalties.repeated_log_query_penalty +
            penalties.no_new_info_penalty +
            penalties.redundant_action_penalty
        )
        
        return penalties
    
    def _count_redundant_patterns(self) -> int:
        """Count redundant action patterns"""
        count = 0
        
        for i, action in enumerate(self.action_history[1:], 1):
            prev = self.action_history[i - 1]
            
            # Same action on same service consecutively
            if (action.action_type == prev.action_type and
                action.target_service == prev.target_service):
                count += 1
        
        return count
    
    def get_action_summary(self) -> dict:
        """Get summary of tracked actions"""
        return {
            "total_actions": len(self.action_history),
            "unique_services_queried": len(self.services_discovered),
            "services_restarted": list(self.services_restarted),
            "restart_count": self.restart_count,
            "repeated_log_queries": dict(self.log_query_counts),
            "actions_with_new_info": sum(1 for a in self.action_history if a.new_information),
            "actions_without_new_info": sum(1 for a in self.action_history if not a.new_information),
        }
    
    def is_brute_force_detected(self) -> bool:
        """Check if brute-force pattern is detected"""
        penalties = self.calculate_penalties()
        return penalties.total_penalty > 0.1


class IntelligentActionTracker(ActionTracker):
    """
    Enhanced tracker that promotes intelligent behavior.
    
    Additional tracking:
    - Relevant service discoveries
    - Dependency tracing
    - Timeline correlation identification
    """
    
    def __init__(self, seed: int = 42):
        super().__init__(seed)
        self.relevant_services_discovered: Set[str] = set()
        self.dependencies_traced: List[tuple] = []
        self.timeline_correlations: List[dict] = []
        self.root_cause_service: Optional[str] = None
        self.affected_services: Set[str] = set()

    def set_fault_context(self, root_cause: str, affected_services: Set[str]) -> None:
        """Set fault context for intelligent tracking"""
        self.root_cause_service = root_cause
        self.affected_services = affected_services

    def is_guessing_behavior(self) -> bool:
        """Check if agent is exhibiting guessing/brute-force behavior"""
        if len(self.action_history) < 3:
            return False
        # High restart ratio with few queries suggests guessing
        restart_actions = sum(1 for a in self.action_history if a.action_type in ("restart_service", "scale_service", "rollback_deployment"))
        query_actions = sum(1 for a in self.action_history if a.action_type.startswith("query_"))
        if query_actions == 0 and restart_actions > 0:
            return True
        if restart_actions > query_actions:  # pragma: no cover
            return True  # pragma: no cover
        return self.is_brute_force_detected()
    
    def record_relevant_discovery(
        self,
        service: str,
        reason: str
    ) -> None:
        """Record discovery of a relevant service"""
        self.relevant_services_discovered.add(service)
    
    def record_dependency_trace(
        self,
        from_service: str,
        to_service: str,
        relation: str
    ) -> None:
        """Record a dependency trace"""
        self.dependencies_traced.append((from_service, to_service, relation))
    
    def record_timeline_correlation(
        self,
        event_type: str,
        timestamp: str,
        metric_change: str
    ) -> None:
        """Record a timeline correlation identification"""
        self.timeline_correlations.append({
            "event_type": event_type,
            "timestamp": timestamp,
            "metric_change": metric_change,
        })
    
    def get_intelligence_summary(self) -> dict:
        """Get summary of intelligent behavior"""
        return {
            **self.get_action_summary(),
            "relevant_services_found": list(self.relevant_services_discovered),
            "dependencies_traced": len(self.dependencies_traced),
            "timeline_correlations_found": len(self.timeline_correlations),
            "intelligence_score": self._calculate_intelligence_score(),
        }
    
    def _calculate_intelligence_score(self) -> float:
        """Calculate intelligence score based on reasoning quality"""
        if not self.action_history:
            return 0.0
        
        # Base score from info gathering
        info_ratio = sum(1 for a in self.action_history if a.new_information) / len(self.action_history)
        
        # Bonus for relevant discoveries
        discovery_bonus = min(0.2, len(self.relevant_services_discovered) * 0.05)
        
        # Bonus for dependency tracing
        dep_bonus = min(0.2, len(self.dependencies_traced) * 0.05)
        
        # Bonus for timeline correlation
        timeline_bonus = min(0.1, len(self.timeline_correlations) * 0.1)
        
        return min(1.0, info_ratio + discovery_bonus + dep_bonus + timeline_bonus)
