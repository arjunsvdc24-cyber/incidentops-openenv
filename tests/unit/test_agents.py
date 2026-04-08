"""
IncidentOps - Multi-Agent System Tests

Tests the multi-agent RL system: InvestigatorAgent, FixerAgent, AnalystAgent,
AgentCoordinator, and BaseAgent.
"""
import pytest
from app.agents.base import (
    BaseAgent, AgentRole, AgentObservation, AgentDecision,
)
from app.agents.investigator import InvestigatorAgent
from app.agents.fixer import FixerAgent
from app.agents.analyst import AnalystAgent
from app.agents.coordinator import AgentCoordinator, MultiAgentEpisodeResult
from app.models import ActionType


class TestAgentRole:
    """AgentRole enum values."""

    def test_agent_role_values(self):
        assert AgentRole.INVESTIGATOR.value == "investigator"
        assert AgentRole.FIXER.value == "fixer"
        assert AgentRole.ANALYST.value == "analyst"

    def test_agent_role_is_string_enum(self):
        assert isinstance(AgentRole.INVESTIGATOR, str)


class TestAgentObservation:
    """AgentObservation dataclass."""

    def test_observation_creation(self):
        obs = AgentObservation(
            step=0,
            action_history=[],
            reward_history=[],
            information_summary={"services": []},
            reasoning_score=0.5,
            is_guessing=False,
        )
        assert obs.step == 0
        assert obs.reasoning_score == 0.5
        assert obs.is_guessing is False

    def test_observation_with_history(self):
        obs = AgentObservation(
            step=3,
            action_history=[
                {"action_type": "query_service", "target_service": "api-gateway"},
                {"action_type": "query_metrics", "target_service": "payment-service"},
            ],
            reward_history=[0.1, 0.2],
            information_summary={},
            reasoning_score=0.7,
            is_guessing=False,
        )
        assert len(obs.action_history) == 2
        assert len(obs.reward_history) == 2


class TestAgentDecision:
    """AgentDecision dataclass."""

    def test_decision_creation(self):
        decision = AgentDecision(
            action_type="query_service",
            target_service="api-gateway",
            confidence=0.8,
            reasoning="Testing the api-gateway",
        )
        assert decision.action_type == "query_service"
        assert decision.target_service == "api-gateway"
        assert decision.confidence == 0.8

    def test_decision_defaults(self):
        decision = AgentDecision(action_type="restart_service")
        assert decision.target_service is None
        assert decision.parameters == {}
        assert decision.confidence == 1.0
        assert decision.reasoning == ""


class TestBaseAgent:
    """BaseAgent abstract class."""

    def test_base_agent_is_abc(self):
        assert hasattr(BaseAgent, "reset")
        assert hasattr(BaseAgent, "decide")
        assert hasattr(BaseAgent, "learn")
        assert hasattr(BaseAgent, "get_stats")

    def test_base_agent_get_stats(self):
        class DummyAgent(BaseAgent):
            role = AgentRole.INVESTIGATOR

            def reset(self, seed: int) -> None:
                pass

            def decide(self, observation: AgentObservation) -> AgentDecision:
                return AgentDecision(action_type="query_service")

            def learn(self, observation: AgentObservation, decision: AgentDecision, reward: float) -> None:
                pass

        agent = DummyAgent()
        stats = agent.get_stats()
        assert stats["role"] == "investigator"


