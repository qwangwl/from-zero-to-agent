import os

from dotenv import load_dotenv
from openai import OpenAI
from agent import Agent

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_ID = os.getenv("MODEL_ID")


SYSTEM_PROMPT = """
你是一个智能助手。

请根据用户请求选择合适的工具，并根据工具结果继续完成任务。
工具已经通过 Function Calling 声明，不需要输出 Thought、Action 或 Finish。

请使用中文回答，不要假设没有通过工具获得的文件信息。
"""


client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)


agent = Agent(
    client=client,
    model_id=MODEL_ID,
    system_prompt=SYSTEM_PROMPT,
)


while True:
    user_input = input("You: ")

    if user_input == "exit":
        break

    agent.run(user_input)
