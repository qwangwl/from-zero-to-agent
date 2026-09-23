# day09-使用 LLM 统一模型调用

Day08 使用 `ToolResponse` 统一了工具响应。文件工具返回原始结果，由 `ToolRegistry` 校验参数、执行工具，再将成功结果或捕获到的异常包装为 `ToolResponse`。Agent 将完整响应交回模型，让它决定下一步操作。

但是如果继续观察当前的 Agent，会发现还有一部分代码仍然和具体模型调用方式绑定得很紧。

```python
response = self.client.responses.create(
    model=self.model_id,
    instructions=self.system_prompt,
    input=self.messages,
    tools=self.tool_registry.get_schemas(),
)
```

随后，Agent 还要遍历 `response.output`，找出其中的 `function_call`，并从 `response.output_text` 获取文本。这些字段都来自当前使用的 OpenAI Responses API。

而其他模型服务的表示方式可能不同。例如，使用各自的 Python SDK 时，工具调用中的关键字段可以这样对比：

```text
OpenAI Responses
    call.name            # 工具名称
    call.arguments       # JSON 字符串参数
    call.call_id         # 工具调用 ID

Claude Messages
    tool_use.name        # 工具名称
    tool_use.input       # 结构化参数对象
    tool_use.id          # 工具调用 ID

Gemini GenerateContent
    function_call.name   # 工具名称
    function_call.args   # 结构化参数对象
    function_call.id     # 工具调用 ID，可能未提供
```

