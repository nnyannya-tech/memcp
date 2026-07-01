"""Tests for memcp CLI commands."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from memcp.cli import _copy_config_example, main
from memcp.ingest.parsers.claude import parse as claude_parse
from memcp.ingest.sources import Source
from memcp.storage import repository as repo
from memcp.storage.db import connect, init_schema


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return path to a freshly initialised SQLite database."""
    path = tmp_path / "test.sqlite"
    c = connect(path)
    init_schema(c)
    c.close()
    return path


def _fresh_conn(db_path: Path) -> sqlite3.Connection:
    """Open a new connection; CLI closes its own — callers must manage theirs."""
    c = connect(db_path)
    init_schema(c)
    return c


def _write_log(directory: Path, session_id: str, title: str = "Test session") -> Path:
    log = directory / f"{session_id}.jsonl"
    records = [
        {"type": "ai-title", "aiTitle": title, "sessionId": session_id},
        {
            "type": "system",
            "subtype": "turn_duration",
            "timestamp": "2026-06-26T10:00:00.000Z",
            "cwd": "/code/app",
            "gitBranch": "main",
            "sessionId": session_id,
        },
        {
            "type": "user",
            "isSidechain": False,
            "promptId": "p-1",
            "message": {"role": "user", "content": "Implement the feature"},
        },
    ]
    log.write_text("\n".join(json.dumps(r) for r in records))
    return log


class TestIngestCommand:
    def test_ingest_specific_file(self, runner: CliRunner, db_path: Path, tmp_path: Path) -> None:
        log = _write_log(tmp_path, "cli-test-001")
        with patch("memcp.cli._open_conn", side_effect=lambda: _fresh_conn(db_path)):
            result = runner.invoke(main, ["ingest", str(log)])
        assert result.exit_code == 0
        assert "Ingested" in result.output
        with _fresh_conn(db_path) as conn:
            assert repo.session_exists(conn, "cli-test-001")

    def test_ingest_missing_file_exits_nonzero(self, runner: CliRunner, db_path: Path) -> None:
        with patch("memcp.cli._open_conn", side_effect=lambda: _fresh_conn(db_path)):
            result = runner.invoke(main, ["ingest", "/nonexistent/abc.jsonl"])
        assert result.exit_code != 0

    def test_ingest_duplicate_skips(self, runner: CliRunner, db_path: Path, tmp_path: Path) -> None:
        log = _write_log(tmp_path, "cli-dup-001")
        with patch("memcp.cli._open_conn", side_effect=lambda: _fresh_conn(db_path)):
            runner.invoke(main, ["ingest", str(log)])
            result = runner.invoke(main, ["ingest", str(log)])
        assert "Already ingested" in result.output


class TestIngestNewCommand:
    def _make_sources(self, scan_dir: Path) -> list[Source]:
        return [Source(name="claude_code", scan_dir=scan_dir, parse_fn=claude_parse)]

    def test_ingests_new_logs(self, runner: CliRunner, db_path: Path, tmp_path: Path) -> None:
        projects_dir = tmp_path / "projects" / "myproject"
        projects_dir.mkdir(parents=True)
        _write_log(projects_dir, "auto-001", "Auto session A")
        _write_log(projects_dir, "auto-002", "Auto session B")

        sources = self._make_sources(tmp_path / "projects")
        with (
            patch("memcp.cli._open_conn", side_effect=lambda: _fresh_conn(db_path)),
            patch("memcp.ingest.sources.get_sources", return_value=sources),
        ):
            result = runner.invoke(main, ["ingest-new"])

        assert result.exit_code == 0
        assert "ingested 2" in result.output
        with _fresh_conn(db_path) as conn:
            assert repo.session_exists(conn, "auto-001")
            assert repo.session_exists(conn, "auto-002")

    def test_skips_already_ingested(self, runner: CliRunner, db_path: Path, tmp_path: Path) -> None:
        projects_dir = tmp_path / "projects" / "proj"
        projects_dir.mkdir(parents=True)
        _write_log(projects_dir, "skip-001")

        sources = self._make_sources(tmp_path / "projects")
        with (
            patch("memcp.cli._open_conn", side_effect=lambda: _fresh_conn(db_path)),
            patch("memcp.ingest.sources.get_sources", return_value=sources),
        ):
            runner.invoke(main, ["ingest-new"])
            result = runner.invoke(main, ["ingest-new"])

        assert "ingested" not in result.output

    def test_no_scan_dir_is_silent(self, runner: CliRunner, db_path: Path, tmp_path: Path) -> None:
        sources = self._make_sources(tmp_path / "no-such-dir")
        with (
            patch("memcp.cli._open_conn", side_effect=lambda: _fresh_conn(db_path)),
            patch("memcp.ingest.sources.get_sources", return_value=sources),
        ):
            result = runner.invoke(main, ["ingest-new"])
        assert result.exit_code == 0
        assert result.output == ""

    def test_since_skips_logs_older_than_cutoff(
        self, runner: CliRunner, db_path: Path, tmp_path: Path
    ) -> None:
        import os
        import time
        from datetime import UTC, datetime, timedelta

        projects_dir = tmp_path / "projects" / "proj"
        projects_dir.mkdir(parents=True)
        old_log = _write_log(projects_dir, "old-001")
        new_log = _write_log(projects_dir, "new-001")

        old_time = time.time() - 3600
        os.utime(old_log, (old_time, old_time))

        cutoff = datetime.now(UTC) - timedelta(minutes=30)
        sources = [
            Source(
                name="claude_code",
                scan_dir=tmp_path / "projects",
                parse_fn=claude_parse,
                since=cutoff,
            )
        ]
        with (
            patch("memcp.cli._open_conn", side_effect=lambda: _fresh_conn(db_path)),
            patch("memcp.ingest.sources.get_sources", return_value=sources),
        ):
            result = runner.invoke(main, ["ingest-new"])

        assert result.exit_code == 0
        assert "ingested 1" in result.output
        with _fresh_conn(db_path) as conn:
            assert not repo.session_exists(conn, "old-001")
            assert repo.session_exists(conn, "new-001")
        assert new_log.exists()


class TestCopyConfigExample:
    def test_backfill_true_writes_no_since_key(self, tmp_path: Path) -> None:
        _copy_config_example(tmp_path, backfill=True)
        content = (tmp_path / "config.yaml").read_text()
        assert "since:" not in content.replace("# since:", "")

    def test_backfill_false_writes_since_key(self, tmp_path: Path) -> None:
        _copy_config_example(tmp_path, backfill=False)
        content = (tmp_path / "config.yaml").read_text()
        assert '    since: "' in content

    def test_existing_config_is_left_untouched(self, tmp_path: Path) -> None:
        dest = tmp_path / "config.yaml"
        dest.write_text("custom: true\n")
        _copy_config_example(tmp_path, backfill=False)
        assert dest.read_text() == "custom: true\n"
