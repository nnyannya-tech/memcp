from dataclasses import dataclass
from datetime import datetime


@dataclass
class Session:
    id: str
    repository: str
    branch: str
    started_at: datetime
    ended_at: datetime | None
    title: str
    path: str


@dataclass
class Message:
    id: str
    session_id: str
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime


@dataclass
class ToolCall:
    id: str
    session_id: str
    tool_name: str
    arguments: str  # JSON string
    result: str
