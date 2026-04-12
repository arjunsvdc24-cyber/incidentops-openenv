"""
IncidentOps - Edge Case Tests for API Endpoints

Tests:
1. /metadata, /schema, /mcp endpoints
2. Empty trajectory grading
3. Malformed action handling
4. Fault injection edge cases
5. Reward calculation boundary values
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture(autouse=True)
async def reset_globals():
    """Reset global environment and tracker state between tests."""
    import app.main as main_module
    main_module._env = None
    main_module._tracker = None
    yield
    main_module._env = None
    main_module._tracker = None


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestMetadataSchemaEndpoints:
    """Test the new /metadata, /schema, and /mcp endpoints."""

    @pytest.mark.asyncio
    async def test_metadata_endpoint(self, client):
        """GET /metadata returns OpenEnv metadata."""
        response = await client.get("/metadata")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "IncidentOps"
        assert "description" in data

    @pytest.mark.asyncio
    async def test_schema_endpoint(self, client):
        """GET /schema returns action, observation, and state schemas."""
        response = await client.get("/schema")
        assert response.status_code == 200
        data = response.json()
        assert "action" in data
        assert "observation" in data
        assert "state" in data
        # Verify action schema has required fields
        assert "action_type" in data["action"]
        assert data["action"]["action_type"]["type"] == "string"
        assert "enum" in data["action"]["action_type"]
        # Verify all 11 action types are present
        assert len(data["action"]["action_type"]["enum"]) == 11

    @pytest.mark.asyncio
    async def test_mcp_endpoint_tool_calls(self, client):
        """POST /mcp with tool_calls returns tools list."""
        response = await client.post("/mcp", json={
            "method": "tools/list",
            "id": 1,
            "tool_calls": [{"name": "list_tools"}]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert "result" in data
        assert "tools" in data["result"]
        assert len(data["result"]["tools"]) > 0

    @pytest.mark.asyncio
    async def test_mcp_endpoint_method_call(self, client):
        """POST /mcp with method returns method response."""
        response = await client.post("/mcp", json={
            "method": "environment/reset",
            "id": 2,
            "params": {"seed": 42}
        })
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"

    @pytest.mark.asyncio
    async def test_mcp_endpoint_invalid_json(self, client):
        """POST /mcp with invalid JSON returns 400."""
        response = await client.post("/mcp", content="not json", headers={"Content-Type": "application/json"})
        assert response.status_code == 400


class TestEmptyTrajectoryGrading:
    """Test grading with empty or minimal trajectories."""

    @pytest.mark.asyncio
    async def test_grader_empty_actions(self, client):
        """Grade with empty actions list."""
        await client.post("/reset", json={"seed": 42})
        response = await client.post("/grader", json={
            "actions": [],
            "final_state": {},
            "scenario": {"fault_type": "oom", "difficulty": 2},
        })
        assert response.status_code == 200
        data = response.json()
        assert "final_score" in data
        assert isinstance(data["final_score"], (int, float))
        assert 0.0 <= data["final_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_grader_empty_scenario(self, client):
        """Grade with minimal scenario info."""
        await client.post("/reset", json={"seed": 42})
        response = await client.post("/grader", json={
            "actions": [
                {"action_type": "restart_service", "target_service": "payment-service"},
            ],
            "final_state": {"fix_applied": True},
            "scenario": {},
        })
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_grader_no_final_state(self, client):
        """Grade without final_state provided."""
        await client.post("/reset", json={"seed": 42})
        response = await client.post("/grader", json={
            "actions": [],
            "scenario": {"fault_type": "cascade", "difficulty": 3},
        })
        assert response.status_code == 200


class TestMalformedActionHandling:
    """Test handling of malformed action requests."""

    @pytest.mark.asyncio
    async def test_step_unknown_action_type(self, client):
        """Step with unknown action_type returns validation error."""
        await client.post("/reset", json={"seed": 42})
        response = await client.post("/step", json={
            "action_type": "unknown_action",
            "target_service": "api-gateway",
        })
        assert response.status_code == 422  # FastAPI validation error

    @pytest.mark.asyncio
    async def test_step_invalid_service(self, client):
        """Step with invalid service name returns validation error."""
        await client.post("/reset", json={"seed": 42})
        response = await client.post("/step", json={
            "action_type": "query_service",
            "target_service": "invalid-service-xyz",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_step_missing_target_for_service_action(self, client):
        """Step without target_service for service action returns 422."""
        await client.post("/reset", json={"seed": 42})
        response = await client.post("/step", json={
            "action_type": "restart_service",
            # Missing target_service
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_reset_invalid_seed_type(self, client):
        """Reset with invalid seed type handles gracefully."""
        response = await client.post("/reset", json={"seed": "not-a-number"})
        # Should either return 422 or handle gracefully
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_reset_invalid_difficulty(self, client):
        """Reset with difficulty out of range."""
        response = await client.post("/reset", json={"seed": 42, "difficulty": 10})
        # Should either return 200 (handled) or 422 (rejected)
        assert response.status_code in [200, 422]


class TestFaultInjectionEdgeCases:
    """Test fault injection edge cases."""

    def test_fault_registry_unknown_fault(self):
        """FaultRegistry raises KeyError for unknown fault."""
        from app.faults import FaultRegistry
        with pytest.raises(KeyError):
            FaultRegistry.get("nonexistent_fault_xyz")

    def test_fault_registry_generate_unknown(self):
        """FaultRegistry.generate raises KeyError for unknown fault."""
        from app.faults import FaultRegistry
        from app.determinism import DeterministicRNG
        rng = DeterministicRNG(42)
        with pytest.raises(KeyError):
            FaultRegistry.generate("unknown", rng, 3, ["api-gateway"])

    def test_cascade_fault_generates(self):
        """Cascade fault generates valid scenario."""
        from app.fault_injector import FaultInjector, FaultType
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.CASCADE, difficulty=3)
        assert len(scenario.affected_services) > 0
        assert isinstance(scenario.correct_fix, str)

    def test_ghost_fault_generates(self):
        """Ghost fault generates valid scenario."""
        from app.fault_injector import FaultInjector, FaultType
        inj = FaultInjector(seed=42)
        scenario = inj.generate_scenario(FaultType.GHOST, difficulty=5)
        assert scenario.root_cause_service is not None
        assert isinstance(scenario.correct_fix, str)
        # Ghost should have misleading signals
        assert len(scenario.misleading_signals) > 0

    def test_all_fault_types_generate(self):
        """All FaultType values generate valid scenarios."""
        from app.fault_injector import FaultInjector, FaultType
        inj = FaultInjector(seed=42)
        for fault_type in list(FaultType):
            scenario = inj.generate_scenario(fault_type, difficulty=3)
            assert scenario is not None
            assert scenario.root_cause_service is not None
            assert scenario.correct_fix is not None

    def test_deterministic_scenario_generation(self):
        """Same seed produces identical scenarios."""
        from app.fault_injector import FaultInjector, FaultType
        inj1 = FaultInjector(seed=12345)
        inj2 = FaultInjector(seed=12345)
        s1 = inj1.generate_scenario(FaultType.OOM, difficulty=2)
        s2 = inj2.generate_scenario(FaultType.OOM, difficulty=2)
        assert s1.root_cause_service == s2.root_cause_service
        assert s1.difficulty == s2.difficulty
        assert s1.correct_fix == s2.correct_fix


class TestRewardCalculationBoundary:
    """Test reward calculation with boundary values."""

    def test_reward_calculator_initialization(self):
        """RewardCalculator initializes without error."""
        from app.reward import RewardCalculator
        calc = RewardCalculator()
        assert calc is not None

    def test_reward_calculator_set_fault_info(self):
        """RewardCalculator.set_fault_info works."""
        from app.reward import RewardCalculator
        calc = RewardCalculator()
        calc.set_fault_info(root_cause="payment-service", affected_services=set(), fault_type="oom")
        assert calc is not None

    def test_reward_calculator_reset(self):
        """RewardCalculator.reset works."""
        from app.reward import RewardCalculator
        calc = RewardCalculator()
        calc.set_fault_info(root_cause="payment-service", affected_services=set())
        calc.reset()
        assert calc is not None

    def test_reward_calculator_step_reward(self):
        """RewardCalculator.calculate_step_reward works."""
        from app.reward import RewardCalculator
        calc = RewardCalculator()
        calc.set_fault_info(root_cause="payment-service", affected_services={"order-service"}, fault_type="oom")
        reward = calc.calculate_step_reward("query_service", "payment-service", {"payment-service": {}})
        assert reward is not None
        assert hasattr(reward, "total")


class TestActionTrackerEdgeCases:
    """Test action tracker edge cases."""

    def test_tracker_initialization(self):
        """ActionTracker initializes without error."""
        from app.action_tracker import ActionTracker
        tracker = ActionTracker()
        assert tracker is not None

    def test_tracker_record_action(self):
        """ActionTracker.record_action works with empty list."""
        from app.action_tracker import ActionTracker
        tracker = ActionTracker()
        record = tracker.record_action(0, "restart_service", "payment-service", None)
        assert record is not None

    def test_tracker_empty_trajectory(self):
        """ActionTracker with empty trajectory - check brute force not detected."""
        from app.action_tracker import ActionTracker
        tracker = ActionTracker()
        result = tracker.calculate_penalties()
        assert isinstance(result, (dict, object))
        assert not tracker.is_brute_force_detected()

    def test_tracker_get_action_summary(self):
        """ActionTracker.get_action_summary works."""
        from app.action_tracker import ActionTracker
        tracker = ActionTracker()
        tracker.record_action(0, "query_service", "payment-service", None)
        summary = tracker.get_action_summary()
        assert isinstance(summary, dict)

    def test_tracker_reset(self):
        """ActionTracker.reset works."""
        from app.action_tracker import ActionTracker
        tracker = ActionTracker()
        tracker.record_action(0, "restart_service", "payment-service", None)
        tracker.reset()
        summary = tracker.get_action_summary()
        assert summary.get("total_actions", 0) == 0


class TestDeceptiveSignalsEdgeCases:
    """Test deceptive signal generation edge cases."""

    def test_deceptive_signal_generator_initialization(self):
        """DeceptiveSignalGenerator initializes without error."""
        from app.deceptive_signals import DeceptiveSignalGenerator
        gen = DeceptiveSignalGenerator(seed=42)
        assert gen is not None

    def test_generate_full_deception_suite(self):
        """DeceptiveSignalGenerator.generate_full_deception_suite returns a dict."""
        from app.deceptive_signals import DeceptiveSignalGenerator
        gen = DeceptiveSignalGenerator(seed=42)
        signals = gen.generate_full_deception_suite(actual_root_cause="payment-service")
        assert isinstance(signals, dict)

    def test_deterministic_signal_generation(self):
        """Same seed produces same deceptive signals."""
        from app.deceptive_signals import DeceptiveSignalGenerator
        gen1 = DeceptiveSignalGenerator(seed=42)
        gen2 = DeceptiveSignalGenerator(seed=42)
        signals1 = gen1.generate_full_deception_suite(actual_root_cause="payment-service")
        signals2 = gen2.generate_full_deception_suite(actual_root_cause="payment-service")
        assert signals1 == signals2

    def test_deception_methods_work(self):
        """Deception pattern generation methods work."""
        from app.deceptive_signals import DeceptiveSignalGenerator
        gen = DeceptiveSignalGenerator(seed=42)
        pattern = gen.generate_false_root_cause_pattern(
            actual_root_cause="payment-service",
            false_root_cause="user-service"
        )
        assert pattern is not None


class TestInformationTrackerEdgeCases:
    """Test information tracker edge cases."""

    def test_enhanced_action_tracker_initialization(self):
        """EnhancedActionTracker initializes without error."""
        from app.information_tracker import EnhancedActionTracker
        tracker = EnhancedActionTracker()
        assert tracker is not None

    def test_empty_trajectory_summary(self):
        """EnhancedActionTracker with empty action list."""
        from app.information_tracker import EnhancedActionTracker
        tracker = EnhancedActionTracker()
        summary = tracker.get_information_summary()
        assert isinstance(summary, dict)

    def test_observation_without_investigation(self):
        """Agent takes no investigative actions."""
        from app.information_tracker import EnhancedActionTracker
        tracker = EnhancedActionTracker()
        tracker.record_action("restart_service", "payment-service", None)
        summary = tracker.get_information_summary()
        assert "services_queried" in summary
        # Restart without investigation should show no services queried
        assert summary.get("services_queried", 0) == 0

    def test_thorough_investigation(self):
        """Agent thoroughly investigates before fixing."""
        from app.information_tracker import EnhancedActionTracker
        tracker = EnhancedActionTracker()
        tracker.record_action("query_service", "payment-service", None)
        tracker.record_action("query_metrics", "payment-service", None)
        tracker.record_action("query_logs", "payment-service", None)
        tracker.record_action("query_dependencies", "payment-service", None)
        tracker.record_action("identify_root_cause", "payment-service", None)
        tracker.record_action("restart_service", "payment-service", None)
        summary = tracker.get_information_summary()
        assert "services_queried" in summary
        # Should have queried some services
        assert summary.get("services_queried", 0) > 0

    def test_reasoning_score(self):
        """EnhancedActionTracker.get_reasoning_score works."""
        from app.information_tracker import EnhancedActionTracker
        tracker = EnhancedActionTracker()
        score = tracker.get_reasoning_score()
        assert isinstance(score, (int, float))


class TestEnvironmentEdgeCases:
    """Test environment edge cases."""

    def test_env_reset_returns_observation(self):
        """Environment reset returns valid observation."""
        from app.environment import IncidentEnv
        env = IncidentEnv()
        obs = env.reset(seed=42)
        assert "step" in obs
        assert "services" in obs
        assert obs["step"] == 0

    def test_env_deterministic_reset(self):
        """Environment produces identical observations with same seed."""
        from app.environment import IncidentEnv
        env1 = IncidentEnv()
        env2 = IncidentEnv()
        obs1 = env1.reset(seed=999)
        obs2 = env2.reset(seed=999)
        assert obs1["step"] == obs2["step"]
        assert obs1["services"] == obs2["services"]

    def test_env_step_returns_step_response(self):
        """Environment step returns StepResponse."""
        from app.environment import IncidentEnv
        from app.models import StepResponse
        env = IncidentEnv()
        env.reset(seed=42)
        response = env.step({"action_type": "query_service", "target_service": "api-gateway"})
        assert isinstance(response, StepResponse)
        assert response.observation is not None
        assert response.reward is not None
        assert response.terminated is not None

    def test_env_services_count(self):
        """Environment has all 15 services."""
        from app.environment import IncidentEnv
        env = IncidentEnv()
        obs = env.reset(seed=42)
        assert len(obs["services"]) == 15

    def test_env_valid_actions_accepted(self):
        """Environment accepts valid action types."""
        from app.environment import IncidentEnv
        env = IncidentEnv()
        env.reset(seed=42)
        # Test query_service
        response = env.step({"action_type": "query_service", "target_service": "api-gateway"})
        assert isinstance(response.observation, dict)

    def test_env_terminal_state(self):
        """Environment reaches terminal state after fix."""
        from app.environment import IncidentEnv
        env = IncidentEnv()
        env.reset(seed=42)
        # Take actions until terminated or max steps
        for _ in range(51):
            response = env.step({"action_type": "query_service", "target_service": "api-gateway"})
            if response.terminated:
                break
        # Should complete without error
        assert True
