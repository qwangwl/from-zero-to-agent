import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_ID = os.getenv("MODEL_ID")


SYSTEM_PROMPT = """
你是一名资深 Agent 开发研究者。

请遵守以下规则：
1. 使用中文回答；
2. 尽量使用简单的语言；
3. 遇到抽象概念时给出例子；
4. 回答尽量简洁。
"""

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

messages = []

while True:
    user_input = input("You: ")

    if user_input == "exit":
        break

    messages.append({
        "role": "user",
        "content": user_input,
    })

    response = client.responses.create(
        model=MODEL_ID,
        instructions=SYSTEM_PROMPT,
        input=messages,
    )

    assistant_message = response.output_text
    messages.append({
        "role": "assistant",
        "content": assistant_message,
    })

    print("Assistant:", assistant_message)
