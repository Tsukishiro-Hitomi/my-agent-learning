# AI Agent 入门学习方案

> 面向有 Python 基础的 agent 新手，以"多动手"为核心。
> 动手载体：**Claude API + Python**。学习阶段用便宜快的 `claude-haiku-4-5` 反复练，复杂任务再换 `claude-opus-4-8`。

## 核心概念（先记住这一句）

> **Agent（智能体）= 一个大模型（LLM）+ 工具 + 一个循环。**
> 模型在循环里不断：**观察 → 思考该做什么 → 调用工具行动 → 看到结果 → 再思考……** 直到任务完成。

学 agent 最有效的顺序不是先学框架，而是**先亲手搭出这个循环**。理解它之后，框架只是帮你省事。

---

## 进度总览

- [yes] 阶段 0 · 环境准备
- [yes] 阶段 1 · LLM 基础（命令行聊天机器人）
- [yes] 阶段 2 · 工具调用 Tool Use
- [yes] 阶段 3 · 手写 Agent 循环 ⭐（最关键）
- [ ] 阶段 4 · 用 SDK 简化循环（tool_runner）
- [ ] 阶段 5 · 综合小项目
- [ ] 阶段 6 · 进阶概念（记忆 / RAG / 多 agent / 评估）

建议节奏：约 2–3 周，每天 1–2 小时。每阶段都有「✅ 验证」标准，用来自测"学会了没有"。

---

## 阶段 0 · 环境准备（0.5 小时）

```bash
pip install anthropic
export ANTHROPIC_API_KEY="你的key"   # 从 https://console.anthropic.com 获取
```

第一个调用（`hello.py`）：

```python
import anthropic

client = anthropic.Anthropic()  # 自动读取环境变量 ANTHROPIC_API_KEY

resp = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "用一句话解释什么是 AI agent"}],
)
print(resp.content[0].text)
```

**✅ 验证：** 终端打印出一句话回复。

---

## 阶段 1 · 理解 LLM 基础（2 小时）

**要点：API 是无状态的**——每次请求都要把完整对话历史发过去，模型才"记得"上文。这是理解后面一切的基础。

- `system`：系统提示词，定义模型角色/行为
- `messages`：`user` 与 `assistant` 交替的对话列表
- 多轮对话 = 自己维护 `messages` 列表并每轮追加

**动手：能连续对话的命令行聊天机器人（`chat.py`）**

```python
import anthropic

client = anthropic.Anthropic()
messages = []

while True:
    user_input = input("你: ")
    if user_input == "quit":
        break
    messages.append({"role": "user", "content": user_input})

    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system="你是一个友好的中文助手，回答简洁。",
        messages=messages,
    )
    reply = resp.content[0].text
    print(f"AI: {reply}")
    messages.append({"role": "assistant", "content": reply})  # 关键：把回复也存进历史
```

**✅ 验证：** 你说"我叫小明"，下一轮问"我叫什么"，它能答对。
**🔬 试一试：** 删掉追加 `assistant` 那一行，看它是否"失忆"——理解无状态。

---

## 阶段 2 · 工具调用 Tool Use（3 小时）

从"聊天机器人"到"agent"的第一道门槛。

**机制（务必理解这个来回）：**
1. 你把"工具说明书"（名字、描述、参数 schema）随请求发给模型
2. 模型若想用工具，返回 `stop_reason == "tool_use"`，并告诉你调用哪个工具、传什么参数
3. **模型不会自己执行**——由你的代码执行，把结果发回去
4. 模型拿到结果后生成最终回答

**动手：给模型一个"查天气"工具（`tool_use.py`，先用假数据打通流程）**

```python
import anthropic

client = anthropic.Anthropic()

tools = [{
    "name": "get_weather",
    "description": "获取某个城市的当前天气。当用户询问天气时调用此工具。",
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名，例如 北京"},
        },
        "required": ["city"],
    },
}]

def get_weather(city):
    return f"{city}：晴，25°C"  # 假数据，之后可换成真实 API

messages = [{"role": "user", "content": "北京今天天气怎么样？"}]

resp = client.messages.create(
    model="claude-haiku-4-5", max_tokens=1024, tools=tools, messages=messages,
)

if resp.stop_reason == "tool_use":
    messages.append({"role": "assistant", "content": resp.content})
    results = []
    for block in resp.content:
        if block.type == "tool_use":
            output = get_weather(**block.input)          # 你来执行
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,                 # 必须回传对应的 id
                "content": output,
            })
    messages.append({"role": "user", "content": results})

    resp = client.messages.create(
        model="claude-haiku-4-5", max_tokens=1024, tools=tools, messages=messages,
    )

print(next(b.text for b in resp.content if b.type == "text"))
```

**✅ 验证：** 打印出基于工具结果的回答（如"北京晴 25°C"）。
**🔬 试一试：** 加一个 `calculator` 工具，问"123 乘以 456 是多少"，看模型会不会主动选它。

---

## 阶段 3 · 手写 Agent 循环 ⭐（4 小时，最关键的一课）

