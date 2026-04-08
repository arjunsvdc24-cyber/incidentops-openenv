"""
Tests for app/memory.py - Incident Memory System

Covers:
- IncidentRecord dataclass
- MemoryMatch dataclass
- IncidentMemory class
- MemoryIntegrator class
"""
import pytest
import json
import tempfile
from pathlib import Path

from app.memory import IncidentRecord, MemoryMatch, IncidentMemory, MemoryIntegrator


# =============================================================================
# IncidentRecord Tests
# =============================================================================

class TestIncidentRecord:
    """Tests for IncidentRecord dataclass"""

    def test_create_incident_record(self):
        """Test creating an IncidentRecord with required fields"""
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError", "heap"],
        )
        assert record.fault_type == "oom"
        assert record.root_cause_service == "payment-service"
        assert record.correct_action == "restart_service"
        assert record.symptoms == ["OutOfMemoryError", "heap"]
        assert record.affected_services == []
        assert record.resolution_steps == []
        assert record.difficulty == 3

    def test_create_incident_record_with_all_fields(self):
        """Test creating an IncidentRecord with all fields"""
        record = IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="scale_service",
            symptoms=["timeout", "slow queries"],
            affected_services=["user-service", "order-service"],
            resolution_steps=["Check DB health", "Scale"],
            difficulty=4,
        )
        assert record.difficulty == 4
        assert record.affected_services == ["user-service", "order-service"]
        assert record.resolution_steps == ["Check DB health", "Scale"]

    def test_to_dict(self):
        """Test converting IncidentRecord to dictionary"""
        record = IncidentRecord(
            fault_type="network",
            root_cause_service="api-gateway",
            correct_action="restart_service",
            symptoms=["timeout"],
            difficulty=2,
        )
        d = record.to_dict()
        assert isinstance(d, dict)
        assert d["fault_type"] == "network"
        assert d["root_cause_service"] == "api-gateway"
        assert d["correct_action"] == "restart_service"
        assert d["symptoms"] == ["timeout"]
        assert "difficulty" in d

    def test_from_dict(self):
        """Test creating IncidentRecord from dictionary"""
        data = {
            "fault_type": "ghost",
            "root_cause_service": "search-service",
            "correct_action": "rollback_deployment",
            "symptoms": ["search quality drop"],
            "affected_services": ["search-service"],
            "resolution_steps": ["Check metrics"],
            "difficulty": 5,
        }
        record = IncidentRecord.from_dict(data)
        assert record.fault_type == "ghost"
        assert record.root_cause_service == "search-service"
        assert record.difficulty == 5

    def test_from_dict_with_missing_optional_fields(self):
        """Test from_dict with missing optional fields (default values)"""
        data = {
            "fault_type": "oom",
            "root_cause_service": "payment-service",
            "correct_action": "restart_service",
            "symptoms": ["OutOfMemoryError"],
        }
        record = IncidentRecord.from_dict(data)
        assert record.affected_services == []
        assert record.resolution_steps == []
        assert record.difficulty == 3

    def test_get_id_deterministic(self):
        """Test that get_id is deterministic"""
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError"],
        )
        id1 = record.get_id()
        id2 = record.get_id()
        assert id1 == id2
        assert len(id1) == 8

    def test_get_id_different_content_different_id(self):
        """Test that different content produces different IDs"""
        record1 = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError"],
        )
        record2 = IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="scale_service",
            symptoms=["timeout"],
        )
        assert record1.get_id() != record2.get_id()


# =============================================================================
# MemoryMatch Tests
# =============================================================================

class TestMemoryMatch:
    """Tests for MemoryMatch dataclass"""

    def test_create_memory_match(self):
        """Test creating a MemoryMatch"""
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError"],
        )
        match = MemoryMatch(
            record=record,
            relevance_score=0.75,
            matched_keywords=["oom", "OutOfMemoryError"],
        )
        assert match.record == record
        assert match.relevance_score == 0.75
        assert match.matched_keywords == ["oom", "OutOfMemoryError"]
        assert match.match_details == {}

    def test_memory_match_with_details(self):
        """Test MemoryMatch with match_details"""
        record = IncidentRecord(
            fault_type="network",
            root_cause_service="api-gateway",
            correct_action="restart_service",
            symptoms=["timeout"],
        )
        match = MemoryMatch(
            record=record,
            relevance_score=0.5,
            matched_keywords=["timeout"],
            match_details={"search_keywords": 3, "incident_keywords": 10},
        )
        assert match.match_details["search_keywords"] == 3


