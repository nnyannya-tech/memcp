import sqlite3
from collections.abc import Generator
from datetime import datetime

import pytest

from memcp.storage import repository as repo
from memcp.storage.db import connect, init_schema
from memcp.storage.models import Message, Session, ToolCall


@pytest.fixture
def conn() -> Generator[sqlite3.Connection, None, None]:
    c = connect()
    init_schema(c)
    yield c
    c.close()


def _session(id: str = "sess_001", started_at: datetime = datetime(2026, 6, 23, 10, 0)) -> Session:
    return Session(
        id=id,
        repository="github.com/acme/backend",
        branch="main",
        started_at=started_at,
        ended_at=datetime(2026, 6, 23, 10, 30),
        title="Test session",
        path="/tmp/test.jsonl",
    )


def _message(session_id: str = "sess_001", role: str = "user", content: str = "hello") -> Message:
    return Message(
        id=f"msg_{role}_{session_id}",
        session_id=session_id,
        role=role,
        content=content,
        timestamp=datetime(2026, 6, 23, 10, 0, 1),
    )


def _tool_call(session_id: str = "sess_001") -> ToolCall:
    return ToolCall(
        id=f"tc_{session_id}",
        session_id=session_id,
        tool_name="read_file",
        arguments='{"path": "src/main.py"}',
        result="file content here",
    )


class TestInsertAndGet:
    def test_insert_and_get_session(self, conn: sqlite3.Connection) -> None:
        repo.insert_session(conn, _session(), [], [])
        result = repo.get_session(conn, "sess_001")
        assert result is not None
        assert result.id == "sess_001"
        assert result.title == "Test session"
        assert result.repository == "github.com/acme/backend"

    def test_get_missing_session_returns_none(self, conn: sqlite3.Connection) -> None:
        assert repo.get_session(conn, "nonexistent") is None

    def test_ended_at_none_roundtrips(self, conn: sqlite3.Connection) -> None:
        s = _session()
        s.ended_at = None
        repo.insert_session(conn, s, [], [])
        result = repo.get_session(conn, "sess_001")
        assert result is not None
        assert result.ended_at is None

    def test_messages_are_stored_and_ordered(self, conn: sqlite3.Connection) -> None:
        msgs = [
            _message(role="user", content="first"),
            _message(role="assistant", content="second"),
        ]
        # give distinct ids and timestamps
        msgs[0].id = "msg_1"
        msgs[0].timestamp = datetime(2026, 6, 23, 10, 0, 1)
        msgs[1].id = "msg_2"
        msgs[1].timestamp = datetime(2026, 6, 23, 10, 0, 2)
        repo.insert_session(conn, _session(), msgs, [])
        result = repo.get_messages(conn, "sess_001")
        assert len(result) == 2
        assert result[0].content == "first"
        assert result[1].content == "second"

    def test_tool_calls_are_stored(self, conn: sqlite3.Connection) -> None:
        repo.insert_session(conn, _session(), [], [_tool_call()])
        tcs = repo.get_tool_calls(conn, "sess_001")
        assert len(tcs) == 1
        assert tcs[0].tool_name == "read_file"

    def test_duplicate_session_raises(self, conn: sqlite3.Connection) -> None:
        repo.insert_session(conn, _session(), [], [])
        with pytest.raises(Exception):
            repo.insert_session(conn, _session(), [], [])


class TestSessionExists:
    def test_returns_false_before_insert(self, conn: sqlite3.Connection) -> None:
        assert not repo.session_exists(conn, "sess_001")

    def test_returns_true_after_insert(self, conn: sqlite3.Connection) -> None:
        repo.insert_session(conn, _session(), [], [])
        assert repo.session_exists(conn, "sess_001")


class TestListRecent:
    def test_returns_latest_first(self, conn: sqlite3.Connection) -> None:
        repo.insert_session(conn, _session("sess_001", datetime(2026, 6, 23, 9, 0)), [], [])
        repo.insert_session(conn, _session("sess_002", datetime(2026, 6, 24, 9, 0)), [], [])
        results = repo.list_recent(conn)
        assert results[0].id == "sess_002"
        assert results[1].id == "sess_001"

    def test_respects_limit(self, conn: sqlite3.Connection) -> None:
        for i in range(5):
            repo.insert_session(
                conn,
                _session(f"sess_{i:03}", datetime(2026, 6, i + 1, 0, 0)),
                [],
                [],
            )
        assert len(repo.list_recent(conn, limit=3)) == 3

    def test_empty_db_returns_empty_list(self, conn: sqlite3.Connection) -> None:
        assert repo.list_recent(conn) == []
