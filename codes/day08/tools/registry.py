import json

from .base import Tool
from .response import ToolResponse


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

    def execute(self, name: str, arguments: dict) -> ToolResponse:

        if name not in self._tools:
            return ToolResponse.error("unknown_tool", f"未知工具：{name}")
        
        tool = self.get(name)

        try:
            self.validate_arguments(tool, arguments)
        except ValueError as error:
            return ToolResponse.error("invalid_arguments", str(error))

        try:
            result = tool.execute(arguments)
            text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)

            return ToolResponse.success(text=text, data=result)
        except (OSError, ValueError, UnicodeError) as error:
            return ToolResponse.error(type(error).__name__, str(error))

    @staticmethod
    def validate_arguments(tool: Tool, arguments: dict) -> None:
        if not isinstance(arguments, dict):
            raise ValueError("工具参数必须是 JSON 对象。")
        
        parameters = {param.name: param for param in tool.get_parameters()}
        extra = arguments.keys() - parameters.keys()

        if extra:
            raise ValueError(f"未知参数：{', '.join(sorted(extra))}")
        
        types = {
            "string": (str,), "integer": (int,), "number": (int, float),
            "boolean": (bool,), "array": (list,), "object": (dict,),
        }

        for name, param in parameters.items():
            if name not in arguments:
                if param.required:
                    raise ValueError(f"缺少必需参数：{name}")
                continue
            # bool 是 int 的子类，这里使用精确类型判断。
            if type(arguments[name]) not in types[param.type]:
                raise ValueError(f"参数 {name} 必须是 {param.type} 类型。")

    def unregister(self, name: str) -> None:
        """移除已注册的工具。"""
        try:
            del self._tools[name]
        except KeyError as error:
            raise ValueError(f"未知工具：{name}") from error
