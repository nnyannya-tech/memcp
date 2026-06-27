"""memcp CLI — setup and maintenance commands."""

import json
import shlex
import sqlite3
import sys
from pathlib import Path

import click

_CLAUDE_JSON = Path.home() / ".claude.json"
_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"


def _open_conn() -> sqlite3.Connection:
    from memcp.config import load as load_config
    from memcp.storage.db import connect, init_schema

    cfg = load_config()
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    c = connect(cfg.db_path)
    init_schema(c)
    return c


@click.group()
def main() -> None:
    """Agent Memory — long-term memory for AI coding agents."""


# ── setup ─────────────────────────────────────────────────────────────────────


@main.command()
def setup() -> None:
    """One-command bootstrap: create DB, register MCP server, add auto-ingest hook."""
    click.echo("Agent Memory setup\n")

    from memcp.config import load as load_config

    cfg = load_config()
    storage = cfg.db_path.parent
    storage.mkdir(parents=True, exist_ok=True)
    click.echo(f"  [1/5] Storage directory  {storage}")

    _copy_config_example(storage)
    click.echo(f"  [2/5] Config template    {storage / 'config.yaml'}")

    conn = _open_conn()
    conn.close()
    click.echo(f"  [3/5] Database           {cfg.db_path}")

    _register_mcp_server()
    click.echo(f"  [4/5] MCP server         {_CLAUDE_JSON}")

    _register_session_end_hook()
    click.echo(f"  [5/5] SessionEnd hook    {_CLAUDE_SETTINGS}")

    click.echo("\nDone. Restart Claude Code to activate.")
    click.echo(f"To customise scan directories, edit {storage / 'config.yaml'}")


def _copy_config_example(storage: Path) -> None:
    dest = storage / "config.yaml"
    if dest.exists():
        return
    from memcp.config import DEFAULT_CONFIG_YAML

    dest.write_text(DEFAULT_CONFIG_YAML)


def _python_and_env() -> tuple[str, dict[str, str]]:
    """Return (python_executable, env) for registering the MCP server.

    For proper installs (site-packages) env is empty.
    For dev checkouts, PYTHONPATH must point to src/ so the module is importable.
    """
    python = sys.executable
    import memcp

    pkg_parent = Path(memcp.__file__).parent.parent
    if "site-packages" in str(pkg_parent) or "dist-packages" in str(pkg_parent):
        return python, {}
    return python, {"PYTHONPATH": str(pkg_parent)}


def _register_mcp_server() -> None:
    python, env = _python_and_env()

    data: dict[str, object] = {}
    if _CLAUDE_JSON.exists():
        try:
            data = json.loads(_CLAUDE_JSON.read_text())
        except json.JSONDecodeError:
            data = {}

    entry: dict[str, object] = {
        "type": "stdio",
        "command": python,
        "args": ["-m", "memcp.mcp.server"],
    }
    if env:
        entry["env"] = env

    if not isinstance(data.get("mcpServers"), dict):
        data["mcpServers"] = {}
    data["mcpServers"]["agent-memory"] = entry  # type: ignore[index]
    _CLAUDE_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _register_session_end_hook() -> None:
    memcp_bin = str(Path(sys.executable).parent / "memcp")
    cmd = f"{shlex.quote(memcp_bin)} ingest-new"

    data: dict[str, object] = {}
    if _CLAUDE_SETTINGS.exists():
        try:
            data = json.loads(_CLAUDE_SETTINGS.read_text())
        except json.JSONDecodeError:
            data = {}

    if not isinstance(data.get("hooks"), dict):
        data["hooks"] = {}
    hooks = data["hooks"]
    assert isinstance(hooks, dict)
    if not isinstance(hooks.get("SessionEnd"), list):
        hooks["SessionEnd"] = []
    session_end_hooks = hooks["SessionEnd"]
    assert isinstance(session_end_hooks, list)

    # Replace any existing memcp ingest-new entries (handles stale paths from re-installs)
    kept: list[object] = []
    for entry in session_end_hooks:
        if isinstance(entry, dict):
            inner = entry.get("hooks", [])
            if isinstance(inner, list) and any(
                isinstance(h, dict) and "memcp ingest-new" in str(h.get("command", ""))
                for h in inner
            ):
                continue
        kept.append(entry)

    kept.append({"hooks": [{"type": "command", "command": cmd}]})
    hooks["SessionEnd"] = kept
    _CLAUDE_SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# ── ingest-new ────────────────────────────────────────────────────────────────


@main.command("ingest-new")
def ingest_new() -> None:
    """Ingest any session logs not yet in the database.

    Called automatically by the SessionEnd hook. Iterates all configured
    sources (see ~/.agent-memory/config.yaml).
    """
    from memcp.config import load as load_config
    from memcp.ingest.pipeline import ingest_one
    from memcp.ingest.sources import get_sources
    from memcp.storage import repository as repo

    cfg = load_config()
    conn = _open_conn()
    ingested = 0
    errors = 0

    for source in get_sources(cfg):
        if not source.scan_dir.exists():
            continue
        for log_path in sorted(source.scan_dir.rglob("*.jsonl")):
            # Fast pre-check before parsing (valid because Claude session_id == path.stem)
            if repo.session_exists(conn, log_path.stem):
                continue
            try:
                result = ingest_one(conn, log_path, source.parse_fn)
                if result.was_new:
                    ingested += 1
            except Exception as exc:
                click.echo(f"[memcp] skip {log_path.name}: {exc}", err=True)
                errors += 1

    conn.close()
    if ingested:
        suffix = f", {errors} error(s)" if errors else ""
        click.echo(f"[memcp] ingested {ingested} session(s){suffix}")


# ── ingest ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("path")
def ingest(path: str) -> None:
    """Ingest a specific session log file into the database."""
    from memcp.ingest.parsers.claude import parse as claude_parse
    from memcp.ingest.pipeline import ingest_one

    log_path = Path(path)
    if not log_path.exists():
        click.echo(f"Error: file not found: {path}", err=True)
        sys.exit(1)

    conn = _open_conn()
    result = ingest_one(conn, log_path, claude_parse)
    conn.close()

    if not result.was_new:
        click.echo(f"Already ingested: {result.session.title!r} ({result.session.id})")
        return

    s = result.session
    click.echo(
        f"Ingested: {s.title!r}\n"
        f"  Session ID : {s.id}\n"
        f"  Repository : {s.repository}\n"
        f"  Branch     : {s.branch}\n"
        f"  Messages   : {len(result.messages)}\n"
        f"  Tool calls : {len(result.tool_calls)}"
    )
