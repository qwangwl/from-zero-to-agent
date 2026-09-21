# day07-使用 Tool 和 ToolRegistry 统一管理工具

Day06 已经把 Agent 的工具调用从自定义的 `Action:` 文本改成了标准 Function Calling。模型返回一个结构化的 `function_call`，程序执行对应函数，再把 `function_call_output` 送回模型。

但 Day06 的工具定义分散在两处：`TOOLS` 保存模型看到的描述，`TOOL_REGISTRY` 保存程序实际执行的函数。

第一份是给模型看的 `TOOLS`，这里以 `read_file` 为例：

```python
TOOLS = [
    {
        "type": "function",
        "name": "read_file",
        "description": "读取指定文件的内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]
```
它告诉模型：

```text
工具叫什么？
工具是做什么的？
需要哪些参数？
参数是什么类型？
```

第二份则是程序真正用于执行工具的 `TOOL_REGISTRY`：

```python
TOOL_REGISTRY = {
    "list_files": list_files,
    "read_file": read_file,
}
```
它负责把工具名称映射到真正的 Python 函数。

这种设计在只有两个工具时没有太大问题。但随着工具增加，每新增一个工具，都需要同时修改这两处。例如增加 `delete_file` 时，只修改 `TOOLS`，模型可以调用但程序找不到函数；只修改 `TOOL_REGISTRY`，程序有实现但模型不知道它存在。

因此，Day07 要解决的问题是：

> **如何把工具的描述、参数和执行逻辑统一管理起来？**


## 用 Tool 约定工具接口

首先定义所有工具共同遵循的接口。`Tool` 是一个抽象基类，只约定每个工具必须提供哪些能力：

```python
# codes/day07/tools/base.py

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def get_parameters(self) -> list[ToolParameter]:
        pass

    @abstractmethod
    def execute(self, arguments: dict) -> Any:
        pass
```

`Tool` 不负责注册，也不实现具体文件操作。子类保存自己的名称和描述，并实现参数定义和执行逻辑。注册表因此只需要依赖稳定接口，不必知道工具内部是读文件、搜索文本还是调用其他服务。

## 用 ToolParameter 描述参数

模型需要 JSON Schema，而 Python 方法只需要接收参数。项目用一个很小的 `ToolParameter` 表示单个参数：

```python
# codes/day07/tools/base.py

class ToolParameter:
    def __init__(
        self,
        name: str,
        type: str,
        description: str,
        required: bool = True,
    ):
        self.name = name
        self.type = type
        self.description = description
        self.required = required
```


例如 `read_file` 只有一个参数：`path`，可以表示为：

```python
ToolParameter(
    name="path",
    type="string",
    description="文件的相对路径。",
)
```

这里保存的是便于在 Python 中维护的参数信息。模型接收的是 JSON Schema，因此还需要将 `ToolParameter` 转换成相应的格式。

## Tool 自动生成 Function Calling Schema

我们在 `Tool` 中增加 `to_schema()` 方法，遍历参数列表，组装 Responses API 使用的 Function Calling Schema：

```python
# codes/day07/tools/base.py

def to_schema(self) -> dict:
    properties = {}
    required = []

    for param in self.get_parameters():
        properties[param.name] = {
            "type": param.type,
            "description": param.description,
        }
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
        "strict": True,
    }
```

这样，工具类只维护一份参数定义。模型看到的 Schema 由工具对象生成，例如：

```python
ToolParameter(
    "path",
    "string",
    "文件的相对路径。",
    True
)
```

这项参数定义会与 `ReadFileTool` 的名称、描述一起，生成下面的完整工具定义：

```python
{
    "type": "function",
    "name": "read_file",
    "description": "读取 UTF-8 文本文件。",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件的相对路径。",
            }
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    "strict": True,
}
```

## 实现第一个 Tool

现在就可以实现一个具体工具，例如 `ReadFileTool`：

