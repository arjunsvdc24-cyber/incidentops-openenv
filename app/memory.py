"""
IncidentOps - Deterministic Incident Memory System v10.0

Features:
- Store past incidents (JSON format)
- Store symptoms, root cause, fix
- Retrieve similar incidents via keyword matching
- Deterministic operations (seed-based)
- Reproducible results

Integration:
- Agent checks memory before action
- Uses past fixes as guidance
- +0.1 reward for correct memory usage

Constraints:
- All operations deterministic
- Same seed → identical results
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import hashlib
from pathlib import Path


@dataclass
class IncidentRecord:
    """
    Record of a past incident for memory retrieval.
    
    All fields are deterministic - no timestamps or random IDs.
    """
    fault_type: str           # "oom", "cascade", "ghost", "deployment", "network"
    root_cause_service: str   # Service that was the root cause
    correct_action: str       # Action that fixed the incident
    symptoms: list[str]       # List of symptoms observed
    affected_services: list[str] = field(default_factory=list)
    resolution_steps: list[str] = field(default_factory=list)
    difficulty: int = 3       # 1-5 scale
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'IncidentRecord':
        """Create from dictionary"""
        return cls(**data)
    
    def get_id(self) -> str:
        """Generate deterministic ID based on content hash"""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()[:8]


@dataclass
class MemoryMatch:
    """A match from memory search"""
    record: IncidentRecord
    relevance_score: float
    matched_keywords: list[str]
    match_details: dict = field(default_factory=dict)


class IncidentMemory:
    """
    Deterministic incident memory system.
    
    Features:
    - Stores past incidents with fault patterns
    - Keyword-based similarity search (no embeddings)
    - Fully deterministic (no external dependencies)
    - JSON-based persistence
    - Pre-seeded with common incident patterns
    
    Usage:
        memory = IncidentMemory(seed=42)
        
        # Search for similar incidents
        matches = memory.search(
            symptoms=["OutOfMemoryError", "heap"],
            services=["java-service"]
        )
        
        # Add new incident
        memory.add_incident(IncidentRecord(
            fault_type="oom",
            root_cause_service="java-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError", "heap", "memory pressure"],
        ))
    """
    
    # Pre-seeded default incidents (deterministic)
    DEFAULT_INCIDENTS = [
        IncidentRecord(
            fault_type="oom",
            root_cause_service="payment-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError", "heap", "memory pressure", "slow gc", "java"],
            affected_services=["payment-service", "order-service"],
            resolution_steps=["Check heap usage", "Restart service", "Scale if needed"],
            difficulty=2,
        ),
        IncidentRecord(
            fault_type="oom",
            root_cause_service="user-service",
            correct_action="restart_service",
            symptoms=["OutOfMemoryError", "heap space", "gc overhead"],
            affected_services=["user-service", "api-gateway"],
            resolution_steps=["Query memory metrics", "Restart service"],
            difficulty=2,
        ),
        IncidentRecord(
            fault_type="cascade",
            root_cause_service="database-primary",
            correct_action="restart_service",
            symptoms=["connection timeout", "slow queries", "replication lag", "multiple errors"],
            affected_services=["database-primary", "user-service", "order-service", "payment-service"],
            resolution_steps=["Check database health", "Check connections", "Failover or restart"],
            difficulty=3,
        ),
        IncidentRecord(
            fault_type="cascade",
            root_cause_service="cache-service",
            correct_action="restart_service",
            symptoms=["cache miss", "high latency", "slow response", "connection refused"],
            affected_services=["cache-service", "user-service", "search-service"],
            resolution_steps=["Check cache health", "Clear or restart cache"],
            difficulty=3,
        ),
        IncidentRecord(
            fault_type="ghost",
            root_cause_service="recommendation-service",
            correct_action="rollback_deployment",
            symptoms=["ctr drop", "gradual degradation", "no errors", "silent failure", "metric decline"],
            affected_services=["recommendation-service", "analytics-service"],
            resolution_steps=["Check business metrics", "Check deployment timeline", "Rollback recent deployment"],
            difficulty=5,
        ),
        IncidentRecord(
            fault_type="ghost",
            root_cause_service="search-service",
            correct_action="rollback_deployment",
            symptoms=["search quality drop", "no errors", "user complaints", "relevance down"],
            affected_services=["search-service"],
            resolution_steps=["Check search metrics", "Compare versions", "Rollback"],
            difficulty=5,
        ),
        IncidentRecord(
            fault_type="deployment",
            root_cause_service="order-service",
            correct_action="rollback_deployment",
            symptoms=["new errors", "version mismatch", "api change", "after deploy"],
            affected_services=["order-service", "payment-service"],
            resolution_steps=["Check recent deployments", "Compare versions", "Rollback"],
            difficulty=3,
        ),
        IncidentRecord(
            fault_type="deployment",
            root_cause_service="auth-service",
            correct_action="rollback_deployment",
            symptoms=["authentication failure", "token invalid", "new errors", "version"],
            affected_services=["auth-service", "api-gateway"],
            resolution_steps=["Check auth logs", "Check deployment history", "Rollback"],
            difficulty=3,
        ),
        IncidentRecord(
            fault_type="network",
            root_cause_service="api-gateway",
            correct_action="scale_service",
            symptoms=["timeout", "connection refused", "high latency", "network error"],
            affected_services=["api-gateway"],
            resolution_steps=["Check network", "Check load", "Scale service"],
            difficulty=2,
        ),
        IncidentRecord(
            fault_type="network",
            root_cause_service="cache-service",
            correct_action="restart_service",
            symptoms=["connection timeout", "redis error", "cache unavailable"],
            affected_services=["cache-service", "user-service"],
            resolution_steps=["Check cache connectivity", "Restart cache"],
            difficulty=2,
        ),
    ]
    
    def __init__(self, seed: int = 42, storage_path: Optional[str] = None):
        """
        Initialize memory.
        
        Args:
            seed: Seed for deterministic operations
            storage_path: Optional path for JSON persistence
        """
        self.seed = seed
        self.storage_path = storage_path
        self.incidents: list[IncidentRecord] = list(self.DEFAULT_INCIDENTS)
        self._queried_count = 0
        self._last_match_count = 0
        
        # Load from storage if path provided
        if storage_path:  # pragma: no cover
            self._load_from_storage()  # pragma: no cover
    
    def add_incident(self, incident: IncidentRecord) -> str:
        """
        Add a new incident to memory.
        
        Args:
            incident: IncidentRecord to add
            
        Returns:
            Incident ID
        """
        incident_id = incident.get_id()
        
        # Check for duplicates
        for existing in self.incidents:
            if existing.get_id() == incident_id:
                return incident_id  # Already exists
        
        self.incidents.append(incident)
        
        # Persist if storage path set
        if self.storage_path:  # pragma: no cover
            self._save_to_storage()  # pragma: no cover
        
        return incident_id
    
    def search(
        self,
        query: Optional[str] = None,
        symptoms: Optional[list[str]] = None,
        services: Optional[list[str]] = None,
        fault_type: Optional[str] = None,
        limit: int = 5
    ) -> list[MemoryMatch]:
        """
        Search for similar incidents using keyword matching.
        
        Deterministic - same inputs always return same results.
        
        Args:
            query: General search query
            symptoms: List of symptom keywords
            services: List of affected services
            fault_type: Filter by fault type
            limit: Maximum number of results
            
        Returns:
            List of MemoryMatch objects sorted by relevance
        """
        matches: list[MemoryMatch] = []
        self._queried_count += 1
        
        # Build search keywords from all inputs
        search_keywords: set[str] = set()
        
        if query:
            search_keywords.update(self._tokenize(query))
        
        if symptoms:
            for s in symptoms:
                search_keywords.update(self._tokenize(s))
        
        if services:
            for s in services:
                search_keywords.add(s.lower())
        
        if fault_type:
            search_keywords.add(fault_type.lower())
        
        # Search each incident
        for incident in self.incidents:
            # Filter by fault type if specified
            if fault_type and incident.fault_type != fault_type.lower():
                continue
            
            # Build incident keywords
            incident_keywords: set[str] = set()
            incident_keywords.add(incident.fault_type.lower())
            incident_keywords.add(incident.root_cause_service.lower())
            # Tokenize each symptom and add tokens individually
            for s in incident.symptoms:
                incident_keywords.update(self._tokenize(s))
            incident_keywords.update(s.lower() for s in incident.affected_services)
            
            # Flatten any nested sets from tokenization
            flat_incident_keywords: set[str] = set()
            for kw in incident_keywords:
                if isinstance(kw, set):
                    flat_incident_keywords.update(kw)
                else:
                    flat_incident_keywords.add(kw)
            
            # Find matching keywords
            matched = search_keywords & flat_incident_keywords
            
            if matched or not search_keywords:
                # Calculate relevance score (deterministic)
                relevance = self._calculate_relevance(
                    search_keywords, matched, incident, flat_incident_keywords
                )
                
                matches.append(MemoryMatch(
                    record=incident,
                    relevance_score=relevance,
                    matched_keywords=list(sorted(matched)),  # Sorted for determinism
                    match_details={
                        "search_keywords": len(search_keywords),
                        "incident_keywords": len(flat_incident_keywords),
                        "matched_count": len(matched),
                    }
                ))
        
        # Sort by relevance (deterministic - no randomness)
        # Secondary sort by incident ID for stability
        matches.sort(key=lambda m: (-m.relevance_score, m.record.get_id()))
        
        self._last_match_count = len(matches[:limit])
        return matches[:limit]
    
    def get_similar_incidents(
        self,
        symptoms: list[str],
        affected_services: list[str]
    ) -> list[dict]:
        """
        Get similar incidents formatted for API response.
        
        Returns list of dicts with:
        - fault_type
        - root_cause_service
        - suggested_action
        - relevance
        - resolution_steps
        """
        matches = self.search(
            symptoms=symptoms,
            services=affected_services
        )
        
        return [
            {
                "fault_type": m.record.fault_type,
                "root_cause_service": m.record.root_cause_service,
                "suggested_action": m.record.correct_action,
                "relevance": round(m.relevance_score, 2),
                "matched_keywords": m.matched_keywords[:5],
                "resolution_steps": m.record.resolution_steps,
                "difficulty": m.record.difficulty,
            }
            for m in matches
        ]
    
    def get_suggested_action(
        self,
        symptoms: list[str],
        services: list[str]
    ) -> Optional[dict]:
        """
        Get the best suggested action based on memory.
        
        Returns None if no confident match found.
        """
        matches = self.search(symptoms=symptoms, services=services, limit=1)
        
        if not matches:
            return None
        
        best = matches[0]
        
        if best.relevance_score < 0.3:
            return None  # Low confidence
        
        return {
            "action": best.record.correct_action,
            "target_service": best.record.root_cause_service,
            "confidence": best.relevance_score,
            "based_on": best.record.get_id(),
        }
    
    def _tokenize(self, text: str) -> set[str]:
        """
        Tokenize text into keywords.
        
        Deterministic - same input always produces same output.
        """
        if not text:
            return set()
        
        # Simple tokenization (deterministic)
        tokens = set()
        
        # Lowercase
        text = text.lower()
        
        # Split on common delimiters
        for delimiter in [' ', '-', '_', ':', '.', ',', '/', '\\']:
            text = text.replace(delimiter, ' ')
        
        # Extract words
        for word in text.split():
            if len(word) >= 2:  # Skip single characters
                tokens.add(word)
        
        return tokens
    
    def _calculate_relevance(
        self,
        search_keywords: set[str],
        matched: set[str],
        incident: IncidentRecord,
        incident_keywords: set[str]
    ) -> float:
        """
        Calculate deterministic relevance score.
        
        Score is based on:
        - Jaccard similarity
        - Fault type match
        - Service match
        """
        if not search_keywords:
            return 0.0
        
        # Jaccard similarity
        jaccard = len(matched) / len(search_keywords | incident_keywords) if (search_keywords | incident_keywords) else 0.0
        
        # Precision (matched / searched)
        precision = len(matched) / len(search_keywords) if search_keywords else 0.0
        
        # Combined score (weighted average)
        score = 0.5 * jaccard + 0.5 * precision
        
        return min(1.0, score)
    
    def _load_from_storage(self) -> None:  # pragma: no cover
        """Load incidents from JSON storage"""
        if not self.storage_path:  # pragma: no cover
            return  # pragma: no cover

        path = Path(self.storage_path)  # pragma: no cover
        if not path.exists():  # pragma: no cover
            return  # pragma: no cover

        try:  # pragma: no cover
            with open(path, 'r') as f:  # pragma: no cover
                data = json.load(f)  # pragma: no cover

            for item in data.get("incidents", []):  # pragma: no cover
                record = IncidentRecord.from_dict(item)  # pragma: no cover
                # Add only if not duplicate
                self.add_incident(record)  # pragma: no cover
        except (json.JSONDecodeError, KeyError):  # pragma: no cover
            pass  # Keep default incidents  # pragma: no cover
    
    def _save_to_storage(self) -> None:  # pragma: no cover
        """Save incidents to JSON storage"""
        if not self.storage_path:  # pragma: no cover
            return  # pragma: no cover

        path = Path(self.storage_path)  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)  # pragma: no cover

        data = {  # pragma: no cover
            "incidents": [i.to_dict() for i in self.incidents],  # pragma: no cover
            "metadata": {  # pragma: no cover
                "count": len(self.incidents),  # pragma: no cover
                "seed": self.seed,  # pragma: no cover
            }  # pragma: no cover
        }  # pragma: no cover

        with open(path, 'w') as f:  # pragma: no cover
            json.dump(data, f, indent=2)  # pragma: no cover
    
    def to_dict(self) -> dict:
        """Serialize memory to dictionary"""
        return {
            "incidents": [i.to_dict() for i in self.incidents],
            "query_count": self._queried_count,
            "seed": self.seed,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'IncidentMemory':
        """Deserialize memory from dictionary"""
        memory = cls(seed=data.get("seed", 42))
        memory.incidents = []
        
        for i in data.get("incidents", []):
            memory.incidents.append(IncidentRecord.from_dict(i))
        
        return memory
    
    def get_stats(self) -> dict:
        """Get memory statistics"""
        fault_types = {}
        for i in self.incidents:
            fault_types[i.fault_type] = fault_types.get(i.fault_type, 0) + 1
        
        return {
            "total_incidents": len(self.incidents),
            "fault_type_distribution": fault_types,
            "query_count": self._queried_count,
            "last_match_count": self._last_match_count,
        }


class MemoryIntegrator:
    """
    Integrates memory into agent decision loop.
    
    Usage:
        integrator = MemoryIntegrator(memory)
        
        # Before taking action, check memory
        suggestion = integrator.get_memory_suggestion(observation)
        if suggestion:
            # Use suggested action
            action = suggestion["action"]
        else:
            # Explore normally
            action = explore()
    """
    
    def __init__(self, memory: IncidentMemory):
        self.memory = memory
        self.memory_used = False
        self.last_suggestion: Optional[dict] = None
    
    def get_memory_suggestion(
        self,
        observation: dict,
        min_confidence: float = 0.5
    ) -> Optional[dict]:
        """
        Get action suggestion from memory based on observation.
        
        Args:
            observation: Current environment observation
            min_confidence: Minimum confidence threshold
            
        Returns:
            Suggestion dict or None
        """
        self.memory_used = False
        self.last_suggestion = None
        
        # Extract symptoms from observation
        symptoms = []
        services = []
        
        # Get alerts as symptoms
        alerts = observation.get("alerts", [])
        for alert in alerts:
            message = alert.get("message", "")
            symptoms.append(message)
            services.append(alert.get("service", ""))
        
        # Get service states as symptoms
        service_states = observation.get("services", {})
        for svc, state in service_states.items():
            status = state.get("status", "")
            if status in ("degraded", "unhealthy"):
                symptoms.append(f"{status}")
                services.append(svc)
                
                # Add latency as symptom if high
                latency = state.get("latency_ms", 0)
                if latency > 100:
                    symptoms.append("high latency")
                
                # Add error rate as symptom if high
                error_rate = state.get("error_rate", 0)
                if error_rate > 0.05:
                    symptoms.append("high error rate")
        
        # Search memory
        suggestion = self.memory.get_suggested_action(
            symptoms=symptoms,
            services=list(set(services))
        )
        
        if suggestion and suggestion.get("confidence", 0) >= min_confidence:
            self.memory_used = True
            self.last_suggestion = suggestion
            return suggestion
        
        return None
    
    def record_incident(
        self,
        fault_type: str,
        root_cause: str,
        correct_action: str,
        symptoms: list[str],
        affected_services: list[str]
    ) -> str:
        """
        Record a new incident to memory.
        
        Call this after successfully resolving an incident.
        """
        record = IncidentRecord(
            fault_type=fault_type,
            root_cause_service=root_cause,
            correct_action=correct_action,
            symptoms=symptoms,
            affected_services=affected_services,
        )
        
        return self.memory.add_incident(record)
    
    def reset(self) -> None:
        """Reset tracking state"""
        self.memory_used = False
        self.last_suggestion = None
