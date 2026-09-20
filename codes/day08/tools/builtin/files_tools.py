from pathlib import Path
from typing import Any, Optional

from ..base import Tool, ToolParameter


class FileTool(Tool):
    """统一的文件工具，通过 action 参数执行不同的文件操作。"""

    def __init__(self, workspace: Optional[str] = "."):
        super().__init__(
            "file",
            "文件工具 - 列出、读取、创建、编辑和删除文件或目录。",
        )
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description=(
                    "操作类型: list(列出目录), read(读取文件), "
                    "create_directory(创建目录), create(创建或覆盖文件), "
                    "edit(替换文件文本), delete(删除文件)"
                ),
            ),
            ToolParameter(
                name="path",
                type="string",
                description="相对于工作目录的路径；list 的根目录使用 .。",
                required=False,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="create 操作写入的完整文本内容。",
                required=False,
            ),
            ToolParameter(
                name="old_text",
                type="string",
                description="edit 操作中需要替换的原文。",
                required=False,
            ),
            ToolParameter(
                name="new_text",
                type="string",
                description="edit 操作中替换后的文本，可为空字符串。",
                required=False,
            ),
        ]

    def execute(self, arguments: dict) -> Any:
        action = arguments.get("action")
        handlers = {
            "list": self._list,
            "read": self._read,
            "create_directory": self._create_directory,
            "create": self._create,
            "edit": self._edit,
            "delete": self._delete,
        }
        handler = handlers.get(action)
        if handler is None:
            return {"error": f"不支持的操作: {action}"}
        return handler(arguments)

    def _path(self, arguments: dict) -> Path:
        path = arguments.get("path")
        if not path:
            raise ValueError("该操作需要提供 path")
        target = (self.workspace / path).resolve()
        try:
            target.relative_to(self.workspace)
        except ValueError as error:
            raise ValueError("path 不能超出 workspace 目录") from error
        return target

    @staticmethod
    def _path_value(arguments: dict) -> str:
        return str(arguments["path"])

    def _list(self, arguments: dict) -> list[dict]:
        directory = self._path(arguments)
        return [
            {"name": item.name, "type": "directory" if item.is_dir() else "file"}
            for item in sorted(directory.iterdir(), key=lambda item: item.name)
        ]

    def _read(self, arguments: dict) -> str:
        with self._path(arguments).open("r", encoding="utf-8", newline="") as file:
            return file.read()

    def _create_directory(self, arguments: dict) -> dict:
        path = self._path(arguments)
        path.mkdir(parents=True, exist_ok=True)
        return {"created_directory": self._path_value(arguments)}

    def _create(self, arguments: dict) -> dict:
        path = self._path(arguments)
        content = arguments.get("content")
        if content is None:
            raise ValueError("create 操作需要提供 content")
        with path.open("w", encoding="utf-8", newline="") as file:
            file.write(content)
        return {"created_file": self._path_value(arguments)}

    def _edit(self, arguments: dict) -> dict:
        path = self._path(arguments)
        old_text = arguments.get("old_text")
        new_text = arguments.get("new_text")
        if old_text is None or new_text is None:
            raise ValueError("edit 操作需要提供 old_text 和 new_text")
        with path.open("r", encoding="utf-8", newline="") as file:
            content = file.read()
        replacements = content.count(old_text)
        with path.open("w", encoding="utf-8", newline="") as file:
            file.write(content.replace(old_text, new_text))
        return {
            "edited_file": self._path_value(arguments),
            "replacements": replacements,
        }

    def _delete(self, arguments: dict) -> dict:
        path = self._path(arguments)
        path.unlink()
        return {"deleted_file": self._path_value(arguments)}
