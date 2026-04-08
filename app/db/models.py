"""
IncidentOps - SQLAlchemy ORM Models
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, JSON, Index, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    """User account for leaderboard and episode tracking"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(256), unique=True, nullable=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    episodes: Mapped[list["Episode"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    leaderboard_entries: Mapped[list["LeaderboardEntry"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class Episode(Base):
    """Recorded episode trajectory for replay and analysis"""
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Scenario metadata
    fault_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)

    # Agent metadata
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False, default="human")
    agent_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Trajectory
    actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    observations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rewards: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Outcome
    total_reward: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    grade: Mapped[str] = mapped_column(String(16), nullable=False)

    # Breakdown scores
    root_cause_score: Mapped[float] = mapped_column(Float, nullable=True)
    fix_score: Mapped[float] = mapped_column(Float, nullable=True)
    efficiency_score: Mapped[float] = mapped_column(Float, nullable=True)
    disruption_score: Mapped[float] = mapped_column(Float, nullable=True)
    reasoning_score: Mapped[float] = mapped_column(Float, nullable=True)

    # Episode stats
    num_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    terminated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # User relationship
    user: Mapped[Optional["User"]] = relationship(back_populates="episodes")

    __table_args__ = (
        Index("ix_episodes_fault_difficulty", "fault_type", "difficulty"),
        Index("ix_episodes_user_fault", "user_id", "fault_type"),
    )

    def __repr__(self) -> str:
        return f"<Episode(id={self.id}, fault={self.fault_type}, score={self.final_score})>"


class LeaderboardEntry(Base):
    """Aggregated leaderboard scores per user per task"""
    __tablename__ = "leaderboard_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Task identity
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fault_type: Mapped[str] = mapped_column(String(32), nullable=False)
    grader_type: Mapped[str] = mapped_column(String(32), nullable=False, default="enhanced")

    # Best score achieved
    best_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    avg_score: Mapped[float] = mapped_column(Float, nullable=False)
    episode_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="leaderboard_entries")

    __table_args__ = (
        UniqueConstraint("user_id", "task_id", "grader_type", name="uq_user_task_grader"),
        Index("ix_leaderboard_task_score", "task_id", "best_score"),
    )

    def __repr__(self) -> str:
        return f"<LeaderboardEntry(user={self.user_id}, task={self.task_id}, best={self.best_score})>"
