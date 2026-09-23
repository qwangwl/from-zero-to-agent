# day10-让模型逐段输出回答

现在运行 `python codes/day09/main.py`，然后测试一下

```text
User: 读取 README.md，总结这个项目是什么
```

我们会发现，等一轮响应完成之后，Agent会把所有文本一下子全部显示出来。假如在遇到较长的回答时，终端会等待超长的时间，然后再输出。在这种情况下，立刻开始出字会更照顾用户的体验。

因此，本日将学习流式调用（streaming）和非流式调用（non-streaming），这两种方法是调用 Agent/LLM 时两种不同的响应返回方式，核心区别在于结果是一次性给你，还是边生成边给你。

## 流式调用和非流式调用

在开始之前，我们先学习一下流式和非流式的区别，其中

**非流式（non-streaming）**

* 请求发出后，服务端会先把整个回答生成完成，再一次性返回最终结果。
* 客户端在等待期间拿不到中间内容，看起来就像程序一直“卡住”直到生成结束。
* 返回的是一个完整响应，例如完整文本、完整工具调用信息等。

**流式（streaming）**

* 服务端每生成一部分内容，就可以立即把新的增量结果发送给客户端。
* 客户端持续接收这些增量片段，因此可以在模型尚未生成完成时就开始展示内容。
* 对于 Agent，流式也不只是“文本逐字返回”。后续还可以把工具调用状态、工具执行结果、任务阶段以及多个 Agent 之间的交接等运行事件持续发送给调用者。

## 流式调用的 API

实现流式调用很简单，只需要在调用API时，增加:

```python
events = self.client.responses.create(
        model=self.model_id,
        instructions=instructions,
        input=messages,
        tools=tools,
        stream=True,
    )
```