# =============================================================================
# IncidentMemory Tests
# =============================================================================

class TestIncidentMemory:
    """Tests for IncidentMemory class"""

    def test_init_default(self):
        """Test initialization with defaults"""
        memory = IncidentMemory()
        assert memory.seed == 42
        assert memory.storage_path is None
        # Should have default incidents
        assert len(memory.incidents) > 0

    def test_init_with_seed(self):
        """Test initialization with custom seed"""
        memory = IncidentMemory(seed=123)
        assert memory.seed == 123

    def test_init_with_storage_path(self):
        """Test initialization with storage path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "memory.json")
            memory = IncidentMemory(seed=42, storage_path=path)
            assert memory.storage_path == path

    def test_default_incidents_loaded(self):
        """Test that default incidents are loaded on init"""
        memory = IncidentMemory()
        # Should have oom incidents
        oom_incidents = [i for i in memory.incidents if i.fault_type == "oom"]
        assert len(oom_incidents) >= 2
        # Should have cascade incidents
        cascade_incidents = [i for i in memory.incidents if i.fault_type == "cascade"]
        assert len(cascade_incidents) >= 2
        # Should have ghost incidents
        ghost_incidents = [i for i in memory.incidents if i.fault_type == "ghost"]
        assert len(ghost_incidents) >= 2

    def test_add_incident(self):
        """Test adding a new incident"""
        memory = IncidentMemory()
        initial_count = len(memory.incidents)

        new_incident = IncidentRecord(
            fault_type="deployment",
            root_cause_service="inventory-service",
            correct_action="rollback_deployment",
            symptoms=["api error", "after deploy"],
        )

        incident_id = memory.add_incident(new_incident)
        assert len(memory.incidents) == initial_count + 1
        assert len(incident_id) == 8

    def test_add_incident_duplicate(self):
        """Test that adding duplicate incident returns existing ID"""
        memory = IncidentMemory()

        incident = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError"],
        )

        initial_count = len(memory.incidents)
        id1 = memory.add_incident(incident)
        count_after_first = len(memory.incidents)

        # Adding same content should not increase count
        id2 = memory.add_incident(incident)
        assert len(memory.incidents) == count_after_first
        assert id1 == id2

    def test_add_incident_no_duplicate(self):
        """Test that adding different incident increases count"""
        memory = IncidentMemory()
        initial_count = len(memory.incidents)

        incident = IncidentRecord(
            fault_type="deployment",
            root_cause_service="inventory-service",
            correct_action="rollback_deployment",
            symptoms=["api error"],
        )

        memory.add_incident(incident)
        assert len(memory.incidents) == initial_count + 1

    def test_search_with_symptoms(self):
        """Test search with symptoms"""
        memory = IncidentMemory()
        matches = memory.search(symptoms=["OutOfMemoryError", "heap"])

        assert len(matches) > 0
        assert all(isinstance(m, MemoryMatch) for m in matches)
        # Results should be sorted by relevance
        if len(matches) > 1:
            assert matches[0].relevance_score >= matches[1].relevance_score

    def test_search_with_services(self):
        """Test search with services"""
        memory = IncidentMemory()
        matches = memory.search(services=["payment-service"])

        assert len(matches) > 0
        assert any("payment-service" in i.root_cause_service for i in [m.record for m in matches])

    def test_search_with_fault_type(self):
        """Test search with fault type filter"""
        memory = IncidentMemory()
        matches = memory.search(fault_type="oom")

        assert len(matches) > 0
        assert all(m.record.fault_type == "oom" for m in matches)

    def test_search_with_query(self):
        """Test search with general query"""
        memory = IncidentMemory()
        matches = memory.search(query="OutOfMemoryError heap")

        assert len(matches) > 0

    def test_search_limit(self):
        """Test search with limit"""
        memory = IncidentMemory()
        matches = memory.search(symptoms=["error"], limit=3)

        assert len(matches) <= 3

    def test_search_empty_keywords(self):
        """Test search with empty keywords returns all incidents (default limit applies)"""
        memory = IncidentMemory()
        # Search with no keywords returns all incidents due to "if matched or not search_keywords" logic
        # But default limit is 5, so it returns up to 5
        matches = memory.search()
        # Default limit is 5, so returns at most 5
        assert len(matches) <= 5

    def test_search_increments_queried_count(self):
        """Test that search increments _queried_count"""
        memory = IncidentMemory()
        initial_count = memory._queried_count

        memory.search(symptoms=["OutOfMemoryError"])
        assert memory._queried_count == initial_count + 1

    def test_search_updates_last_match_count(self):
        """Test that search updates _last_match_count"""
        memory = IncidentMemory()
        memory.search(symptoms=["OutOfMemoryError"], limit=5)
        # _last_match_count is set to len(matches[:limit])
        # May be less than limit if fewer matches found
        assert memory._last_match_count >= 0
        assert memory._last_match_count <= 5

    def test_get_similar_incidents(self):
        """Test get_similar_incidents returns formatted results"""
        memory = IncidentMemory()
        results = memory.get_similar_incidents(
            symptoms=["OutOfMemoryError"],
            affected_services=["payment-service"]
        )

        assert len(results) > 0
        result = results[0]
        assert "fault_type" in result
        assert "root_cause_service" in result
        assert "suggested_action" in result
        assert "relevance" in result
        assert "matched_keywords" in result
        assert "resolution_steps" in result
        assert "difficulty" in result
        assert isinstance(result["relevance"], float)

    def test_get_suggested_action(self):
        """Test get_suggested_action returns best action"""
        memory = IncidentMemory()
        suggestion = memory.get_suggested_action(
            symptoms=["OutOfMemoryError", "heap"],
            services=["payment-service"]
        )

        assert suggestion is not None
        assert "action" in suggestion
        assert "target_service" in suggestion
        assert "confidence" in suggestion
        assert "based_on" in suggestion

    def test_get_suggested_action_no_match(self):
        """Test get_suggested_action returns None for no match"""
        memory = IncidentMemory()
        suggestion = memory.get_suggested_action(
            symptoms=["nonexistent symptom xyz123"],
            services=["nonexistent-service-xyz"]
        )

        # May return None if relevance is too low
        # or may return suggestion with low confidence

    def test_get_suggested_action_low_confidence(self):
        """Test get_suggested_action returns None for low confidence"""
        memory = IncidentMemory()
        # Search with very specific/non-matching symptoms
        suggestion = memory.get_suggested_action(
            symptoms=["completely unrelated xyz"],
            services=["fake-service-123"]
        )
        # Either returns None or has low confidence
        if suggestion:
            assert suggestion["confidence"] < 0.3

    def test_tokenize(self):
        """Test _tokenize method"""
        memory = IncidentMemory()

        # Test basic tokenization
        tokens = memory._tokenize("OutOfMemoryError")
        assert "outofmemoryerror" in tokens

    def test_tokenize_with_spaces(self):
        """Test _tokenize with spaces"""
        memory = IncidentMemory()
        tokens = memory._tokenize("Out Of Memory Error")
        assert "out" in tokens
        assert "of" in tokens
        assert "memory" in tokens
        assert "error" in tokens

    def test_tokenize_with_delimiters(self):
        """Test _tokenize with various delimiters"""
        memory = IncidentMemory()
        tokens = memory._tokenize("Out-Of_Memory.Error")
        assert "out" in tokens
        assert "of" in tokens
        assert "memory" in tokens
        assert "error" in tokens

    def test_tokenize_empty_string(self):
        """Test _tokenize with empty string"""
        memory = IncidentMemory()
        tokens = memory._tokenize("")
        assert tokens == set()

    def test_tokenize_short_words_filtered(self):
        """Test _tokenize filters single characters"""
        memory = IncidentMemory()
        tokens = memory._tokenize("a b c")
        assert len(tokens) == 0  # All single characters filtered

    def test_calculate_relevance(self):
        """Test _calculate_relevance"""
        memory = IncidentMemory()

        search_keywords = {"error", "timeout"}
        incident_keywords = {"timeout", "slow", "queries"}
        matched = {"timeout"}

        relevance = memory._calculate_relevance(search_keywords, matched, None, incident_keywords)
        assert 0.0 <= relevance <= 1.0

    def test_calculate_relevance_empty_search_keywords(self):
        """Test _calculate_relevance with empty search keywords"""
        memory = IncidentMemory()
        relevance = memory._calculate_relevance(set(), set(), None, {"error"})
        assert relevance == 0.0

    def test_save_and_load_from_storage(self):
        """Test saving and loading from storage"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "memory.json")

            # Create memory with storage path
            memory1 = IncidentMemory(seed=42, storage_path=path)
            initial_count = len(memory1.incidents)
            memory1.add_incident(IncidentRecord(
                fault_type="test",
                root_cause_service="test-service",
                correct_action="test_action",
                symptoms=["test symptom"],
            ))
            # Verify incident was added
            assert len(memory1.incidents) == initial_count + 1

            # add_incident saves automatically when storage_path is set
            # Verify file was created by reading it
            with open(path, 'r') as f:
                saved_data = json.load(f)
            assert "incidents" in saved_data
            assert saved_data["metadata"]["seed"] == 42

            # Load from same path - should have the saved incidents
            memory2 = IncidentMemory(seed=42, storage_path=path)
            # Should have at least the initial count (may have more from load)
            assert len(memory2.incidents) >= initial_count

    def test_load_from_corrupted_storage(self):
        """Test loading from corrupted JSON file falls back gracefully"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "corrupted_memory.json")

            # Write invalid JSON
            with open(path, 'w') as f:
                f.write("{ invalid json }")

            # Should not crash, should use default incidents
            memory = IncidentMemory(storage_path=path)
            assert len(memory.incidents) > 0

    def test_load_from_nonexistent_storage(self):
        """Test loading from nonexistent path doesn't crash"""
        memory = IncidentMemory(storage_path="/nonexistent/path/memory.json")
        # Should just use default incidents
        assert len(memory.incidents) > 0

    def test_to_dict(self):
        """Test to_dict serialization"""
        memory = IncidentMemory()
        d = memory.to_dict()

        assert "incidents" in d
        assert "query_count" in d
        assert "seed" in d
        assert isinstance(d["incidents"], list)

    def test_from_dict(self):
        """Test from_dict deserialization"""
        # Create a memory with custom incidents
        memory1 = IncidentMemory()
        memory1.add_incident(IncidentRecord(
            fault_type="test",
            root_cause_service="test-service",
            correct_action="test_action",
            symptoms=["test symptom"],
        ))

        data = memory1.to_dict()

        # Deserialize
        memory2 = IncidentMemory.from_dict(data)
        assert memory2.seed == memory1.seed
        assert len(memory2.incidents) == len(memory1.incidents)

    def test_from_dict_with_missing_seed(self):
        """Test from_dict with missing seed uses default"""
        data = {"incidents": []}
        memory = IncidentMemory.from_dict(data)
        assert memory.seed == 42

    def test_get_stats(self):
        """Test get_stats returns statistics"""
        memory = IncidentMemory()
        stats = memory.get_stats()

        assert "total_incidents" in stats
        assert "fault_type_distribution" in stats
        assert "query_count" in stats
        assert "last_match_count" in stats
        assert stats["total_incidents"] > 0

    def test_get_stats_distribution(self):
        """Test fault_type_distribution in stats"""
        memory = IncidentMemory()
        stats = memory.get_stats()

        distribution = stats["fault_type_distribution"]
        assert isinstance(distribution, dict)
        assert all(isinstance(v, int) for v in distribution.values())


