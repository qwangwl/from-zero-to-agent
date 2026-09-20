from pathlib import Path

from ..base import Tool, ToolParameter


class FileTool(Tool):
    """共享文件操作的基础目录。"""

    def __init__(self, workspace: str | Path, name: str, description: str):
        super().__init__(name, description)
        self.workspace = Path(workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)


class ListFilesTool(FileTool):
    def __init__(self, workspace: str | Path):
        super().__init__(workspace, 'list_files', '列出指定目录下的文件和子目录，不递归。')

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="path", type="string", description="相对于工作目录的路径，根目录使用 .。"),
        ]

    def execute(self, arguments: dict) -> list[dict]:
        path = arguments['path']
        directory = self.workspace / path
        return [
            {"name": item.name, "type": "directory" if item.is_dir() else "file"}
            for item in sorted(directory.iterdir(), key=lambda item: item.name)
        ]


class ReadFileTool(FileTool):
    def __init__(self, workspace: str | Path):
        super().__init__(workspace, 'read_file', '读取 UTF-8 文本文件。')

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="path", type="string", description="文件的相对路径。"),
        ]

    def execute(self, arguments: dict) -> str:
        path = arguments['path']
        with (self.workspace / path).open("r", encoding="utf-8", newline="") as file:
            return file.read()


class CreateDirectoryTool(FileTool):
    def __init__(self, workspace: str | Path):
        super().__init__(workspace, 'create_directory', '创建目录及缺失的父目录，已有目录保持不变。')

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="path", type="string", description="要创建的目录相对路径。"),
        ]

    def execute(self, arguments: dict) -> dict:
        path = arguments['path']
        (self.workspace / path).mkdir(parents=True, exist_ok=True)
        return {"created_directory": path}


class CreateFileTool(FileTool):
    def __init__(self, workspace: str | Path):
        super().__init__(workspace, 'create_file', '写入 UTF-8 文本文件，已存在时覆盖内容；父目录须已存在。')

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="path", type="string", description="新文件的相对路径。"),
            ToolParameter(name="content", type="string", description="新文件的完整文本内容。"),
        ]

    def execute(self, arguments: dict) -> dict:
        path = arguments['path']
        content = arguments['content']
        with (self.workspace / path).open("w", encoding="utf-8", newline="") as file:
            file.write(content)
        return {"created_file": path}


class EditFileTool(FileTool):
    def __init__(self, workspace: str | Path):
        super().__init__(workspace, 'edit_file', '读取文件并替换所有匹配的旧文本，再写回文件。')

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="path", type="string", description="文件的相对路径。"),
            ToolParameter(name="old_text", type="string", description="需要替换的原文。"),
            ToolParameter(name="new_text", type="string", description="替换后的文本，可为空字符串。"),
        ]

    def execute(self, arguments: dict) -> dict:
        path = arguments['path']
        old_text = arguments['old_text']
        new_text = arguments['new_text']
        target = self.workspace / path
        with target.open("r", encoding="utf-8", newline="") as file:
            content = file.read()
        with target.open("w", encoding="utf-8", newline="") as file:
            file.write(content.replace(old_text, new_text))
        return {"edited_file": path, "replacements": content.count(old_text)}


class DeleteFileTool(FileTool):
    def __init__(self, workspace: str | Path):
        super().__init__(workspace, 'delete_file', '删除指定文件。')

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="path", type="string", description="需要删除的文件相对路径。"),
        ]

    def execute(self, arguments: dict) -> dict:
        path = arguments['path']
        (self.workspace / path).unlink()
        return {"deleted_file": path}
