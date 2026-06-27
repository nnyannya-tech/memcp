"""Single entry point for parsing and storing one session log."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from memcp.ingest.parsers.base import ParseFn
from memcp.storage import repository as repo
from memcp.storage.models import Message, Session, ToolCall


@dataclass
class IngestResult:
    session: Session
    messages: list[Message]
    tool_calls: list[ToolCall]
    was_new: bool


def ingest_one(conn: sqlite3.Connection, path: Path, parse_fn: ParseFn) -> IngestResult:
    """Parse *path* with *parse_fn* and store if not already in *conn*.

    Always returns a populated result; check ``was_new`` to distinguish
    first-time ingestion from a duplicate.
    """
    session, messages, tool_calls = parse_fn(path)
    was_new = not repo.session_exists(conn, session.id)
    if was_new:
        repo.insert_session(conn, session, messages, tool_calls)
    return IngestResult(session=session, messages=messages, tool_calls=tool_calls, was_new=was_new)
