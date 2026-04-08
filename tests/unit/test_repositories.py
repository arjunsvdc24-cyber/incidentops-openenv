"""
IncidentOps - Repository Layer Coverage Tests
Targets uncovered lines in app/db/repositories/*.py
"""
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import User
from app.db.repositories import LeaderboardRepository, EpisodeRepository, UserRepository
from app.db.schemas import EpisodeCreate, UserCreate


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session


@pytest.fixture
async def user_repo(db_session):
    return UserRepository(db_session)


@pytest.fixture
async def episode_repo(db_session):
    return EpisodeRepository(db_session)


@pytest.fixture
async def leaderboard_repo(db_session):
    return LeaderboardRepository(db_session)


@pytest.fixture
async def test_user(db_session, user_repo):
    user_create = UserCreate(
        username="testuser",
        email="test@example.com",
        password="TestPassword123!",
    )
    user = await user_repo.create(user_create)
    return user


class TestUserRepository:
    """Coverage for app/db/repositories/user.py"""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session, user_repo):
        """Cover: UserRepository.create()"""
        user_create = UserCreate(
            username="newuser",
            email="new@example.com",
            password="password123",
        )
        user = await user_repo.create(user_create)
        assert user.id is not None
        assert user.username == "newuser"
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_create_duplicate_user_raises(self, db_session, user_repo, test_user):
        """Cover: user_repo.create duplicate path"""
        user_create = UserCreate(
            username="testuser",
            email="another@example.com",
            password="password456",
        )
        with pytest.raises(Exception):
            await user_repo.create(user_create)

    @pytest.mark.asyncio
    async def test_authenticate_valid(self, db_session, user_repo):
        """Cover: UserRepository.authenticate()"""
        user_create = UserCreate(
            username="authtest",
            email="auth@example.com",
            password="CorrectPass123!",
        )
        await user_repo.create(user_create)
        result = await user_repo.authenticate("authtest", "CorrectPass123!")
        assert result is not None
        assert result.username == "authtest"

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self, db_session, user_repo):
        """Cover: UserRepository.authenticate() wrong password path"""
        user_create = UserCreate(
            username="wrongpass",
            email="wrong@example.com",
            password="CorrectPass123!",
        )
        await user_repo.create(user_create)
        result = await user_repo.authenticate("wrongpass", "WrongPassword!")
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent(self, db_session, user_repo):
        """Cover: UserRepository.authenticate() nonexistent user"""
        result = await user_repo.authenticate("nonexistent", "password")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_api_key(self, db_session, user_repo):
        """Cover: UserRepository.get_by_api_key()"""
        user_create = UserCreate(
            username="apikeyuser",
            email="apikey@example.com",
            password="password123",
        )
        user = await user_repo.create(user_create)
        assert user.api_key is not None
        result = await user_repo.get_by_api_key(user.api_key)
        assert result is not None
        assert result.username == "apikeyuser"

    @pytest.mark.asyncio
    async def test_get_by_api_key_invalid(self, db_session, user_repo):
        """Cover: UserRepository.get_by_api_key() invalid key"""
        result = await user_repo.get_by_api_key("invalid-key-xyz")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_last_seen(self, db_session, user_repo):
        """Cover: UserRepository.update_last_seen()"""
        user_create = UserCreate(
            username="lastseen",
            email="lastseen@example.com",
            password="password123",
        )
        user = await user_repo.create(user_create)
        await user_repo.update_last_seen(user.id)
        await db_session.flush()
        await db_session.refresh(user)
        assert user.last_seen is not None


