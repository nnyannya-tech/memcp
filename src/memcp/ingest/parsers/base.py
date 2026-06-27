from collections.abc import Callable
from pathlib import Path

from memcp.storage.models import Message, Session, ToolCall

ParseFn = Callable[[Path], tuple[Session, list[Message], list[ToolCall]]]
