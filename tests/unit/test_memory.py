"""
IncidentOps - Memory Module Tests

Tests IncidentMemory for past incident retrieval and similarity matching.
"""
import pytest
from app.memory import IncidentRecord, IncidentMemory, MemoryMatch, MemoryIntegrator


class TestIncidentRecord:
    """IncidentRecord dataclass."""

    def test_record_creation(self):
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError", "OOM crash"],
        )
        assert record.fault_type == "oom"
        assert record.root_cause_service == "payment-service"
        assert record.correct_action == "restart_service"
        assert len(record.symptoms) == 2

    def test_record_to_dict(self):
        record = IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="scale_service",
            symptoms=["connection pool exhausted"],
        )
        d = record.to_dict()
        assert isinstance(d, dict)
        assert d["fault_type"] == "cascade"

    def test_record_from_dict(self):
        data = {
            "fault_type": "ghost",
            "root_cause_service": "recommendation-service",
            "correct_action": "rollback_deployment",
            "symptoms": ["silent degradation", "CTR drop"],
            "affected_services": [],
            "resolution_steps": [],
            "difficulty": 3,
        }
        record = IncidentRecord.from_dict(data)
        assert record.fault_type == "ghost"
        assert record.root_cause_service == "recommendation-service"

    def test_get_id_generates_string(self):
        record = IncidentRecord(
            fault_type="ddos",
            root_cause_service="api-gateway",
            correct_action="scale_service",
            symptoms=["high request rate"],
        )
        incident_id = record.get_id()
        assert isinstance(incident_id, str)
        assert len(incident_id) > 0

    def test_get_id_deterministic(self):
        r1 = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OOM"],
        )
        r2 = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OOM"],
        )
        assert r1.get_id() == r2.get_id()

    def test_get_id_differs_with_content(self):
        r1 = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OOM"],
        )
        r2 = IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="scale_service",
            symptoms=["pool exhausted"],
        )
        assert r1.get_id() != r2.get_id()


class TestMemoryMatch:
    """MemoryMatch dataclass."""

    def test_match_creation(self):
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OOM"],
        )
        match = MemoryMatch(
            record=record,
            relevance_score=0.85,
            matched_keywords=["OOM", "memory"],
        )
        assert match.relevance_score == 0.85
        assert len(match.matched_keywords) == 2

    def test_match_fields(self):
        record = IncidentRecord(
            fault_type="ddos",
            root_cause_service="api-gateway",
            correct_action="scale_service",
            symptoms=["high latency"],
        )
        match = MemoryMatch(
            record=record,
            relevance_score=0.7,
            matched_keywords=["latency"],
            match_details={"step": 1},
        )
        assert 0.0 <= match.relevance_score <= 1.0


