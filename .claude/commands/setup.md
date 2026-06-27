# /setup

Initialize Agent Memory for first use on this machine.

## Steps

1. Create `~/.agent-memory/` with subdirectories `logs/`.
2. Initialize `~/.agent-memory/database.sqlite` with the schema (sessions, messages, tool_calls, FTS index).
3. Write `~/.agent-memory/config.yaml` from the project's `config.yaml.example` if it doesn't exist.
4. Verify the MCP server entry point (`src/mcp/server.py`) exists and dependencies are installed (`uv pip install -e .` or `pip install -e .`).
5. Print the MCP config snippet the user should add to their Claude Code `settings.json`.

## Example output

```
Agent Memory setup complete.

Storage initialized at: ~/.agent-memory/
  database.sqlite  ✓
  logs/            ✓
  config.yaml      ✓ (created from example)

Dependencies installed. ✓

Add this to your Claude Code MCP config (~/.claude/settings.json):

  "mcpServers": {
    "agent-memory": {
      "command": "python",
      "args": ["-m", "memcp.mcp.server"],
      "cwd": "/path/to/memcp"
    }
  }

Then restart Claude Code. Run /ingest to add your first session.
```
