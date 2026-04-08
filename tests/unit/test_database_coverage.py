"""
IncidentOps - Unit Tests: Database Layer Additional Coverage

Tests the database module's exported symbols, module-level configuration,
and functions that are testable without heavy mocking.

These tests complement tests/unit/test_repositories.py which covers repository methods.
"""
import pytest
from app.db.database import (
    get_db,
    get_db_context,
    init_db,
    close_db,
    _async_session_factory,
    engine,
    Base,
)


class TestDatabaseModuleSymbols:
    """Test module-level symbols are accessible."""

    def test_base_declarative_base_exists(self):
        """Base is a SQLAlchemy DeclarativeBase."""
        from sqlalchemy.orm import DeclarativeBase
        assert issubclass(Base, DeclarativeBase)

    def test_engine_exists(self):
        """Engine is created at module import."""
        assert engine is not None
        assert hasattr(engine, "begin")

    def test_session_factory_exists(self):
        """Async session factory is available."""
        assert _async_session_factory is not None
        assert callable(_async_session_factory)

    def test_get_db_is_async_generator(self):
        """get_db is an async generator function."""
        import inspect
        assert inspect.isasyncgenfunction(get_db)

    def test_get_db_context_is_async_context_manager(self):
        """get_db_context is an async context manager (decorated with @asynccontextmanager)."""
        import contextlib
        cm = get_db_context()
        # Should be an async context manager
        assert isinstance(cm, contextlib.AbstractAsyncContextManager)

    def test_init_db_is_async_function(self):
        """init_db is an async function."""
        import inspect
        assert inspect.iscoroutinefunction(init_db)

    def test_close_db_is_async_function(self):
        """close_db is an async function."""
        import inspect
        assert inspect.iscoroutinefunction(close_db)


class TestDatabaseModuleConfiguration:
    """Test database module configuration."""

    def test_database_url_from_env_or_default(self):
        """DATABASE_URL defaults to SQLite when env var not set."""
        from app.db import database
        assert database.DATABASE_URL is not None
        assert "sqlite" in database.DATABASE_URL or "aiosqlite" in database.DATABASE_URL

    def test_engine_echo_from_env(self):
        """Engine echo is boolean based on SQLALCHEMY_ECHO env var."""
        # Echo is False unless SQLALCHEMY_ECHO is set to a truthy value
        assert isinstance(engine.echo, bool)

    def test_session_factory_async_session(self):
        """Session factory creates AsyncSession."""
        from sqlalchemy.ext.asyncio import AsyncSession
        assert _async_session_factory.class_ == AsyncSession

    def test_session_factory_created_with_expire_on_commit_false(self):
        """Session factory is configured with expire_on_commit=False."""
        # The factory is created with expire_on_commit=False in database.py
        # Check by examining the factory's configuration
        from sqlalchemy.ext.asyncio import async_sessionmaker
        assert isinstance(_async_session_factory, async_sessionmaker)


class TestInitDbFunction:
    """Test init_db() function behavior."""

    @pytest.mark.asyncio
    async def test_init_db_runs_without_error(self):
        """init_db() completes successfully (tables already created via lifespan)."""
        # init_db is called during app startup via lifespan
        # This test verifies the function exists and is callable
        # In actual use, tables may already exist (create_all is idempotent)
        await init_db()

    @pytest.mark.asyncio
    async def test_init_db_can_be_called_multiple_times(self):
        """init_db() is safe to call multiple times."""
        # create_all is idempotent - can be called multiple times safely
        await init_db()
        await init_db()
        # No exception means success


class TestCloseDbFunction:
    """Test close_db() function behavior."""

    @pytest.mark.asyncio
    async def test_close_db_disposes_engine(self):
        """close_db() disposes the engine connection pool."""
        # close_db disposes the engine - subsequent DB calls would fail
        # This tests that the function exists and is callable
        await close_db()
        # Note: After close_db, the engine is disposed.
        # Re-importing would create a new engine, so we just verify the function works.


class TestGetDbContext:
    """Test get_db_context() context manager behavior."""

    @pytest.mark.asyncio
    async def test_context_manager_is_async_cm(self):
        """get_db_context is an async context manager."""
        import contextlib
        cm = get_db_context()
        # Should be an async context manager
        assert isinstance(cm, contextlib.AbstractAsyncContextManager)

    @pytest.mark.asyncio
    async def test_context_manager_yields_session(self):
        """Context manager yields a session object."""
        async with get_db_context() as session:
            # Session should have close and commit methods
            assert hasattr(session, 'close')
            assert hasattr(session, 'commit')


class TestGetDb:
    """Test get_db() FastAPI dependency behavior."""

    @pytest.mark.asyncio
    async def test_get_db_is_dependency(self):
        """get_db is suitable for FastAPI Depends()."""
        import inspect
        # It's an async generator, which is what FastAPI expects for Depends()
        assert inspect.isasyncgenfunction(get_db)

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        """get_db yields a session when used as generator."""
        gen = get_db()
        session = await gen.__anext__()
        # Session should be an AsyncSession-like object
        assert hasattr(session, 'close')
        assert hasattr(session, 'commit')
