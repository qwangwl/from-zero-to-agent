from abc import ABC, abstractmethod
from typing import Any, Iterator
from openai import OpenAI, OpenAIError
from .llm_response import LLMResponse, StreamEvent, ToolCall

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

    @abstractmethod
    def stream_invoke(self, messages: list[Any], instructions: str,
               tools: list[dict]) -> Iterator[StreamEvent]:
        """逐段返回文本事件，最后返回带完整响应的结束事件。"""
        pass

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

        return self._convert(response)

    def stream_invoke(self, messages: list, instructions: str,
               tools: list[dict]) -> Iterator[StreamEvent]:
        """文字到达时立即交给调用方；工具调用在响应完成后统一处理。"""
        try:
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
                    yield StreamEvent(kind="text", text=event.delta)
                elif event.type == "response.completed":
                    completed = event.response
                elif event.type in ("response.failed", "response.incomplete", "error"):
                    raise RuntimeError(f"模型流式响应失败：{event.type}")
        except OpenAIError as error:
            raise RuntimeError(f"模型请求失败：{type(error).__name__}") from error

        if completed is None or completed.status != "completed":
            raise RuntimeError("模型流式响应未完成。")
        yield StreamEvent(kind="completed", response=self._convert(completed))

    @staticmethod
    def _convert(response) -> LLMResponse:
        # 完整响应保留原始输出项，工具调用无需在增量事件中自行拼接。
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
