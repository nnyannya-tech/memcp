import sqlite3
from collections.abc import Generator
from datetime import datetime

import pytest

from memcp.search.fts import search
from memcp.storage import repository as repo
from memcp.storage.db import connect, init_schema
from memcp.storage.models import Message, Session, ToolCall


@pytest.fixture
def conn() -> Generator[sqlite3.Connection, None, None]:
    c = connect()
    init_schema(c)
    yield c
    c.close()


def _insert(
    conn: sqlite3.Connection,
    id: str,
    title: str,
    messages: list[str],
    tool_calls: list[tuple[str, str]] | None = None,
    repository: str = "github.com/acme/backend",
) -> None:
    session = Session(
        id=id,
        repository=repository,
        branch="main",
        started_at=datetime(2026, 6, 23, 10, 0),
        ended_at=None,
        title=title,
        path=f"/tmp/{id}.jsonl",
    )
    msgs = [
        Message(
            id=f"msg_{id}_{i}",
            session_id=id,
            role="user" if i % 2 == 0 else "assistant",
            content=content,
            timestamp=datetime(2026, 6, 23, 10, i),
        )
        for i, content in enumerate(messages)
    ]
    tcs = [
        ToolCall(
            id=f"tc_{id}_{i}",
            session_id=id,
            tool_name=name,
            arguments=args,
            result="",
        )
        for i, (name, args) in enumerate(tool_calls or [])
    ]
    repo.insert_session(conn, session, msgs, tcs)


class TestSearch:
    def test_finds_session_by_message_content(self, conn: sqlite3.Connection) -> None:
        _insert(conn, "sess_jwt", "Auth work", ["Implement JWT authentication with RS256"])
        _insert(conn, "sess_other", "Other work", ["Fix the database connection timeout"])

        results = search(conn, "JWT")
        assert len(results) == 1
        assert results[0].session.id == "sess_jwt"

    def test_finds_session_by_title(self, conn: sqlite3.Connection) -> None:
        _insert(conn, "sess_redis", "Redis Lock Investigation", ["checking deadlock"])
        _insert(conn, "sess_db", "DB migration", ["alter table users"])

        results = search(conn, "Redis")
        assert len(results) == 1
        assert results[0].session.id == "sess_redis"

    def test_finds_session_by_tool_call(self, conn: sqlite3.Connection) -> None:
        _insert(
            conn,
            "sess_read",
            "File editing",
            ["let me read the file"],
            tool_calls=[("read_file", '{"path": "src/auth.py"}')],
        )
        _insert(conn, "sess_other", "Other", ["unrelated content"])

        results = search(conn, "auth.py")
        assert len(results) == 1
        assert results[0].session.id == "sess_read"

    def test_finds_session_by_repository(self, conn: sqlite3.Connection) -> None:
        _insert(conn, "sess_a", "Work A", ["hello"], repository="github.com/acme/payments")
        _insert(conn, "sess_b", "Work B", ["hello"], repository="github.com/acme/backend")

        results = search(conn, "payments")
        assert len(results) == 1
        assert results[0].session.id == "sess_a"

    def test_returns_empty_for_no_match(self, conn: sqlite3.Connection) -> None:
        _insert(conn, "sess_a", "Some session", ["nothing relevant"])

        assert search(conn, "xyzzy") == []

    def test_respects_limit(self, conn: sqlite3.Connection) -> None:
        for i in range(5):
            _insert(conn, f"sess_{i}", f"Session {i}", ["JWT token authentication"])

        results = search(conn, "JWT", limit=3)
        assert len(results) == 3

    def test_multi_word_query(self, conn: sqlite3.Connection) -> None:
        _insert(conn, "sess_race", "Race fix", ["race condition in payment processor"])
        _insert(conn, "sess_other", "Other", ["race unrelated"])

        results = search(conn, "race condition")
        assert any(r.session.id == "sess_race" for r in results)

    def test_result_has_snippet(self, conn: sqlite3.Connection) -> None:
        _insert(conn, "sess_jwt", "Auth", ["Implement JWT authentication"])

        results = search(conn, "JWT")
        assert results[0].snippet != ""

    def test_empty_db_returns_empty(self, conn: sqlite3.Connection) -> None:
        assert search(conn, "anything") == []
