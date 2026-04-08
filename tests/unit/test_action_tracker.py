"""
IncidentOps - Action Tracker Anti-Bruteforce Tests

Tests the brute-force detection system:
- Penalizes redundant restarts
- Penalizes repeated queries
- Detects guessing behavior
- Intelligent tracker tracks fault context
"""
import pytest
from app.action_tracker import (
    ActionTracker,
    IntelligentActionTracker,
    ActionRecord,
    BruteForcePenalties,
)


class TestActionRecord:
    """ActionRecord dataclass holds individual action data."""

    def test_action_record_creation(self):
        record = ActionRecord(
            step=1,
            action_type="query_service",
            target_service="api-gateway",
            new_information=True,
            information_gained=["status", "health"],
        )
        assert record.step == 1
        assert record.action_type == "query_service"
        assert record.target_service == "api-gateway"
        assert record.new_information is True

    def test_action_record_defaults(self):
        record = ActionRecord(
            step=1,
            action_type="restart_service",
            target_service="api-gateway",
        )
        assert record.new_information is False
        assert record.information_gained == []


class TestBruteForcePenalties:
    """BruteForcePenalties dataclass holds penalty breakdown."""

    def test_penalties_default_zero(self):
        penalties = BruteForcePenalties()
        assert penalties.excessive_restart_penalty == 0.0
        assert penalties.repeated_log_query_penalty == 0.0
        assert penalties.no_new_info_penalty == 0.0
        assert penalties.total_penalty == 0.0

    def test_penalties_can_be_nonzero(self):
        penalties = BruteForcePenalties(
            excessive_restart_penalty=0.2,
            repeated_log_query_penalty=0.1,
            no_new_info_penalty=0.05,
        )
        assert penalties.excessive_restart_penalty == 0.2
        assert penalties.repeated_log_query_penalty == 0.1
        assert penalties.no_new_info_penalty == 0.05


class TestActionTrackerBasics:
    """ActionTracker core functionality."""

    def test_tracker_initializes_with_seed(self):
        tracker = ActionTracker(seed=42)
        assert tracker is not None

    def test_tracker_reset(self):
        tracker = ActionTracker(seed=42)
        tracker.reset()
        assert len(tracker.action_history) == 0

    def test_record_action_adds_to_history(self):
        tracker = ActionTracker(seed=42)
        tracker.reset()
        tracker.record_action(
            step=1,
            action_type="query_service",
            target_service="api-gateway",
            observation_result={"status": "healthy"},
        )
        assert len(tracker.action_history) == 1

    def test_record_action_returns_record(self):
        tracker = ActionTracker(seed=42)
        tracker.reset()
        record = tracker.record_action(
            step=1,
            action_type="query_service",
            target_service="api-gateway",
        )
        assert isinstance(record, ActionRecord)


class TestBruteForceDetection:
    """Brute force strategies are detected and penalized."""

    def test_excessive_restarts_penalized(self):
        """Restarting many services without justification earns penalty."""
        tracker = ActionTracker(seed=42)
        tracker.reset()

        # Restart 3 different services (MAX_UNJUSTIFIED_RESTARTS=2)
        for i in range(3):
            tracker.record_action(
                step=i + 1,
                action_type="restart_service",
                target_service=f"service-{i}",
            )

        # Pass root_cause and affected_services to calculate_penalties
        penalties = tracker.calculate_penalties(
            root_cause="service-0",
            affected_services={"service-0", "service-1"},
        )
        assert penalties.excessive_restart_penalty > 0, (
            "3 restarts should be penalized (max without justification: 2)"
        )

    def test_repeated_queries_on_same_service_penalized(self):
        """Repeating the same query type on the same service is penalized."""
        tracker = ActionTracker(seed=42)
        tracker.reset()

        # Query logs 3 times on the same service
        for _ in range(3):
            tracker.record_action(
                step=1,
                action_type="query_logs",
                target_service="api-gateway",
            )

        penalties = tracker.calculate_penalties(
            root_cause="api-gateway",
            affected_services={"api-gateway"},
        )
        assert penalties.repeated_log_query_penalty > 0, (
            "Repeated queries should be penalized"
        )

    def test_is_brute_force_detected_true(self):
        """Multiple excessive restarts trigger brute-force detection."""
        tracker = ActionTracker(seed=42)
        tracker.reset()

        # Restart 5 different unrelated services
        for i in range(5):
            tracker.record_action(
                step=i,
                action_type="restart_service",
                target_service=f"unrelated-{i}",
            )

        assert tracker.is_brute_force_detected() is True

    def test_is_brute_force_detected_false_with_good_behavior(self):
        """Targeted investigation is not flagged as brute-force."""
        tracker = ActionTracker(seed=42)
        tracker.reset()

        # Focused investigation: query service, query metrics, restart
        tracker.record_action(1, "query_service", "payment-service", {"status": "ok"})
        tracker.record_action(2, "query_metrics", "payment-service", {"latency": 100})
        tracker.record_action(3, "restart_service", "payment-service")

        assert tracker.is_brute_force_detected() is False

    def test_get_action_summary_returns_dict(self):
        tracker = ActionTracker(seed=42)
        tracker.reset()
        tracker.record_action(1, "query_service", "api-gateway", {"status": "ok"})
        summary = tracker.get_action_summary()
        assert isinstance(summary, dict)
        assert "total_actions" in summary


