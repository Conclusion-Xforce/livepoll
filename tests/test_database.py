"""Unit tests for app/database.py helper functions."""

from pathlib import Path

from app.database import _prepare_sqlite_path, _resolve_sqlite_file_path

# ---------------------------------------------------------------------------
# _resolve_sqlite_file_path
# ---------------------------------------------------------------------------


def test_resolve_empty_string_returns_none():
    assert _resolve_sqlite_file_path("") is None


def test_resolve_memory_returns_none():
    assert _resolve_sqlite_file_path(":memory:") is None


def test_resolve_relative_path():
    result = _resolve_sqlite_file_path("./livepoll.db")
    assert isinstance(result, Path)
    assert str(result).endswith("livepoll.db")


def test_resolve_absolute_path():
    result = _resolve_sqlite_file_path("/tmp/livepoll.db")
    assert result == Path("/tmp/livepoll.db")


def test_resolve_file_uri_memory_returns_none():
    assert _resolve_sqlite_file_path("file::memory:") is None


def test_resolve_file_uri_with_path():
    result = _resolve_sqlite_file_path("file:/tmp/mydb.db")
    assert result == Path("/tmp/mydb.db")


# ---------------------------------------------------------------------------
# _prepare_sqlite_path
# ---------------------------------------------------------------------------


def test_prepare_sqlite_path_skips_non_sqlite():
    # Should not raise or do any filesystem work for a Postgres URL
    _prepare_sqlite_path("postgresql+asyncpg://user:pass@localhost/db")


def test_prepare_sqlite_path_skips_memory():
    # In-memory SQLite needs no directory creation
    _prepare_sqlite_path("sqlite+aiosqlite:///:memory:")


def test_prepare_sqlite_path_creates_parent_directory(tmp_path):
    new_dir = tmp_path / "subdir" / "nested"
    db_url = f"sqlite+aiosqlite:///{new_dir}/test.db"
    _prepare_sqlite_path(db_url)
    assert new_dir.exists()
