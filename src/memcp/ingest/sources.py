"""Source registry — maps agent log directories to their parsers.

To add a new agent (e.g. Cursor):
1. Create src/memcp/ingest/parsers/cursor.py implementing ParseFn.
2. Add a "cursor" block to config.yaml under ``sources:``.
3. Register it in ``get_sources()`` below.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from memcp.config import Config
from memcp.ingest.parsers.base import ParseFn


@dataclass
class Source:
    name: str
    scan_dir: Path
    parse_fn: ParseFn
    enabled: bool = True
    since: datetime | None = None


def get_sources(cfg: Config) -> list[Source]:
    """Return enabled sources from *cfg*, each carrying the right parser."""
    sources: list[Source] = []
    raw = cfg.sources

    # ── Claude Code ───────────────────────────────────────────────────────────
    cc = raw.get("claude_code", {})
    if isinstance(cc, dict) and cc.get("enabled", True):
        from memcp.ingest.parsers.claude import parse as claude_parse

        scan_dir = Path(str(cc.get("scan_dir", "~/.claude/projects"))).expanduser()
        since_raw = cc.get("since")
        since = datetime.fromisoformat(str(since_raw)) if since_raw else None
        sources.append(
            Source(name="claude_code", scan_dir=scan_dir, parse_fn=claude_parse, since=since)
        )

    # ── Future agents ─────────────────────────────────────────────────────────
    # cursor = raw.get("cursor", {})
    # if isinstance(cursor, dict) and cursor.get("enabled", False):
    #     from memcp.ingest.parsers.cursor import parse as cursor_parse
    #     scan_dir = Path(str(cursor.get("scan_dir", "~/.cursor/logs"))).expanduser()
    #     sources.append(Source(name="cursor", scan_dir=scan_dir, parse_fn=cursor_parse))

    return sources
