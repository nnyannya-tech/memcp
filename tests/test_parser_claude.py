import json
from pathlib import Path

import pytest

from memcp.ingest.parsers.claude import parse


def write_log(tmp_path: Path, records: list[dict], session_id: str = "abc-123") -> Path:
    path = tmp_path / f"{session_id}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records))
    return path


def system_record(
    cwd: str = "/home/user/project",
    branch: str = "main",
    timestamp: str = "2026-06-23T10:00:00.000Z",
) -> dict:
    return {
        "type": "system",
        "subtype": "turn_duration",
        "timestamp": timestamp,
        "cwd": cwd,
        "gitBranch": branch,
        "sessionId": "abc-123",
    }


def user_record(content: str | list, prompt_id: str = "prompt-1") -> dict:
    return {
        "type": "user",
        "isSidechain": False,
        "promptId": prompt_id,
        "message": {"role": "user", "content": content},
    }


def assistant_record(msg_id: str, content_blocks: list) -> dict:
    return {
        "type": "assistant",
        "isSidechain": False,
        "message": {"id": msg_id, "role": "assistant", "content": content_blocks},
    }


def ai_title_record(title: str) -> dict:
    return {"type": "ai-title", "aiTitle": title, "sessionId": "abc-123"}


class TestSessionExtraction:
    def test_session_id_from_filename(self, tmp_path: Path) -> None:
        path = write_log(tmp_path, [system_record()], session_id="my-session-uuid")
        session, _, _ = parse(path)
        assert session.id == "my-session-uuid"

    def test_title_from_ai_title_record(self, tmp_path: Path) -> None:
        path = write_log(tmp_path, [ai_title_record("Fix the payment bug"), system_record()])
        session, _, _ = parse(path)
        assert session.title == "Fix the payment bug"

    def test_title_fallback_to_first_user_message(self, tmp_path: Path) -> None:
        path = write_log(tmp_path, [system_record(), user_record("What is the issue?")])
        session, _, _ = parse(path)
        assert session.title == "What is the issue?"

    def test_title_truncated_to_80_chars(self, tmp_path: Path) -> None:
        long_text = "A" * 100
        path = write_log(tmp_path, [system_record(), user_record(long_text)])
        session, _, _ = parse(path)
        assert len(session.title) == 80

    def test_cwd_and_branch_from_system_record(self, tmp_path: Path) -> None:
        path = write_log(tmp_path, [system_record(cwd="/code/myapp", branch="feat/auth")])
        session, _, _ = parse(path)
        assert session.repository == "/code/myapp"
        assert session.branch == "feat/auth"

    def test_started_at_from_first_system_timestamp(self, tmp_path: Path) -> None:
        records = [
            system_record(timestamp="2026-06-23T09:00:00.000Z"),
            system_record(timestamp="2026-06-23T10:00:00.000Z"),
        ]
        path = write_log(tmp_path, records)
        session, _, _ = parse(path)
        assert session.started_at.hour == 9

    def test_ended_at_from_last_system_timestamp(self, tmp_path: Path) -> None:
        records = [
            system_record(timestamp="2026-06-23T09:00:00.000Z"),
            system_record(timestamp="2026-06-23T10:30:00.000Z"),
        ]
        path = write_log(tmp_path, records)
        session, _, _ = parse(path)
        assert session.ended_at is not None
        assert session.ended_at.hour == 10
        assert session.ended_at.minute == 30

    def test_path_stored_as_string(self, tmp_path: Path) -> None:
        path = write_log(tmp_path, [system_record()])
        session, _, _ = parse(path)
        assert session.path == str(path)


class TestMessageExtraction:
    def test_user_string_message(self, tmp_path: Path) -> None:
        path = write_log(tmp_path, [system_record(), user_record("Hello world")])
        _, messages, _ = parse(path)
        assert any(m.role == "user" and m.content == "Hello world" for m in messages)

    def test_assistant_text_message(self, tmp_path: Path) -> None:
        path = write_log(
            tmp_path,
            [
                system_record(),
                assistant_record("msg-1", [{"type": "text", "text": "Here is the fix"}]),
            ],
        )
        _, messages, _ = parse(path)
        assert any(m.role == "assistant" and m.content == "Here is the fix" for m in messages)

    def test_thinking_blocks_are_skipped(self, tmp_path: Path) -> None:
        path = write_log(
            tmp_path,
            [
                system_record(),
                assistant_record(
                    "msg-1",
                    [
                        {"type": "thinking", "thinking": "internal thought"},
                        {"type": "text", "text": "My answer"},
                    ],
                ),
            ],
        )
        _, messages, _ = parse(path)
        assert len(messages) == 1
        assert messages[0].content == "My answer"

    def test_sidechain_records_are_skipped(self, tmp_path: Path) -> None:
        sidechain = {
            "type": "user",
            "isSidechain": True,
            "promptId": "p1",
            "message": {"role": "user", "content": "should be ignored"},
        }
        path = write_log(tmp_path, [system_record(), sidechain])
        _, messages, _ = parse(path)
        assert not any(m.content == "should be ignored" for m in messages)

    def test_user_array_content_extracts_text_blocks(self, tmp_path: Path) -> None:
        content = [{"type": "text", "text": "Follow-up question"}]
        path = write_log(tmp_path, [system_record(), user_record(content)])
        _, messages, _ = parse(path)
        assert any(m.content == "Follow-up question" for m in messages)

    def test_messages_have_session_id(self, tmp_path: Path) -> None:
        path = write_log(
            tmp_path, [system_record(), user_record("hi")], session_id="sess-xyz"
        )
        _, messages, _ = parse(path)
        assert all(m.session_id == "sess-xyz" for m in messages)


class TestToolCallExtraction:
    def test_tool_use_block_creates_tool_call(self, tmp_path: Path) -> None:
        path = write_log(
            tmp_path,
            [
                system_record(),
                assistant_record(
                    "msg-1",
                    [{"type": "tool_use", "id": "tc-1", "name": "Bash", "input": {"command": "ls"}}],
                ),
            ],
        )
        _, _, tool_calls = parse(path)
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "Bash"
        assert '"command": "ls"' in tool_calls[0].arguments

    def test_tool_result_matched_to_tool_call(self, tmp_path: Path) -> None:
        records = [
            system_record(),
            assistant_record(
                "msg-1",
                [{"type": "tool_use", "id": "tc-1", "name": "Bash", "input": {"command": "ls"}}],
            ),
            user_record(
                [{"type": "tool_result", "tool_use_id": "tc-1", "content": "file1.py\nfile2.py"}]
            ),
        ]
        path = write_log(tmp_path, records)
        _, _, tool_calls = parse(path)
        assert tool_calls[0].result == "file1.py\nfile2.py"

    def test_tool_calls_have_session_id(self, tmp_path: Path) -> None:
        path = write_log(
            tmp_path,
            [
                system_record(),
                assistant_record(
                    "msg-1",
                    [{"type": "tool_use", "id": "tc-1", "name": "Read", "input": {}}],
                ),
            ],
            session_id="sess-xyz",
        )
        _, _, tool_calls = parse(path)
        assert all(tc.session_id == "sess-xyz" for tc in tool_calls)
