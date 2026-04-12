"""
IncidentOps - Multi-Agent Routes

Endpoints:
- POST /agents/episode - Run multi-agent coordinated episode
- GET  /agents/stats    - Get multi-agent system statistics
"""
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException

from app.main import make_env

router = APIRouter(prefix="/agents", tags=["agents"])


class MultiAgentRequest(BaseModel):
    seed: int = 42
    max_steps: int = 20
    enable_analyst: bool = True
    confidence_threshold: float = 0.7


@router.post("/episode")
async def run_multi_agent_episode(request: MultiAgentRequest):
    """
    Run a multi-agent coordinated episode.

    The multi-agent system includes:
    - Investigator: Gathers evidence by querying services
    - Fixer: Applies remediations (activates when suspicion > threshold)
    - Analyst: Provides pattern-based hints (optional)
    """
    from app.agents.coordinator import AgentCoordinator

    env = make_env(seed=request.seed)
    coordinator = AgentCoordinator(
        enable_analyst=request.enable_analyst,
        confidence_threshold=request.confidence_threshold,
        max_steps=request.max_steps,
    )

    result = coordinator.run_episode(env, seed=request.seed)

    return {
        "episode_id": result.episode_id,
        "total_reward": result.total_reward,
        "final_score": result.final_score,
        "grade": result.grade,
        "steps": result.steps,
        "duration_ms": result.duration_ms,
        "agent_decisions": {
            role: [
                {
                    "action": d.action_type,
                    "service": d.target_service,
                    "confidence": d.confidence,
                    "reasoning": d.reasoning,
                }
                for d in decisions
            ]
            for role, decisions in result.agent_decisions.items()
        },
        "investigation_summary": result.investigation_summary,
        "fix_summary": result.fix_summary,
        "analysis_summary": result.analysis_summary,
    }


@router.get("/stats")
async def get_agent_stats():
    """Get multi-agent system statistics and configuration"""
    from app.agents.coordinator import AgentCoordinator

    coordinator = AgentCoordinator()
    return coordinator.get_coordinator_stats()