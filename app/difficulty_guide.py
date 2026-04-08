"""
IncidentOps Difficulty Progression Guide
=======================================

This document describes how task difficulty is calibrated and what agents
need to handle at each level for the OpenEnv hackathon.

Difficulty 1 (Trivial):
- Single service affected
- Obvious symptoms (OOM error in logs)
- Direct fix (restart_service)
- Rule-based: 100% success
- Example: payment-service OOM crash

Difficulty 2 (Easy):
- One service + 1-2 downstream
- Clear error signals
- Simple fix (restart_service)
- Rule-based: ~0.86 success
- Example: The OOM Crash (payment-service)

Difficulty 3 (Medium):
- Core service + cascade
- Confusing cascade signals (symptom services look like root cause)
- Requires dependency graph reasoning
- Rule-based: ~0.68 success
- Example: The Cascade (database-primary connection pool exhaustion)

Difficulty 4 (Hard):
- Silent degradation or misleading signals
- Multiple false leads
- Requires metric correlation
- Rule-based: ~0.43 success
- Example: The Memory Spiral (analytics-service slow leak)

Difficulty 5 (Expert):
- Ghost patterns (no error signals, only business metrics)
- Requires deployment timeline correlation
- Requires multi-step reasoning chain
- Rule-based: ~0.0 success
- LLM agents: 0.82+ success
- Example: The Ghost (recommendation-service silent corruption)
"""

DIFFICULTY_GUIDE = {
    1: {
        "name": "Trivial",
        "rule_based_success": "100%",
        "llm_success": "100%",
        "key_skill": "Basic service health check",
        "typical_symptoms": "Explicit OOM errors, immediate service crash",
        "correct_action": "restart_service",
    },
    2: {
        "name": "Easy",
        "rule_based_success": "~86%",
        "llm_success": "~95%",
        "key_skill": "Log reading and service restart",
        "typical_symptoms": "Unhealthy service with clear error logs",
        "correct_action": "restart_service",
    },
    3: {
        "name": "Medium",
        "rule_based_success": "~68%",
        "llm_success": "~90%",
        "key_skill": "Dependency graph reasoning",
        "typical_symptoms": "Cascading 503s, misleading error patterns",
        "correct_action": "scale_service (on root cause, not symptoms)",
    },
    4: {
        "name": "Hard",
        "rule_based_success": "~43%",
        "llm_success": "~85%",
        "key_skill": "Metric trend analysis over time",
        "typical_symptoms": "Slow degradation, memory leaks, gradual latency increase",
        "correct_action": "restart_service (after identifying leak source)",
    },
    5: {
        "name": "Expert",
        "rule_based_success": "~0%",
        "llm_success": "~82%",
        "key_skill": "Multi-hop reasoning: metrics + deployments + business data",
        "typical_symptoms": "No error logs, no unhealthy services — only CTR/revenue drift",
        "correct_action": "rollback_deployment (on silently corrupted service)",
    },
}
