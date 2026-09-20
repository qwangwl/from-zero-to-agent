import os
from dotenv import load_dotenv
from openai import OpenAI
from agent import Agent
from tools import ToolRegistry
from tools.builtin import (
    ListFilesTool,
    ReadFileTool,
    CreateDirectoryTool,
    CreateFileTool,
    EditFileTool,
    DeleteFileTool,
)


load_dotenv()
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_ID = os.getenv("MODEL_ID")

SYSTEM_PROMPT = """
你是一个能够处理文件的智能助手，请使用中文回答。
使用已声明的工具执行任务，只根据工具实际返回的结果描述文件和操作结果。
"""

registry = ToolRegistry()
registry.register_tool(ListFilesTool())
registry.register_tool(ReadFileTool())
registry.register_tool(CreateDirectoryTool())
registry.register_tool(CreateFileTool())
registry.register_tool(EditFileTool())
registry.register_tool(DeleteFileTool())

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

agent = Agent(
    client=client,
    model_id=MODEL_ID,
    system_prompt=SYSTEM_PROMPT,
    tool_registry=registry,
)

while True:
    
    user_input = input("You: ").strip()

    if user_input == "exit":
        break
    
    if user_input:
        print("Assistant:", agent.run(user_input))
