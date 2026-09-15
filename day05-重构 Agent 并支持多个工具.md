# day05-重构 Agent 并支持多个工具

Day04 已经实现了一个最小的 Agent Loop：

```text
Thought → Action → Tool → Observation → Thought → Finish
```

现在，我们给 Agent 增加一个新的能力：**读取指定文件的内容**。

先新增一个 `read_file()` 工具：

```python
def read_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
```

同时修改 System Prompt，让 LLM 知道现在有哪些工具可以使用：

```text
# 可用工具

- list_files(): 获取当前目录下的文件和文件夹。
- read_file(path: str): 读取指定文件的内容。
```

接着，在工具执行部分增加对 `read_file()` 的处理：

```python
if action == "list_files()":
    observation = list_files()

if action.startswith("read_file("):
    path = action.split('path="')[1].split('"')[0]
    observation = read_file(path)
```

现在，我们的 Agent 已经同时拥有了**查看目录**和**读取文件**两个工具。

运行程序测试一下：

```text
You: 这个项目是什么

--- 循环 1 ---

Thought: 先查看当前目录下有哪些文件和文件夹，了解项目结构。
Action: list_files()

--- 循环 2 ---

Thought: 阅读 README.md 了解项目说明。
Action: read_file(path="README.md")

--- 循环 3 ---

Thought: 已经通过 README.md 了解了项目内容，可以直接总结回答。
Action: Finish[这是一个从零实现 Agent（智能体）的教程项目，叫 30daysAgent。它按天记录学习过程，从简单的 LLM 调用开始，逐步让 LLM 学会记忆对话、使用工具、循环调用工具，并重构支持多个工具。目前最新是 day05，代码结构分为 main.py（用户输入）、agent.py（Agent Loop）和 tools.py（具体工具）。]

任务完成: 这是一个从零实现 Agent（智能体）的教程项目，叫 30daysAgent。它按天记录学习过程，从简单的 LLM 调用开始，逐步让 LLM 学会记忆对话、使用工具、循环调用工具，并重构支持多个工具。目前最新是 day05，代码结构分为 main.py（用户输入）、agent.py（Agent Loop）和 tools.py（具体工具）。
```

可以看到，LLM 已经可以根据任务自己选择调用 `list_files()` 和 `read_file()`。

Day04 中，我们只有：

```text
list_files()
```

现在，Agent 可以在多个 Tool 之间进行选择：

```text
list_files()
read_file(path)
```

不过随着功能继续增加，我们的 `main.py` 也开始变得越来越长。

现在它同时包含：

```text
LLM 调用
Agent Loop
Action 解析
Tool 执行
用户输入
```

如果以后继续加入更多 Tool 或新的 Agent 能力，所有代码都堆在一个文件中会越来越难维护。

因此，我们顺便对当前代码做一次简单的重构。

这里并不会改变 Agent 的行为，只是重新组织代码结构，让不同模块负责不同的功能。

将目录调整为：

```text
code/day05/

├── main.py      # 负责接收用户输入
├── agent.py     # 负责 Agent Loop 和 Action 处理
└── tools.py     # 负责具体 Tool
```

首先是 `tools.py`：

```python
import os


def list_files():
    return os.listdir(".")


def read_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
```

这样，所有 Tool 都集中放在一个文件中。

接下来创建 `agent.py`。

我们把 Day04 中与 Agent 相关的逻辑封装成一个 `Agent` 类：

```python
from tools import list_files, read_file


class Agent:
    def __init__(self, client, model_id, system_prompt):
        self.client = client
        self.model_id = model_id
        self.system_prompt = system_prompt

    def run(self, user_input: str):
        messages = [{
            "role": "user",
            "content": user_input,
        }]

        for i in range(10):
            print(f"--- 循环 {i + 1} ---\n")

            # 将当前 Context 发送给 LLM，让 LLM 决定下一步 Action
            response = self.client.responses.create(
                model=self.model_id,
                instructions=self.system_prompt,
                input=messages,
            )

            assistant_message = response.output_text

            messages.append({
                "role": "assistant",
                "content": assistant_message,
            })

            print()
            print(assistant_message)
            print()

            # 解析 LLM 返回的 Action
            action = self.parse_action(assistant_message)

            # 如果 LLM 返回 Finish，提取最终答案并结束本次任务
            if self.is_finish(action):
                answer = self.parse_finish(action)

                print("任务完成:", answer)
                print()

                break

            # 执行 Tool
            observation = None

            if action == "list_files()":
                observation = list_files()

            if action.startswith("read_file("):
                path = action.split('path="')[1].split('"')[0]
                observation = read_file(path)

            # 将 Tool Result 作为 Observation 放回 Context
            messages.append({
                "role": "user",
                "content": f"Observation: {observation}",
            })

    def parse_action(self, response: str):
        ...

    def is_finish(self, action: str):
        ...

    def parse_finish(self, action: str):
        ...
```

现在，原来散落在 `main.py` 中的 Agent Loop、Action 解析和 Tool 执行逻辑都被集中到了 `Agent` 类中。

于是 `main.py` 就可以变得非常简单，只负责初始化 Agent 和接收用户输入：

```python
...

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
```


现在集中在 `main.py` 中的代码拆分成了更清晰的模块，为后面继续增加新的 Agent 能力做好了准备。

完整源代码：`codes/day05`
