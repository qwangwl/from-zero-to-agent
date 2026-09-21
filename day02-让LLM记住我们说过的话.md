# day02-让 LLM 记住我们说过的话

在 Day01 中，我们已经可以让 Python 调用 LLM，并通过循环不断提问。

但是现在的程序还有一个问题：虽然我们可以连续输入多个问题，但模型并不知道前面发生过什么。

例如：

```text
You: 我是小明
Assistant: 你好，小明！
You: 我叫什么
Assistant: 我不知道你的名字，因为你还没有告诉我。
```

这是因为 Day01 的程序每次请求都只把**当前问题**发送给模型：

```python
response = client.responses.create(
    model=MODEL_ID,
    instructions=SYSTEM_PROMPT,
    input=user_input
)
```

模型并不会自动记住之前的请求。我们可以先把 LLM 理解成一个无状态函数：

```text
LLM(当前输入) -> 当前输出
```

如果希望模型知道之前的对话，就需要由程序保存历史，并在下一次请求时一起发送：

```text
LLM(历史对话 + 当前问题) -> 当前输出
```

于是我们可以先使用一个最简单的方法，使用一个 Python 列表保存对话。


我们首先在循环外创建一个列表：

```python
messages = []

while True:
    ...
```

用户每次输入问题后，把它保存为一条 `user` 消息：

```python

user_input = input("You: ")

messages.append({
    "role": "user",
    "content": user_input
})
```

模型回复后，再把回复保存为一条 `assistant` 消息：

```python
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
```

那么完整的一段对话自然可以保存成一个 Message 列表：

```python
messages = [
    {
        "role": "user",
        "content": "我叫小明"
    },
    {
        "role": "assistant",
        "content": "你好，小明！"
    },
    {
        "role": "user",
        "content": "我叫什么名字？"
    }
]
```

下一次请求时，把整个 `messages` 作为 `input` 发送：

```python
response = client.responses.create(
    model=MODEL_ID,
    instructions=SYSTEM_PROMPT,
    input=messages
)
```

现在重新运行程序：

```text
You: 我叫小明
Assistant: 你好，小明！我是研究 Agent 开发的。有什么想了解的，尽管问。
You: 我叫什么
Assistant: 你叫小明。
```

我们发现程序已经记住我们叫什么了。这也是今天非常重要的一个认识：**LLM 并不是因为上一次调用过它，就自动记住了之前发生的事情。**真正保存对话历史的是我们的应用程序。

现在程序的结构已经从 day01 的：

```text
User
 |
 v
LLM
 |
 v
Response
```

变成：

```text
                messages
                   |
                   v
User ----------> append
                   |
                   v
                  LLM
                   |
                   v
               Response
                   |
                   v
                append
                   |
                   +----------> 下一轮
```

对话历史保存下来之后，模型就能够基于之前的内容继续回答问题。

不过这里还隐藏着一个非常重要的概念。每一次调用模型时，我们实际上会提供：

```text
System Prompt
+
messages
```

比如：
```text
System Prompt:

你是一名面向 Agent 初学者的老师。


User:
我叫小明

Assistant:
你好，小明！


User:
我正在学习 Agent

Assistant:
很不错！


User:
我现在在学习什么？
```

这些模型在当前这一次调用中能够看到的信息，可以统称为：

**Context。**

简单表示就是：

```text
┌──────────────────────────┐
│         Context          │
│                          │
│ System Prompt            │
│                          │
│ User: 我叫小明            │
│                          │
│ Assistant: 你好，小明     │
│                          │
│ User: 我正在学习 Agent    │
│                          │
│ Assistant: 很不错         │
│                          │
│ User: 我现在在学习什么？   │
└─────────────┬────────────┘
              |
              v
             LLM
              |
              v
           Response
```

因此，LLM 当前的回答不仅取决于用户最后输入的那一句话，也取决于模型当前能够看到的整个 Context。

到这里，day02 已经完成了一个很重要的变化：

day01 中：

```python
input=user_input
```

模型每次只能看到当前输入。

而现在：

```python
input=messages
```

模型能够看到之前的对话。

我们的程序也第一次真正具备了多轮对话能力。

## 本日新增与修改的文件

- [main.py](codes/day02/main.py)：修改：使用消息列表保存历史，并在每次请求中携带之前的对话。