此时，服务端会不断返回事件，具体事件名称见 [OpenAI 流式响应文档](https://developers.openai.com/api/docs/guides/streaming-responses)。考虑到流式调用处理起来非常复杂，我们先仅实现文本逐段显示，我们重点关注两种事件：

- `response.output_text.delta`：携带新生成的一段文本，读取 `event.delta` 就能立即显示。
- `response.completed`：表示这一轮响应已经完成，“event.response 是完整的 Response 对象，结构与非流式调用获得的响应相同。

前者用于让用户尽快看到模型输出，后者则用于获得这一轮完整响应中的工具调用、Token 用量和原始输出项。这样，我们可以一边显示模型已经生成的文本，一边在响应完成后继续按照原来的 Agent Loop 处理工具调用。

本日暂时不处理工具参数自身的流式事件，而是在本轮流结束后，从完整响应中读取 Tool Call。

为了不让 Agent 直接依赖 OpenAI 返回的是 SDK 事件，我们在定义 `StreamEvent`，用 `kind` 区分文本片段和结束事件，

```python
# codes/day10/core/llm_response.py
@dataclass
class StreamEvent:
    kind: Literal["text", "completed"]
    text: str = ""
    response: LLMResponse | None = None
```

其中 `text` 保存文本信息，而 `response` 则等待 `response.completed` 事件，并获得 `event.response` 将其处理为常规的 `LLMResponse`。

接下来在 `LLM` 基类再增加 `stream_invoke()`，并在 `OpenAILLM` 中实现具体的逻辑：

```python
# codes/day10/core/llm.py
class LLM(ABC):
    @abstractmethod
    def stream_invoke(self, messages, instructions, tools) -> Iterator[StreamEvent]:
        """逐段返回文本事件，最后返回带完整响应的结束事件。"""
        pass

class OpenAILLM(LLM):
    def stream_invoke(self, messages: list, instructions: str,
               tools: list[dict]) -> Iterator[StreamEvent]:
        """逐段交出文本；结束时交出完整响应，供 Agent 处理工具调用。"""
        try:
            # 同一次请求持续返回事件，调用方可以边接收边显示文本。
            events = self.client.responses.create(
                model=self.model_id,
                instructions=instructions,
                input=messages,
                tools=tools,
                stream=True,
            )
            completed = None
            for event in events:
                if event.type == "response.output_text.delta":
                    # 文本片段立即交出，不等待完整响应。
                    yield StreamEvent(kind="text", text=event.delta)
                elif event.type == "response.completed":
                    # 完成事件携带本轮完整响应，后续从中读取工具调用和用量。
                    completed = event.response
                elif event.type in ("response.failed", "response.incomplete", "error"):
                    raise RuntimeError(f"模型流式响应失败：{event.type}")
        except OpenAIError as error:
            raise RuntimeError(f"模型请求失败：{type(error).__name__}") from error

        if completed is None or completed.status != "completed":
            raise RuntimeError("模型流式响应未完成。")
        # 转成与 invoke() 相同的 LLMResponse，减少重复编码。
        yield StreamEvent(kind="completed", response=self._convert(completed))
```

OpenAILLM.stream_invoke() 负责把 SDK 的流式事件转换成项目自己的 StreamEvent。

收到：

```text
response.output_text.delta
```

时立即返回：

```python
StreamEvent(
    kind="text",
    text=event.delta,
)
```

收到：

```text
response.completed
```

后先保存完整 Response，最后再转换成和非流式调用相同的：

```text
LLMResponse
```

这样流式和非流式虽然返回方式不同，但最终仍然可以使用同一套 `LLMResponse` 处理工具调用。

## Agent 分别提供流式入口

现在我们可以在在agent中定义流式运行的逻辑了，它和原来的 Agent Loop 并没有本质区别。

主要变化是：

> 原来直接等待一个完整 `LLMResponse`，现在改成遍历 `StreamEvent`。

收到文本事件时立即输出；收到完成事件以后，再按照原来的流程处理工具调用。

```python
def run_stream(self, user_input: str) -> str:
    """流式运行：逐段显示文本，并完成后续工具调用。"""
    self.messages.append({"role": "user", "content": user_input})

    for step in range(self.max_step):
        print(f"--- 循环 {step + 1} ---")
        response = None
        printed_text = False
        for event in self.llm.stream_invoke(
            messages=self.messages,
            instructions=self.system_prompt,
            tools=self.tool_registry.get_schemas(),
        ):
            if event.kind == "text" and event.text:
                # 文本片段一到就显示，无需等待这一轮模型响应结束。
                if not printed_text:
                    print("Assistant: ", end="", flush=True)
                    printed_text = True
                print(event.text, end="", flush=True)
            elif event.kind == "completed":
                # 完整响应用于读取工具调用和用量，不重复打印已显示的文本。
                response = event.response

        if response is None:
            raise RuntimeError("模型未返回完整响应。")
        print()
        print("Usage:", response.usage)
        # 保存模型原始输出项，供工具结果返回后的下一轮请求使用。
        self.messages.extend(response.content)

        if not response.tool_calls:
            answer = response.text or "模型未返回文本或工具调用。"
            if not response.text:
                print("Assistant:", answer)
            return answer

        # 工具调用需要完整参数，因此等本轮流结束后统一执行。
        self._execute_tools(response)

    answer = "已达到模型调用轮次上限，尚未获得最终回答；已执行的文件操作不会自动撤销。"
    print("Assistant:", answer)
    return answer
```

## 总结
现在重新运行命令：

```bash
python codes/day10/main.py
```

```text
User: 读取 README.md，总结这个项目是什么
```

这一次，模型生成的文本会随着 `delta` 到达不断显示，而不是等整轮模型响应结束以后再一次性出现。

## 本日新增与修改的文件

- [core/llm_response.py](codes/day10/core/llm_response.py)：新增 `StreamEvent`，区分文本片段和结束事件。
- [core/llm.py](codes/day10/core/llm.py)：增加 `stream_invoke()`，将接口事件整理为统一流式事件。
- [agent.py](codes/day10/agent.py)：创建`run_stream()` 使用流式请求。
- [main.py](codes/day10/main.py)：组装组件并调用 `agent.run_stream()`。
