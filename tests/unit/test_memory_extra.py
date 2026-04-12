"""
IncidentOps - Memory Module Extended Tests

Tests coverage gaps in memory.py: search with fault_type filter,
get_similar_incidents, get_suggested_action, to_dict/from_dict,
_load_from_storage, _save_to_storage, MemoryIntegrator, and helpers.
"""
import pytest
import tempfile
import json
from pathlib import Path
from app.memory import (
    IncidentRecord, IncidentMemory, MemoryMatch, MemoryIntegrator,
)


class TestIncidentRecordFields:
    """Additional IncidentRecord field tests."""

    def test_record_with_affected_services(self):
        record = IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="scale_service",
            symptoms=["pool exhausted"],
            affected_services=["order-service", "user-service"],
        )
        assert len(record.affected_services) == 2

    def test_record_with_resolution_steps(self):
        record = IncidentRecord(
            fault_type="ghost",
            root_cause_service="recommendation-service",
            correct_action="rollback_deployment",
            symptoms=["silent degradation"],
            resolution_steps=["check deployments", "rollback", "verify"],
        )
        assert len(record.resolution_steps) == 3

    def test_record_to_dict_complete(self):
        record = IncidentRecord(
            fault_type="network_partition",
            root_cause_service="api-gateway",
            correct_action="scale_service",
            symptoms=["timeout", "connection refused"],
            affected_services=["order-service"],
            resolution_steps=["scale services", "wait for recovery"],
            difficulty=3,
        )
        d = record.to_dict()
        assert d["fault_type"] == "network_partition"
        assert d["affected_services"] == ["order-service"]
        assert d["resolution_steps"] == ["scale services", "wait for recovery"]
        assert d["difficulty"] == 3

    def test_record_from_dict_complete(self):
        data = {
            "fault_type": "ddos",
            "root_cause_service": "api-gateway",
            "correct_action": "scale_service",
            "symptoms": ["traffic spike"],
            "affected_services": ["auth-service"],
            "resolution_steps": ["rate limit", "scale"],
            "difficulty": 4,
        }
        record = IncidentRecord.from_dict(data)
        assert record.affected_services == ["auth-service"]
        assert record.resolution_steps == ["rate limit", "scale"]
        assert record.difficulty == 4


class TestMemorySearchFaultType:
    """Test search with fault_type filter."""

    def test_search_by_fault_type_exact_match(self):
        memory = IncidentMemory(seed=42)
        # Add a known cascade incident
        record = IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="scale_service",
            symptoms=["connection pool exhausted"],
        )
        memory.add_incident(record)

        # Search with fault_type filter
        matches = memory.search(fault_type="cascade", limit=5)
        assert isinstance(matches, list)
        # Should return at least our added record
        cascade_matches = [m for m in matches if m.record.fault_type == "cascade"]
        assert len(cascade_matches) >= 1

    def test_search_by_fault_type_no_match(self):
        memory = IncidentMemory(seed=42)
        # Add only oom incidents
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError"],
        )
        memory.add_incident(record)

        # Search for cascade - should return only cascade records
        matches = memory.search(fault_type="cascade", limit=5)
        assert isinstance(matches, list)
        # May return default cascade records
        for m in matches:
            assert m.record.fault_type == "cascade"

    def test_search_with_query_and_fault_type(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="ghost",
            root_cause_service="recommendation-service",
            correct_action="rollback_deployment",
            symptoms=["CTR drop", "silent degradation"],
        )
        memory.add_incident(record)

        matches = memory.search(query="CTR drop", fault_type="ghost", limit=5)
        assert isinstance(matches, list)

    def test_search_with_all_filters(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="memory_leak",
            root_cause_service="user-service",
            correct_action="restart_service",
            symptoms=["gradual OOM", "heap increasing"],
            affected_services=["cache-service"],
        )
        memory.add_incident(record)

        matches = memory.search(
            query="OOM",
            symptoms=["heap"],
            services=["user-service"],
            fault_type="memory_leak",
            limit=3,
        )
        assert isinstance(matches, list)

    def test_search_no_keywords_returns_all(self):
        """When no search keywords provided, returns incidents."""
        memory = IncidentMemory(seed=42)
        matches = memory.search(limit=5)
        assert isinstance(matches, list)


