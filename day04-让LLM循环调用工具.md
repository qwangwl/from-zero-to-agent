# day04-让 LLM 循环调用工具

在 Day03 中，我们已经让 LLM 学会根据用户的问题选择并调用 `list_files()`。

例如用户输入：

```text
You: 当前目录下有哪些文件？
```

LLM 可以返回：

```text
Thought: 我需要查看当前目录中的文件和文件夹。
Action: list_files()
```

Python 程序解析 Action，并真正执行：

```python
list_files()
```

得到：

```text
Tool Result: ['codes', '.env', 'day02-让LLM记住我们说过的话.md', '.gitignore', 'day01-从一次简单的LLM调用开始.md']
```

看起来已经能够完成一些简单任务了。

但是这里还有一个明显的问题：

**Tool Result 只有 Python 程序知道，LLM 并没有看到工具执行的结果。**

在 Day03 中，我们只是：

```python
print("Tool Result:", result)
```

把结果打印到了终端，并没有重新发送给 LLM。

如果任务只是：

```text
当前目录下有哪些文件？
```

直接把 Tool Result 展示出来似乎也能解决问题。

但现在把任务稍微改复杂一点：

```text
You: 当前目录下有哪些文件？哪些文件是 Markdown 文件？
```

这时，仅仅调用一次 `list_files()` 就不够了。

程序首先可以得到：

```text
['codes', '.env', 'day02-让LLM记住我们说过的话.md', '.gitignore', 'day01-从一次简单的LLM调用开始.md']
```

接下来还需要根据这个结果判断：

```text
哪些文件的后缀是 .md？
```

当然，我们可以专门再写一段 Python 代码去筛选，但如果下一次任务变成：

```text
当前目录下有哪些文件？哪些文件是 Python 文件？
```

我们又需要增加新的处理逻辑。这样一来，程序的任务处理流程还是由我们提前写死的。

而一个更通用的方法是：

> **把 Tool Result 再交给 LLM，让模型根据工具执行结果继续完成任务。**

Tool 执行之后返回的结果，可以称为 **Observation**。

于是整个过程就变成：

```text
Thought
   ↓
Action
   ↓
Tool
   ↓
Observation
   ↓
Thought
   ↓
Action
```

模型根据当前 Context 决定下一步 Action。Python 执行 Action，得到 Observation。然后我们再把 Observation 放回 Context，让模型根据新的信息继续做出决策。

在 Day02 中，我们已经使用 `messages` 保存上下文，因此现在只需要把 Observation 追加进去：

```python
messages.append({
    "role": "user",
    "content": f"Observation: {observation}",
})
```

不过现在又有一个问题。虽然我们将 Observation，但是一次任务仍然无法完成我们的任务。

```text
You: 当前目录下有哪些文件？哪些文件是 Markdown 文件？

Thought: 我先查看当前目录下的所有文件和文件夹，然后从中筛选出 Markdown 文件。
Action: list_files()

Observation: ['codes','.env','day02-让LLM记住我们说过的话.md', '.gitignore', 'day01-从一次简单的LLM调用开始.md']

You: 哪些文件是 Markdown 文件？

Thought: 根据已获取的目录列表，筛选出扩展名为 `.md` 的文件。
Action: Finish[当前目录下的 Markdown 文件有：  

- day01-从一次简单的LLM调用开始.md  

- day02-让LLM记住我们说过的话.md ]

```

一个复杂任务可能需要多次`Thought -> Action -> Observation`过程。因此，我们需要一个循环。这就是今天要实现的：**Agent Loop。**

为了避免模型因为异常情况不断调用工具，产生无限循环和无意义的 API 消耗，我们暂时为 Agent 设置一个最大循环次数：

```python
for i in range(10):
    print(f"--- 循环 {i + 1} ---\n")

    # 1. 将当前 Context 发送给 LLM，
    #    让模型根据已有信息决定下一步 Action
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
    print()

    # 2. 解析 LLM 返回的 Action
    action = parse_action(assistant_message)

    # 3. 如果模型认为任务已经完成，
    #    提取最终答案并结束 Agent Loop
    if is_finish(action):
        answer = parse_finish(action)

        print("任务完成:", answer)
        print()

        break

    # 4. 执行模型选择的 Tool
    observation = None

    if action == "list_files()":
        observation = list_files()

    # 5. 将 Tool Result 作为 Observation 放回 Context
    messages.append({
        "role": "user",
        "content": f"Observation: {observation}",
    })
```

除此之外，我们还需要在 System Prompt 中告诉 LLM：

> Tool 执行完成以后，它会收到一个 Observation，并需要根据 Observation 决定下一步行动。

因此增加：

```python
SYSTEM_PROMPT = """
...

# 工作方式

你需要根据用户请求和已有的 Observation 决定下一步行动。

每次只能执行一个 Action。

当工具执行完成后，你会收到：

Observation: [工具执行结果]

请根据 Observation 继续思考并决定下一步行动。

...
"""
```

现在重新运行程序：

```text
You: 当前目录下有哪些文件？哪些文件是 Markdown 文件？
```

整个执行过程可能是：

```text
--- 循环 1 ---

Thought: 我需要先查看当前目录中的文件和文件夹。
Action: list_files()

Observation: ['codes', '.env', 'day02-让LLM记住我们说过的话.md', '.gitignore', 'day01-从一次简单的LLM调用开始.md']


--- 循环 2 ---

Thought: 我已经获得当前目录的文件列表，可以筛选其中扩展名为 .md 的 Markdown 文件。
Action: Finish[当前目录下的 Markdown 文件有：
- day01-从一次简单的LLM调用开始.md
- day02-让LLM记住我们说过的话.md]
```

这里最关键的变化就是：

**Tool Result 不再只是被打印出来，而是重新进入 Context，成为 LLM 下一次决策的依据。**

也就是说我们把最后的 Tool Result 重新连接回 LLM：

```text
       +--------------------+
       |                    |
       v                    |
      LLM                   |
       |                    |
       v                    |
     Action                 |
       |                    |
       v                    |
      Tool                  |
       |                    |
       v                    |
  Observation -------------+
       |
       v
     Finish
```

这个不断重复：

```text
Thought
→ Action
→ Observation
→ Thought
→ Action
→ Observation
→ ...
→ Finish
```

的过程，就是最简单的 **Agent Loop**。

到这里，我们已经拥有了第一个能够根据工具执行结果继续行动，直到任务完成的 Agent。

完整源代码：`code/day04`
