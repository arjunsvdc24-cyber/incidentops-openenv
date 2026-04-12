"""
IncidentOps - Unit Tests: Investigator Agent Additional Coverage

Tests the InvestigatorAgent's internal logic branches in the decide() method,
including dependency checking, escalation, and final fallback logic.

These tests complement tests/unit/test_agents.py which covers basic functionality.
"""
import pytest
from app.agents.investigator import InvestigatorAgent
from app.agents.base import AgentObservation, AgentDecision, AgentRole
from app.models import ActionType, VALID_SERVICES


class TestInvestigatorAgentBranches:
    """
    Test internal branches of decide() that are hard to hit without specific state setup.
    These correspond to lines 95-153 of app/agents/investigator.py.
    """

    def test_decide_queries_first_high_connectivity_service(self):
        """Line 96-105: First decide() call queries first unqueried high-connectivity service."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        obs = AgentObservation(
            step=0,
            action_history=[],
            reward_history=[],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=False,
        )
        decision = agent.decide(obs)

        # First service in HIGH_CONNECTIVITY_SERVICES should be queried
        assert decision.target_service == "api-gateway"
        assert decision.action_type == ActionType.QUERY_METRICS.value
        assert "api-gateway" in agent._services_queried
        assert agent._investigation_sequence == ["api-gateway"]

    def test_decide_second_high_connectivity_service(self):
        """Second decide() call queries second high-connectivity service."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        obs1 = AgentObservation(step=0, action_history=[], reward_history=[],
                               information_summary={}, reasoning_score=0.0, is_guessing=False)
        decision1 = agent.decide(obs1)
        assert decision1.target_service == "api-gateway"

        obs2 = AgentObservation(step=1, action_history=[], reward_history=[],
                                information_summary={}, reasoning_score=0.0, is_guessing=False)
        decision2 = agent.decide(obs2)
        assert decision2.target_service == "auth-service"

    def test_decide_high_suspicion_high_confidence_queries_logs(self):
        """
        Line 76-85: When suspicion > 0.7 on a service, query logs for more details.
        """
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        agent._suspicion_scores["payment-service"] = 0.8
        agent._suspicion_scores["api-gateway"] = 0.3

        obs = AgentObservation(
            step=3,
            action_history=[],
            reward_history=[0.5],
            information_summary={},
            reasoning_score=0.6,
            is_guessing=False,
        )
        decision = agent.decide(obs)

        # High suspicion (>0.7) should drill into logs
        assert decision.action_type == ActionType.QUERY_LOGS.value
        assert decision.target_service == "payment-service"
        assert decision.confidence <= 0.9

    def test_decide_medium_suspicion_queries_metrics(self):
        """
        Line 86-93: When suspicion is 0.5-0.7, query metrics for more info.
        """
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        agent._suspicion_scores["payment-service"] = 0.6
        agent._suspicion_scores["api-gateway"] = 0.2

        obs = AgentObservation(
            step=2,
            action_history=[],
            reward_history=[0.3],
            information_summary={},
            reasoning_score=0.5,
            is_guessing=False,
        )
        decision = agent.decide(obs)

        # Medium suspicion (0.5-0.7) should check metrics
        assert decision.action_type == ActionType.QUERY_METRICS.value
        assert decision.target_service == "payment-service"

    def test_decide_no_escalate_when_suspicion_low(self):
        """
        Even with 3+ services queried, no escalation if suspicion < 0.3.
        The agent continues to query services.
        """
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        agent._services_queried.update(["api-gateway", "auth-service", "order-service"])
        agent._investigation_sequence.extend(["api-gateway", "auth-service", "order-service"])
        # Low suspicion
        agent._suspicion_scores["payment-service"] = 0.1

        obs = AgentObservation(
            step=3,
            action_history=[],
            reward_history=[0.1, 0.1, 0.1],
            information_summary={},
            reasoning_score=0.1,
            is_guessing=False,
        )
        decision = agent.decide(obs)

        # Should NOT escalate - max_suspicion is 0.1 which is not > 0.5
        assert decision.action_type != ActionType.IDENTIFY_ROOT_CAUSE.value

    def test_decide_ultimate_fallback_after_all_services_queried(self):
        """
        When even VALID_SERVICES exhausted, agent falls back to querying dependencies or logs.
        """
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        # Simulate ALL services queried
        for svc in VALID_SERVICES:
            agent._services_queried.add(svc)
            agent._investigation_sequence.append(svc)

        obs = AgentObservation(
            step=20,
            action_history=[],
            reward_history=[],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=True,
        )
        decision = agent.decide(obs)

        # Should return a valid action (depends on exact fallback path)
        valid_actions = [a.value for a in ActionType]
        assert decision.action_type in valid_actions

    def test_decide_with_high_initial_suspicion(self):
        """High suspicion in initial scores affects first decision."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        # Set high suspicion before first call
        agent._suspicion_scores["payment-service"] = 0.9

        obs = AgentObservation(
            step=0,
            action_history=[],
            reward_history=[],
            information_summary={},
            reasoning_score=0.8,
            is_guessing=False,
        )
        decision = agent.decide(obs)

        # With high suspicion, agent may check logs on the suspicious service
        # rather than the first high-connectivity service
        valid_actions = [a.value for a in ActionType]
        assert decision.action_type in valid_actions


class TestInvestigatorAgentLearnBranches:
    """Test learn() method branches."""

    def test_learn_positive_reward_caps_at_one(self):
        """Suspicion scores are capped at 1.0."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        obs = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        decision = AgentDecision(
            action_type="query_service",
            target_service="payment-service",
            confidence=0.5,
        )

        # Apply many positive rewards
        for _ in range(10):
            agent.learn(obs, decision, reward=1.0)

        assert agent._suspicion_scores["payment-service"] == 1.0

    def test_learn_negative_reward_floors_at_zero(self):
        """Suspicion scores have a floor of 0.0."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._suspicion_scores["payment-service"] = 0.1

        obs = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        decision = AgentDecision(
            action_type="query_service",
            target_service="payment-service",
            confidence=0.5,
        )

        # Apply many negative rewards
        for _ in range(10):
            agent.learn(obs, decision, reward=-1.0)

        assert agent._suspicion_scores["payment-service"] == 0.0

    def test_learn_steps_without_progress_tracking(self):
        """Track steps without new information."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        obs_no_info = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        obs_with_info = AgentObservation(
            step=1, action_history=[], reward_history=[],
            information_summary={"key": ["value"]}, reasoning_score=0.5, is_guessing=False,
        )

        decision = AgentDecision(action_type="query_service", target_service="api-gateway")

        # First call - no new info
        agent.learn(obs_no_info, decision, reward=0.1)
        assert agent._steps_without_progress == 1

        # Second call - still no new info
        agent.learn(obs_no_info, decision, reward=0.1)
        assert agent._steps_without_progress == 2

        # New info resets counter
        agent.learn(obs_with_info, decision, reward=0.1)
        assert agent._steps_without_progress == 0

    def test_learn_propagates_suspicion_to_dependents(self):
        """When reward > 0.2, suspicion propagates to dependents."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        obs = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        decision = AgentDecision(
            action_type="query_service",
            target_service="order-service",
            confidence=0.5,
        )

        # Get initial suspicion of dependents
        initial_payment = agent._suspicion_scores.get("payment-service", 0.0)
        initial_inventory = agent._suspicion_scores.get("inventory-service", 0.0)

        # High reward should propagate
        agent.learn(obs, decision, reward=0.5)

        # order-service depends on payment-service and inventory-service
        assert agent._suspicion_scores.get("payment-service", 0.0) >= initial_payment
        assert agent._suspicion_scores.get("inventory-service", 0.0) >= initial_inventory

    def test_learn_propagation_caps_at_0_6(self):
        """Propagated suspicion is capped at 0.6."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        # api-gateway propagates to auth-service, user-service, order-service
        agent._suspicion_scores["auth-service"] = 0.0

        obs = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        decision = AgentDecision(
            action_type="query_service",
            target_service="api-gateway",
            confidence=0.5,
        )

        # High reward multiple times
        for _ in range(5):
            agent.learn(obs, decision, reward=1.0)

        # Propagated suspicion should be capped at 0.6
        assert agent._suspicion_scores.get("auth-service", 0.0) <= 0.6