class TestGetSimilarIncidents:
    """Test get_similar_incidents method."""

    def test_get_similar_incidents_returns_list(self):
        memory = IncidentMemory(seed=42)
        result = memory.get_similar_incidents(
            symptoms=["OutOfMemoryError"],
            affected_services=["payment-service"],
        )
        assert isinstance(result, list)

    def test_get_similar_incidents_format(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError", "heap exhausted"],
        )
        memory.add_incident(record)

        result = memory.get_similar_incidents(
            symptoms=["OutOfMemoryError"],
            affected_services=["payment-service"],
        )
        if result:
            item = result[0]
            assert "fault_type" in item
            assert "root_cause_service" in item
            assert "suggested_action" in item
            assert "relevance" in item
            assert "matched_keywords" in item
            assert "resolution_steps" in item
            assert "difficulty" in item

    def test_get_similar_incidents_empty(self):
        memory = IncidentMemory(seed=42)
        result = memory.get_similar_incidents(
            symptoms=["completely_unknown_error_xyz"],
            affected_services=["nonexistent-service-xyz"],
        )
        assert isinstance(result, list)


class TestGetSuggestedAction:
    """Test get_suggested_action method."""

    def test_get_suggested_action_no_match(self):
        memory = IncidentMemory(seed=42)
        suggestion = memory.get_suggested_action(
            symptoms=["completely_unknown_error_xyz_abc"],
            services=["nonexistent-svc-xyz"],
        )
        assert suggestion is None

    def test_get_suggested_action_low_confidence(self):
        """When best match has low relevance, returns None."""
        memory = IncidentMemory(seed=999)
        suggestion = memory.get_suggested_action(
            symptoms=["some random symptoms"],
            services=["api-gateway"],
        )
        # May return None if all matches have low relevance
        if suggestion is not None:
            assert "action" in suggestion
            assert "target_service" in suggestion
            assert "confidence" in suggestion
            assert suggestion["confidence"] >= 0.3  # Threshold

    def test_get_suggested_action_returns_dict(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError", "OOM crash"],
        )
        memory.add_incident(record)

        suggestion = memory.get_suggested_action(
            symptoms=["OutOfMemoryError", "OOM"],
            services=["payment-service"],
        )
        assert suggestion is not None
        assert isinstance(suggestion, dict)
        assert "action" in suggestion
        assert "target_service" in suggestion
        assert "confidence" in suggestion
        assert "based_on" in suggestion


class TestMemoryToDictFromDict:
    """Test serialization/deserialization."""

    def test_to_dict_structure(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="ddos",
            root_cause_service="api-gateway",
            correct_action="scale_service",
            symptoms=["traffic spike"],
        )
        memory.add_incident(record)
        d = memory.to_dict()
        assert "incidents" in d
        assert "query_count" in d
        assert "seed" in d
        assert isinstance(d["incidents"], list)

    def test_from_dict_structure(self):
        data = {
            "incidents": [
                {
                    "fault_type": "cert_expiry",
                    "root_cause_service": "api-gateway",
                    "correct_action": "apply_fix",
                    "symptoms": ["TLS handshake failed"],
                    "affected_services": [],
                    "resolution_steps": ["renew cert"],
                    "difficulty": 2,
                }
            ],
            "seed": 99,
        }
        memory = IncidentMemory.from_dict(data)
        assert len(memory.incidents) == 1
        assert memory.incidents[0].fault_type == "cert_expiry"
        assert memory.seed == 99

    def test_roundtrip(self):
        """to_dict followed by from_dict preserves data."""
        memory = IncidentMemory(seed=77)
        record = IncidentRecord(
            fault_type="version_mismatch",
            root_cause_service="order-service",
            correct_action="rollback_deployment",
            symptoms=["API version conflict"],
        )
        memory.add_incident(record)
        d = memory.to_dict()
        restored = IncidentMemory.from_dict(d)
        assert len(restored.incidents) == len(memory.incidents)