阶段 2 只处理了"一次"工具调用。真正的 agent 会**连续多步**。做法：把阶段 2 包进 `while` 循环，直到模型不再要工具（`stop_reason == "end_turn"`）。这就是 **agent loop**，也叫 **ReAct 模式（Reason + Act，边推理边行动）**。

**动手：一个能操作文件的迷你 agent（`agent.py`）**

```python
import anthropic

client = anthropic.Anthropic()

tools = [
    {
        "name": "write_file",
        "description": "把内容写入一个文本文件。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "读取一个文本文件的内容。",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
]

def execute(name, args):
    if name == "write_file":
        with open(args["path"], "w") as f:
            f.write(args["content"])
        return f"已写入 {args['path']}"
    if name == "read_file":
        with open(args["path"]) as f:
            return f.read()

messages = [{"role": "user",
             "content": "创建一个 todo.txt，写入三件今天要做的事，然后读回来确认。"}]

while True:
    resp = client.messages.create(
        model="claude-haiku-4-5", max_tokens=1024, tools=tools, messages=messages,
    )
    for b in resp.content:
        if b.type == "text":
            print("🤖", b.text)
        if b.type == "tool_use":
            print(f"🔧 调用 {b.name}({b.input})")

    if resp.stop_reason != "tool_use":   # 模型不再需要工具 → 任务结束
        break

    messages.append({"role": "assistant", "content": resp.content})
    results = [
        {"type": "tool_result", "tool_use_id": b.id, "content": execute(b.name, b.input)}
        for b in resp.content if b.type == "tool_use"
    ]
    messages.append({"role": "user", "content": results})
```

**✅ 验证：** 运行后目录里出现 `todo.txt`，终端能看到模型**自己**分成"先写、再读、最后确认"多步完成。
**💡 恍然大悟点：** 你没写"先做A再做B"的流程代码——是模型在循环里**自己规划了步骤**。这就是 agent 和普通脚本的本质区别。

---

## 阶段 4 · 用 SDK 简化循环（2 小时）

手写循环理解透后，用 SDK 的 **Tool Runner** 自动跑循环，你只管写工具函数。

```python
import anthropic
from anthropic import beta_tool

client = anthropic.Anthropic()

@beta_tool
def get_weather(city: str) -> str:
    """获取某个城市的当前天气。

    Args:
        city: 城市名，例如 北京
    """
    return f"{city}：晴，25°C"

# tool_runner 自动跑"调用→执行→回传→再调用"的整个循环
runner = client.beta.messages.tool_runner(
    model="claude-haiku-4-5",
    max_tokens=1024,
    tools=[get_weather],
    messages=[{"role": "user", "content": "北京和上海今天天气怎么样？"}],
)

for message in runner:
    for block in message.content:
        if block.type == "text":
            print(block.text)
```

**✅ 验证：** 用 `tool_runner` 重写阶段 3 的文件 agent，行为一致但代码少一半。
**🎯 重点：** 对比阶段 3 和 4——你现在**知道框架背后到底做了什么**，比直接学框架的人理解深得多。

---

## 阶段 5 · 综合小项目（1 周）

挑一个感兴趣的，把前面全部串起来：

- **文件问答助手**：给 agent `read_file` + `list_dir` 工具，回答"我项目里 XX 功能在哪个文件"
- **联网研究助手**：用 Claude 内置服务端工具 `web_search`（无需自己实现），做"调研某话题并总结带出处"
- **数据分析 agent**：用内置 `code_execution` 工具，对 CSV 做统计并画图

Web search 版本（内置工具，模型直接联网）：

```python
resp = client.messages.create(
    model="claude-opus-4-8",   # 研究类任务建议用 opus
    max_tokens=4096,
    tools=[{"type": "web_search_20260209", "name": "web_search"}],
    messages=[{"role": "user",
               "content": "调研一下 2025 年 AI agent 的主要开源框架，列出3个并说明特点"}],
)
```

**✅ 验证：** 项目端到端跑通，且你能对别人讲清"我的 agent 有哪些工具、循环怎么转"。

---

## 阶段 6 · 进阶概念（理解为主，按需深入）

会搭 agent 后，让它更强、更可靠的方向：

- **记忆 / 持久化**：跨会话记住东西（存文件/数据库，下次读回来）
- **RAG（检索增强）**：接知识库，回答前先检索——解决"模型不知道你私有数据"
- **上下文管理**：对话太长会超上下文窗口，了解 `compaction`（自动压缩历史）
- **多 Agent 协作**：一个"协调者"把任务拆给多个专职 agent（研究员、写手、审校）
- **评估（Evals）**：科学判断 agent 好不好——从玩具到生产的关键
- **安全护栏（Guardrails）**：危险操作（删文件、发邮件、花钱）加人工确认

不用一次学完，做项目遇到瓶颈时再针对性补。

---

## 备忘

- 便宜练手模型：`claude-haiku-4-5`；复杂 agent 任务：`claude-opus-4-8`
- 关键心智模型：API 无状态 → 每轮发完整历史；agent = LLM + 工具 + 循环
- 起步文件建议：`hello.py`(阶段0) → `chat.py`(阶段1) → `tool_use.py`(阶段2) → `agent.py`(阶段3)