"""Shared pytest fixtures for LivePoll tests."""

from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import create_admin_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Session as PollSession

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create an in-memory SQLite engine with all tables for a single test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Yield a fresh AsyncSession for each test, rolling back after the test."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session):
    """
    Return an AsyncClient wired to the FastAPI app with the test DB session injected.
    Redirects are NOT followed so tests can assert on 303 responses directly.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Patch init_db so the app lifespan runs without touching any real DB file.
    with patch("app.main.init_db", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def admin_session_factory(db_session, async_client):
    """
    Factory fixture: call it to create a poll Session in the DB and return
    a dict with ``session_id`` and ``admin_token`` ready to use as a cookie.
    """

    async def _factory(title: str = "Test Session", password: str = "secret"):
        poll_session = PollSession(
            title=title,
            admin_password_hash=hash_password(password),
        )
        db_session.add(poll_session)
        await db_session.commit()
        await db_session.refresh(poll_session)
        token = create_admin_token(poll_session.id)
        return {"session_id": poll_session.id, "admin_token": token}

    return _factory