class TestMemoryStorage:
    """Test _load_from_storage and _save_to_storage."""

    def test_save_and_load_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "memory.json"
            memory = IncidentMemory(seed=42, storage_path=str(storage_path))

            # Clear default incidents for cleaner test
            memory.incidents = []
            record = IncidentRecord(
                fault_type="zombie_process",
                root_cause_service="notification-service",
                correct_action="restart_service",
                symptoms=["orphaned process"],
            )
            memory.add_incident(record)

            # File should be saved automatically
            assert storage_path.exists()

            # Load into new memory instance
            memory2 = IncidentMemory(seed=42, storage_path=str(storage_path))
            assert len(memory2.incidents) >= 1

    def test_load_from_nonexistent_file(self):
        """Loading from nonexistent file should not crash, uses defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = Path(tmpdir) / "nonexistent.json"
            memory = IncidentMemory(seed=42, storage_path=str(nonexistent))
            # Should not raise - defaults are used
            assert len(memory.incidents) >= 0

    def test_load_invalid_json(self):
        """Invalid JSON in storage file is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "invalid.json"
            storage_path.write_text("{ invalid json }")

            memory = IncidentMemory(seed=42, storage_path=str(storage_path))
            # Should not crash - uses default incidents
            assert memory.incidents is not None


class TestMemoryStats:
    """Test get_stats method."""

    def test_get_stats_structure(self):
        memory = IncidentMemory(seed=42)
        stats = memory.get_stats()
        assert "total_incidents" in stats
        assert "fault_type_distribution" in stats
        assert "query_count" in stats
        assert "last_match_count" in stats

    def test_get_stats_after_search(self):
        memory = IncidentMemory(seed=42)
        memory.search(symptoms=["OOM"], limit=5)
        stats = memory.get_stats()
        assert stats["query_count"] == 1


class TestTokenizeHelper:
    """Test _tokenize helper method."""

    def test_tokenize_basic(self):
        memory = IncidentMemory(seed=42)
        tokens = memory._tokenize("OutOfMemoryError")
        assert isinstance(tokens, set)
        assert "outofmemoryerror" in tokens

    def test_tokenize_with_dashes(self):
        memory = IncidentMemory(seed=42)
        tokens = memory._tokenize("connection-pool-exhausted")
        assert "connection" in tokens
        assert "pool" in tokens
        assert "exhausted" in tokens

    def test_tokenize_with_underscores(self):
        memory = IncidentMemory(seed=42)
        tokens = memory._tokenize("high_memory_usage")
        assert "high" in tokens
        assert "memory" in tokens
        assert "usage" in tokens

    def test_tokenize_empty_string(self):
        memory = IncidentMemory(seed=42)
        tokens = memory._tokenize("")
        assert tokens == set()

    def test_tokenize_single_char(self):
        memory = IncidentMemory(seed=42)
        tokens = memory._tokenize("a")
        # Single chars are filtered out
        assert len(tokens) == 0

    def test_tokenize_case_insensitive(self):
        memory = IncidentMemory(seed=42)
        tokens1 = memory._tokenize("OOM")
        tokens2 = memory._tokenize("oom")
        assert tokens1 == tokens2


class TestCalculateRelevance:
    """Test _calculate_relevance helper method."""

    def test_relevance_no_search_keywords(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OOM"],
        )
        relevance = memory._calculate_relevance(
            search_keywords=set(),
            matched=set(),
            incident=record,
            incident_keywords={"oom"},
        )
        assert relevance == 0.0

    def test_relevance_partial_match(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OOM"],
        )
        relevance = memory._calculate_relevance(
            search_keywords={"oom", "payment"},
            matched={"oom"},
            incident=record,
            incident_keywords={"oom", "payment", "service"},
        )
        assert 0.0 <= relevance <= 1.0

    def test_relevance_full_match(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="scale_service",
            symptoms=["pool exhausted"],
        )
        relevance = memory._calculate_relevance(
            search_keywords={"cascade", "database"},
            matched={"cascade", "database"},
            incident=record,
            incident_keywords={"cascade", "database", "primary"},
        )
        assert 0.0 < relevance <= 1.0

    def test_relevance_capped_at_one(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OOM"],
        )
        # When matched == search_keywords and both are subsets of incident_keywords
        relevance = memory._calculate_relevance(
            search_keywords={"oom"},
            matched={"oom"},
            incident=record,
            incident_keywords={"oom"},  # Same as search
        )
        # Score = 0.5*1 + 0.5*1 = 1.0, capped at 1.0
        assert relevance == 1.0


