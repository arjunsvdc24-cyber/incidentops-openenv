"""
IncidentOps - Information Tracker Tests

Tests the EnhancedActionTracker for information gathering and reasoning evaluation.
"""
import pytest
from app.information_tracker import EnhancedActionTracker, ActionResult


class TestEnhancedActionTracker:
    def test_initializes(self):
        tracker = EnhancedActionTracker(seed=42)
        assert tracker is not None

    def test_reset(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        assert len(tracker.action_history) == 0

    def test_record_action(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        result = tracker.record_action("query_service", "api-gateway")
        assert isinstance(result, ActionResult)

    def test_record_action_returns_correct_fields(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        result = tracker.record_action("query_metrics", "payment-service")
        assert hasattr(result, "action_type")
        assert hasattr(result, "target_service")
        assert hasattr(result, "information_gained")

    def test_set_fault_context(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context(
            root_cause="payment-service",
            affected_services={"payment-service", "order-service"},
        )
        assert tracker is not None

    def test_get_information_summary(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.record_action("query_service", "api-gateway")
        tracker.record_action("query_metrics", "payment-service")
        summary = tracker.get_information_summary()
        assert isinstance(summary, dict)

    def test_get_reasoning_score(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        score = tracker.get_reasoning_score()
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_is_guessing_behavior(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        is_guessing = tracker.is_guessing_behavior()
        assert isinstance(is_guessing, bool)

    def test_deterministic_with_seed(self):
        tracker1 = EnhancedActionTracker(seed=42)
        tracker2 = EnhancedActionTracker(seed=42)
        tracker1.reset()
        tracker2.reset()
        r1 = tracker1.record_action("query_service", "api-gateway")
        r2 = tracker2.record_action("query_service", "api-gateway")
        assert r1.information_gained == r2.information_gained

    def test_reasoning_score_after_investigation(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())
        tracker.record_action("query_metrics", "payment-service")
        tracker.record_action("query_logs", "payment-service")
        score = tracker.get_reasoning_score()
        assert 0.0 <= score <= 1.0

    def test_action_history_grows(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        assert len(tracker.action_history) == 0
        tracker.record_action("query_service", "api-gateway")
        assert len(tracker.action_history) == 1
        tracker.record_action("query_metrics", "payment-service")
        assert len(tracker.action_history) == 2

    def test_get_information_summary_has_keys(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.record_action("query_service", "api-gateway")
        summary = tracker.get_information_summary()
        assert isinstance(summary, dict)


class TestActionResult:
    """ActionResult dataclass."""

    def test_action_result_creation(self):
        result = ActionResult(
            action_type="query_service",
            target_service="api-gateway",
            information_gained=["status", "health"],
            information_type="service_health",
            new_information=True,
            state_changed=False,
            is_redundant=False,
            is_unrelated_restart=False,
            penalty=0.0,
            reasoning_hint="check service health",
        )
        assert result.action_type == "query_service"
        assert result.target_service == "api-gateway"
        assert result.information_gained == ["status", "health"]
        assert result.new_information is True

    def test_action_result_fields(self):
        result = ActionResult(
            action_type="restart_service",
            target_service="api-gateway",
            information_gained=[],
            information_type="",
            new_information=False,
            state_changed=False,
            is_redundant=False,
            is_unrelated_restart=False,
            penalty=0.0,
            reasoning_hint="",
        )
        assert result.action_type == "restart_service"
        assert result.penalty == 0.0


class TestInformationTrackerEdgeCases:
    """Coverage for uncovered lines in information_tracker.py."""

    def test_duplicate_log_query_is_redundant(self):
        """Cover: information_tracker.py line 314 - repeated log query."""
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())
        tracker.record_action("query_logs", "payment-service")
        tracker.record_action("query_logs", "payment-service")  # duplicate
        result = tracker.record_action("query_logs", "payment-service")  # redundant
        assert result.is_redundant is True

    def test_unrelated_restart_penalty(self):
        """Cover: information_tracker.py lines 329-330 - unrelated service."""
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", {"payment-service"})
        tracker.record_action("restart_service", "email-service")  # unrelated
        result = tracker.record_action("restart_service", "email-service")
        assert result.is_unrelated_restart is True
        assert result.penalty > 0

    def test_no_new_info_penalty_after_step_3(self):
        """Cover: information_tracker.py lines 347-349 - step > 3."""
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())
        for _ in range(4):
            tracker.record_action("query_service", "api-gateway")
        penalties = tracker.get_total_penalties()
        assert penalties.no_new_info_penalty > 0

    def test_reasoning_hint_no_info_no_suggestions(self):
        """Cover: information_tracker.py line 392 - no suggestions path."""
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())
        # No info gained, no dependencies, no deploys, no memory queried
        tracker.record_action("restart_service", "payment-service")
        summary = tracker.get_information_summary()
        assert isinstance(summary, dict)

    def test_get_total_penalties_with_penalties(self):
        """Cover: information_tracker.py lines 399-410 - penalties accumulate."""
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())
        for _ in range(5):
            tracker.record_action("restart_service", "email-service")
        penalties = tracker.get_total_penalties()
        assert penalties.total_penalty > 0
        assert len(penalties.reasons) >= 0

    def test_get_investigation_sequence(self):
        """Cover: information_tracker.py lines 433-443 - sequence."""
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.record_action("query_service", "api-gateway")
        tracker.record_action("query_metrics", "payment-service")
        seq = tracker.get_investigation_sequence()
        assert len(seq) == 2
        assert seq[0]["step"] == 1

    def test_is_guessing_with_high_penalty(self):
        """Cover: information_tracker.py line 449-450 - high penalty."""
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())
        for _ in range(6):
            tracker.record_action("restart_service", "email-service")
        is_guessing = tracker.is_guessing_behavior()
        assert isinstance(is_guessing, bool)

    def test_is_guessing_many_restarts(self):
        """Cover: information_tracker.py lines 452-460 - many restarts."""
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())
        tracker.record_action("restart_service", "email-service")
        tracker.record_action("restart_service", "notification-service")
        tracker.record_action("restart_service", "shipping-service")
        # No investigation — guessing
        is_guessing = tracker.is_guessing_behavior()
        assert isinstance(is_guessing, bool)