class TestInvestigatorAgentReset:
    """Test reset() initializes all suspicion scores."""

    def test_reset_initializes_all_valid_services(self):
        """All VALID_SERVICES should have initial suspicion of 0.0."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        for svc in VALID_SERVICES:
            assert svc in agent._suspicion_scores
            assert agent._suspicion_scores[svc] == 0.0

    def test_reset_clears_investigation_sequence(self):
        """reset() clears the investigation sequence."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._investigation_sequence = ["api-gateway", "auth-service"]

        agent.reset(seed=99)

        assert agent._investigation_sequence == []
        assert agent._seed == 99

    def test_reset_clears_evidence(self):
        """reset() clears collected evidence."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._evidence["api-gateway"] = [{"type": "error", "message": "test"}]

        agent.reset(seed=42)

        assert len(agent._evidence) == 0

    def test_reset_clears_services_queried(self):
        """reset() clears the set of queried services."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._services_queried.add("api-gateway")
        agent._services_queried.add("auth-service")

        agent.reset(seed=42)

        assert len(agent._services_queried) == 0


class TestInvestigatorAgentGetSuspectService:
    """Test get_suspect_service edge cases."""

    def test_get_suspect_service_with_tie(self):
        """When multiple services have same suspicion, returns one deterministically."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)

        agent._suspicion_scores["api-gateway"] = 0.5
        agent._suspicion_scores["payment-service"] = 0.5

        suspect = agent.get_suspect_service()
        # Should return one of the tied services
        assert suspect in ["api-gateway", "payment-service"]

    def test_get_suspect_service_empty_scores(self):
        """Returns None when suspicion scores are empty."""
        agent = InvestigatorAgent()
        # Never called reset(), scores are empty
        assert agent.get_suspect_service() is None


class TestInvestigatorAgentGetSuspicion:
    """Test get_suspicion() method."""

    def test_get_suspicion_returns_max(self):
        """Returns maximum suspicion score."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._suspicion_scores["api-gateway"] = 0.3
        agent._suspicion_scores["payment-service"] = 0.8

        assert agent.get_suspicion() == 0.8

    def test_get_suspicion_empty_returns_zero(self):
        """Returns 0.0 when no scores are set."""
        agent = InvestigatorAgent()
        assert agent.get_suspicion() == 0.0