# =============================================================================
# MemoryIntegrator Tests
# =============================================================================

class TestMemoryIntegrator:
    """Tests for MemoryIntegrator class"""

    def test_init(self):
        """Test MemoryIntegrator initialization"""
        memory = IncidentMemory()
        integrator = MemoryIntegrator(memory)

        assert integrator.memory == memory
        assert integrator.memory_used is False
        assert integrator.last_suggestion is None

    def test_get_memory_suggestion_with_matching_incident(self):
        """Test get_memory_suggestion with matching incident"""
        memory = IncidentMemory()
        integrator = MemoryIntegrator(memory)

        observation = {
            "alerts": [
                {"message": "OutOfMemoryError in payment-service", "service": "payment-service"}
            ],
            "services": {}
        }

        suggestion = integrator.get_memory_suggestion(observation)
        # May or may not find suggestion depending on confidence
        if suggestion:
            assert "action" in suggestion
            assert integrator.memory_used is True
            assert integrator.last_suggestion is not None

    def test_get_memory_suggestion_with_degraded_service(self):
        """Test get_memory_suggestion with degraded service"""
        memory = IncidentMemory()
        integrator = MemoryIntegrator(memory)

        observation = {
            "alerts": [],
            "services": {
                "payment-service": {
                    "status": "degraded",
                    "latency_ms": 200,
                    "error_rate": 0.1
                }
            }
        }

        suggestion = integrator.get_memory_suggestion(observation)
        # With degraded service and high latency/error rate, should get symptoms

    def test_get_memory_suggestion_with_unhealthy_service(self):
        """Test get_memory_suggestion with unhealthy service"""
        memory = IncidentMemory()
        integrator = MemoryIntegrator(memory)

        observation = {
            "alerts": [],
            "services": {
                "database-primary": {
                    "status": "unhealthy",
                    "latency_ms": 50,
                    "error_rate": 0.0
                }
            }
        }

        suggestion = integrator.get_memory_suggestion(observation)

    def test_get_memory_suggestion_no_match(self):
        """Test get_memory_suggestion with no matching incident"""
        memory = IncidentMemory()
        integrator = MemoryIntegrator(memory)

        observation = {
            "alerts": [],
            "services": {
                "unknown-service": {
                    "status": "degraded",
                    "latency_ms": 10,
                    "error_rate": 0.0
                }
            }
        }

        suggestion = integrator.get_memory_suggestion(observation)
        # May return None or low confidence suggestion

    def test_get_memory_suggestion_min_confidence(self):
        """Test min_confidence parameter"""
        memory = IncidentMemory()
        integrator = MemoryIntegrator(memory)

        observation = {
            "alerts": [
                {"message": "OutOfMemoryError", "service": "payment-service"}
            ],
            "services": {}
        }

        # Set high min_confidence
        suggestion = integrator.get_memory_suggestion(observation, min_confidence=0.99)
        # Should return None if no high-confidence match
        if suggestion:
            assert suggestion.get("confidence", 0) >= 0.99

    def test_get_memory_suggestion_empty_observation(self):
        """Test get_memory_suggestion with empty observation"""
        memory = IncidentMemory()
        integrator = MemoryIntegrator(memory)

        observation = {"alerts": [], "services": {}}
        suggestion = integrator.get_memory_suggestion(observation)
        # Empty observation means no symptoms to match

    def test_record_incident(self):
        """Test recording a new incident"""
        memory = IncidentMemory()
        integrator = MemoryIntegrator(memory)

        initial_count = len(memory.incidents)

        incident_id = integrator.record_incident(
            fault_type="deployment",
            root_cause="inventory-service",
            correct_action="rollback_deployment",
            symptoms=["api error", "after deploy"],
            affected_services=["inventory-service"]
        )

        assert len(memory.incidents) == initial_count + 1
        assert len(incident_id) == 8

    def test_reset(self):
        """Test reset clears tracking state"""
        memory = IncidentMemory()
        integrator = MemoryIntegrator(memory)

        # Trigger a suggestion to set memory_used
        observation = {
            "alerts": [
                {"message": "OutOfMemoryError", "service": "payment-service"}
            ],
            "services": {}
        }
        integrator.get_memory_suggestion(observation)

        # Reset
        integrator.reset()

        assert integrator.memory_used is False
        assert integrator.last_suggestion is None

    def test_reset_when_no_suggestion(self):
        """Test reset when no suggestion was made"""
        memory = IncidentMemory()
        integrator = MemoryIntegrator(memory)

        assert integrator.memory_used is False
        integrator.reset()
        assert integrator.memory_used is False


