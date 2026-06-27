import sqlite3
from dataclasses import dataclass

from memcp.storage.models import Session
from memcp.storage.repository import row_to_session


@dataclass
class SearchResult:
    session: Session
    snippet: str
    rank: float


def search(conn: sqlite3.Connection, query: str, limit: int = 5) -> list[SearchResult]:
    """Full-text search over session content. Returns sessions ranked by relevance."""
    rows = conn.execute(
        """
        SELECT s.*, fts.rank,
               snippet(sessions_fts, 1, '', '', '...', 20) AS snippet
        FROM sessions_fts fts
        JOIN sessions s ON s.id = fts.session_id
        WHERE sessions_fts MATCH ?
        ORDER BY fts.rank
        LIMIT ?
        """,
        (_escape_query(query), limit),
    ).fetchall()

    return [
        SearchResult(
            session=row_to_session(row),
            snippet=row["snippet"],
            rank=row["rank"],
        )
        for row in rows
    ]


def _escape_query(query: str) -> str:
    """Wrap each token in double quotes to avoid FTS5 syntax errors.

    Strips internal double-quotes from tokens so user input cannot break
    FTS5 phrase syntax (e.g. hello"world → "helloworld").
    """
    escaped = []
    for token in query.split():
        clean = token.replace('"', "")
        if clean:
            escaped.append(f'"{clean}"')
    return " ".join(escaped)