class TestIncidentMemory:
    """IncidentMemory for storing and retrieving past incidents."""

    def test_memory_initializes(self):
        memory = IncidentMemory(seed=42)
        assert memory is not None

    def test_add_incident(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError"],
        )
        incident_id = memory.add_incident(record)
        assert isinstance(incident_id, str)
        assert len(incident_id) > 0

    def test_add_multiple_incidents(self):
        memory = IncidentMemory(seed=42)
        for i in range(3):
            record = IncidentRecord(
                fault_type="oom",
                root_cause_service=f"service-{i}",
                correct_action="restart_service",
                symptoms=["OOM"],
            )
            memory.add_incident(record)
        assert len(memory.incidents) >= 3

    def test_search_by_symptoms(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError", "heap exhausted"],
        )
        memory.add_incident(record)

        matches = memory.search(symptoms=["OutOfMemoryError"], limit=5)
        assert isinstance(matches, list)
        assert len(matches) >= 1

    def test_search_by_services(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="scale_service",
            symptoms=["pool exhaustion"],
        )
        memory.add_incident(record)

        matches = memory.search(services=["database-primary"], limit=5)
        assert isinstance(matches, list)

    def test_search_by_fault_type(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="ghost",
            root_cause_service="recommendation-service",
            correct_action="rollback_deployment",
            symptoms=["CTR drop"],
        )
        memory.add_incident(record)

        matches = memory.search(fault_type="ghost", limit=5)
        assert isinstance(matches, list)

    def test_search_empty_results(self):
        memory = IncidentMemory(seed=42)
        # No incidents added
        matches = memory.search(symptoms=["UnknownError"], services=["unknown"])
        assert isinstance(matches, list)

    def test_search_limit(self):
        memory = IncidentMemory(seed=42)
        for i in range(10):
            record = IncidentRecord(
                fault_type="oom",
                root_cause_service=f"svc-{i}",
                correct_action="restart_service",
                symptoms=["OOM", f"symptom-{i}"],
            )
            memory.add_incident(record)

        matches = memory.search(symptoms=["OOM"], limit=3)
        assert len(matches) <= 3

    def test_search_returns_memory_match_objects(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="ddos",
            root_cause_service="api-gateway",
            correct_action="scale_service",
            symptoms=["traffic spike"],
        )
        memory.add_incident(record)
        matches = memory.search(symptoms=["traffic spike"], limit=5)
        for match in matches:
            assert isinstance(match, MemoryMatch)
            assert isinstance(match.record, IncidentRecord)

    def test_get_similar_incidents(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="scale_service",
            symptoms=["connection pool exhausted"],
        )
        memory.add_incident(record)
        similar = memory.get_similar_incidents(
            symptoms=["connection pool exhausted"],
            affected_services=["database-primary"],
        )
        assert isinstance(similar, list)

    def test_get_suggested_action(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="ddos",
            root_cause_service="api-gateway",
            correct_action="scale_service",
            symptoms=["high request rate"],
        )
        memory.add_incident(record)
        suggestion = memory.get_suggested_action(
            symptoms=["high request rate"],
            services=["api-gateway"],
        )
        # Returns dict or None
        assert suggestion is None or isinstance(suggestion, dict)

    def test_to_dict(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="memory_leak",
            root_cause_service="user-service",
            correct_action="restart_service",
            symptoms=["gradual OOM"],
        )
        memory.add_incident(record)
        d = memory.to_dict()
        assert isinstance(d, dict)
        assert "incidents" in d
        assert len(d["incidents"]) >= 1

    def test_from_dict(self):
        data = {
            "incidents": [
                {
                    "fault_type": "oom",
                    "root_cause_service": "payment-service",
                    "correct_action": "restart_service",
                    "symptoms": ["OutOfMemoryError"],
                    "affected_services": [],
                    "resolution_steps": [],
                    "difficulty": 2,
                }
            ],
        }
        memory = IncidentMemory.from_dict(data)
        assert len(memory.incidents) == 1
        assert memory.incidents[0].fault_type == "oom"

    def test_get_stats(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OOM"],
        )
        memory.add_incident(record)
        stats = memory.get_stats()
        assert isinstance(stats, dict)

    def test_deterministic_search(self):
        """Same inputs → same search results."""
        m1 = IncidentMemory(seed=42)
        m2 = IncidentMemory(seed=42)
        for i in range(3):
            for mem in [m1, m2]:
                rec = IncidentRecord(
                    fault_type="oom",
                    root_cause_service="payment-service",
                    correct_action="restart_service",
                    symptoms=["OOM"],
                )
                mem.add_incident(rec)
        r1 = m1.search(symptoms=["OOM"], services=["payment-service"])
        r2 = m2.search(symptoms=["OOM"], services=["payment-service"])
        assert len(r1) == len(r2)


class TestMemoryIntegrator:
    """MemoryIntegrator connects memory to the RL environment."""

    def test_integrator_initializes(self):
        memory = IncidentMemory(seed=42)
        integrator = MemoryIntegrator(memory)
        assert integrator is not None

    def test_integrator_has_memory(self):
        memory = IncidentMemory(seed=42)
        integrator = MemoryIntegrator(memory)
        assert integrator.memory is memory
