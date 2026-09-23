from dataclasses import dataclass, field
from typing import Any, Literal

# 屏蔽不同模型服务之间工具调用格式的差异。
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    content: list[Any] = field(default_factory=list) # `field()` 会为每个响应创建独立的列表和字典，避免不同响应共享可变数据。


@dataclass
class StreamEvent:
    """一次流式事件：文本增量，或携带完整响应的结束事件。"""

    kind: Literal["text", "completed"]
    text: str = ""
    response: LLMResponse | None = None

