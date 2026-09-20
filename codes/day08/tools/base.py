from abc import ABC, abstractmethod
from typing import Any


class ToolParameter:
    """一个工具参数的名称、类型、描述和必填标记。"""

    def __init__(self, name: str, type: str, description: str, required: bool = True):
        self.name = name
        self.type = type
        self.description = description
        self.required = required


class Tool(ABC):
    """工具只约定描述、参数和执行接口，不负责注册。"""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def get_parameters(self) -> list[ToolParameter]:
        """返回工具参数定义列表。"""
        pass

    @abstractmethod
    def execute(self, arguments: dict) -> Any:
        """执行工具并返回可 JSON 序列化的结果。"""
        pass

    def to_schema(self) -> dict:
        """由参数定义生成 OpenAI API 使用的 Function Calling Schema。"""
        properties = {}
        required = []

        for param in self.get_parameters():
            prop = {
                "type": param.type,
                "description": param.description,
            }

            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            # 可省略参数不符合严格模式的全字段必填要求，显式关闭。
            "strict": True,
        }