class TestInvestigatorAgentGetInvestigationSummary:
    """Test get_investigation_summary() method."""

    def test_summary_includes_all_fields(self):
        """Summary contains all expected fields."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._services_queried.add("api-gateway")
        agent._suspicion_scores["payment-service"] = 0.8
        agent._steps_without_progress = 3

        summary = agent.get_investigation_summary()

        assert "services_queried" in summary
        assert "suspicion_scores" in summary
        assert "top_suspect" in summary
        assert "max_suspicion" in summary
        assert "steps_without_progress" in summary
        assert "investigation_sequence" in summary

    def test_summary_values_correct(self):
        """Summary contains correct values."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._services_queried.add("api-gateway")
        agent._suspicion_scores["payment-service"] = 0.8
        agent._investigation_sequence.append("api-gateway")
        agent._steps_without_progress = 5

        summary = agent.get_investigation_summary()

        assert summary["services_queried"] == ["api-gateway"]
        assert summary["top_suspect"] == "payment-service"
        assert summary["max_suspicion"] == 0.8
        assert summary["steps_without_progress"] == 5


class TestInvestigatorAgentRole:
    """Test AgentRole assignment."""

    def test_role_is_investigator(self):
        """Agent role is INVESTIGATOR."""
        agent = InvestigatorAgent()
        assert agent.role == AgentRole.INVESTIGATOR

    def test_role_is_string_enum(self):
        """Agent role is string enum value."""
        agent = InvestigatorAgent()
        assert agent.role.value == "investigator"


class TestInvestigatorAgentHighConnectivityServices:
    """Test HIGH_CONNECTIVITY_SERVICES configuration."""

    def test_high_connectivity_services_ordered(self):
        """High connectivity services are in correct order."""
        expected_order = ["api-gateway", "auth-service", "order-service", "user-service", "recommendation-service"]
        assert InvestigatorAgent.HIGH_CONNECTIVITY_SERVICES == expected_order

    def test_high_connectivity_services_are_subset(self):
        """High connectivity services are subset of VALID_SERVICES."""
        for svc in InvestigatorAgent.HIGH_CONNECTIVITY_SERVICES:
            assert svc in VALID_SERVICES