class TestIntelligentActionTracker:
    """IntelligentActionTracker adds fault context awareness."""

    def test_intelligent_tracker_initializes(self):
        tracker = IntelligentActionTracker(seed=42)
        assert tracker is not None

    def test_set_fault_context(self):
        tracker = IntelligentActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context(
            root_cause="payment-service",
            affected_services={"order-service"},
        )
        assert tracker.root_cause_service == "payment-service"
        assert "order-service" in tracker.affected_services

    def test_set_fault_context_multiple(self):
        tracker = IntelligentActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("recommendation-service", {"analytics-service"})
        assert tracker.root_cause_service == "recommendation-service"

    def test_is_guessing_behavior_true(self):
        """Guessing (random restarts) is detected as guessing."""
        tracker = IntelligentActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())

        # Random unrelated restarts without any queries
        for i in range(4):
            tracker.record_action(
                i, "restart_service", f"random-svc-{i}"
            )

        assert tracker.is_guessing_behavior() is True

    def test_is_guessing_behavior_false_with_systematic(self):
        """Systematic investigation is NOT guessing."""
        tracker = IntelligentActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())

        tracker.record_action(1, "query_service", "payment-service", {"status": "ok"})
        tracker.record_action(2, "query_metrics", "payment-service", {"latency": 50})
        tracker.record_action(3, "restart_service", "payment-service")

        assert tracker.is_guessing_behavior() is False

    def test_record_relevant_discovery(self):
        tracker = IntelligentActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())
        tracker.record_relevant_discovery("payment-service", "Found in metrics")
        summary = tracker.get_intelligence_summary()
        assert isinstance(summary, dict)

    def test_record_dependency_trace(self):
        tracker = IntelligentActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("database-primary", {"payment-service"})
        tracker.record_dependency_trace(
            from_service="payment-service",
            to_service="database-primary",
            relation="upstream",
        )
        summary = tracker.get_intelligence_summary()
        assert isinstance(summary, dict)

    def test_record_timeline_correlation(self):
        tracker = IntelligentActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("recommendation-service", set())
        tracker.record_timeline_correlation(
            event_type="deployment",
            timestamp="2024-01-15T10:00:00Z",
            metric_change="latency_spike",
        )
        summary = tracker.get_intelligence_summary()
        assert isinstance(summary, dict)

    def test_get_intelligence_summary(self):
        tracker = IntelligentActionTracker(seed=42)
        tracker.reset()
        tracker.set_fault_context("payment-service", set())
        tracker.record_action(1, "query_metrics", "payment-service", {"latency": 50})
        summary = tracker.get_intelligence_summary()
        assert "relevant_services_found" in summary
        assert "dependencies_traced" in summary

    def test_deterministic_with_seed(self):
        """Same seed produces same tracking results."""
        t1 = IntelligentActionTracker(seed=42)
        t2 = IntelligentActionTracker(seed=42)
        t1.reset()
        t2.reset()
        t1.set_fault_context("payment-service", {"order-service"})
        t2.set_fault_context("payment-service", {"order-service"})
        t1.record_action(1, "query_service", "payment-service", {"status": "ok"})
        t2.record_action(1, "query_service", "payment-service", {"status": "ok"})
        assert t1.is_guessing_behavior() == t2.is_guessing_behavior()
