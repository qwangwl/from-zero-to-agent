# day06-使用 Function Calling 重构工具调用

> 开始本节之前，请先阅读官方文档：[Function calling | OpenAI API](https://developers.openai.com/api/docs/guides/function-calling)

在 Day05 中，我们已经实现了一个可以使用多个 Tool 的 Agent。

不过目前 Tool Calling 仍然依赖我们自己设计的文本协议，例如：

```text
Thought: 我需要查看当前目录。

Action: list_files()
```

这种方式有助于理解 Agent Loop，但它也有明显的问题：程序需要自己解析字符串，处理换行、参数、引号和格式错误。

在真实项目中，我们通常应该优先使用 SDK 和 API 已经提供的 Function Calling 能力。因此在开始 Day06 之前，请先阅读官方文档，重点关注：

- 如何通过 `tools` 声明函数；
- `function_call` 中的 `name`、`arguments` 和 `call_id`；
- 如何执行函数；
- 如何通过 `function_call_output` 把执行结果交回模型。

官方文档说明，函数工具由 JSON Schema 描述，模型返回的 `function_call` 包含函数名和 JSON 编码的参数；程序执行函数后，需要把对应的 `function_call_output` 追加到下一次请求的输入中。[官方文档](https://developers.openai.com/api/docs/guides/function-calling)

## 为什么要重构

Day05 使用 Prompt 要求模型输出：

```text
Thought: ...
Action: read_file(path="README.md")
```

然后程序通过字符串解析：

```python
action = parse_action(response)
```

这种方式存在几个问题：

- 模型可能改变格式；
- `Finish[...]` 可能跨多行；
- 参数需要自己解析；
- 工具调用和普通文本混在一起；
- 程序难以稳定处理多个工具调用。

实际上，这一整套流程并不需要我们自己定义协议。OpenAI 的 Responses API 已经提供了标准的 Function Calling。Function Calling 允许我们直接告诉模型我们的函数定义，当模型认为需要使用某个 Tool 时，它返回一个结构化的 Function Call。

首先，我们不需要再将 Tool 写在 System Prompt 中了，而是定义一个新的 `TOOLS`：

```python
TOOLS = [
    {
        "type": "function",
        "name": "list_files",
        "description": "获取当前目录下的文件和文件夹",
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
        "description": "读取指定文件的内容",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "需要读取的文件路径",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]
```

`TOOLS` 不包含 Python 函数本身，而是包含给模型看的工具描述：

- `name`：工具名称；
- `description`：工具用途；
- `parameters`：参数的 JSON Schema；
- `strict`：要求参数符合 Schema。

调用 Responses API 时，把 `TOOLS` 传入 `tools` 参数：

```python
response = client.responses.create(
    model=MODEL_ID,
    instructions=SYSTEM_PROMPT,
    input=messages,
    tools=TOOLS,
)
```

System Prompt 可以简化为行为要求，并让模型在调用工具前简要说明操作目的：

```python
SYSTEM_PROMPT = """
你是一个能够处理文件的智能助手，请使用中文回答。
使用已声明的工具执行任务，只根据工具实际返回的结果描述文件和操作结果。
每次调用工具前，请用一句话说明本次操作的目的。
"""
```

工具声明通过 `tools` 参数传入，不再需要在提示词中重复定义工具或规定 `Thought / Action / Finish` 格式。模型返回的操作说明通过 `response.output_text` 打印，工具调用则从 `response.output` 中读取。

模型可能直接回答，也可能返回一个或多个 `function_call`。

与 Day05 不同，我们不再从 `response.output_text` 中解析 `Action:`。而是直接检查 `response.output`：

```python
function_calls = [
    item
    for item in response.output
    if item.type == "function_call"
]
```

每一个函数调用都带有：

```python
function_call.name       # 函数名
function_call.arguments  # JSON 字符串参数
function_call.call_id    # 本次调用的唯一 ID
```

为了便于调用工具，我们用一个 Tool Registry，把工具名直接映射到 Python 函数：

```python
TOOL_REGISTRY = {
    "list_files": list_files,
    "read_file": read_file,
}
```

解析参数并执行：

```python
arguments = json.loads(function_call.arguments)
tool = TOOL_REGISTRY.get(function_call.name)

if tool is None:
    result = f"Unknown tool: {function_call.name}"
else:
    result = tool(**arguments)
```

整个关系可以表示成：

```text
                    TOOLS
                      |
                      v
User -------------> LLM
                      |
                      | function_call
                      | name="read_file"
                      | arguments={...}
                      v
               TOOL_REGISTRY
                      |
                      v
                 read_file()
```

执行结果需要使用 Function Calling 标准模式返回给模型：

```python
messages.append({
    "type": "function_call_output", 
    "call_id": function_call.call_id,
    "output": json.dumps(result, ensure_ascii=False),
})
```

这里的 `call_id` 非常重要，它将工具结果和对应的函数调用关联起来。告知模型，这个 Tool Result 是哪一次 Function Call 返回的。

因此 Agent Loop 可以重写成：

```python
import json

def run(self, user_input: str):
    self.messages.append({
        "role": "user",
        "content": user_input,
    })

    for step in range(self.max_step):
        response = self.client.responses.create(
            model=self.model_id,
            instructions=self.system_prompt,
            input=self.messages,
            tools=TOOLS,
        )

        self.messages.extend(response.output)

        function_calls = [
            item
            for item in response.output
            if item.type == "function_call"
        ]

        # 没有 Function Call，说明模型已经生成最终回答
        if not function_calls:
            print(response.output_text)
            break

        print("Assistant:", response.output_text)

        for function_call in function_calls:
            arguments = json.loads(function_call.arguments)

            tool = TOOL_REGISTRY.get(function_call.name)

            if tool is None:
                result = f"Unknown tool: {function_call.name}"
            else:
                result = tool(**arguments)

            print(
                f"Tool Call: {function_call.name}({arguments})"
            )

            self.messages.append({
                "type": "function_call_output",
                "call_id": function_call.call_id,
                "output": json.dumps(result, ensure_ascii=False),
            })
```

其中 `self.messages` 在 Agent 初始化时创建：

```python
self.messages = []
```

每次 `run()` 都把新的用户输入追加到同一份历史中。因此 Function Calling 不仅能在一次任务内部关联工具调用和结果，同一个 Agent 实例也能在多次用户提问之间保留完整上下文。

现在运行：

```text
You:  查看当前目录，找到 README.md，读取它并告诉我这个项目是做什么的。
--- 循环 1 ---

Tool Call: list_files({})
--- 循环 2 ---

Tool Call: read_file({'path': 'README.md'})
--- 循环 3 ---

我已经找到并读取了 `README.md`。以下是这个项目的情况：

## 项目名称：30 Days Agent

**一句话概括**：这是一个从零开始学习 AI Agent 开发的实践/教程项目，不依赖复杂的 Agent 框架，而是从最基础的 LLM 调用起步，一步步手写实现出一个完整的 Agent。
```

现在下面这些代码都可以删除：

```python
parse_action()
is_finish()
parse_finish()
```

System Prompt 中的自定义格式也不再需要。

不过我们仍然需要自己：

```text
定义 Tool
实现 Tool
执行 Tool
维护 Agent Loop
```

但是 LLM 和 Python 程序之间的通信协议，现在已经从我们自己规定的文本格式，替换成了标准的 Function Calling。

这就是 Day06 完成的事情。

完整源代码：`codes/day06`

## 本日新增与修改的文件

- [tools.py](codes/day06/tools.py)：修改：定义工具 Schema 和工具名到函数的映射。
- [agent.py](codes/day06/agent.py)：修改：处理 function_call，解析参数并通过 function_call_output 回传结果。
- [main.py](codes/day06/main.py)：修改：调整提示词与 Agent 初始化，接入 Function Calling。
