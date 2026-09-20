from typing import Any

from .base import Tool


class ToolRegistry:
    """保存工具，并统一提供注册、描述导出和执行入口。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:

        if tool.name in self._tools:
            raise ValueError(f"工具已注册：{tool.name}")
        
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """按名称获取工具；不存在时返回明确错误。"""
        try:
            return self._tools[name]
        except KeyError as error:
            raise ValueError(f"未知工具：{name}") from error

    def get_schemas(self) -> list[dict]:
        return [tool.to_schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> Any:
        return self.get(name).execute(arguments)

    def unregister(self, name: str) -> None:
        """移除已注册的工具。"""
        try:
            del self._tools[name]
        except KeyError as error:
            raise ValueError(f"未知工具：{name}") from error