class TestEpisodeRepository:
    """Coverage for app/db/repositories/episode.py"""

    @pytest.mark.asyncio
    async def test_create_episode(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.create()"""
        data = EpisodeCreate(
            episode_id="test-episode-001",
            fault_type="oom",
            difficulty=2,
            seed=42,
            agent_type="rule_based",
            actions=[{"action_type": "query_service", "target_service": "api-gateway"}],
            observations=[],
            rewards=[0.5],
            total_reward=0.5,
            final_score=0.864,
            grade="good",
            num_steps=5,
            terminated=True,
            truncated=False,
            duration_ms=1234,
        )
        episode = await episode_repo.create(data, user_id=test_user.id)
        assert episode.id is not None
        assert episode.episode_id == "test-episode-001"
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.get_by_id()"""
        data = EpisodeCreate(
            episode_id="test-ep-002",
            fault_type="cascade",
            difficulty=3,
            seed=42,
            agent_type="rule_based",
            actions=[],
            observations=[],
            rewards=[],
            total_reward=0.0,
            final_score=0.5,
            grade="moderate",
            num_steps=3,
            terminated=True,
            truncated=False,
            duration_ms=500,
        )
        episode = await episode_repo.create(data, user_id=test_user.id)
        await db_session.commit()
        result = await episode_repo.get_by_id(episode.id)
        assert result is not None
        assert result.episode_id == "test-ep-002"

    @pytest.mark.asyncio
    async def test_get_by_episode_id(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.get_by_episode_id()"""
        data = EpisodeCreate(
            episode_id="unique-ep-id-003",
            fault_type="ghost",
            difficulty=5,
            seed=42,
            agent_type="rule_based",
            actions=[],
            observations=[],
            rewards=[],
            total_reward=0.0,
            final_score=0.3,
            grade="poor",
            num_steps=10,
            terminated=True,
            truncated=False,
            duration_ms=2000,
        )
        episode = await episode_repo.create(data, user_id=test_user.id)
        await db_session.commit()
        result = await episode_repo.get_by_episode_id("unique-ep-id-003")
        assert result is not None
        assert result.fault_type == "ghost"

    @pytest.mark.asyncio
    async def test_list_recent(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.list_recent()"""
        for i in range(3):
            data = EpisodeCreate(
                episode_id=f"recent-ep-{i}",
                fault_type="oom",
                difficulty=2,
                seed=42 + i,
                agent_type="rule_based",
                actions=[],
                observations=[],
                rewards=[],
                total_reward=0.0,
                final_score=0.5 + i * 0.1,
                grade="moderate",
                num_steps=2,
                terminated=True,
                truncated=False,
                duration_ms=100,
            )
            await episode_repo.create(data, user_id=test_user.id)
        await db_session.commit()
        result = await episode_repo.list_recent(limit=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_by_fault(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.list_by_fault()"""
        for ft in ["oom", "cascade", "ghost"]:
            data = EpisodeCreate(
                episode_id=f"fault-ep-{ft}",
                fault_type=ft,
                difficulty=3,
                seed=42,
                agent_type="rule_based",
                actions=[],
                observations=[],
                rewards=[],
                total_reward=0.0,
                final_score=0.5,
                grade="moderate",
                num_steps=2,
                terminated=True,
                truncated=False,
                duration_ms=100,
            )
            await episode_repo.create(data, user_id=test_user.id)
        await db_session.commit()
        result = await episode_repo.list_by_fault("cascade")
        assert len(result) == 1
        assert result[0].fault_type == "cascade"

    @pytest.mark.asyncio
    async def test_list_by_fault_with_difficulty(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.list_by_fault() with difficulty filter"""
        data = EpisodeCreate(
            episode_id="fault-diff-ep",
            fault_type="oom",
            difficulty=4,
            seed=42,
            agent_type="rule_based",
            actions=[],
            observations=[],
            rewards=[],
            total_reward=0.0,
            final_score=0.5,
            grade="moderate",
            num_steps=2,
            terminated=True,
            truncated=False,
            duration_ms=100,
        )
        await episode_repo.create(data, user_id=test_user.id)
        await db_session.commit()
        result = await episode_repo.list_by_fault("oom", difficulty=4)
        assert len(result) == 1
        result_no_diff = await episode_repo.list_by_fault("oom", difficulty=2)
        assert len(result_no_diff) == 0

    @pytest.mark.asyncio
    async def test_count(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.count()"""
        for i in range(5):
            data = EpisodeCreate(
                episode_id=f"count-ep-{i}",
                fault_type="oom",
                difficulty=2,
                seed=42 + i,
                agent_type="rule_based",
                actions=[],
                observations=[],
                rewards=[],
                total_reward=0.0,
                final_score=0.5,
                grade="moderate",
                num_steps=2,
                terminated=True,
                truncated=False,
                duration_ms=100,
            )
            await episode_repo.create(data, user_id=test_user.id)
        await db_session.commit()
        count = await episode_repo.count()
        assert count == 5

    @pytest.mark.asyncio
    async def test_avg_score(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.avg_score()"""
        for score in [0.5, 0.7, 0.9]:
            data = EpisodeCreate(
                episode_id=f"avg-ep-{score}",
                fault_type="oom",
                difficulty=2,
                seed=42,
                agent_type="rule_based",
                actions=[],
                observations=[],
                rewards=[],
                total_reward=score,
                final_score=score,
                grade="good" if score > 0.7 else "moderate",
                num_steps=2,
                terminated=True,
                truncated=False,
                duration_ms=100,
            )
            await episode_repo.create(data, user_id=test_user.id)
        await db_session.commit()
        avg = await episode_repo.avg_score()
        assert 0.6 < avg < 1.0

    @pytest.mark.asyncio
    async def test_avg_score_by_fault(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.avg_score() with fault_type filter"""
        data = EpisodeCreate(
            episode_id="avg-fault-ep",
            fault_type="cascade",
            difficulty=3,
            seed=42,
            agent_type="rule_based",
            actions=[],
            observations=[],
            rewards=[],
            total_reward=0.6,
            final_score=0.6,
            grade="moderate",
            num_steps=3,
            terminated=True,
            truncated=False,
            duration_ms=200,
        )
        await episode_repo.create(data, user_id=test_user.id)
        await db_session.commit()
        avg = await episode_repo.avg_score(fault_type="cascade")
        assert avg == 0.6

    @pytest.mark.asyncio
    async def test_scores_by_fault(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.scores_by_fault()"""
        for ft, score in [("oom", 0.8), ("cascade", 0.6), ("oom", 0.9)]:
            data = EpisodeCreate(
                episode_id=f"scores-ep-{ft}-{score}",
                fault_type=ft,
                difficulty=2,
                seed=42,
                agent_type="rule_based",
                actions=[],
                observations=[],
                rewards=[],
                total_reward=score,
                final_score=score,
                grade="good",
                num_steps=2,
                terminated=True,
                truncated=False,
                duration_ms=100,
            )
            await episode_repo.create(data, user_id=test_user.id)
        await db_session.commit()
        result = await episode_repo.scores_by_fault()
        assert "oom" in result
        assert "cascade" in result

    @pytest.mark.asyncio
    async def test_top_agents(self, db_session, episode_repo, test_user):
        """Cover: EpisodeRepository.top_agents()"""
        for agent, score in [("rule_based", 0.8), ("llm", 0.9), ("rule_based", 0.7)]:
            data = EpisodeCreate(
                episode_id=f"top-ep-{agent}-{score}",
                fault_type="oom",
                difficulty=2,
                seed=42,
                agent_type=agent,
                actions=[],
                observations=[],
                rewards=[],
                total_reward=score,
                final_score=score,
                grade="good",
                num_steps=2,
                terminated=True,
                truncated=False,
                duration_ms=100,
            )
            await episode_repo.create(data, user_id=test_user.id)
        await db_session.commit()
        result = await episode_repo.top_agents()
        assert len(result) >= 2


class TestLeaderboardRepository:
    """Coverage for app/db/repositories/leaderboard.py"""

    @pytest.mark.asyncio
    async def test_upsert_new_entry(self, db_session, leaderboard_repo, test_user):
        """Cover: LeaderboardRepository.upsert_entry() new entry path"""
        entry = await leaderboard_repo.upsert_entry(
            user_id=test_user.id,
            task_id="oom_2",
            fault_type="oom",
            grader_type="enhanced",
            final_score=0.85,
        )
        assert entry.best_score == 0.85
        assert entry.episode_count == 1
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, db_session, leaderboard_repo, test_user):
        """Cover: LeaderboardRepository.upsert_entry() update path"""
        await leaderboard_repo.upsert_entry(
            user_id=test_user.id,
            task_id="cascade_3",
            fault_type="cascade",
            grader_type="enhanced",
            final_score=0.6,
        )
        await db_session.flush()
        entry = await leaderboard_repo.upsert_entry(
            user_id=test_user.id,
            task_id="cascade_3",
            fault_type="cascade",
            grader_type="enhanced",
            final_score=0.8,
        )
        await db_session.commit()
        assert entry.best_score == 0.8
        assert entry.episode_count == 2

    @pytest.mark.asyncio
    async def test_get_leaderboard(self, db_session, leaderboard_repo, test_user):
        """Cover: LeaderboardRepository.get_leaderboard()"""
        await leaderboard_repo.upsert_entry(
            user_id=test_user.id,
            task_id="ghost_5",
            fault_type="ghost",
            grader_type="enhanced",
            final_score=0.7,
        )
        await db_session.flush()
        result = await leaderboard_repo.get_leaderboard("ghost_5")
        assert len(result) == 1
        assert result[0][0].best_score == 0.7

    @pytest.mark.asyncio
    async def test_count_entries(self, db_session, leaderboard_repo, test_user):
        """Cover: LeaderboardRepository.count_entries()"""
        await leaderboard_repo.upsert_entry(
            user_id=test_user.id,
            task_id="oom_2",
            fault_type="oom",
            grader_type="enhanced",
            final_score=0.85,
        )
        await db_session.flush()
        count = await leaderboard_repo.count_entries("oom_2")
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_user_rank(self, db_session, leaderboard_repo, test_user):
        """Cover: LeaderboardRepository.get_user_rank()"""
        await leaderboard_repo.upsert_entry(
            user_id=test_user.id,
            task_id="oom_2",
            fault_type="oom",
            grader_type="enhanced",
            final_score=0.9,
        )
        await db_session.flush()
        rank = await leaderboard_repo.get_user_rank(test_user.id, "oom_2")
        assert rank == 1

    @pytest.mark.asyncio
    async def test_get_user_rank_no_entry(self, db_session, leaderboard_repo, test_user):
        """Cover: LeaderboardRepository.get_user_rank() no entry"""
        rank = await leaderboard_repo.get_user_rank(test_user.id, "nonexistent_task")
        assert rank is None

    @pytest.mark.asyncio
    async def test_get_user_entries(self, db_session, leaderboard_repo, test_user):
        """Cover: LeaderboardRepository.get_user_entries()"""
        for task in ["oom_2", "cascade_3", "ghost_5"]:
            await leaderboard_repo.upsert_entry(
                user_id=test_user.id,
                task_id=task,
                fault_type="mixed",
                grader_type="enhanced",
                final_score=0.7,
            )
            await db_session.flush()
        await db_session.commit()
        entries = await leaderboard_repo.get_user_entries(test_user.id)
        assert len(entries) == 3