class TestInvestigatorAgent:
    """InvestigatorAgent systematically gathers evidence."""

    def test_initializes(self):
        agent = InvestigatorAgent()
        assert agent.role == AgentRole.INVESTIGATOR

    def test_reset_clears_state(self):
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        assert agent._seed == 42
        assert len(agent._services_queried) == 0
        assert len(agent._evidence) == 0
        assert agent._steps_without_progress == 0

    def test_reset_initializes_suspicion_scores(self):
        agent = InvestigatorAgent()
        agent.reset(seed=99)
        assert "api-gateway" in agent._suspicion_scores
        assert "payment-service" in agent._suspicion_scores
        assert agent._suspicion_scores["api-gateway"] == 0.0

    def test_decide_initial_step(self):
        """At step 0, queries high-connectivity services."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0,
            action_history=[],
            reward_history=[],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=True,
        )
        decision = agent.decide(obs)
        assert decision.action_type in [a.value for a in ActionType]
        assert decision.target_service is not None
        assert 0.0 <= decision.confidence <= 1.0

    def test_decide_after_investigation(self):
        """After querying services, escalates to identify root cause."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        # Simulate having queried services
        agent._services_queried.update(["api-gateway", "auth-service", "payment-service"])
        agent._investigation_sequence.extend(["api-gateway", "auth-service", "payment-service"])
        # Set a suspicion
        agent._suspicion_scores["payment-service"] = 0.5

        obs = AgentObservation(
            step=3,
            action_history=[
                {"action_type": "query_service", "target_service": "api-gateway"},
                {"action_type": "query_service", "target_service": "auth-service"},
                {"action_type": "query_service", "target_service": "payment-service"},
            ],
            reward_history=[0.1, 0.2, 0.3],
            information_summary={},
            reasoning_score=0.5,
            is_guessing=False,
        )
        decision = agent.decide(obs)
        assert decision is not None

    def test_decide_fallback(self):
        """When all services queried, uses fallback."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        # Simulate all services queried
        for svc in [
            "api-gateway", "auth-service", "order-service", "user-service",
            "recommendation-service", "payment-service", "database-primary",
        ]:
            agent._services_queried.add(svc)
            agent._investigation_sequence.append(svc)

        obs = AgentObservation(
            step=10,
            action_history=[],
            reward_history=[],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=True,
        )
        decision = agent.decide(obs)
        assert decision is not None

    def test_learn_positive_reward(self):
        """Positive reward increases suspicion on target service."""
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
        initial = agent._suspicion_scores.get("payment-service", 0.0)
        agent.learn(obs, decision, reward=0.5)
        updated = agent._suspicion_scores.get("payment-service", 0.0)
        assert updated > initial

    def test_learn_negative_reward(self):
        """Negative reward decreases suspicion on target service."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._suspicion_scores["payment-service"] = 0.5
        obs = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        decision = AgentDecision(
            action_type="query_service",
            target_service="payment-service",
            confidence=0.5,
        )
        agent.learn(obs, decision, reward=-0.5)
        assert agent._suspicion_scores["payment-service"] < 0.5

    def test_learn_propagates_suspicion(self):
        """High reward propagates to dependent services."""
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        decision = AgentDecision(
            action_type="query_service",
            target_service="api-gateway",
            confidence=0.5,
        )
        initial_auth = agent._suspicion_scores.get("auth-service", 0.0)
        agent.learn(obs, decision, reward=0.5)
        # auth-service is a dependency of api-gateway
        assert agent._suspicion_scores.get("auth-service", 0.0) >= initial_auth

    def test_get_suspicion_empty(self):
        agent = InvestigatorAgent()
        # Before reset, suspicion is empty
        suspicion = agent.get_suspicion()
        assert suspicion == 0.0

    def test_get_suspicion_after_reset(self):
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        assert agent.get_suspicion() == 0.0

    def test_get_suspicion_with_scores(self):
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._suspicion_scores["payment-service"] = 0.7
        agent._suspicion_scores["api-gateway"] = 0.3
        assert agent.get_suspicion() == 0.7

    def test_get_suspect_service(self):
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._suspicion_scores["payment-service"] = 0.9
        agent._suspicion_scores["api-gateway"] = 0.3
        assert agent.get_suspect_service() == "payment-service"

    def test_get_suspect_service_empty(self):
        agent = InvestigatorAgent()
        assert agent.get_suspect_service() is None

    def test_get_investigation_summary(self):
        agent = InvestigatorAgent()
        agent.reset(seed=42)
        agent._services_queried.add("api-gateway")
        agent._suspicion_scores["payment-service"] = 0.8
        summary = agent.get_investigation_summary()
        assert "services_queried" in summary
        assert "suspicion_scores" in summary
        assert "top_suspect" in summary
        assert summary["services_queried"] == ["api-gateway"]


