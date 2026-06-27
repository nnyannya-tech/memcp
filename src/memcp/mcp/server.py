import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from memcp.config import load as load_config
from memcp.ingest.parsers.claude import parse as claude_parse
from memcp.ingest.pipeline import ingest_one
from memcp.search.fts import search as fts_search
from memcp.storage import repository as repo
from memcp.storage.db import connect, init_schema

mcp = FastMCP("agent-memory")

_db_conn: sqlite3.Connection | None = None


def _conn() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        cfg = load_config()
        cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
        _db_conn = connect(cfg.db_path)
        init_schema(_db_conn)
    return _db_conn


@mcp.tool()
def ingest_session(path: str) -> str:
    """
    Ingest a Claude Code JSONL session log into the memory database.
    Call this to store a finished session so it can be searched in the future.
    The path should point to a .jsonl file under ~/.claude/projects/.
    """
    log_path = Path(path)
    if not log_path.exists():
        return f"Error: file not found: {path}"

    result = ingest_one(_conn(), log_path, claude_parse)

    if not result.was_new:
        return f"Already ingested: {result.session.title!r} ({result.session.id})"

    s = result.session
    return (
        f"Ingested: {s.title!r}\n"
        f"  Session ID : {s.id}\n"
        f"  Repository : {s.repository}\n"
        f"  Branch     : {s.branch}\n"
        f"  Messages   : {len(result.messages)}\n"
        f"  Tool calls : {len(result.tool_calls)}"
    )


@mcp.tool()
def search_memory(query: str, limit: int = 5) -> str:
    """
    Search past coding sessions by keyword or natural language query.
    Use this when the user asks about previous work, past implementations,
    historical context, bugs, or failures — for example:
    "JWT authentication", "race condition fix", "database migration error".
    Returns a ranked list of matching sessions with context snippets.
    """
    results = fts_search(_conn(), query, limit)

    if not results:
        return f"No sessions found matching {query!r}."

    lines = [f"Found {len(results)} session(s) matching {query!r}:\n"]
    for i, result in enumerate(results, 1):
        s = result.session
        date = s.started_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"{i}. [{date}] {s.title!r}")
        lines.append(f"   Repository : {s.repository}")
        lines.append(f"   Branch     : {s.branch}")
        lines.append(f"   Session ID : {s.id}")
        lines.append(f"   Snippet    : ...{result.snippet}...")
        lines.append("")

    lines.append("To read the full transcript: use read_session(session_id=...)")
    return "\n".join(lines)


@mcp.tool()
def read_session(session_id: str, query: str = "", max_messages: int = 20) -> str:
    """
    Read messages from a stored session.
    If query is provided, returns only messages matching that query (up to max_messages).
    If query is omitted, returns the first max_messages messages chronologically.
    Use query to drill into a specific topic found via search_memory.
    Example: read_session(session_id="abc", query="JWT authentication")
    """
    conn = _conn()
    session = repo.get_session(conn, session_id)
    if session is None:
        return f"Session not found: {session_id}"

    if query:
        messages = repo.get_messages_matching(conn, session_id, query, max_messages)
    else:
        messages = repo.get_messages(conn, session_id)[:max_messages]

    tool_calls = repo.get_tool_calls(conn, session_id)

    lines = [
        f"Session  : {session.title}",
        f"Repo     : {session.repository}  [{session.branch}]",
        f"Started  : {session.started_at.strftime('%Y-%m-%d %H:%M')}",
        "─" * 60,
        "",
    ]

    for msg in messages:
        ts = msg.timestamp.strftime("%H:%M")
        label = "User" if msg.role == "user" else "Assistant"
        lines.append(f"[{ts}] {label}")
        lines.append(msg.content[:2000])
        lines.append("")

    if tool_calls:
        lines.append("─" * 60)
        lines.append(f"Tool calls ({len(tool_calls)}):")
        for tc in tool_calls:
            lines.append(f"  {tc.tool_name}  {tc.arguments[:120]}")
            if tc.result:
                lines.append(f"  → {tc.result[:120]}")

    return "\n".join(lines)


@mcp.tool()
def list_recent_sessions(limit: int = 10) -> str:
    """
    List the most recently stored sessions in reverse chronological order.
    Use this when the user asks 'what have we been working on?',
    'show recent sessions', or wants to browse past work without a specific query.
    """
    sessions = repo.list_recent(_conn(), limit)

    if not sessions:
        return "No sessions stored yet. Use ingest_session(path=...) to add one."

    lines = [f"Recent {len(sessions)} session(s):\n"]
    for i, s in enumerate(sessions, 1):
        date = s.started_at.strftime("%Y-%m-%d %H:%M")
        duration = ""
        if s.ended_at:
            mins = int((s.ended_at - s.started_at).total_seconds() / 60)
            duration = f" ({mins} min)"
        lines.append(f"{i:2}. [{date}]{duration}  {s.title!r}")
        lines.append(f"      {s.repository}  [{s.branch}]")
        lines.append(f"      {s.id}")
        lines.append("")

    lines.append("To search: use search_memory(query=...)")
    lines.append("To read:   use read_session(session_id=...)")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
