import sqlite3
from datetime import datetime

from .models import Message, Session, ToolCall


def _fmt(dt: datetime) -> str:
    return dt.isoformat()


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s)


def row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        repository=row["repository"],
        branch=row["branch"],
        started_at=_parse(row["started_at"]),
        ended_at=_parse(row["ended_at"]) if row["ended_at"] else None,
        title=row["title"],
        path=row["path"],
    )


def session_exists(conn: sqlite3.Connection, session_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return row is not None


def insert_session(
    conn: sqlite3.Connection,
    session: Session,
    messages: list[Message],
    tool_calls: list[ToolCall],
) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO sessions (id, repository, branch, started_at, ended_at, title, path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.repository,
                session.branch,
                _fmt(session.started_at),
                _fmt(session.ended_at) if session.ended_at else None,
                session.title,
                session.path,
            ),
        )
        conn.executemany(
            "INSERT INTO messages (id, session_id, role, content, timestamp)"
            " VALUES (?, ?, ?, ?, ?)",
            [(m.id, m.session_id, m.role, m.content, _fmt(m.timestamp)) for m in messages],
        )
        conn.executemany(
            "INSERT INTO tool_calls (id, session_id, tool_name, arguments, result)"
            " VALUES (?, ?, ?, ?, ?)",
            [(tc.id, tc.session_id, tc.tool_name, tc.arguments, tc.result) for tc in tool_calls],
        )

        body_parts = [session.title, session.repository, session.branch]
        body_parts += [m.content for m in messages]
        body_parts += [f"{tc.tool_name} {tc.arguments}" for tc in tool_calls]
        body = " ".join(filter(None, body_parts))
        conn.execute(
            "INSERT INTO sessions_fts(session_id, body) VALUES (?, ?)",
            (session.id, body),
        )


def get_session(conn: sqlite3.Connection, session_id: str) -> Session | None:
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return row_to_session(row) if row else None


def get_messages(conn: sqlite3.Connection, session_id: str) -> list[Message]:
    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp", (session_id,)
    ).fetchall()
    return [
        Message(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            timestamp=_parse(row["timestamp"]),
        )
        for row in rows
    ]


def get_messages_matching(
    conn: sqlite3.Connection,
    session_id: str,
    query: str,
    limit: int = 20,
) -> list[Message]:
    """Return messages within a session whose content contains any query term."""
    all_messages = get_messages(conn, session_id)
    terms = [t.lower() for t in query.split() if t]
    matched = [m for m in all_messages if any(term in m.content.lower() for term in terms)]
    return matched[:limit]


def get_tool_calls(conn: sqlite3.Connection, session_id: str) -> list[ToolCall]:
    rows = conn.execute("SELECT * FROM tool_calls WHERE session_id = ?", (session_id,)).fetchall()
    return [
        ToolCall(
            id=row["id"],
            session_id=row["session_id"],
            tool_name=row["tool_name"],
            arguments=row["arguments"],
            result=row["result"],
        )
        for row in rows
    ]


def list_recent(conn: sqlite3.Connection, limit: int = 10) -> list[Session]:
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [row_to_session(row) for row in rows]
