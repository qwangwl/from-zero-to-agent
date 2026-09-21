# day03-让LLM学会使用工具

在 day02 中，我们已经让 LLM 具备了多轮对话能力。

现在模型能够看到之前的 Message，也能够根据 Context 继续回答问题。

不过到目前为止，它仍然只能做一件事情：**生成文本。**这作为一个ChatBot已经足够了。

但如果我们问：

```text
You: 当前目录下有哪些文件？
```

模型就会遇到问题。因为LLM只能生成文本，它并不能直接访问我们的本地文件系统。

它可能回答：

```text
Assistant:  我无法直接查看你电脑上的“当前目录”。
```

LLM 能够理解用户的问题，但是它无法自己读取电脑上的文件。

但 Python 可以。例如我们可以使用：

```python
import os

print(os.listdir("."))
```

运行后可能得到：

```text
['.env', '.gitignore', 'README.md', 'codes']
```

如果能够把它们连接起来，那么 LLM 就不再只是“会说话”，而是可以开始借助外部工具完成任务。

首先定义一个最简单的函数：

```python
import os


def list_files():
    return os.listdir(".")
```

这个函数能够遍历当前目录下的文件，是我们今天提供给 LLM 的第一个 **Tool**。 不过现在有一个问题。LLM 并不知道我们的程序中存在这个工具。

所以我们需要主动告诉它：

> 你现在有哪些工具可以使用。

最简单的方法就是把工具信息写进 System Prompt。我们修订System Prompt。

```python
SYSTEM_PROMPT = """
你是一个智能助手。你的任务是分析用户请求，并使用可用工具一步步解决问题。

# 可用工具
- list_files(): 获取当前目录下的文件和文件夹。
"""
```

现在再次输入：

```text
You: 当前目录下有哪些文件？
```

模型已经知道：

```text
我有一个 list_files() 工具可以使用
```

所以它可能会回答一些信息说应该调用`list_files()`来查看当前目录。看起来模型已经知道应该使用哪个 Tool 了。

但是LLM并不具备执行代码的能力，它只是生成了一句话：`我需要调用 list_files()`

换句话说：

> **LLM 只是决定应该做什么，但是执行 Action 的仍然必须是我们的 Python 程序。**

一种最简单的办法当然是判断模型回答中有没有`list_files()`。

比如我们可以在代码中添加：

```python
if "list_files()" in response.output_text:
    result = list_files()
```

但是这存在一个问题。模型可能回答：

`我认为应该调用 list_files()`

也可能回答：

`下一步可以使用 list_files 工具。`

或者其他回答，甚至换一个模型、换一次采样，表达方式都有可能不同。对于人来说，这些句子的意思都差不多。但对于程序来说，稍微差一点都会导致程序的错误。这带来了一个问题：

> **LLM 的自然语言输出太自由，Python 程序无法稳定地知道它到底想执行什么。**

所以我们需要进一步约束模型的输出。

我们希望无论模型内部如何判断，最后都按照一个固定格式告诉程序：

```text
Thought: 我需要查看当前目录下的文件。
Action: list_files()
```

于是我们再次修改 System Prompt：

```python
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
```

此时，当我们再次运行代码并输出: `You: 当前目录下有哪些文件？`时，我们可以得到模型稳定的回复了：

```text
Assistant: Thought: 用户想知道当前目录下的文件，我需要先列出目录内容。
Action: list_files()
```

模型仍然在生成文本，但是这个文本开始具有固定的结构。

这就是一种最简单的 **Structured Output**。Structured Output 的目的并不是让回答看起来更整齐，而是**让模型的输出能够被程序稳定地解析和处理。**

现在我们可以写一个简单的解析函数来判断LLM是否需要我们执行程序了。

```python
def parse_action(response: str):
    marker = "Action:"
    marker_index = response.find(marker)

    if marker_index == -1:
        return None

    return response[marker_index + len(marker):].strip()
```

然后在代码的最后加入：
```python
print(assistant_message)

action = parse_action(assistant_message)

if action == "list_files()":
    result = list_files()
    print("Tool Result:", result)
```

此时再运行就得到了:
```text
You: 当前目录下有哪些文件？

Thought: 我需要查看当前目录中的文件和文件夹。
Action: list_files()

Tool Result: ['README.md', 'main.py', 'code']
```

到这里，我们终于真正打通了：

```text
用户请求
   |
   v
  LLM
   |
   | Structured Output
   v
 Action
   |
   v
 Parser
   |
   v
Python Function
   |
   v
File System
```

这就是一个最简单的 **Tool Calling**。

它其实可以拆成五步：

```text
1. 程序拥有一个 Tool

2. 通过 System Prompt 告诉 LLM Tool 的存在

3. LLM 根据任务决定应该使用哪个 Tool

4. LLM 使用固定结构输出 Action

5. Python 解析 Action，并真正执行 Tool
```

因此我们现在实际上第一次把模型和程序分成了两个角色：

```text
LLM
负责思考和决策

 ↓ Action

Python
负责真正执行
```

这已经开始有 Agent 的样子了。

完整源代码：`codes/day03`

## 本日新增与修改的文件

- [main.py](codes/day03/main.py)：修改：增加列目录工具，通过提示词约定工具调用格式，并解析、执行模型选择的操作。
