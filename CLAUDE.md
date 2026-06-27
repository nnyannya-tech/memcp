# Agent Memory

Long-term memory for AI coding agents. Stores Claude Code sessions in SQLite and exposes them via MCP so agents can search their own history across sessions.

## Project Structure

```
memcp/
├── src/
│   ├── ingest/          # Log parsers (Claude parser MVP)
│   ├── storage/         # SQLite schema and queries
│   ├── search/          # FTS search layer
│   └── mcp/             # MCP server and tool definitions
├── tests/
├── .claude/
│   └── commands/        # Project slash commands
├── config.yaml.example
└── CLAUDE.md
```

## Storage

Sessions are stored at `~/.agent-memory/`:
- `config.yaml` — user config
- `database.sqlite` — main store
- `logs/` — raw log archive

## Data Model

**Session** — `id, repository, branch, started_at, ended_at, title, path`
**Message** — `id, session_id, role, content, timestamp`
**ToolCall** — `id, session_id, tool_name, arguments, result`

No Memory extraction table in MVP; raw sessions only.

## MCP Tools

| Tool | Input | Output |
|------|-------|--------|
| `ingest_session` | `path` | confirmation |
| `search_memory` | `query, limit` | session list |
| `read_session` | `session_id` | full transcript |
| `list_recent_sessions` | `limit` | recent sessions |

## Search

MVP: SQLite FTS over prompt, response, tool calls, repository.
Future: hybrid FTS + embedding.

## Key Constraints

- Local-only, offline-capable, OSS
- No cloud dependencies in MVP
- SQLite only — no external DB
- Must handle 1000+ sessions without degradation
- Target: setup in under 5 minutes

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Language | Python 3.11+ | MCP SDK, parser ecosystem |
| Package manager | uv | Fast, lockfile-based, replaces pip/venv |
| MCP framework | `mcp` (Anthropic SDK) | Official Python MCP server SDK |
| DB | SQLite (stdlib `sqlite3`) | Zero-dep, FTS5 built-in |
| Config | PyYAML | Simple YAML config |
| Testing | pytest | Standard, supports fixtures well |
| Lint/format | Ruff | Replaces black + flake8 + isort in one tool |
| Type checking | mypy (strict) | Catches parser/DB interface bugs early |

## Development Setup

```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install deps
uv sync --dev

# Run tests
uv run pytest

# Lint + format check
uv run ruff check .
uv run ruff format --check .

# Type check
uv run mypy src/
```

## Development Conventions

- Each parser lives in `src/ingest/parsers/` and implements the `Parser` protocol
- MCP server entry point: `src/mcp/server.py`
- Type hints required on all public functions; mypy strict mode must pass
- No mocking of SQLite — use `sqlite3.connect(":memory:")` in tests
- One module per concern: storage queries never call MCP layer and vice versa

## Testing

```
tests/
├── test_parser_claude.py   # Claude log parsing
├── test_storage.py         # DB insert/query with in-memory SQLite
├── test_search.py          # FTS queries
└── test_mcp_tools.py       # MCP tool integration (in-memory DB)
```

Rules:
- All tests run against in-memory SQLite (`":memory:"`) — no fixture files on disk
- Each test file is independent; no shared global state
- `pytest -x` must pass before any commit
- Target: 80%+ coverage on `src/storage/` and `src/search/`

## Linting & Formatting

Config lives in `pyproject.toml` under `[tool.ruff]`.

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]  # pycodestyle, pyflakes, isort, pyupgrade, bugbear
```

Run before committing:
```bash
uv run ruff check . --fix
uv run ruff format .
```

## CI (GitHub Actions)

Pipeline runs on every push and PR to `main`.

```yaml
# .github/workflows/ci.yml
jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src/
      - run: uv run pytest --tb=short
```

PRはすべてCIグリーンを必須とする。`main`への直接pushは禁止。

## MVP Scope

- Claude Code log ingestion only
- SQLite FTS search
- 4 MCP tools: ingest_session, search_memory, read_session, list_recent_sessions
- macOS + Linux

## Out of Scope (MVP)

- Cursor / Codex / Gemini parsers
- Embedding search
- Memory extraction (distilling facts from sessions)
- Windows support
- GUI
