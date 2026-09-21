# from-zero-to-agent

这是一个从零开始学习 AI Agent 开发的实践项目。

项目不依赖复杂的 Agent 框架，而是从最基础的 LLM 调用开始，逐步实现更完整的 Agent。

## 学习路线

1. [day01-从一次简单的 LLM 调用开始](day01-从一次简单的LLM调用开始.md)
2. [day02-让 LLM 记住我们说过的话](day02-让LLM记住我们说过的话.md)
3. [day03-让 LLM 学会使用工具](day03-让LLM学会使用工具.md)
4. [day04-让 LLM 循环调用工具](day04-让LLM循环调用工具.md)
5. [day05-重构 Agent 并支持多个工具](day05-重构%20Agent%20并支持多个工具.md)
6. [day06-使用 Function Calling 重构工具调用](day06-使用%20Function%20Calling%20重构工具调用.md)

## 环境要求

- Python 3.10 或更高版本；
- 一个兼容 OpenAI API 格式的模型服务；
- 对 Python 基础语法有基本了解。

## 安装依赖

```bash
pip install openai python-dotenv
```

## 配置环境变量

在项目根目录创建 `.env` 文件：

```env
API_KEY="YOUR_API_KEY"
BASE_URL="YOUR_BASE_URL"
MODEL_ID="YOUR_MODEL_ID"
```

示例：

```env
API_KEY="your-api-key"
BASE_URL="https://api.deepseek.com"
MODEL_ID="your-model-id"
```

请不要把真实 API Key 提交到 Git 仓库。项目已经通过 `.gitignore` 忽略 `.env` 文件。

## 运行示例

从项目根目录运行对应 Day 的代码：

```bash
python codes/day01/main.py
```

不同 Day 的代码相互独立，可以按照顺序学习，也可以单独运行某一天的示例。
