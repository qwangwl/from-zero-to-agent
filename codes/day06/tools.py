import os

def list_files():
    return os.listdir(".")

def read_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

TOOL_REGISTRY = {
    "list_files": list_files,
    "read_file": read_file,
}

TOOLS = [
    {
        "type": "function",
        "name": "list_files",
        "description": "获取当前目录下的文件和文件夹列表。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "读取指定文本文件的内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "需要读取的文件路径。",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]
