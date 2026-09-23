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
                    "create_directory(创建目录), create(创建新文件，禁止覆盖), "
                    "edit(唯一匹配后替换文本), delete(删除文件)"
                ),
                required=True,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="工作目录内的相对路径，不允许隐藏项或符号链接；list 默认 .。",
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
            raise ValueError(f"不支持的操作: {action}")
        return handler(arguments)

    def _path(self, arguments: dict) -> Path:
        path = arguments.get("path", "." if arguments.get("action") == "list" else None)

        if not path:
            raise ValueError("该操作需要提供 path")

        relative = Path(path)

        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("path 必须是工作目录内的相对路径，不能包含 ..")
        if any(part.startswith(".") for part in relative.parts):
            raise ValueError("不允许访问隐藏文件或隐藏目录。")

        target = self.workspace
        for part in relative.parts:
            target = target / part
            if target.is_symlink():
                raise ValueError("不允许访问符号链接。")
        target = target.resolve()

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
            if not item.name.startswith(".") and not item.is_symlink()
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
        with path.open("x", encoding="utf-8", newline="") as file:
            file.write(content)
        return {"created_file": self._path_value(arguments)}

    def _edit(self, arguments: dict) -> dict:
        path = self._path(arguments)
        old_text = arguments.get("old_text")
        new_text = arguments.get("new_text")
        if old_text is None or new_text is None:
            raise ValueError("edit 操作需要提供 old_text 和 new_text")
        if not old_text:
            raise ValueError("old_text 不能为空。")
        with path.open("r", encoding="utf-8", newline="") as file:
            content = file.read()
        replacements = content.count(old_text)
        first_match = content.find(old_text)

        if first_match >= 0 and content.find(old_text, first_match + 1) >= 0:
            raise ValueError("old_text 存在多处匹配，请提供更长的原文。")
        if replacements != 1:
            raise ValueError(f"old_text 必须唯一匹配，实际匹配 {replacements} 处。")

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