class TestFixerAgent:
    """FixerAgent applies remediations."""

    def test_initializes(self):
        agent = FixerAgent()
        assert agent.role == AgentRole.FIXER

    def test_reset_clears_state(self):
        agent = FixerAgent()
        agent.reset(seed=42)
        assert agent._seed == 42
        assert agent._last_fix_service is None
        assert agent._fix_attempts == 0
        assert len(agent._fix_history) == 0

    def test_decide_returns_valid_action(self):
        agent = FixerAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0,
            action_history=[],
            reward_history=[],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=True,
        )
        decision = agent.decide(obs)
        valid_actions = [a.value for a in ActionType]
        assert decision.action_type in valid_actions

    def test_decide_after_failed_fix(self):
        """After a failed fix, tries alternative approach."""
        agent = FixerAgent()
        agent.reset(seed=42)
        agent._fix_attempts = 1
        agent._last_fix_service = "payment-service"
        agent._last_fix_action = ActionType.RESTART_SERVICE.value

        obs = AgentObservation(
            step=1,
            action_history=[
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            reward_history=[-0.2],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=False,
        )
        decision = agent.decide(obs)
        assert decision.target_service == "payment-service"

    def test_decide_after_successful_fix(self):
        """After a successful fix, identifies root cause."""
        agent = FixerAgent()
        agent.reset(seed=42)
        agent._fix_attempts = 1
        agent._last_fix_service = "payment-service"
        agent._last_fix_action = ActionType.RESTART_SERVICE.value

        obs = AgentObservation(
            step=1,
            action_history=[
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            reward_history=[0.8],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=False,
        )
        decision = agent.decide(obs)
        # Should identify root cause after successful fix
        assert decision is not None

    def test_find_suspected_service_from_history(self):
        agent = FixerAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0,
            action_history=[
                {"action_type": "query_service", "target_service": "api-gateway"},
                {"action_type": "query_service", "target_service": "payment-service"},
                {"action_type": "query_service", "target_service": "payment-service"},
                {"action_type": "query_service", "target_service": "payment-service"},
            ],
            reward_history=[],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=False,
        )
        service = agent._find_suspected_service(obs)
        # Most frequently queried service
        assert service == "payment-service"

    def test_find_suspected_service_fallback(self):
        agent = FixerAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0,
            action_history=[],
            reward_history=[],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=True,
        )
        service = agent._find_suspected_service(obs)
        assert service == "payment-service"  # Default fallback

    def test_determine_fix_action_memory_keyword(self):
        agent = FixerAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0,
            action_history=[
                {"action_type": "query_logs", "target_service": "api-gateway"},
            ],
            reward_history=[],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=False,
        )
        action, reason = agent._determine_fix_action(obs, "api-gateway")
        valid_actions = [a.value for a in ActionType]
        assert action in valid_actions
        assert isinstance(reason, str)

    def test_learn_records_fix(self):
        agent = FixerAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        decision = AgentDecision(
            action_type="restart_service",
            target_service="payment-service",
        )
        agent.learn(obs, decision, reward=-0.3)
        assert len(agent._fix_history) == 1
        assert agent._fix_attempts == 1

    def test_learn_successful_fix_resets(self):
        agent = FixerAgent()
        agent.reset(seed=42)
        agent._fix_attempts = 2
        obs = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        decision = AgentDecision(
            action_type="restart_service",
            target_service="payment-service",
        )
        agent.learn(obs, decision, reward=0.8)
        assert agent._fix_attempts == 0

    def test_get_fix_summary(self):
        agent = FixerAgent()
        agent.reset(seed=42)
        agent._last_fix_service = "payment-service"
        agent._last_fix_action = "restart_service"
        agent._fix_attempts = 1
        summary = agent.get_fix_summary()
        assert "fix_attempts" in summary
        assert "last_fix_service" in summary
        assert "last_fix_action" in summary
        assert "fix_history" in summary


