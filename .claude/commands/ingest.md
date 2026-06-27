# /ingest

Ingest a Claude Code session log into the local Agent Memory database.

## Usage

```
/ingest [path]
```

If `path` is omitted, look for the most recent Claude Code session log under `~/.claude/projects/`.

## Steps

1. Locate the log file (use the provided path, or auto-discover the latest session under `~/.claude/projects/`).
2. Parse the JSONL log with the Claude parser (`src/ingest/parsers/claude.py`).
3. Extract Session, Message, and ToolCall records.
4. Insert into `~/.agent-memory/database.sqlite` — skip if session_id already exists.
5. Report: session title, message count, tool call count, and session ID.

## Example output

```
Ingested session: "Fix race condition in payment processor"
  Messages : 42
  Tool calls: 17
  Session ID: sess_01HX...
  Stored at : ~/.agent-memory/database.sqlite
```
