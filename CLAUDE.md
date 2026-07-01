# memcp — Agent Memory

memcp gives AI coding agents persistent memory across sessions. When a Claude Code session ends, logs are automatically ingested into a local SQLite database. Agents can then search and retrieve past work via MCP tools exposed to Claude Code.

The core loop:
1. Session ends → SessionEnd hook fires → `memcp ingest-new` scans `~/.claude/projects/` for new logs
2. New session → agent calls `search_memory("JWT auth")` → retrieves relevant past sessions
3. Agent calls `read_session(session_id, query="JWT")` → gets filtered messages from that session

**Memory usage:** At the start of each session, or whenever the user references prior work ("last time", "earlier", "we decided", "what was that X again"), proactively call `search_memory` with relevant keywords before responding.

All data stays local. No cloud, no external services.

## Development

```bash
uv sync --dev
uv run pytest          # must pass before committing
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy src/       # type check (strict)
```

All PRs must pass CI. Direct pushes to `main` are not allowed.

## Non-obvious constraints

**Testing**
- Never mock SQLite. Use `sqlite3.connect(":memory:")` — real query behavior (FTS5, foreign keys) must be tested.
- Each test file is independent; no shared global state between test modules.

**Module boundaries**
- `storage/` has no knowledge of `mcp/` or `cli/`. It only exposes data access functions.
- `search/` only imports from `storage/`. It does not call parsers or MCP tools.
- `mcp/server.py` and `cli.py` are the only places that orchestrate across layers.

**Types**
- All public functions must have type hints. `uv run mypy src/` must pass in strict mode before opening a PR.
- Parsers are plain functions, not classes: `ParseFn = Callable[[Path], tuple[Session, list[Message], list[ToolCall]]]`. See `src/memcp/ingest/parsers/base.py`.

## Adding a parser for a new agent

1. Create `src/memcp/ingest/parsers/<agent>.py` that implements `ParseFn`
2. Register it in `src/memcp/ingest/sources.py:get_sources()` with its scan directory
3. Add the corresponding config key to `DEFAULT_CONFIG_YAML` in `src/memcp/config.py`
