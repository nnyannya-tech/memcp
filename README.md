# memcp — Agent Memory

Persistent memory for Claude Code. Sessions are automatically stored in a local SQLite database and exposed via MCP, so Claude can search its own history across sessions.

---

## The problem

Claude Code starts every session from scratch. Ask it about a bug you fixed last week, an architectural decision you made last month, or a library you evaluated last quarter — it has no idea. Every session is an island.

memcp fixes that. When a session ends, the log is automatically ingested. In the next session, Claude can search and retrieve anything from past work.

```
User: How did we handle JWT refresh token rotation in the auth service?
Claude: [calls search_memory("JWT refresh token rotation")]
        Found session from 2026-06-10 — "Auth service hardening"
        You used a sliding window with Redis for token revocation...
```

---

## How it works

```
Claude Code session ends
        │
        ▼
SessionEnd hook fires automatically
        │
        ▼
memcp ingest-new   scans configured log directories for new .jsonl files
        │
        ▼
SQLite (FTS5) stores sessions, messages, and tool calls
        │
        ▼
Next session: Claude calls search_memory / read_session via MCP
```

All data stays on your machine. No cloud, no telemetry.

---

## Requirements

- macOS or Linux
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Claude Code

---

## Quick start

```bash
git clone https://github.com/nnyannya-tech/memcp.git
cd memcp
uv sync
uv run memcp setup
```

Then **restart Claude Code**. That's it.

`memcp setup` does five things in one command:

1. Creates `~/.agent-memory/` and initialises the SQLite database
2. Writes a default `~/.agent-memory/config.yaml` you can edit
3. Registers the MCP server in `~/.claude.json`
4. Adds a SessionEnd hook to `~/.claude/settings.json` for automatic ingestion
5. (Future sessions are now ingested automatically on end)

---

## MCP tools

Defined in `src/memcp/mcp/server.py`. Claude calls these automatically when relevant; you can also invoke them explicitly in chat.

| Tool | Description |
|------|-------------|
| `search_memory(query, limit)` | Full-text search across all past sessions |
| `read_session(session_id, query, max_messages)` | Read a session transcript; `query` filters to matching messages only |
| `list_recent_sessions(limit)` | List sessions in reverse chronological order |
| `ingest_session(path)` | Manually ingest a specific `.jsonl` file |

`search_memory` and `read_session` are the primary tools. Claude uses them when the user references past work, asks about previous decisions, or needs historical context.

---

## CLI

```bash
# First-time setup
memcp setup

# Ingest any new sessions not yet in the database (runs automatically via hook)
memcp ingest-new

# Ingest a specific log file
memcp ingest ~/.claude/projects/<project>/<session-id>.jsonl
```

---

## Configuration

`~/.agent-memory/config.yaml` is created by `memcp setup`. Edit it to customise behaviour:

```yaml
sources:
  claude_code:
    scan_dir: ~/.claude/projects   # where Claude Code stores session logs
    enabled: true
```

The config is optional — defaults work out of the box.

---

## Contributing

```bash
uv sync --dev
uv run pytest              # run tests
uv run ruff check . --fix  # lint
uv run ruff format .       # format
uv run mypy src/           # type check
```

All PRs must pass CI (ruff + mypy + pytest). Open a PR against `main`.

### Adding a parser for another agent

memcp is designed to support multiple agents. Each agent needs:

1. A parser — `src/memcp/ingest/parsers/<agent>.py` implementing `ParseFn`:
   ```python
   ParseFn = Callable[[Path], tuple[Session, list[Message], list[ToolCall]]]
   ```
2. Registration in `src/memcp/ingest/sources.py:get_sources()`
3. A config key in `DEFAULT_CONFIG_YAML` in `src/memcp/config.py`

---

## Roadmap

### Near-term
- [ ] `memcp status` — show ingestion stats (sessions stored, last ingested, DB size)
- [ ] Cursor support — parse Cursor session logs (needs format investigation)
- [ ] Windsurf / Cline support — same approach as Cursor

### Medium-term
- [ ] Semantic search — hybrid FTS + embedding vectors for better recall on paraphrased queries
- [ ] Memory extraction — distil key facts and decisions from sessions into a compact memory store
- [ ] `memcp search <query>` — CLI search without opening Claude Code

### Out of scope for now
- Windows support
- Cloud sync
- GUI / web dashboard

---

## License

MIT — see [LICENSE](LICENSE)
