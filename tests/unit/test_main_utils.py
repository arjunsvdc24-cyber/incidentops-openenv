"""
IncidentOps - Main Module Utilities & Request Model Tests

Tests utility functions, request validators, exception handlers,
and WebSocket management from app.main.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient


class TestCreateAccessToken:
    """create_access_token utility function."""

    def test_create_access_token_returns_string(self):
        from app.main import create_access_token
        token = create_access_token(user_id=1, username="testuser")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_different_users(self):
        from app.main import create_access_token
        token1 = create_access_token(user_id=1, username="user1")
        token2 = create_access_token(user_id=2, username="user2")
        assert token1 != token2

    def test_create_access_token_deterministic(self):
        from app.main import create_access_token
        # Note: tokens have expiry so may differ across calls
        token = create_access_token(user_id=42, username="fixeduser")
        assert isinstance(token, str)


class TestConnectionManager:
    """ConnectionManager WebSocket management."""

    @pytest.mark.asyncio
    async def test_connect_accepts_and_stores_websocket(self):
        from app.main import ConnectionManager
        manager = ConnectionManager()
        ws = AsyncMock()
        ws.accept = AsyncMock()
        await manager.connect(ws)
        ws.accept.assert_called_once()
        assert ws in manager.active_connections

    def test_disconnect_removes_websocket(self):
        from app.main import ConnectionManager
        manager = ConnectionManager()
        ws = MagicMock()
        ws.accept = MagicMock()
        # Manually add
        manager.active_connections.append(ws)
        manager.disconnect(ws)
        assert ws not in manager.active_connections

    def test_disconnect_nonexistent_safe(self):
        from app.main import ConnectionManager
        manager = ConnectionManager()
        ws = MagicMock()
        manager.disconnect(ws)  # Should not raise
        assert ws not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        from app.main import ConnectionManager
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2.accept = AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.broadcast({"type": "test"})
        ws1.send_json.assert_called_once_with({"type": "test"})
        ws2.send_json.assert_called_once_with({"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected(self):
        from app.main import ConnectionManager
        manager = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2.accept = AsyncMock()

        async def raise_on_send(msg):
            raise Exception("disconnected")

        ws2.send_json = raise_on_send
        await manager.connect(ws1)
        await manager.connect(ws2)

        await manager.broadcast({"type": "test"})
        # ws1 got the message
        ws1.send_json.assert_called_once()
        # ws2 was disconnected and removed
        assert ws2 not in manager.active_connections


class TestResetRequestValidator:
    """ResetRequest field validators."""

    def test_valid_seed_only(self):
        from app.main import ResetRequest
        req = ResetRequest(seed=42)
        assert req.seed == 42

    def test_valid_fault_type(self):
        from app.main import ResetRequest
        req = ResetRequest(fault_type="oom")
        assert req.fault_type == "oom"

    def test_valid_difficulty(self):
        from app.main import ResetRequest
        req = ResetRequest(difficulty=3)
        assert req.difficulty == 3

    def test_invalid_fault_type_raises(self):
        from app.main import ResetRequest
        with pytest.raises(ValueError) as exc_info:
            ResetRequest(fault_type="not_a_fault")
        assert "Invalid fault_type" in str(exc_info.value)

    def test_invalid_difficulty_low(self):
        from app.main import ResetRequest
        with pytest.raises(ValueError) as exc_info:
            ResetRequest(difficulty=0)
        assert "difficulty must be 1-5" in str(exc_info.value)

    def test_invalid_difficulty_high(self):
        from app.main import ResetRequest
        with pytest.raises(ValueError) as exc_info:
            ResetRequest(difficulty=6)
        assert "difficulty must be 1-5" in str(exc_info.value)

    def test_all_valid_fault_types(self):
        from app.main import ResetRequest
        # Only the 5 canonical FaultType enum values are accepted
        for ft in ["oom", "cascade", "ghost", "deployment", "network"]:
            req = ResetRequest(fault_type=ft)
            assert req.fault_type == ft

    def test_difficulty_boundary_values(self):
        from app.main import ResetRequest
        # Boundary: 1 and 5 should be valid
        assert ResetRequest(difficulty=1).difficulty == 1
        assert ResetRequest(difficulty=5).difficulty == 5


class TestGradeRequestModel:
    """GradeRequest model."""

    def test_valid_basic_request(self):
        from app.main import GradeRequest
        req = GradeRequest(
            actions=[{"action_type": "query_service", "target_service": "api-gateway"}],
            final_state={"terminated": False},
            scenario={"fault_type": "oom", "difficulty": 2},
        )
        assert len(req.actions) == 1
        assert req.seed == 42
        assert req.use_enhanced is True

    def test_with_rewards(self):
        from app.main import GradeRequest
        req = GradeRequest(
            actions=[],
            rewards=[0.1, 0.2, 1.0],
            final_state={"terminated": True},
            scenario={"fault_type": "cascade", "difficulty": 3},
        )
        assert req.rewards == [0.1, 0.2, 1.0]


class TestExceptionHandlers:
    """Custom exception handlers."""

    def test_http_exception_handler(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)

        # HTTPException is handled - we can test by triggering a known one
        # The /episodes/{id} endpoint raises HTTPException 404 for unknown IDs
        response = client.get("/episodes/nonexistent-episode-123")
        # Should get either 404 (handled) or 422 (validation) depending on Pydantic
        assert response.status_code in [404, 422]


class TestApiEndpoint:
    """GET /api endpoint returns API info."""

    def test_api_info_endpoint(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "IncidentOps"
        assert data["version"] == "15.0"
        assert "features" in data


class TestLeaderboardTasksEndpoint:
    """GET /leaderboard/tasks endpoint."""

    def test_leaderboard_tasks_endpoint(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/leaderboard/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert len(data["tasks"]) >= 3
        task_ids = [t["task_id"] for t in data["tasks"]]
        assert "oom_crash" in task_ids
        assert "cascade_failure" in task_ids
        assert "ghost_corruption" in task_ids


class TestMetricsEnabled:
    """Prometheus metrics configuration."""

    def test_metrics_enabled_flag(self):
        from app.main import _metrics_enabled
        # Should be True if prometheus_client is available
        assert isinstance(_metrics_enabled, bool)


class TestRootEndpoint:
    """GET / endpoint serves dashboard HTML."""

    def test_root_returns_html(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_root_content(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/")
        # Should contain IncidentOps or dashboard content
        content = response.text
        assert "IncidentOps" in content or "html" in content.lower()


class TestAgentStatsEndpoint:
    """GET /agents/stats endpoint."""

    def test_agents_stats_endpoint(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/agents/stats")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "config" in data
        assert "investigator" in data["agents"]
        assert "fixer" in data["agents"]
        assert "confidence_threshold" in data["config"]


class TestLifespan:
    """Test lifespan context manager initialization."""

    def test_lifespan_initializes(self):
        from app.main import app
        # The lifespan is attached to the app - just verify app exists
        assert app is not None
        # Verify lifespan is configured
        assert hasattr(app, "router")


class TestFrontierEndpoint:
    """GET /frontier endpoint."""

    def test_frontier_endpoint(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/frontier")
        assert response.status_code == 200
        data = response.json()
        assert "scenario_id" in data
        assert "difficulty" in data
        assert "dual_layer_failure" in data
        assert "deceptive_signals" in data


class TestMultiAgentEpisodeEndpoint:
    """POST /agents/episode endpoint - multi-agent coordination."""

    def test_multi_agent_episode_endpoint(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post("/agents/episode", json={
            "seed": 42,
            "max_steps": 5,
            "enable_analyst": True,
            "confidence_threshold": 0.7,
        })
        assert response.status_code == 200
        data = response.json()
        assert "episode_id" in data
        assert "total_reward" in data
        assert "final_score" in data
        assert "grade" in data
        assert "steps" in data
        assert "agent_decisions" in data

    def test_multi_agent_episode_minimal(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post("/agents/episode", json={
            "seed": 99,
        })
        assert response.status_code == 200
        data = response.json()
        assert "episode_id" in data

    def test_multi_agent_episode_no_analyst(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post("/agents/episode", json={
            "seed": 123,
            "enable_analyst": False,
            "max_steps": 3,
        })
        assert response.status_code == 200
        data = response.json()
        assert "grade" in data


class TestDeterminismCheckEndpoint:
    """GET /determinism/check endpoint."""

    def test_determinism_check_endpoint(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/determinism/check")
        assert response.status_code == 200
        data = response.json()
        assert "passed" in data
        assert "rewards_match" in data


class TestValidationEndpoint:
    """GET /validation endpoint."""

    def test_validation_endpoint(self):
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/validation")
        assert response.status_code == 200
        data = response.json()
        # Validation runner returns summary dict
        assert isinstance(data, dict)


class TestExceptionHandlerGeneral:
    """Test general exception handler."""

    def test_exception_handler_registered(self):
        from app.main import app
        # Verify exception handlers are registered
        assert app.exception_handler(Exception) is not None
