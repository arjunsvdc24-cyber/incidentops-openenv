from typing import Any
"""
IncidentOps - Pydantic Schemas for API
"""
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator


# === User Schemas ===

class UserCreate(BaseModel):
    username: str
    email: EmailStr | None = None
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 64:
            raise ValueError("Username must be 3-64 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must be alphanumeric (with _ or -)")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    api_key: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_seen: datetime | None = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# === Episode Schemas ===

class EpisodeCreate(BaseModel):
    """Schema for saving a completed episode"""
    episode_id: str
    fault_type: str
    difficulty: int
    seed: int
    agent_type: str = "human"
    agent_model: str | None = None
    actions: list
    observations: list
    rewards: list
    total_reward: float
    final_score: float
    grade: str
    root_cause_score: float | None = None
    fix_score: float | None = None
    efficiency_score: float | None = None
    disruption_score: float | None = None
    reasoning_score: float | None = None
    num_steps: int
    terminated: bool = False
    truncated: bool = False
    duration_ms: int | None = None


class EpisodeResponse(BaseModel):
    id: int
    episode_id: str
    fault_type: str
    difficulty: int
    seed: int
    agent_type: str
    agent_model: str | None = None
    total_reward: float
    final_score: float
    grade: str
    root_cause_score: float | None = None
    fix_score: float | None = None
    efficiency_score: float | None = None
    disruption_score: float | None = None
    reasoning_score: float | None = None
    num_steps: int
    created_at: datetime
    duration_ms: int | None = None

    class Config:
        from_attributes = True


class EpisodeDetail(EpisodeResponse):
    actions: list
    observations: list
    rewards: list


class EpisodeListResponse(BaseModel):
    total: int
    episodes: list[EpisodeResponse]
    page: int = 1
    per_page: int = 20


# === Leaderboard Schemas ===

class LeaderboardEntryResponse(BaseModel):
    rank: int
    user_id: int
    username: str
    task_id: str
    best_score: float
    avg_score: float
    episode_count: int
    updated_at: datetime

    class Config:
        from_attributes = True


class LeaderboardResponse(BaseModel):
    task_id: str | None = None
    grader_type: str = "enhanced"
    entries: list[LeaderboardEntryResponse] = []
    total: int = 0


# === Aggregate Stats ===

class StatsResponse(BaseModel):
    total_episodes: int
    total_users: int
    avg_score: float
    scores_by_fault: dict[str, float]
    top_agents: list[dict]
    recent_episodes: list[EpisodeResponse]
