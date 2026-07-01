"""Load ~/.agent-memory/config.yaml with defaults."""

from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path.home() / ".agent-memory" / "config.yaml"

DEFAULT_CONFIG_YAML = """\
# Agent Memory configuration (~/.agent-memory/config.yaml)

storage:
  path: ~/.agent-memory/database.sqlite

search:
  default_limit: 5
  max_limit: 50

sources:
  claude_code:
    scan_dir: ~/.claude/projects
    enabled: true
    # since: "2026-07-01T00:00:00+00:00"  # only ingest logs modified after this time

  # To add Cursor support, uncomment and create src/memcp/ingest/parsers/cursor.py:
  # cursor:
  #   scan_dir: ~/.cursor/logs
  #   enabled: false
"""

_DEFAULTS: dict[str, Any] = {
    "storage": {
        "path": "~/.agent-memory/database.sqlite",
    },
    "search": {
        "default_limit": 5,
        "max_limit": 50,
    },
    "sources": {
        "claude_code": {
            "scan_dir": "~/.claude/projects",
            "enabled": True,
            "since": None,
        },
    },
}


class Config:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @property
    def db_path(self) -> Path:
        return Path(str(self._data["storage"]["path"])).expanduser()

    @property
    def sources(self) -> dict[str, Any]:
        val = self._data.get("sources", {})
        return dict(val) if isinstance(val, dict) else {}


def load(path: Path = _CONFIG_PATH) -> Config:
    """Load config from *path*, falling back to built-in defaults for missing keys."""
    return Config(_deep_merge(_DEFAULTS, _read_yaml(path)))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return dict(data) if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
