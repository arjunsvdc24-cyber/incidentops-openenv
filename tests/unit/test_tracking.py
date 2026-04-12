"""
IncidentOps - Unit Tests: Information Tracking
"""
import pytest
from app.information_tracker import EnhancedActionTracker, ActionResult


class TestEnhancedActionTracker:
    def test_initializes(self):
        tracker = EnhancedActionTracker(seed=42)
        assert tracker is not None

    def test_record_action(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        result = tracker.record_action("query_service", "api-gateway")
        assert isinstance(result, ActionResult)

    def test_set_fault_context(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.set_fault_context(root_cause="payment-service", affected_services={"payment-service", "order-service"})
        assert tracker is not None

    def test_get_information_summary(self):
        tracker = EnhancedActionTracker(seed=42)
        tracker.reset()
        tracker.record_action("query_service", "api-gateway")
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
        # Results should be deterministic
        assert r1.information_gained == r2.information_gained