```python
# codes/day07/tools/builtin/files_tools.py

from pathlib import Path
from ..base import Tool, ToolParameter

class ReadFileTool(Tool):
    def __init__(self):
        super().__init__(
            "read_file",
            "读取 UTF-8 文本文件。",
        )

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                "path",
                "string",
                "文件的相对路径。",
            )
        ]

    def execute(self, arguments: dict) -> str:
        path = arguments["path"]

        file_path = Path(path)

        with file_path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as file:
            return file.read()
```

现在 `ReadFileTool` 自己就已经知道：

```text
我的名字是什么？
我的作用是什么？
我有哪些参数？
收到参数后应该执行什么？
```

不再需要另外维护 `TOOLS` 和 `TOOL_REGISTRY` 两套独立定义。

## ToolRegistry

有了 `Tool` 之后，还需要一个地方统一管理多个 Tool。

Day06 中我们使用的是一个普通字典：

```python
TOOL_REGISTRY = {
    "list_files": list_files,
    "read_file": read_file,
}
```

它已经具备了最基础的 Registry 思想：

```text
工具名称 → Python 函数
```

但这个字典只保存 Python 函数。如果想获得工具的描述和参数，仍然必须去另一个 `TOOLS` 中查找。

因此 Day07 将它进一步抽象成 `ToolRegistry`：

```python
# codes/day07/tools/registry.py

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(
                f"工具已注册：{tool.name}"
            )

        self._tools[tool.name] = tool

    def get_schemas(self) -> list[dict]:
        return [
            tool.to_schema()
            for tool in self._tools.values()
        ]
```

创建工具实例后，直接注册：

```python
registry = ToolRegistry()
registry.register_tool(ReadFileTool())
registry.register_tool(ListFilesTool())
```

内部保存的结构仍然类似一个字典：

```python
{
    "list_files": ListFilesTool(),
    "read_file": ReadFileTool(),
}
```

但是这里的映射已经不再是：

```text
工具名称 → Python 函数
```

而是：

```text
工具名称 → Tool 对象 → name + description + get_parameters() + execute()
```

为了统一生成模型需要的全部工具定义，Registry 可以直接从每一个 Tool 获取 Schema：

```python
# codes/day07/tools/registry.py

def get_schemas(self) -> list[dict]:
    return [
        tool.to_schema()
        for tool in self._tools.values()
    ]
```

## 由 Registry 统一执行工具

接下来再来看工具执行。

Day06 中：

```python
# codes/day06/agent.py

tool = TOOL_REGISTRY.get(function_call.name)

if tool is None:
    result = f"Unknown tool: {function_call.name}"
else:
    result = tool(**arguments)
```

Agent 自己需要：

1. 根据名字寻找 Python 函数；
2. 判断工具是否存在；
3. 执行工具。

现在这些事情都可以交给 `ToolRegistry`：

```python
# codes/day07/tools/registry.py

def get(self, name: str) -> Tool:
    try:
        return self._tools[name]
    except KeyError as error:
        raise ValueError(f"未知工具：{name}") from error

def execute(self, name: str, arguments: dict):
    return self.get(name).execute(arguments)
```

Agent 中只需要：

```python
result = self.tool_registry.execute(
    function_call.name,
    arguments,
)
```

Agent 不需要知道：

```text
read_file 到底对应哪个类？
具体文件怎么读取？
这个 Tool 有哪些参数？
```

它只负责把：

```text
工具名称 + arguments
```

交给 `ToolRegistry`。

这样职责就进一步分开了：

```text
Agent
    负责 Agent Loop

ToolRegistry
    负责寻找和管理 Tool

Tool
    负责描述并执行一个具体能力
```

## 增加文件工具

沿用同样的接口，我们把文件操作扩展为六个工具：

