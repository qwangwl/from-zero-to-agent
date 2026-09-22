import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ToolStatus(Enum):
    """工具执行状态：完全成功、部分成功或失败。"""

    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"


@dataclass
class ToolResponse:
    """工具响应数据类，统一各类工具的返回格式。

    字段说明：
        status: 执行状态（success/partial/error）。
        text: 给 LLM 阅读的结果说明；部分成功时应说明限制或缺失。
        data: 结构化结果数据，需支持 JSON 序列化；未提供时为 None。
        error_info: 失败时的错误码和原因，序列化后使用键名 error。
    """

    status: ToolStatus
    text: str
    data: Any = None
    error_info: dict[str, str] | None = None

    def to_dict(self) -> dict:
        """转换为字典，将状态枚举转为字符串，并按需附加错误信息。"""
        result = {
            "status": self.status.value, 
            "text": self.text, 
            "data": self.data
        }

        if self.error_info:
            result["error"] = self.error_info
        return result

    def to_json(self) -> str:
        """转换为 JSON 字符串，保留中文字符，供 Agent 回传工具结果。"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def success(cls, text: str, data: Any = None) -> "ToolResponse":
        """创建成功响应，data 保存工具返回的结构化数据。"""
        return cls(
            status=ToolStatus.SUCCESS,
            text=text,
            data=data,
        )

    @classmethod
    def partial(cls, text: str, data: Any = None) -> "ToolResponse":
        """创建部分成功响应，text 应说明结果不完整的原因。"""
        return cls(
            status=ToolStatus.PARTIAL,
            text=text,
            data=data,
        )

    @classmethod
    def error(cls, code: str, message: str) -> "ToolResponse":
        """创建失败响应，保存错误码和具体原因。"""
        return cls(
            status=ToolStatus.ERROR,
            text=message,
            error_info={"code": code, "message": message},
        )
