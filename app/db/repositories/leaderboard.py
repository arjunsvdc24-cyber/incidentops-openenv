"""
IncidentOps - Leaderboard Repository
"""
from datetime import datetime, timezone

from sqlalchemy import select, desc, func, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LeaderboardEntry, User, Episode


class LeaderboardRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_entry(
        self,
        user_id: int,
        task_id: str,
        fault_type: str,
        grader_type: str,
        final_score: float,
        episode_avg: float | None = None,
    ) -> LeaderboardEntry:
        """Insert or update leaderboard entry for a user+task combo"""
        existing = await self.session.execute(
            select(LeaderboardEntry).where(
                LeaderboardEntry.user_id == user_id,
                LeaderboardEntry.task_id == task_id,
                LeaderboardEntry.grader_type == grader_type,
            )
        )
        entry = existing.scalar_one_or_none()

        if entry is None:
            entry = LeaderboardEntry(
                user_id=user_id,
                task_id=task_id,
                fault_type=fault_type,
                grader_type=grader_type,
                best_score=final_score,
                avg_score=episode_avg or final_score,
                episode_count=1,
            )
            self.session.add(entry)
        else:
            entry.best_score = max(entry.best_score, final_score)
            total = entry.avg_score * entry.episode_count + final_score
            entry.episode_count += 1
            entry.avg_score = total / entry.episode_count
            entry.updated_at = datetime.now(timezone.utc)

        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def get_leaderboard(
        self,
        task_id: str,
        grader_type: str = "enhanced",
        limit: int = 100,
        offset: int = 0,
    ) -> list[tuple[LeaderboardEntry, User]]:
        result = await self.session.execute(
            select(LeaderboardEntry, User)
            .join(User, LeaderboardEntry.user_id == User.id)
            .where(
                LeaderboardEntry.task_id == task_id,
                LeaderboardEntry.grader_type == grader_type,
            )
            .order_by(desc(LeaderboardEntry.best_score))
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def count_entries(self, task_id: str, grader_type: str = "enhanced") -> int:
        result = await self.session.execute(
            select(func.count(LeaderboardEntry.id)).where(
                LeaderboardEntry.task_id == task_id,
                LeaderboardEntry.grader_type == grader_type,
            )
        )
        return result.scalar()

    async def get_user_rank(
        self,
        user_id: int,
        task_id: str,
        grader_type: str = "enhanced",
    ) -> int | None:
        result = await self.session.execute(
            select(LeaderboardEntry.best_score).where(
                LeaderboardEntry.user_id == user_id,
                LeaderboardEntry.task_id == task_id,
                LeaderboardEntry.grader_type == grader_type,
            )
        )
        user_score = result.scalar_one_or_none()
        if user_score is None:
            return None

        rank_result = await self.session.execute(
            select(func.count(LeaderboardEntry.id)).where(
                LeaderboardEntry.task_id == task_id,
                LeaderboardEntry.grader_type == grader_type,
                LeaderboardEntry.best_score > user_score,
            )
        )
        return rank_result.scalar() + 1

    async def get_user_entries(
        self,
        user_id: int,
        grader_type: str = "enhanced",
    ) -> list[LeaderboardEntry]:
        result = await self.session.execute(
            select(LeaderboardEntry)
            .where(
                LeaderboardEntry.user_id == user_id,
                LeaderboardEntry.grader_type == grader_type,
            )
            .order_by(desc(LeaderboardEntry.best_score))
        )
        return list(result.scalars().all())
