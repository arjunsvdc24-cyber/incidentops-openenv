"""
IncidentOps - Episode and Leaderboard Routes

Endpoints:
- GET  /episodes      - List recorded episodes
- GET  /episodes/:id  - Get episode detail
- GET  /episodes/:id/replay - Get full episode replay
- POST /episodes      - Save episode (auth required)
- GET  /leaderboard   - Get leaderboard
- GET  /leaderboard/tasks - List tasks with entries
- GET  /stats         - Aggregate statistics
- GET  /metrics       - Prometheus metrics
"""
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.repositories import EpisodeRepository, LeaderboardRepository, UserRepository
from app.db.schemas import (
    EpisodeCreate,
    EpisodeResponse,
    EpisodeDetail,
    EpisodeListResponse,
    LeaderboardEntryResponse,
    LeaderboardResponse,
    StatsResponse,
    UserResponse,
)
from app.information_tracker import EnhancedActionTracker
from app.routes.state import ws_manager, _metrics_enabled, episodes_total, episode_score


from app.routes.auth_deps import get_current_user

router = APIRouter(tags=["episodes"])


# === Episode Endpoints ===

@router.get("/episodes", response_model=EpisodeListResponse)
async def list_episodes(
    fault_type: Optional[str] = Query(None),
    agent_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    episode_repo = EpisodeRepository(db)
    offset = (page - 1) * per_page

    if agent_type:
        # Filter by agent type requires full scan for now
        all_eps = await episode_repo.list_recent(limit=per_page, offset=offset)
        all_eps = [e for e in all_eps if e.agent_type == agent_type]
        total = len(all_eps)
    elif fault_type:
        all_eps = await episode_repo.list_by_fault(fault_type, limit=per_page, offset=offset)
        total = len(all_eps)
    else:
        all_eps = await episode_repo.list_recent(limit=per_page, offset=offset)
        total = await episode_repo.count()

    return EpisodeListResponse(
        total=total,
        episodes=[EpisodeResponse.model_validate(e) for e in all_eps],
        page=page,
        per_page=per_page,
    )


@router.get("/episodes/{episode_id}", response_model=EpisodeDetail)
async def get_episode(
    episode_id: int,
    db: AsyncSession = Depends(get_db),
):
    episode_repo = EpisodeRepository(db)
    episode = await episode_repo.get_by_id(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return EpisodeDetail.model_validate(episode)


@router.get("/episodes/{episode_id}/replay")
async def get_episode_replay(
    episode_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get full episode replay with all steps for visualization."""
    episode_repo = EpisodeRepository(db)
    episode = await episode_repo.get_by_id(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    return {
        "episode_id": episode.id,
        "trajectory": getattr(episode, "trajectory", []),
        "final_state": getattr(episode, "final_state", {}),
        "score": episode.final_score,
        "fault_type": episode.fault_type,
        "difficulty": episode.difficulty,
        "agent_type": getattr(episode, "agent_type", "unknown"),
        "steps": len(getattr(episode, "trajectory", [])),
        "duration_minutes": getattr(episode, "duration_seconds", 0) / 60 if getattr(episode, "duration_seconds", 0) else None,
    }


@router.post("/episodes", response_model=EpisodeResponse)
async def save_episode(
    data: EpisodeCreate,
    current_user: Optional[UserResponse] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a completed episode to the database"""
    episode_repo = EpisodeRepository(db)
    leaderboard_repo = LeaderboardRepository(db)

    user_id = current_user.id if current_user else None

    # Check for duplicate
    existing = await episode_repo.get_by_episode_id(data.episode_id)
    if existing:
        raise HTTPException(status_code=409, detail="Episode already recorded")

    episode = await episode_repo.create(data, user_id=user_id)

    # Update leaderboard if user is authenticated
    if user_id:
        task_id = f"{data.fault_type}_d{data.difficulty}"
        await leaderboard_repo.upsert_entry(
            user_id=user_id,
            task_id=task_id,
            fault_type=data.fault_type,
            grader_type="enhanced",
            final_score=data.final_score,
        )

    # Prometheus metrics
    if _metrics_enabled and episodes_total is not None:
        episodes_total.labels(fault_type=data.fault_type, agent_type=data.agent_type).inc()
        episode_score.labels(fault_type=data.fault_type).set(data.final_score)

    # Broadcast score (only if ws_manager is initialized)
    if ws_manager is not None:
        await ws_manager.broadcast({
            "type": "score_recorded",
            "episode_id": data.episode_id,
            "fault_type": data.fault_type,
            "final_score": data.final_score,
            "grade": data.grade,
            "username": current_user.username if current_user else "anonymous",
        })

    return EpisodeResponse.model_validate(episode)


# === Leaderboard Endpoints ===

@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    task_id: Optional[str] = Query(None, description="Task ID e.g. 'oom_2', 'cascade_3'"),
    grader_type: str = Query("enhanced"),
    limit: int = Query(50, ge=1, le=200),
):
    if task_id is None:
        return LeaderboardResponse(grader_type=grader_type, entries=[], total=0)

    @asynccontextmanager
    async def _get_db_session():
        async for db in get_db():
            yield db

    async with _get_db_session() as db:
        leaderboard_repo = LeaderboardRepository(db)
        entries = await leaderboard_repo.get_leaderboard(task_id, grader_type, limit=limit)
        total = await leaderboard_repo.count_entries(task_id, grader_type)

        ranked = []
        for rank, (entry, user) in enumerate(entries, 1):
            ranked.append(LeaderboardEntryResponse(
                rank=rank,
                user_id=entry.user_id,
                username=user.username,
                task_id=entry.task_id,
                best_score=entry.best_score,
                avg_score=entry.avg_score,
                episode_count=entry.episode_count,
                updated_at=entry.updated_at,
            ))
        return LeaderboardResponse(
            task_id=task_id,
            grader_type=grader_type,
            entries=ranked,
            total=total,
        )


@router.get("/leaderboard/tasks")
async def list_leaderboard_tasks():
    """List all tasks that have leaderboard entries"""
    return {
        "tasks": [
            {"task_id": "oom_crash", "fault_type": "oom", "difficulty_level": 2, "name": "The OOM Crash"},
            {"task_id": "cascade_failure", "fault_type": "cascade", "difficulty_level": 3, "name": "The Cascade"},
            {"task_id": "ghost_corruption", "fault_type": "ghost", "difficulty_level": 5, "name": "The Ghost"},
            {"task_id": "ddos_flood", "fault_type": "network", "difficulty_level": 3, "name": "The DDoS Flood"},
            {"task_id": "memory_spiral", "fault_type": "oom", "difficulty_level": 4, "name": "The Memory Spiral"},
        ]
    }


# === Stats Endpoint ===

@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    episode_repo = EpisodeRepository(db)
    user_repo = UserRepository(db)

    total_episodes = await episode_repo.count()
    total_users = await user_repo.count()
    avg_score = await episode_repo.avg_score()
    scores_by_fault = await episode_repo.scores_by_fault()
    top_agents = await episode_repo.top_agents(limit=5)
    recent_episodes = await episode_repo.list_recent(limit=10)

    return StatsResponse(
        total_episodes=total_episodes,
        total_users=total_users,
        avg_score=round(avg_score, 3),
        scores_by_fault={k: round(v, 3) for k, v in scores_by_fault.items()},
        top_agents=top_agents,
        recent_episodes=[EpisodeResponse.model_validate(e) for e in recent_episodes],
    )


# === Prometheus Metrics Endpoint ===

@router.get("/metrics")
async def metrics():
    if not _metrics_enabled:
        raise HTTPException(status_code=503, detail="Prometheus client not installed")
    from starlette.responses import Response
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)