import os
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./livepoll.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


def _resolve_sqlite_file_path(database_name: str) -> Path | None:
    if database_name in ("", ":memory:"):
        return None

    if database_name.startswith("file:"):
        parsed = urlparse(database_name)
        sqlite_path = parsed.path or parsed.netloc
        if sqlite_path in ("", ":memory:"):
            return None
        return Path(sqlite_path)

    return Path(database_name)


def _prepare_sqlite_path(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return

    sqlite_file_path = _resolve_sqlite_file_path(url.database or "")
    if sqlite_file_path is None:
        return

    if not sqlite_file_path.is_absolute():
        sqlite_file_path = (Path.cwd() / sqlite_file_path).resolve()

    sqlite_file_path.parent.mkdir(parents=True, exist_ok=True)


async def init_db():
    try:
        _prepare_sqlite_path(DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        raise RuntimeError(
            f"Database initialization failed for DATABASE_URL '{DATABASE_URL}'. "
            "Ensure the path is valid and writable."
        ) from exc