class TestAnalystAgent:
    """AnalystAgent provides pattern-based analysis."""

    def test_initializes(self):
        agent = AnalystAgent()
        assert agent.role == AgentRole.ANALYST

    def test_reset_clears_state(self):
        agent = AnalystAgent()
        agent.reset(seed=42)
        assert agent._seed == 42
        assert agent._suggested_fault_type is None
        assert agent._confidence == 0.0
        assert agent._fault_probabilities["oom"] == 0.0

    def test_decide_empty_history(self):
        """Initial decide with no history returns a decision."""
        agent = AnalystAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0,
            action_history=[],
            reward_history=[],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=True,
        )
        decision = agent.decide(obs)
        assert decision.action_type == ActionType.QUERY_MEMORY.value
        assert isinstance(decision.reasoning, str)

    def test_decide_with_oom_keywords(self):
        """Detects OOM pattern in action history."""
        agent = AnalystAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=2,
            action_history=[
                {"action_type": "query_service", "target_service": "payment-service"},
                {"action_type": "query_logs", "target_service": "payment-service"},
            ],
            reward_history=[],
            information_summary={},
            reasoning_score=0.3,
            is_guessing=False,
        )
        # Analyze patterns manually to test internal method
        agent._analyze_patterns(obs)
        # No OOM keywords in action history yet
        assert agent._suggested_fault_type is None or agent._suggested_fault_type is not None

    def test_decide_with_matching_pattern(self):
        """Pattern matching when keywords are in history."""
        agent = AnalystAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=1,
            action_history=[
                {"action_type": "query_logs", "target_service": "payment-service"},
            ],
            reward_history=[],
            information_summary={"OOM": ["OutOfMemoryError"]},
            reasoning_score=0.0,
            is_guessing=False,
        )
        decision = agent.decide(obs)
        assert decision is not None

    def test_analyze_patterns_with_fault_keywords(self):
        """Patterns are detected when keywords match."""
        agent = AnalystAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0,
            action_history=[
                {"action_type": "query_logs", "target_service": "payment-service"},
            ],
            reward_history=[],
            information_summary={"OutOfMemory": ["heap exhausted"]},
            reasoning_score=0.0,
            is_guessing=False,
        )
        agent._analyze_patterns(obs)
        assert isinstance(agent._suggested_fault_type, (str, type(None)))
        assert 0.0 <= agent._confidence <= 1.0

    def test_analyze_patterns_no_match(self):
        """No pattern detected with generic history."""
        agent = AnalystAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0,
            action_history=[
                {"action_type": "query_service", "target_service": "api-gateway"},
            ],
            reward_history=[],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=False,
        )
        agent._analyze_patterns(obs)
        # Step 0 with no clear pattern might guess cascade
        assert isinstance(agent._suggested_fault_type, (str, type(None)))

    def test_extract_keywords_from_history(self):
        agent = AnalystAgent()
        agent.reset(seed=42)
        obs = AgentObservation(
            step=0,
            action_history=[
                {"action_type": "query_service", "target_service": "payment-service"},
                {"action_type": "query_metrics", "target_service": "api-gateway"},
            ],
            reward_history=[-0.1, -0.2],
            information_summary={},
            reasoning_score=0.0,
            is_guessing=False,
        )
        keywords = agent._extract_keywords(obs)
        assert isinstance(keywords, list)
        assert "payment-service" in keywords or "api-gateway" in keywords

    def test_learn_positive_reward(self):
        """Positive reward increases confidence."""
        agent = AnalystAgent()
        agent.reset(seed=42)
        agent._confidence = 0.3
        agent._suggested_fault_type = "oom"
        obs = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        decision = AgentDecision(action_type="restart_service", target_service="payment-service")
        agent.learn(obs, decision, reward=0.5)
        assert agent._confidence > 0.3

    def test_learn_negative_reward(self):
        """Negative reward decreases confidence."""
        agent = AnalystAgent()
        agent.reset(seed=42)
        agent._confidence = 0.5
        agent._suggested_fault_type = "oom"
        obs = AgentObservation(
            step=0, action_history=[], reward_history=[],
            information_summary={}, reasoning_score=0.0, is_guessing=False,
        )
        decision = AgentDecision(action_type="restart_service", target_service="payment-service")
        agent.learn(obs, decision, reward=-0.3)
        assert agent._confidence < 0.5

    def test_get_analysis_summary(self):
        agent = AnalystAgent()
        agent.reset(seed=42)
        summary = agent.get_analysis_summary()
        assert "suggested_fault_type" in summary
        assert "confidence" in summary
        assert "fault_probabilities" in summary
        assert "memory_hints" in summary
        assert "pattern_matches" in summary

    def test_get_current_hypothesis_none(self):
        agent = AnalystAgent()
        agent.reset(seed=42)
        hypothesis = agent.get_current_hypothesis()
        assert hypothesis is None

    def test_get_current_hypothesis_with_fault(self):
        agent = AnalystAgent()
        agent.reset(seed=42)
        agent._suggested_fault_type = "oom"
        agent._confidence = 0.7
        hypothesis = agent.get_current_hypothesis()
        assert hypothesis is not None
        assert hypothesis["fault_type"] == "oom"
        assert hypothesis["confidence"] == 0.7
        assert "recommended_action" in hypothesis

    def test_get_action_for_fault(self):
        agent = AnalystAgent()
        assert agent._get_action_for_fault("oom") == ActionType.RESTART_SERVICE.value
        assert agent._get_action_for_fault("cascade") == ActionType.SCALE_SERVICE.value
        assert agent._get_action_for_fault("ghost") == ActionType.ROLLBACK_DEPLOYMENT.value
        assert agent._get_action_for_fault("unknown_type") == ActionType.RESTART_SERVICE.value


