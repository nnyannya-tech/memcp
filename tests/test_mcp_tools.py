import json
import sqlite3
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import memcp.mcp.server as server
from memcp.storage import repository as repo
from memcp.storage.db import connect, init_schema
from memcp.storage.models import Message, Session, ToolCall


@pytest.fixture
def db() -> Generator[sqlite3.Connection, None, None]:
    c = connect()
    init_schema(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def patch_conn(db: sqlite3.Connection) -> Generator[None, None, None]:
    with patch.object(server, "_conn", return_value=db):
        yield


def _stored_session(
    conn: sqlite3.Connection,
    id: str = "sess-001",
    title: str = "Test session",
    repository: str = "/code/app",
    branch: str = "main",
    content: str = "JWT authentication implementation",
) -> None:
    session = Session(
        id=id,
        repository=repository,
        branch=branch,
        started_at=datetime(2026, 6, 23, 10, 0),
        ended_at=datetime(2026, 6, 23, 10, 30),
        title=title,
        path=f"/tmp/{id}.jsonl",
    )
    messages = [
        Message(
            id=f"msg_{id}",
            session_id=id,
            role="user",
            content=content,
            timestamp=datetime(2026, 6, 23, 10, 0, 1),
        )
    ]
    repo.insert_session(conn, session, messages, [])


class TestIngestSession:
    def test_ingest_real_log(self, tmp_path: Path, db: sqlite3.Connection) -> None:
        session_id = "test-ingest-abc"
        log = tmp_path / f"{session_id}.jsonl"
        records = [
            {"type": "ai-title", "aiTitle": "Fix login bug", "sessionId": session_id},
            {
                "type": "system",
                "subtype": "turn_duration",
                "timestamp": "2026-06-23T10:00:00.000Z",
                "cwd": "/code/app",
                "gitBranch": "fix/login",
                "sessionId": session_id,
            },
            {
                "type": "user",
                "isSidechain": False,
                "promptId": "p-1",
                "message": {"role": "user", "content": "Fix the login bug"},
            },
        ]
        log.write_text("\n".join(json.dumps(r) for r in records))

        result = server.ingest_session(str(log))

        assert "Fix login bug" in result
        assert "Messages   : 1" in result
        assert repo.session_exists(db, session_id)

    def test_ingest_missing_file(self) -> None:
        result = server.ingest_session("/nonexistent/path/session.jsonl")
        assert "Error" in result

    def test_ingest_duplicate_is_skipped(self, tmp_path: Path, db: sqlite3.Connection) -> None:
        session_id = "dup-session"
        log = tmp_path / f"{session_id}.jsonl"
        records = [
            {
                "type": "system",
                "subtype": "turn_duration",
                "timestamp": "2026-06-23T10:00:00.000Z",
                "cwd": "/code",
                "gitBranch": "main",
                "sessionId": session_id,
            },
            {
                "type": "user",
                "isSidechain": False,
                "promptId": "p-1",
                "message": {"role": "user", "content": "hello"},
            },
        ]
        log.write_text("\n".join(json.dumps(r) for r in records))

        server.ingest_session(str(log))
        result = server.ingest_session(str(log))

        assert "Already ingested" in result


class TestSearchMemory:
    def test_finds_matching_session(self, db: sqlite3.Connection) -> None:
        _stored_session(db, content="JWT authentication RS256 signing")
        result = server.search_memory("JWT")
        assert "Test session" in result
        assert "sess-001" in result

    def test_no_match_returns_message(self, db: sqlite3.Connection) -> None:
        _stored_session(db, content="unrelated content")
        result = server.search_memory("xyzzy_not_found")
        assert "No sessions found" in result

    def test_result_includes_snippet(self, db: sqlite3.Connection) -> None:
        _stored_session(db, content="race condition in payment processor")
        result = server.search_memory("race condition")
        assert "Snippet" in result

    def test_limit_respected(self, db: sqlite3.Connection) -> None:
        for i in range(5):
            _stored_session(
                db, id=f"sess-{i:03}", title=f"Session {i}", content="JWT token auth"
            )
        result = server.search_memory("JWT", limit=2)
        assert result.count("Session ID") == 2


class TestReadSession:
    def test_returns_transcript(self, db: sqlite3.Connection) -> None:
        _stored_session(db, content="Here is the implementation")
        result = server.read_session("sess-001")
        assert "Test session" in result
        assert "Here is the implementation" in result

    def test_not_found_returns_message(self) -> None:
        result = server.read_session("nonexistent-id")
        assert "not found" in result

    def test_query_filters_to_matching_messages(self, db: sqlite3.Connection) -> None:
        session = Session(
            id="sess-q",
            repository="/code",
            branch="main",
            started_at=datetime(2026, 6, 23, 10, 0),
            ended_at=None,
            title="Mixed session",
            path="/tmp/sess-q.jsonl",
        )
        messages = [
            Message(id="m1", session_id="sess-q", role="user",
                    content="Let's implement JWT authentication", timestamp=datetime(2026, 6, 23, 10, 0)),
            Message(id="m2", session_id="sess-q", role="assistant",
                    content="I'll use RS256 for JWT signing", timestamp=datetime(2026, 6, 23, 10, 1)),
            Message(id="m3", session_id="sess-q", role="user",
                    content="Now fix the database migration", timestamp=datetime(2026, 6, 23, 10, 2)),
            Message(id="m4", session_id="sess-q", role="assistant",
                    content="Running ALTER TABLE users", timestamp=datetime(2026, 6, 23, 10, 3)),
        ]
        repo.insert_session(db, session, messages, [])

        result = server.read_session("sess-q", query="JWT")
        assert "JWT" in result
        assert "ALTER TABLE" not in result

    def test_without_query_returns_first_messages(self, db: sqlite3.Connection) -> None:
        session = Session(
            id="sess-head",
            repository="/code",
            branch="main",
            started_at=datetime(2026, 6, 23, 10, 0),
            ended_at=None,
            title="Long session",
            path="/tmp/sess-head.jsonl",
        )
        messages = [
            Message(id=f"m{i}", session_id="sess-head", role="user",
                    content=f"message {i}", timestamp=datetime(2026, 6, 23, 10, i))
            for i in range(30)
        ]
        repo.insert_session(db, session, messages, [])

        result = server.read_session("sess-head", max_messages=5)
        assert "message 0" in result
        assert "message 29" not in result

    def test_includes_tool_calls(self, db: sqlite3.Connection) -> None:
        session = Session(
            id="sess-tc",
            repository="/code",
            branch="main",
            started_at=datetime(2026, 6, 23, 10, 0),
            ended_at=None,
            title="Tool call session",
            path="/tmp/sess-tc.jsonl",
        )
        tool_calls = [
            ToolCall(
                id="tc-1",
                session_id="sess-tc",
                tool_name="Bash",
                arguments='{"command": "ls"}',
                result="file1.py",
            )
        ]
        repo.insert_session(db, session, [], tool_calls)

        result = server.read_session("sess-tc")
        assert "Bash" in result
        assert "file1.py" in result


class TestListRecentSessions:
    def test_lists_sessions_newest_first(self, db: sqlite3.Connection) -> None:
        _stored_session(db, id="sess-old", title="Old work")
        session_new = Session(
            id="sess-new",
            repository="/code",
            branch="main",
            started_at=datetime(2026, 6, 24, 9, 0),
            ended_at=datetime(2026, 6, 24, 9, 30),
            title="New work",
            path="/tmp/sess-new.jsonl",
        )
        repo.insert_session(db, session_new, [], [])

        result = server.list_recent_sessions()
        assert result.index("New work") < result.index("Old work")

    def test_empty_db_returns_guidance(self) -> None:
        result = server.list_recent_sessions()
        assert "ingest_session" in result

    def test_shows_duration(self, db: sqlite3.Connection) -> None:
        _stored_session(db)
        result = server.list_recent_sessions()
        assert "30 min" in result
