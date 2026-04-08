"""
IncidentOps - Investigator Agent

Systematically gathers evidence by querying services, logs, metrics,
and dependencies. Builds suspicion scores to identify the root cause.
"""
from typing import Optional, Dict, Set
from app.agents.base import BaseAgent, AgentObservation, AgentDecision, AgentRole
from app.models import ActionType, VALID_SERVICES


class InvestigatorAgent(BaseAgent):
    """
    Investigator Agent - systematically gathers evidence.

    Behavior:
    1. Start by querying high-connectivity services (api-gateway, auth-service)
    2. If errors found, drill into specific services
    3. If logs show a pattern, check metrics for corroboration
    4. Keep a "suspicion score" per service (0-1)
    5. After gathering enough evidence, defer to the Fixer
    """

    role = AgentRole.INVESTIGATOR

    # Services ordered by connectivity (most connected first)
    HIGH_CONNECTIVITY_SERVICES = [
        "api-gateway",
        "auth-service",
        "order-service",
        "user-service",
        "recommendation-service",
    ]

    def __init__(self) -> None:
        self._services_queried: Set[str] = set()
        self._evidence: Dict[str, list] = {}
        self._suspicion_scores: Dict[str, float] = {}
        self._steps_without_progress: int = 0
        self._last_info_count: int = 0
        self._seed: int = 42
        self._investigation_sequence: list = []

    def reset(self, seed: int) -> None:
        """Reset agent state for a new episode"""
        self._seed = seed
        self._services_queried.clear()
        self._evidence.clear()
        self._suspicion_scores.clear()
        self._steps_without_progress = 0
        self._last_info_count = 0
        self._investigation_sequence = []

        # Initialize suspicion scores for all services
        all_services = list(self.HIGH_CONNECTIVITY_SERVICES) + [
            "payment-service",
            "database-primary",
            "database-replica",
            "inventory-service",
            "cache-service",
            "notification-service",
            "search-service",
            "analytics-service",
            "email-service",
            "shipping-service",
        ]
        for svc in all_services:
            self._suspicion_scores[svc] = 0.0

    def decide(self, observation: AgentObservation) -> AgentDecision:
        """Decide the next investigation action"""
        # Check if we have enough evidence to hand off to fixer
        max_suspicion = self.get_suspicion()

        # If we have high suspicion on a service, drill deeper
        if max_suspicion > 0.5:
            suspect = max(self._suspicion_scores, key=self._suspicion_scores.get)
            if self._suspicion_scores.get(suspect, 0) > 0.7:
                # High confidence - query logs for more details
                return AgentDecision(
                    action_type=ActionType.QUERY_LOGS.value,
                    target_service=suspect,
                    confidence=min(max_suspicion, 0.9),
                    reasoning=f"High suspicion {max_suspicion:.2f} on {suspect}, drilling into logs",
                )
            else:
                # Medium confidence - query metrics
                return AgentDecision(
                    action_type=ActionType.QUERY_METRICS.value,
                    target_service=suspect,
                    confidence=max_suspicion,
                    reasoning=f"Suspicion {max_suspicion:.2f} on {suspect}, checking metrics",
                )

        # Systematic investigation: query high-connectivity services first
        for svc in self.HIGH_CONNECTIVITY_SERVICES:
            if svc not in self._services_queried:
                self._services_queried.add(svc)
                self._investigation_sequence.append(svc)
                return AgentDecision(
                    action_type=ActionType.QUERY_METRICS.value,
                    target_service=svc,
                    confidence=0.6,
                    reasoning=f"Querying high-connectivity service {svc}",
                )

        # If we've queried most high-connectivity services, check dependencies
        if len(self._investigation_sequence) >= 3 and "api-gateway" in self._investigation_sequence:
            # Check dependencies of the first queried service
            target = self._investigation_sequence[0]
            return AgentDecision(
                action_type=ActionType.QUERY_DEPENDENCIES.value,
                target_service=target,
                confidence=0.5,
                reasoning=f"Checking dependencies of {target} to trace cascade",
            )

        # If we've gathered enough evidence, escalate to fixer
        if len(self._services_queried) >= 3:
            most_suspect = max(self._suspicion_scores, key=self._suspicion_scores.get)
            suspicion_val = self._suspicion_scores.get(most_suspect, 0)

            # Only escalate if we have some evidence
            if suspicion_val > 0.3:
                return AgentDecision(
                    action_type=ActionType.IDENTIFY_ROOT_CAUSE.value,
                    target_service=most_suspect,
                    confidence=suspicion_val,
                    reasoning=f"Escalating with suspicion {suspicion_val:.2f} on {most_suspect}",
                )

        # Fallback: query another service from VALID_SERVICES
        remaining = [s for s in VALID_SERVICES if s not in self._services_queried]
        if remaining:
            # Round-robin through remaining services
            idx = len(self._investigation_sequence) % len(remaining)
            svc = remaining[idx]
            self._services_queried.add(svc)
            self._investigation_sequence.append(svc)
            return AgentDecision(
                action_type=ActionType.QUERY_SERVICE.value,
                target_service=svc,
                confidence=0.4,
                reasoning=f"Investigating {svc}",
            )

        # Ultimate fallback
        return AgentDecision(
            action_type=ActionType.QUERY_LOGS.value,
            target_service="api-gateway",
            confidence=0.3,
            reasoning="Fallback: querying logs",
        )

    def learn(self, observation: AgentObservation, decision: AgentDecision, reward: float) -> None:
        """Update suspicion scores based on reward and evidence"""
        target = decision.target_service

        # Positive reward means we're on the right track
        if reward > 0.1 and target:
            current = self._suspicion_scores.get(target, 0.0)
            self._suspicion_scores[target] = min(current + 0.15, 1.0)

        # Negative reward might mean wrong service
        if reward < -0.2 and target:
            current = self._suspicion_scores.get(target, 0.0)
            self._suspicion_scores[target] = max(current - 0.1, 0.0)

        # Check if we gained new information
        info_count = len(observation.information_summary) if observation.information_summary else 0
        if info_count <= self._last_info_count:
            self._steps_without_progress += 1
        else:
            self._steps_without_progress = 0
        self._last_info_count = info_count

        # Propagate suspicion to dependencies (if we found something wrong)
        if reward > 0.2 and target:
            self._propagate_suspicion(target, 0.1)

    def _propagate_suspicion(self, service: str, amount: float) -> None:
        """
        Propagate suspicion to dependent services.

        If service A depends on B and A is suspicious, B gets some suspicion too.
        """
        # Simple dependency mapping (can be enhanced with actual dependency graph)
        dependencies = {
            "api-gateway": ["auth-service", "user-service", "order-service"],
            "order-service": ["payment-service", "inventory-service", "shipping-service"],
            "user-service": ["database-primary", "cache-service"],
            "recommendation-service": ["analytics-service", "cache-service"],
        }

        dependents = dependencies.get(service, [])
        for dep in dependents:
            current = self._suspicion_scores.get(dep, 0.0)
            self._suspicion_scores[dep] = min(current + amount, 0.6)

    def get_suspicion(self) -> float:
        """Get the highest suspicion score across all services"""
        if not self._suspicion_scores:
            return 0.0
        return max(self._suspicion_scores.values())

    def get_suspect_service(self) -> Optional[str]:
        """Get the service with highest suspicion"""
        if not self._suspicion_scores:
            return None
        return max(self._suspicion_scores, key=self._suspicion_scores.get)

    def get_investigation_summary(self) -> Dict[str, any]:
        """Get summary of investigation progress"""
        return {
            "services_queried": list(self._services_queried),
            "suspicion_scores": dict(self._suspicion_scores),
            "top_suspect": self.get_suspect_service(),
            "max_suspicion": self.get_suspicion(),
            "steps_without_progress": self._steps_without_progress,
            "investigation_sequence": self._investigation_sequence,
        }