| Tool              | 作用       |
| ----------------- | -------- |
| `list_files`      | 查看目录中的文件 |
| `read_file`       | 读取文本文件   |
| `create_file`     | 写入文件，已有内容会被覆盖 |
| `edit_file`       | 替换文件中所有匹配的文本 |
| `delete_file`     | 删除文件     |
| `create_directory` | 创建目录     |

这些工具在 `codes/day07/tools/builtin/files_tools.py` 中实现，都遵循 `Tool` 的接口，分别提供参数定义和执行方法。

## 让 Agent 只依赖注册表

入口文件 `codes/day07/main.py` 创建并注册六个文件工具：

```python
registry = ToolRegistry()
registry.register_tool(ListFilesTool())
registry.register_tool(ReadFileTool())
registry.register_tool(CreateDirectoryTool())
registry.register_tool(CreateFileTool())
registry.register_tool(EditFileTool())
registry.register_tool(DeleteFileTool())
```

然后把注册表注入 Agent：

```python
# codes/day07/main.py

agent = Agent(
    client=client,
    model_id=MODEL_ID,
    system_prompt=SYSTEM_PROMPT,
    tool_registry=registry,
)
```

Agent 请求模型时从注册表取得工具描述：

```python
# codes/day07/agent.py

response = self.client.responses.create(
    model=self.model_id,
    instructions=self.system_prompt,
    input=self.messages,
    tools=self.tool_registry.get_schemas(),
)
```

收到工具调用后，Agent 只负责解析 JSON 并委托注册表执行：

```python
# codes/day07/agent.py

arguments = json.loads(call.arguments)
result = self.tool_registry.execute(call.name, arguments)
```

结果再通过 `call_id` 回传给模型。新增工具只需要创建工具类并调用 `register_tool()`，不需要修改 Agent Loop，也不需要维护第二份工具列表。

当前流程可以概括为：

```text
main.py
  │
  │ 创建具体 Tool
  ▼
ToolRegistry.register_tool()
  │
  ├── get_schemas() ──► Responses API
  │                         │
  │                         └── function_call
  ▼
Agent ─── execute() ───► Tool
  │                         │
  └── function_call_output ◄┘
```

在项目根目录启动交互式 Agent：

```bash
python codes/day07/main.py
```

下面是一段运行记录，展示了创建文件后列目录、再读取确认的过程；具体调用顺序可能随模型响应变化。

````text
You: 帮我创建一个hello.py，并编写hello world
--- 循环 1 ---
Tool Call: create_file({'path': 'hello.py', 'content': 'print("Hello, World!")\n'})
Tool Call: list_files({'path': '.'})
--- 循环 2 ---
Tool Call: read_file({'path': 'hello.py'})
--- 循环 3 ---
Assistant: 已完成。

**操作结果：**
- 已在工作目录根下创建 `hello.py`，内容为：

```python
print("Hello, World!")
```
````

## 总结

本日完成了三件事：

1. 用抽象 `Tool` 统一工具接口。
2. 用 `ToolParameter` 描述参数并生成 Schema。
3. 用 `ToolRegistry` 统一注册、导出、查找、执行和注销工具。

现在：

```text
Agent
    负责对话和 Function Calling 循环

ToolRegistry
    负责管理和调度 Tool

Tool
    负责实现具体能力
```

工具系统的职责边界已经更加清楚。

完整代码位于 [codes/day07](codes/day07/)。

## 本日新增与修改的文件

- [tools/base.py](codes/day07/tools/base.py)：新增：定义 Tool、ToolParameter 和工具 Schema 生成逻辑。
- [tools/registry.py](codes/day07/tools/registry.py)：新增：统一注册、查找和工具执行。
- [tools/builtin/files_tools.py](codes/day07/tools/builtin/files_tools.py)：新增：将文件操作封装为独立的工具类。
- [agent.py](codes/day07/agent.py)：修改：通过注册表获取工具描述并执行工具。
- [main.py](codes/day07/main.py)：修改：创建注册表，注册文件工具并传入 Agent。
