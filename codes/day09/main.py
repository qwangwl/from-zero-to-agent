import os
import readline
from dotenv import load_dotenv
from core.llm import OpenAILLM
from agent import Agent
from tools import ToolRegistry
from pathlib import Path
from tools.builtin import (
    FileTool,
)


load_dotenv()
API_KEY = os.environ["API_KEY"]
BASE_URL = os.getenv("BASE_URL")
MODEL_ID = os.environ["MODEL_ID"]

SYSTEM_PROMPT = """
你是一个能够处理文件的智能助手，请使用中文回答。
使用已声明的工具执行任务，只根据工具实际返回的结果描述文件和操作结果。
每次调用工具前，请用一句话说明本次操作的目的。
"""

workspace = Path.cwd()
registry = ToolRegistry()
registry.register_tool(FileTool(workspace))

llm = OpenAILLM(
    model_id=MODEL_ID,
    api_key=API_KEY,
    base_url=BASE_URL or None,
    timeout=60.0,
)

agent = Agent(
    llm=llm,
    system_prompt=SYSTEM_PROMPT,
    tool_registry=registry,
)

print(f"工作目录: {workspace}")
while True:
    
    user_input = input("You: ").strip()

    if user_input == "exit":
        break
    
    if user_input:
        print("Assistant:", agent.run(user_input))