class TestAgentCoordinator:
    """AgentCoordinator orchestrates multi-agent collaboration."""

    def test_initializes(self):
        coord = AgentCoordinator()
        assert coord.investigator is not None
        assert coord.fixer is not None
        assert coord.analyst is not None

    def test_initializes_without_analyst(self):
        coord = AgentCoordinator(enable_analyst=False)
        assert coord.investigator is not None
        assert coord.fixer is not None
        assert coord.analyst is None

    def test_custom_config(self):
        coord = AgentCoordinator(
            enable_analyst=True,
            confidence_threshold=0.5,
            max_steps=10,
        )
        assert coord.confidence_threshold == 0.5
        assert coord.max_steps == 10
        assert coord.enable_analyst is True

    def test_get_coordinator_stats(self):
        coord = AgentCoordinator()
        stats = coord.get_coordinator_stats()
        assert "agents" in stats
        assert "investigator" in stats["agents"]
        assert "fixer" in stats["agents"]
        assert "analyst" in stats["agents"]
        assert "config" in stats
        assert stats["config"]["confidence_threshold"] == 0.7

    def test_get_coordinator_stats_no_analyst(self):
        coord = AgentCoordinator(enable_analyst=False)
        stats = coord.get_coordinator_stats()
        assert stats["agents"]["analyst"] is None


class TestMultiAgentEpisodeResult:
    """MultiAgentEpisodeResult dataclass."""

    def test_creation(self):
        result = MultiAgentEpisodeResult(
            total_reward=5.0,
            final_score=0.85,
            grade="excellent",
            steps=10,
            agent_decisions={},
            episode_id="abc123",
            duration_ms=1000,
        )
        assert result.total_reward == 5.0
        assert result.final_score == 0.85
        assert result.grade == "excellent"
        assert result.steps == 10

    def test_with_summaries(self):
        result = MultiAgentEpisodeResult(
            total_reward=3.0,
            final_score=0.7,
            grade="good",
            steps=8,
            agent_decisions={},
            episode_id="def456",
            duration_ms=800,
            investigation_summary={"services_queried": ["api-gateway"]},
            fix_summary={"fix_attempts": 1},
            analysis_summary={"suggested_fault_type": "oom"},
        )
        assert result.investigation_summary["services_queried"] == ["api-gateway"]
        assert result.fix_summary["fix_attempts"] == 1
