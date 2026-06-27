import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from memcp.storage.models import Message, Session, ToolCall

Record = dict[str, object]


def parse(path: Path) -> tuple[Session, list[Message], list[ToolCall]]:
    records: list[Record] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    session_id = path.stem
    title = _extract_title(records, session_id)
    cwd, branch = _extract_cwd_branch(records)
    started_at, ended_at = _extract_timestamps(records, path)
    messages, tool_calls = _extract_messages_and_tools(records, session_id, started_at)

    session = Session(
        id=session_id,
        repository=cwd,
        branch=branch,
        started_at=started_at,
        ended_at=ended_at,
        title=title,
        path=str(path),
    )
    return session, messages, tool_calls


def _extract_title(records: list[Record], session_id: str) -> str:
    for record in records:
        if record.get("type") == "ai-title":
            title = record.get("aiTitle", "")
            if isinstance(title, str) and title:
                return title
    for record in records:
        if record.get("type") == "user":
            content = record.get("message", {})
            if isinstance(content, dict):
                text = content.get("content", "")
                if isinstance(text, str) and text.strip():
                    return text[:80].replace("\n", " ")
    return session_id


def _extract_cwd_branch(records: list[Record]) -> tuple[str, str]:
    for record in records:
        if record.get("type") == "system" and record.get("subtype") == "turn_duration":
            cwd = record.get("cwd", "")
            branch = record.get("gitBranch", "")
            return str(cwd), str(branch)
    return "", ""


def _extract_timestamps(records: list[Record], path: Path) -> tuple[datetime, datetime | None]:
    timestamps: list[datetime] = []
    for record in records:
        if record.get("type") == "system" and record.get("subtype") == "turn_duration":
            ts = record.get("timestamp")
            if isinstance(ts, str):
                timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))

    if timestamps:
        return timestamps[0], timestamps[-1]

    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return mtime, None


def _extract_messages_and_tools(
    records: list[Record],
    session_id: str,
    base_timestamp: datetime,
) -> tuple[list[Message], list[ToolCall]]:
    messages: list[Message] = []
    tool_calls: list[ToolCall] = []
    tool_use_map: dict[str, ToolCall] = {}
    msg_counter = 0  # unique per-session index for message IDs

    for record in records:
        if record.get("isSidechain"):
            continue

        rtype = record.get("type")

        if rtype == "user":
            msg_data = record.get("message", {})
            if not isinstance(msg_data, dict):
                continue
            content = msg_data.get("content", "")
            ts = base_timestamp + timedelta(seconds=msg_counter)

            if isinstance(content, str) and content.strip():
                messages.append(
                    Message(
                        id=f"msg_{session_id}_{msg_counter}",
                        session_id=session_id,
                        role="user",
                        content=content,
                        timestamp=ts,
                    )
                )
                msg_counter += 1

            elif isinstance(content, list):
                text_parts: list[str] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text = block.get("text", "")
                        if isinstance(text, str):
                            text_parts.append(text)
                    elif btype == "tool_result":
                        tool_use_id = block.get("tool_use_id", "")
                        if isinstance(tool_use_id, str) and tool_use_id in tool_use_map:
                            result = block.get("content", "")
                            tool_use_map[tool_use_id].result = str(result)

                if text_parts:
                    messages.append(
                        Message(
                            id=f"msg_{session_id}_{msg_counter}",
                            session_id=session_id,
                            role="user",
                            content="\n".join(text_parts),
                            timestamp=ts,
                        )
                    )
                    msg_counter += 1

        elif rtype == "assistant":
            msg_data = record.get("message", {})
            if not isinstance(msg_data, dict):
                continue
            content_blocks = msg_data.get("content", [])
            ts = base_timestamp + timedelta(seconds=msg_counter)

            text_parts = []
            for block in content_blocks if isinstance(content_blocks, list) else []:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    text = block.get("text", "")
                    if isinstance(text, str):
                        text_parts.append(text)
                elif btype == "tool_use":
                    tc = ToolCall(
                        id=str(block.get("id", uuid.uuid4())),
                        session_id=session_id,
                        tool_name=str(block.get("name", "")),
                        arguments=json.dumps(block.get("input", {})),
                        result="",
                    )
                    tool_calls.append(tc)
                    tool_use_map[tc.id] = tc

            if text_parts:
                messages.append(
                    Message(
                        id=f"msg_{session_id}_{msg_counter}",
                        session_id=session_id,
                        role="assistant",
                        content="\n".join(text_parts),
                        timestamp=ts,
                    )
                )
                msg_counter += 1

    return messages, tool_calls