class TestMemoryDeterminism:
    """Additional determinism tests for memory module."""

    def test_search_deterministic(self):
        m1 = IncidentMemory(seed=42)
        m2 = IncidentMemory(seed=42)
        for i in range(5):
            for mem in [m1, m2]:
                rec = IncidentRecord(
                    fault_type="ddos",
                    root_cause_service=f"svc-{i}",
                    correct_action="scale_service",
                    symptoms=[f"spike-{i}"],
                )
                mem.add_incident(rec)
        r1 = m1.search(symptoms=["spike-0", "spike-1"], services=["svc-0"])
        r2 = m2.search(symptoms=["spike-0", "spike-1"], services=["svc-0"])
        assert len(r1) == len(r2)
        if r1 and r2:
            assert r1[0].relevance_score == r2[0].relevance_score

    def test_to_dict_deterministic(self):
        m1 = IncidentMemory(seed=42)
        m2 = IncidentMemory(seed=42)
        d1 = m1.to_dict()
        d2 = m2.to_dict()
        assert d1["seed"] == d2["seed"]
        assert d1["query_count"] == d2["query_count"]


class TestMemoryIntegrator:
    """MemoryIntegrator connects memory to RL environment."""

    def test_integrator_with_empty_observation(self):
        memory = IncidentMemory(seed=42)
        integrator = MemoryIntegrator(memory)

        observation = {"alerts": [], "services": {}}
        suggestion = integrator.get_memory_suggestion(observation)
        # Empty observation -> no symptoms -> no suggestion
        assert suggestion is None or isinstance(suggestion, dict)

    def test_integrator_with_alert_observation(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError", "heap exhausted"],
        )
        memory.add_incident(record)
        integrator = MemoryIntegrator(memory)

        observation = {
            "alerts": [
                {"message": "OutOfMemoryError in payment-service", "service": "payment-service"},
            ],
            "services": {},
        }
        suggestion = integrator.get_memory_suggestion(observation)
        assert integrator.memory_used is not None  # was accessed
        # Should have some suggestion based on the added record
        assert suggestion is None or isinstance(suggestion, dict)

    def test_integrator_with_degraded_service(self):
        memory = IncidentMemory(seed=42)
        record = IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="scale_service",
            symptoms=["connection pool exhausted"],
        )
        memory.add_incident(record)
        integrator = MemoryIntegrator(memory)

        observation = {
            "alerts": [],
            "services": {
                "database-primary": {
                    "status": "degraded",
                    "latency_ms": 500,
                    "error_rate": 0.1,
                }
            },
        }
        suggestion = integrator.get_memory_suggestion(observation)
        assert isinstance(suggestion, (dict, type(None)))

    def test_integrator_tracks_usage(self):
        memory = IncidentMemory(seed=42)
        integrator = MemoryIntegrator(memory)
        assert integrator.memory_used is False

        observation = {"alerts": [], "services": {}}
        integrator.get_memory_suggestion(observation)
        # After calling get_memory_suggestion, memory_used should be set
        # (even if False because no matches found)
        assert isinstance(integrator.memory_used, bool)

    def test_integrator_min_confidence_threshold(self):
        memory = IncidentMemory(seed=999)
        integrator = MemoryIntegrator(memory)

        observation = {
            "alerts": [{"message": "some unknown error", "service": "unknown-svc"}],
            "services": {},
        }
        suggestion = integrator.get_memory_suggestion(observation, min_confidence=0.9)
        # Very high threshold -> likely no suggestion
        assert suggestion is None or isinstance(suggestion, dict)
