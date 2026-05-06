"""Unit tests for app/websocket.py (ConnectionManager)."""

from unittest.mock import AsyncMock

import pytest

from app.websocket import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


def _make_ws():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


async def test_connect_adds_websocket_to_session(manager):
    ws = _make_ws()
    await manager.connect(ws, "session-1")
    assert ws in manager.active_connections["session-1"]
    ws.accept.assert_awaited_once()


async def test_connect_multiple_sessions_are_isolated(manager):
    ws1, ws2 = _make_ws(), _make_ws()
    await manager.connect(ws1, "session-1")
    await manager.connect(ws2, "session-2")
    assert ws1 in manager.active_connections["session-1"]
    assert ws2 in manager.active_connections["session-2"]
    assert ws1 not in manager.active_connections.get("session-2", set())


async def test_connect_multiple_clients_same_session(manager):
    ws1, ws2 = _make_ws(), _make_ws()
    await manager.connect(ws1, "session-1")
    await manager.connect(ws2, "session-1")
    assert {ws1, ws2} == manager.active_connections["session-1"]


def test_disconnect_removes_websocket(manager):
    ws = _make_ws()
    manager.active_connections["session-1"] = {ws}
    manager.disconnect(ws, "session-1")
    assert ws not in manager.active_connections.get("session-1", set())


def test_disconnect_removes_empty_session_bucket(manager):
    ws = _make_ws()
    manager.active_connections["session-1"] = {ws}
    manager.disconnect(ws, "session-1")
    assert "session-1" not in manager.active_connections


def test_disconnect_unknown_session_does_not_raise(manager):
    ws = _make_ws()
    manager.disconnect(ws, "nonexistent-session")  # should not raise


async def test_broadcast_sends_message_to_all_connections(manager):
    ws1, ws2 = _make_ws(), _make_ws()
    manager.active_connections["session-1"] = {ws1, ws2}
    msg = {"type": "test", "data": {}}
    await manager.broadcast("session-1", msg)
    ws1.send_json.assert_awaited_once_with(msg)
    ws2.send_json.assert_awaited_once_with(msg)


async def test_broadcast_to_empty_session_does_nothing(manager):
    # No exception should be raised for a session with no connections
    await manager.broadcast("no-such-session", {"type": "ping"})


async def test_broadcast_drops_dead_connections(manager):
    ws_alive = _make_ws()
    ws_dead = _make_ws()
    ws_dead.send_json.side_effect = Exception("connection closed")

    manager.active_connections["session-1"] = {ws_alive, ws_dead}
    await manager.broadcast("session-1", {"type": "test"})

    # Dead connection should have been removed
    assert ws_dead not in manager.active_connections["session-1"]
    assert ws_alive in manager.active_connections["session-1"]
