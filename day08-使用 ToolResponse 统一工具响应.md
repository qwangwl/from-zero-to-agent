# day08-使用 ToolResponse 统一工具响应

> 在开始之前，我们先调整了 `files_tools.py`，将 Day07 中六个独立的文件工具合并为一个 `FileTool`。这些操作都围绕文件展开，合并后可以共用工作目录和路径校验逻辑，减少重复代码。注册时只需注册一个工具，通过 `action` 参数选择列目录、读取、创建、编辑和删除等操作。同时增加了工作目录范围检查、禁止覆盖已有文件、编辑时要求唯一匹配等约束，明确各项操作的失败条件。

Day07 已经通过 `Tool` 和 `ToolRegistry` 统一了工具的定义与调用。Agent 不需要知道具体工具如何实现，只需要把名称和参数交给注册表：

```python
result = self.tool_registry.execute(call.name, arguments)
```

但是，工具返回的结果格式仍不统一：读取文件返回字符串，列出目录返回列表，创建文件返回字典。如果工具执行失败，还可能直接抛出异常。

例如，模型请求读取一个不存在的文件时，程序会抛出 `FileNotFoundError`。如果异常没有被处理，Agent Loop 就会中断，模型也无法收到失败原因。

```text
工作目录: /home/wlgls/Agents
You: 直接读取当前目录下的README.txt，一句话总结这个项目是什么
--- 循环 1 ---
FileNotFoundError: [Errno 2] No such file or directory: '/home/wlgls/Agents/README.txt'
```

一次工具调用失败，并不意味着整个任务无法继续。在上面的例子中，我们请求的是 `README.txt`，而实际文件是 `README.md`。如果模型能收到文件不存在的错误信息，就可以尝试列出当前目录，查找正确的文件名。

未处理异常时，程序的执行过程是：

```text
file(action="read", path="README.txt") → FileNotFoundError → Agent Loop 中断
```

如果将失败原因返回给模型，它就有机会调整下一步操作。例如：

```text
file(action="read", path="README.txt") → 返回文件不存在的错误 → file(action="list", path=".") → 发现 README.md → 尝试读取
```

因此 Day08 要解决的问题是：

> 如何让 Tool 的成功和失败都通过统一结构返回，并让 Agent 能够继续处理失败结果？

## 用 ToolResponse 统一工具返回值

在 `codes/day08/tools/response.py` 中，我们用 `ToolResponse` 表示一次工具调用的结果：

```python
# codes/day08/tools/response.py

@dataclass
class ToolResponse:
    status: ToolStatus
    text: str
    data: Any = None
    error_info: dict[str, str] | None = None
```

这四个字段分别承担不同的职责：

| 字段         | 作用                                     |
| ------------ | -----------------------------------------|
| `status`     | 标记成功、部分成功或失败                    |
| `text`       | 给模型阅读的结果说明                        |
| `data`       | 保留工具返回的结构化数据，未提供时为 `None` |
| `error_info` | 保存错误码和原因，序列化时使用键名 `error`  |

其中，状态通过枚举定义：

```python
# codes/day08/tools/response.py
class ToolStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"
```

`success` 表示操作成功，`partial` 表示结果可用但不完整，`error` 表示操作失败。目前的文件工具流程尚未使用 `partial`。

为了方便创建响应，类中提供了 `success()`、`partial()` 和 `error()` 三个类方法：

```python
# codes/day08/tools/response.py
@classmethod
def success(cls, text: str, data: Any = None) -> "ToolResponse":
    """创建成功响应，data 保存工具返回的结构化数据。"""
    return cls(
        status=ToolStatus.SUCCESS,
        text=text,
        data=data,
    )

@classmethod
def partial(cls, text: str, data: Any = None) -> "ToolResponse":
    """创建部分成功响应，text 应说明结果不完整的原因。"""
    return cls(
        status=ToolStatus.PARTIAL,
        text=text,
        data=data,
    )

@classmethod
def error(cls, code: str, message: str) -> "ToolResponse":
    """创建失败响应，保存错误码和具体原因。"""
    return cls(
        status=ToolStatus.ERROR,
        text=message,
        error_info={"code": code, "message": message},
    )
```

这里的 `cls` 表示当前类。调用 `ToolResponse.success(...)`，就会得到一个状态为成功的 `ToolResponse` 对象。失败响应则通过 `error()` 创建，将错误码和原因放入 `error_info`。

例如，当工具成功时：

```python
response = ToolResponse.success(
    text="已创建 hello.txt。",
    data={"created_file": "hello.txt"},
)
```

失败时：

```python
response = ToolResponse.error(
    code="invalid_arguments",
    message="缺少必需参数：action",
)
```

## 修改 ToolRegistry.execute()

