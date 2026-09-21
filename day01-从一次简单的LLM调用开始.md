# day01-从一次最简单的LLM调用开始

在开始本项目之前，希望读者具备一定的 Python 编程能力，能够独立运行和调试简单的 Python 程序。

同时，建议读者对 Agent 有一些基础了解，知道 Agent 通常会结合大语言模型、工具调用、记忆和任务规划等能力完成目标。如果你还不了解这些概念，也不必担心，本项目会在实践过程中逐步介绍。

我们的目标是从最简单的一次 LLM 调用开始，一点点实现一个属于自己的 Agent。Agent 看起来有很多复杂的概念，例如 Tool、Memory、Planning、Workflow 等，但无论一个 Agent 最后有多复杂，它最核心的部分始终离不开 LLM。

**让 Python 程序和 LLM 说上第一句话。**

首先安装需要使用的 SDK：

```bash
pip install openai python-dotenv
```

调用模型需要 API Key。我们当然可以直接写在代码中：`client = OpenAI(api_key="YOUR_API_KEY")`

但是在修改时，就会变得过于麻烦，需要在每一个调用的地方都进行修改。因此这里使用环境变量保存 API Key。将 API Key 放在 .env 中可以避免把密钥直接写入源代码。

在项目根目录创建一个 .env 文件：

```python
API_KEY = "YOUR_API_KEY"
BASE_URL = "YOUR_BASE_URL"
MODEL_ID = "YOUR_MODEL_ID"
```

然后创建一个 `main.py`， 我们以DeepSeek为例，假如你需要使用其他模型，请自行修改：

```python
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_ID = os.getenv("MODEL_ID")

client = OpenAI(api_key=API_KEY,
                base_url=BASE_URL)

response = client.responses.create(
    model=MODEL_ID,
    input="你好，简单介绍一下自己"
)

print(response.output_text)
```
运行：

```bash
python main.py
```

如果配置正确，我们应该可以看到类似下面的输出：

```text
你好！我是一个 AI 助手，可以帮助你回答问题、分析内容以及完成各种任务。
```

到这里，我们已经完成了第一次 LLM 调用。

代码其实非常简单，真正关键的只有这一部分：

```python
response = client.responses.create(
    model=MODEL_ID,
    input="你好，简单介绍一下自己"
)
```

我们不用关心模型内部到底发生了什么，从应用开发的角度，我们完全可以先把 LLM 看成一个函数：

```text
LLM(input) -> output
```

给模型一个输入，模型生成一个输出。

例如：

```text
"什么是 TCP？"
        |
        v
       LLM
        |
        v
"TCP 是一种面向连接的传输层协议……"
```

后面我们会不断给这个简单的结构增加新的能力，但无论是 Tool Calling、Memory 还是 Agent Loop，最底层始终离不开一次次这样的模型调用。

不过现在还有一个很明显的问题，我们的问题被直接写死在了程序里：

如果每问一个问题都需要修改一次代码，那这个程序显然没什么用。

所以我们可以使用 `input` 获取用户输入：

```python
from openai import OpenAI

client = OpenAI(...)

user_input = input("You: ")

response = client.responses.create(
    model=MODEL_ID,
    input=user_input
)

print("Assistant:", response.output_text)
```

再次运行程序：

```text
You: 什么是 Agent？

Assistant: Agent 通常指能够根据目标进行推理并执行任务的智能系统……
```

现在我们已经可以输入任意问题了。

但问完一个问题之后，程序就退出了。如果想继续问，就需要重新运行一次：

```bash
python main.py
```

这显然也有些麻烦。

既然我们希望和模型持续交互，最简单的方法就是给程序加一个循环，并通过`exit`进行退出：

```python
client = OpenAI(...)

while True:
    user_input = input("You: ")

    if user_input == "exit":
        break

    response = client.responses.create(
        model=MODEL_ID,
        input=user_input
    )

    print("Assistant:", response.output_text)
```

现在再次运行：

```text
You: 你好

Assistant: 你好！😊 很高兴见到你。有什么我可以帮你的吗？无论是问题解答、写作协助、代码编程，还是日常闲聊，我都很乐意帮忙。

You: 你是谁

Assistant: 我是由深度求索（DeepSeek）开发的 AI 助手，可以帮你解答问题、写作、翻译、编程、学习等。有什么需要帮忙的吗？

You: exit
```

程序就会结束。

