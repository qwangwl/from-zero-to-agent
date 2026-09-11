import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_ID = os.getenv("MODEL_ID")


SYSTEM_PROMPT = """
你是一个智能助手。你的任务是分析用户请求，并使用可用工具一步步解决问题。

# 可用工具

- list_files(): 获取当前目录下的文件和文件夹。

# 输出格式

你的每次回复必须严格使用下面的格式：

Thought: [简要说明下一步准备做什么]
Action: [要执行的具体行动]

Action 必须是下面两种格式之一：

1. 调用工具：
function_name(arg_name="arg_value")

2. 完成任务：
Finish[最终答案]
"""


client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

def list_files():
    return os.listdir(".")

def parse_action(response: str):
    marker = "Action:"
    marker_index = response.find(marker)

    if marker_index == -1:
        return None

    return response[marker_index + len(marker):].strip()

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

    print(assistant_message)

    action = parse_action(assistant_message)

    result = None
    if action == "list_files()":
        result = list_files()

    print("Tool Result:", result)
    print()