接下来修改 `ToolRegistry` 的执行入口。原来它直接返回工具的执行结果，现在它负责返回 `ToolResponse`，并根据执行的不同情况来返回不同的 `ToolResponse`：
```python
def execute(self, name: str, arguments: dict) -> ToolResponse:

    response = None
    # 工具不存在
    if name not in self._tools:
        response = ToolResponse.error(
            code="unknown_tool",
            message=f"未知工具：{name}",
        )
    else:
        tool = self.get(name=name)
        
        # 验证参数是否正确
        try:
            self.validate_arguments(tool=tool, arguments=arguments)
        except ValueError as error:
            response = ToolResponse.error(
                code="invalid_arguments",
                message=str(error),
            )
        else:
            # 只有参数校验通过后，才执行工具。
            try:
                result = tool.execute(arguments=arguments)
                response = ToolResponse.success(
                    text=str(result),
                    data=result,
                )
            # 假如执行失败，则将相应信息传入
            except (OSError, ValueError, UnicodeError) as error:
                response = ToolResponse.error(
                    code=type(error).__name__,
                    message=str(error),
                )

    return response
```

现在，工具的成功结果和注册表捕获到的错误都会返回 `ToolResponse`，调用者可以通过统一结构处理这些结果。


## 把 ToolResponse 交回模型

`ToolResponse` 是一个 Python 对象，需要先转换为 JSON 字符串，再作为工具结果回传给模型。

`to_dict()` 会将 `ToolStatus` 转为对应的状态字符串，并在有错误信息时，将 `error_info` 写入 `error` 字段。随后，`to_json()` 将整个字典转换为 JSON 文本。

```python
# codes/day08/tools/response.py
def to_dict(self) -> dict:
    """转换为字典，将状态枚举转为字符串，并按需附加错误信息。"""
    result = {
        "status": self.status.value, 
        "text": self.text, 
        "data": self.data
    }

    if self.error_info:
        result["error"] = self.error_info
    return result

def to_json(self) -> str:
    """转换为 JSON 字符串，保留中文字符，供 Agent 回传工具结果。"""
    return json.dumps(self.to_dict(), ensure_ascii=False)
```

这样，Agent Loop 就可以统一处理工具结果：

```python
# codes/day08/agent.py

for call in function_calls:
    arguments = json.loads(call.arguments)
    result = self.tool_registry.execute(call.name, arguments)

    self.messages.append({
        "type": "function_call_output",
        "call_id": call.call_id,
        "output": result.to_json(),
    })
```

无论工具执行成功，还是注册表捕获到参数或执行错误，响应都会通过原来的 `call_id` 与对应的工具调用关联。只要错误已被转换为 `ToolResponse`，当前调用就不会因此中断循环，同一轮中的后续调用也能继续处理。

各部分的职责也更加清晰：

- `Tool`：执行具体任务，返回原始结果。
- `ToolRegistry`：校验参数并调用工具，将成功结果和捕获到的异常统一包装为 `ToolResponse`。
- `Agent`：将 `ToolResponse` 序列化后写入对话历史，供模型在下一轮决定如何继续。

## 总结

现在，我们重新运行 `python codes/day08/main.py` 然后测试开始时的错误场景：

```text
You: 直接读取当前目录下的README.txt，一句话总结这个项目是什么
--- 循环 1 ---
Assistant:  我先查看当前目录并读取 README.txt。
Tool Call: file({'action': 'read', 'path': 'README.txt'})
Tool Result: {'code': 'FileNotFoundError', 'message': "[Errno 2] No such file or directory: '/home/wlgls/Agents/README.txt'"}
--- 循环 2 ---
Assistant:  README.txt 不存在，我列出当前目录内容确认一下有哪些文件。
Tool Call: file({'action': 'list', 'path': '.'})
Tool Result: None
--- 循环 3 ---
Assistant:  目录中没有 README.txt，但有 README.md，我读取它来了解项目。
Tool Call: file({'action': 'read', 'path': 'README.md'})
Tool Result: None
--- 循环 4 ---
Assistant: 说明一下：你指定的 `README.txt` 在当前目录中并不存在，实际存在的是 `README.md`，我读取了它。

一句话总结：**这是一个名为 "from-zero-to-agent" 的 AI Agent 开发实践项目，不依赖现成框架，从最基础的 LLM 调用出发，按天（day01～day08）循序渐进地实现一个具备记忆、工具调用等能力的 Agent。**
```

这里的 `Tool Result` 仅打印了调试用的 `result.error_info`，因此成功时显示 `None`；回传给模型的仍是完整的 `result.to_json()`。

这次运行中，Agent 在读取 `README.txt` 失败后，继续列出目录并读取 `README.md`，根据错误反馈调整了下一步操作。

完整代码位于 [codes/day08](codes/day08/)。

## 本日新增与修改的文件

- [main.py](codes/day08/main.py)：修改：注册 FileTool，调整提示词以说明工具操作的目的。
- [tools/builtin/files_tools.py](codes/day08/tools/builtin/files_tools.py)：修改：将文件操作合并为 FileTool，通过 action 分派，并增加操作约束。
- [tools/response.py](codes/day08/tools/response.py)：新增：定义工具状态、统一响应结构及序列化方法。
- [tools/registry.py](codes/day08/tools/registry.py)：修改：将成功结果和捕获到的错误包装为 ToolResponse。
- [agent.py](codes/day08/agent.py)：修改：通过 to_json() 回传工具响应，并打印调用信息。