到这里，我们已经实现了一个非常简单的命令行 LLM 程序，这其实就是一个简单的Chatbot：

```text
      ┌───────────────────┐
      │                   │
      v                   │
    User                  │
      |                   │
      v                   │
     LLM                  │
      |                   │
      v                   │
  Response ───────────────┘
```

但现在我们再考虑一个问题。

假设我们希望这个程序不是一个普通的聊天机器人，而是一个专门帮助初学者学习编程的助手。

我们可以这样问：

```text
You: 你是一名资深 Agent 开发研究者，请使用简单的语言解释什么是 Tool Calling。
```

模型会按照我们的要求回答。

但是下一次如果想问 Memory，我们又需要写：

```text
You: 你是一名资深 Agent 开发研究者，请使用简单的语言解释什么是 Memory。
```

再问 Agent Loop：

```text
You: 你是一名资深 Agent 开发研究者，请使用简单的语言解释什么是 Agent Loop。
```

每次都重复：

```text
你是一名资深 Agent 开发研究者，请使用简单的语言……
```

显然没有必要。

像“你是谁”、“应该使用什么语言回答”、“回答应该是什么风格”这样的要求，并不是某一次用户请求的一部分，而是希望模型在整个程序运行过程中都遵守的规则。

因此我们可以给模型增加一个 **System Prompt**。

例如：

```python
SYSTEM_PROMPT = """
你是一名资深 Agent 开发研究者。

请遵守以下规则：
1. 使用中文回答；
2. 尽量使用简单的语言；
3. 遇到抽象概念时给出例子；
4. 回答尽量简洁。
"""
```

然后把它作为模型的系统指令：

```python
from openai import OpenAI

client = OpenAI()

SYSTEM_PROMPT = """
你是一名资深 Agent 开发研究者。

请遵守以下规则：
1. 使用中文回答；
2. 尽量使用简单的语言；
3. 遇到抽象概念时给出例子；
4. 回答尽量简洁。
"""

while True:
    user_input = input("You: ")

    if user_input == "exit":
        break

    response = client.responses.create(
        model="YOUR_MODEL",
        instructions=SYSTEM_PROMPT,
        input=user_input
    )

    print("Assistant:", response.output_text)
```

现在我们只需要输入：

```text
You: 什么是 Agents？
```

模型就会按照我们预先设定的角色和规则回答。

例如：

```text
Assistant: **Agent（智能体）**可以理解为一个“会自己干活的AI程序”。

它不是只回答问题，而是能：

1. **感知环境**：读取用户指令、网页、文件、传感器信息等。  
2. **做决定**：判断下一步该做什么。  
3. **采取行动**：调用工具，比如搜索、写文件、发邮件、操作浏览器。  
4. **记住过程**：保存上下文，继续推进任务。  
5. **朝目标前进**：多步执行，直到完成任务。

**例子**：  
你说：“帮我订明天去上海的便宜机票。”  
普通聊天机器人只会告诉你“可以去某网站查”。  
Agent 则会：查航班 → 比价格 → 选一个 → 询问确认 → 调用订票工具下单。

所以，一句话：**Agent 是能感知、思考、行动，并自主完成目标的智能程序。**
```

我们可以比较一下在没有`System Prompt`时的回复。

这里第一次出现了两种不同的信息：

```text
System Prompt
```

描述模型应该是谁、应该如何工作，而：

```text
User Input
```

描述用户当前希望模型完成什么任务。

可以简单表示为：

```text
System Prompt
      |
      v
     LLM <------ User Input
      |
      v
   Response
```

以后我们实现真正的 Agent 时，也会经常使用 System Prompt 来描述 Agent 的身份、职责和行为规则。例如一个 Coding Agent，可能会被告知：

```text
你是一个负责分析和修改代码的 Coding Agent。
```

一个 Reviewer Agent 可能会被告知：

```text
你是一个负责检查代码质量和潜在错误的 Reviewer。
```

不过这些都是后话。

至此，day01 的程序已经基本完成了。进入 `codes/day01` 目录运行：

```bash
python main.py
```

我们就可以在终端中不断向模型提问：

```text
You: 你好
Assistant: 你好！有什么可以帮助你的吗？

You: 什么是 Agent？
Assistant: Agent（智能体）可以理解为一个“会自己干活的AI程序”...

You: exit
```

完整源代码：`code/day01`

## 本日新增与修改的文件

- [main.py](codes/day01/main.py)：新增：读取环境变量，调用模型并提供终端问答入口。