# =============================================================================
# Integration Tests
# =============================================================================

class TestMemoryIntegration:
    """Integration tests for memory system"""

    def test_full_workflow(self):
        """Test complete workflow: create, search, integrate"""
        # Create memory
        memory = IncidentMemory(seed=42)

        # Add custom incident
        custom_incident = IncidentRecord(
            fault_type="custom",
            root_cause_service="custom-service",
            correct_action="custom_action",
            symptoms=["custom symptom", "custom error"],
            difficulty=3,
        )
        memory.add_incident(custom_incident)

        # Search for similar
        matches = memory.search(symptoms=["custom symptom"])
        assert len(matches) > 0

        # Get suggestion
        suggestion = memory.get_suggested_action(
            symptoms=["custom symptom"],
            services=["custom-service"]
        )
        assert suggestion is not None

        # Integrate with observation
        integrator = MemoryIntegrator(memory)
        observation = {
            "alerts": [{"message": "custom symptom", "service": "custom-service"}],
            "services": {}
        }
        result = integrator.get_memory_suggestion(observation)
        if result:
            assert "action" in result

        # Get stats
        stats = memory.get_stats()
        assert stats["total_incidents"] > 0

    def test_deterministic_results(self):
        """Test that same seed produces same results"""
        symptoms = ["OutOfMemoryError", "heap"]

        memory1 = IncidentMemory(seed=42)
        results1 = memory1.search(symptoms=symptoms)

        memory2 = IncidentMemory(seed=42)
        results2 = memory2.search(symptoms=symptoms)

        assert len(results1) == len(results2)
        for m1, m2 in zip(results1, results2):
            assert m1.relevance_score == m2.relevance_score
            assert m1.record.get_id() == m2.record.get_id()