这里的变量名用于示意从响应中取出的工具调用对象。不同 API 不仅字段名称不同，参数类型也不同：OpenAI Responses 的 `arguments` 是 JSON 字符串，Claude 的 `input` 和 Gemini 的 `args` 则是结构化对象。Gemini 的调用 ID 是否提供还与模型和接口行为有关，不能假定始终存在。对应格式可参考 [OpenAI 文档](https://developers.openai.com/api/docs/guides/function-calling)、[Claude 文档](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)和 [Gemini 文档](https://ai.google.dev/api/generate-content#FunctionCall)。

如果 Agent 直接读取这些字段，那么每接入一种 API，就要在循环中增加对应的解析逻辑。即使把请求方法单独封装起来，只要返回的仍是 SDK 原始对象，Agent 就仍然需要理解各家接口的格式。

因此，Day09 要解决的问题是：

> **如何把不同模型接口的响应整理为统一结构，让 Agent 只关心模型说了什么、要调用什么工具？**

## 先约定模型返回什么

我们可以看到，虽然不同 API 的表示方式不同，但执行工具所需的信息基本一致：工具名称、调用参数，以及关联调用与结果的标识。因此，我们先定义项目内部的 `ToolCall`，统一使用 `name`、`arguments` 和 `id` 三个字段，再用 `LLMResponse` 保存本轮文本和工具调用列表。

```text
各模型 API 的原始响应 → 对应的模型适配器 → LLMResponse → Agent
```

适配器负责字段映射和必要的类型转换，Agent 只读取统一后的字段。

```python
# codes/day09/core/llm_response.py

from dataclasses import dataclass, field
from typing import Any

# 屏蔽不同模型服务之间工具调用格式的差异。
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    content: list[Any] = field(default_factory=list)
```

`default_factory` 会为每个响应创建独立的列表和字典，避免不同响应共享可变数据。

`ToolCall` 表示模型提出的一次调用请求：

| 字段 | 含义 |
| --- | --- |
| `id` | 关联工具调用与工具结果的标识 |
| `name` | 要调用的工具名称 |
| `arguments` | 模型给出的 JSON 参数字符串 |


`LLMResponse` 保存一轮模型调用的结果：

| 字段 | 含义 |
| --- | --- |
| `text` | 模型返回的文本 |
| `tool_calls` | 模型请求的工具调用列表 |
| `model` | 实际返回响应的模型名称 |
| `usage` | 输入、输出和总 Token 数；服务未提供时为空字典，便于查看本次调用的 Token 用量 |
| `content` | 继续对话需要保留的完整原始响应项 |

一轮响应可以同时包含文本和工具调用。因此，只要 `tool_calls` 非空，Agent 就继续执行工具；没有工具调用时，再把文本作为最终回答返回。

## 用 LLM 约定调用接口

确定模型应该返回什么之后，再定义统一的模型调用接口，我们定义一个基类，减少重复代码：

```python
# codes/day09/core/llm.py
from abc import ABC, abstractmethod
from typing import Any
from .llm_response import LLMResponse, ToolCall

class LLM(ABC):
    def __init__(self, model_id: str, api_key: str,
                 base_url: str | None = None, timeout: float = 60.0):
        # 保存公共参数，具体 SDK 客户端由子类创建。
        self.model_id = model_id
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

    @abstractmethod
    def invoke(self, messages: list[Any], instructions: str,
                 tools: list[dict]) -> LLMResponse:
        """调用模型，返回统一响应；content 保留继续对话所需的原始响应项。"""
        pass
```

有了 `LLM` 的接口约定，接下来直接定义 `OpenAILLM`，实现 `invoke()`。它使用 OpenAI Responses API，将原先写在 Agent 中的模型请求和响应解析集中起来。公共参数由基类保存，`OpenAILLM` 负责创建客户端、发起请求和转换响应。

```python
# codes/day09/core/llm.py
from openai import OpenAI, OpenAIError

class OpenAILLM(LLM):
    """使用 OpenAI Responses API，返回统一的 LLMResponse。"""

    def __init__(self, model_id: str, api_key: str,
                 base_url: str | None = None, timeout: float = 60.0):
        super().__init__(
            model_id=model_id,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        # 使用基类保存的参数，创建 OpenAI 客户端。
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=0,
        )

    def invoke(self, messages: list, instructions: str,
                 tools: list[dict]) -> LLMResponse:
        # 将历史、系统提示和工具声明交给模型。
        try:
            response = self.client.responses.create(
                model=self.model_id,
                instructions=instructions,
                input=messages,
                tools=tools,
            )
        except OpenAIError as error:
            raise RuntimeError(f"模型请求失败：{type(error).__name__}") from error

        if response.status != "completed":
            raise RuntimeError(f"模型响应未完成：{response.status}")

        # 提取本次请求的 Token 用量。
        usage = {}
        if response.usage is not None:
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        # 统一文本和工具调用字段，同时保留完整响应项。
        return LLMResponse(
            text=response.output_text or "",
            tool_calls=[
                ToolCall(
                    id=item.call_id,
                    name=item.name,
                    arguments=item.arguments,
                )
                for item in response.output
                if item.type == "function_call"
            ],
            model=response.model,
            usage=usage,
            content=response.output,
        )
```
`usage` 从 SDK 的用量信息中提取 `input_tokens`、`output_tokens` 和 `total_tokens`。Agent 在每次模型调用返回后直接打印这份用量；服务未提供时显示 `Usage: {}`。这里展示的是单次调用的 Token 数，没有累计整次任务的用量。

调用关系现在变成：

```text
Agent
    ↓ invoke()
OpenAILLM
    ↓ responses.create()
模型服务
    ↓ SDK 响应
OpenAILLM
    ↓ LLMResponse
Agent
```
现在 Anthropic 的调用入口也可以封装成 `ClaudeLLM`。API 细节见 [Claude Messages API](https://platform.claude.com/docs/en/api/messages/create)。本文就不做实现了。

## Agent Loop 只读取统一响应

现在我们可以调整 `Agent` 的定义。原来传入的 `client` 和 `model_id` 改为一个 `llm` 对象，客户端、模型名称和连接参数交给模型层管理，Agent 只保存 `self.llm`。

```python
# codes/day09/agent.py

from core.llm import LLM
from tools import ToolRegistry


class Agent:
    def __init__(self, llm: LLM, system_prompt: str,
                 tool_registry: ToolRegistry, max_step: int = 10):
        if max_step < 1:
            raise ValueError("max_step 必须大于 0。")
        self.llm = llm
        ...
```

于是 Agent 调用模型时，可以改成：

```python
response = self.llm.invoke(
    messages=self.messages,
    instructions=self.system_prompt,
    tools=self.tool_registry.get_schemas(),
)
```

完成模型适配后，Agent 不再遍历 SDK 的 `response.output` 去寻找工具调用，而是直接使用 `response.tool_calls`：

```python
# codes/day09/agent.py

self.messages.extend(response.content)

if not response.tool_calls:
    return response.text or "模型未返回文本或工具调用。"

print(f"Usage: {response.usage}")
print("Assistant:", response.text)

for call in response.tool_calls:
    arguments = json.loads(call.arguments)
    result = self.tool_registry.execute(name=call.name, arguments=arguments)
    print(f"Tool Call: {call.name}({arguments})")
    print(f"Tool Result: {result.error_info}")
    
    self.messages.append({
        "type": "function_call_output",
        "call_id": call.id,
        "output": result.to_json(),
    })
```

## 在入口传入模型参数

现在修改 `main.py` 它只需要组装这些组件即可。

```python
# codes/day09/main.py

import os
from dotenv import load_dotenv
from core.llm import OpenAILLM

load_dotenv()

llm = OpenAILLM(
    model_id=os.environ["MODEL_ID"],
    api_key=os.environ["API_KEY"],
    base_url=os.getenv("BASE_URL") or None,
    timeout=60.0,
)

agent = Agent(
    llm=llm, 
    system_prompt=SYSTEM_PROMPT, 
    tool_registry=registry,
    max_iter=20
)
```

## 总结

现在重新运行 Agent：

```bash
python codes/day09/main.py
```

```text
You: 读取 README.md，一句话总结这个项目是什么
--- 循环 1 ---
Usage: {'input_tokens': 509, 'output_tokens': 109, 'total_tokens': 618}
Assistant: 我先查看工作目录内容，并读取 README.md 文件。
Tool Call: file({'action': 'list', 'path': '.'})
Tool Call: file({'action': 'read', 'path': 'README.md'})
--- 循环 2 ---
Assistant: 一句话总结：**from-zero-to-agent 是一个不依赖复杂框架、从最基础的 LLM 调用起步、按 Day01 到 Day09 循序渐进手写实现 AI Agent 的教学实践项目。**
```

这些部分通过两种响应结构连接起来：模型层用 `LLMResponse` 告诉 Agent 要做什么，工具层用 `ToolResponse` 告诉 Agent 执行结果。Agent 负责组织调用顺序，具体的模型请求和文件操作分别交给对应组件完成。

完整代码见 [codes/day09](codes/day09/)。

## 本日新增与修改的文件

- [core/llm_response.py](codes/day09/core/llm_response.py)：新增：定义 ToolCall 和 LLMResponse，统一模型返回值。
- [core/llm.py](codes/day09/core/llm.py)：新增：定义模型基类和 OpenAILLM，统一请求与响应解析。
- [agent.py](codes/day09/agent.py)：修改：依赖统一模型接口，保留循环和工具调用打印，并输出每次模型调用的 Token 用量。
- [main.py](codes/day09/main.py)：修改：读取环境变量，显式传入模型参数并组装 Agent。
