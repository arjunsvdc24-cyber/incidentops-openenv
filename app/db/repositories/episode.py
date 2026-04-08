"""
IncidentOps - Episode Repository
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Episode
from app.db.schemas import EpisodeCreate


class EpisodeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: EpisodeCreate, user_id: Optional[int] = None) -> Episode:
        episode = Episode(
            episode_id=data.episode_id,
            user_id=user_id,
            fault_type=data.fault_type,
            difficulty=data.difficulty,
            seed=data.seed,
            agent_type=data.agent_type,
            agent_model=data.agent_model,
            actions=data.actions,
            observations=data.observations,
            rewards=data.rewards,
            total_reward=data.total_reward,
            final_score=data.final_score,
            grade=data.grade,
            root_cause_score=data.root_cause_score,
            fix_score=data.fix_score,
            efficiency_score=data.efficiency_score,
            disruption_score=data.disruption_score,
            reasoning_score=data.reasoning_score,
            num_steps=data.num_steps,
            terminated=data.terminated,
            truncated=data.truncated,
            duration_ms=data.duration_ms,
        )
        self.session.add(episode)
        await self.session.flush()
        await self.session.refresh(episode)
        return episode

    async def get_by_id(self, episode_id: int) -> Optional[Episode]:
        result = await self.session.execute(
            select(Episode).where(Episode.id == episode_id)
        )
        return result.scalar_one_or_none()

    async def get_by_episode_id(self, episode_id: str) -> Optional[Episode]:
        result = await self.session.execute(
            select(Episode).where(Episode.episode_id == episode_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: int,
        fault_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Episode], int]:
        query = select(Episode).where(Episode.user_id == user_id)
        count_query = select(func.count(Episode.id)).where(Episode.user_id == user_id)

        if fault_type:
            query = query.where(Episode.fault_type == fault_type)
            count_query = count_query.where(Episode.fault_type == fault_type)

        query = query.order_by(desc(Episode.created_at)).limit(limit).offset(offset)
        result = await self.session.execute(query)
        count_result = await self.session.execute(count_query)
        return list(result.scalars().all()), count_result.scalar()

    async def list_recent(self, limit: int = 20, offset: int = 0) -> list[Episode]:
        result = await self.session.execute(
            select(Episode)
            .order_by(desc(Episode.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_fault(
        self,
        fault_type: str,
        difficulty: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Episode]:
        query = select(Episode).where(Episode.fault_type == fault_type)
        if difficulty is not None:
            query = query.where(Episode.difficulty == difficulty)
        query = query.order_by(desc(Episode.final_score)).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(Episode.id)))
        return result.scalar()

    async def avg_score(self, fault_type: Optional[str] = None) -> float:
        query = select(func.avg(Episode.final_score))
        if fault_type:
            query = query.where(Episode.fault_type == fault_type)
        result = await self.session.execute(query)
        return float(result.scalar() or 0.0)

    async def scores_by_fault(self) -> dict[str, float]:
        result = await self.session.execute(
            select(Episode.fault_type, func.avg(Episode.final_score))
            .group_by(Episode.fault_type)
        )
        return {row[0]: float(row[1]) for row in result.all()}

    async def top_agents(self, limit: int = 10) -> list[dict]:
        result = await self.session.execute(
            select(
                Episode.agent_type,
                func.avg(Episode.final_score).label("avg_score"),
                func.count(Episode.id).label("count"),
            )
            .group_by(Episode.agent_type)
            .order_by(desc("avg_score"))
            .limit(limit)
        )
        return [
            {"agent_type": row[0], "avg_score": round(float(row[1]), 3), "episode_count": row[2]}
            for row in result.all()
        ]
