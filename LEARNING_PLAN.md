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
- [yes] 阶段 4 · 用 SDK 简化循环（tool_runner）
- [yes] 阶段 5 · 综合项目：多工具代码库 agent（capstone）
- [yes] 阶段 6 · 让 agent 更强更可靠（记忆 / 多 agent / RAG / 评估 / 护栏）

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

阶段 2 只处理了"一次"工具调用。真正的 agent 会**连续多步**。做法：把阶段 2 包进 `while` 循环，直到模型不再要工具（`stop_reason != "tool_use"`）。这就是 **agent loop**，也叫 **ReAct 模式（Reason + Act，边推理边行动）**。

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

## 阶段 5 · 综合项目 capstone：多工具代码库问答 agent（1 周）

把前 4 阶段全部串起来，做一个**迷你版 Claude Code**：给 agent 几个操作文件的工具，
它就能**自主探索一个真实目录**回答关于代码的问题——先列目录 / 搜关键字定位文件，
再读文件细节，最后基于内容作答。"先看哪、再看哪"由**模型自己规划**。

> 和前几阶段不同：这一阶段**代码量大、提示少**。练习里只给每个函数的「契约」
> （签名、返回什么、要处理哪些边界、评测查什么），**不给实现代码**——自己写出来。

**这一阶段新学的三件「真实 agent 必备」的事：**
1. **工具会失败 → 错误回传给模型，不能让程序崩**：文件不存在时工具返回「错误：…」字符串，
   模型看到还能自己重试；`execute()` 再用 try/except 兜底，一个工具炸了不掀翻整个循环。
2. **循环护栏 `MAX_STEPS`**：阶段 3 的 `while True` 留的坑，现在亲手补上——到上限就停。
3. **系统提示词(system) + 多工具分发**：用 `system` 告诉 agent 怎么工作，用多个工具扩展能力。

**动手：`exercises/stage5_codebase_agent/`**（练习对象是里面的示例项目 `sandbox/`）

```bash
./run.sh 5          # 评测分两段：先跑不花钱的「离线单测」，全过了才跑「在线端到端」
```

**✅ 验证：** 离线段（工具/schema/execute/护栏全对）+ 在线段（agent 自主多步、
用了发现类工具 + read_file、答对藏在 sandbox 里的问题）都通过；且你能对别人讲清
"我的 agent 有哪些工具、循环怎么转、错误和护栏怎么处理"。

**想挑战更多（可选，非必做）：** 换成 Claude 内置服务端工具做**联网研究助手**
（`web_search`）或**数据分析 agent**（`code_execution`）。注意这类服务端工具需要
**直连 Anthropic API**（或支持服务端工具的网关）——你当前 `.env` 里的 `ANTHROPIC_BASE_URL`
代理不一定支持，先确认能用再动手。

---

## 阶段 6 · 让 agent 更强、更可靠（进阶：拆成 5 个可动手的小关）

你已经会从零搭一个完整 agent 了。阶段 6 不再"理解为主"——**每一关都在你阶段 5 的代码库 agent 上加一个真实能力**。按下面推荐顺序做，每关都有 ✅ 验证。**这 5 关的练习 + 评测都已备好**，和前面一样是"你写代码、评测打分"，用 `./run.sh 6.1` ~ `./run.sh 6.5` 运行（评测都分「离线不花钱」+「在线端到端」两段）。

推荐顺序（一句话目标）：
- [ ] 6.1 记忆 / 持久化 —— 让 agent 跨会话记住东西（热身，最快见效）
- [ ] 6.2 多 Agent 协作 ⭐ —— 一个 sub-agent 其实就是一个工具（本阶段高潮，代码最多）
- [ ] 6.3 RAG 检索增强 —— 从你的私有文档里带出处作答
- [ ] 6.4 评估 Evals —— 用分数科学衡量 agent 好不好
- [ ] 6.5 安全护栏 —— 危险操作先人工确认

### 6.1 记忆 / 持久化（无新依赖）
**建**：给 agent 加两个工具 `save_memory(key, value)` / `recall_memory()`，背后存一个 `memory.json`；或把整段 `messages` 落盘、下次读回来续上。
**✅ 验证**：会话 1 告诉它"我叫小明、在做订单服务"→ 退出进程 → 会话 2 问"我叫什么、在做什么项目"，它答得出。
**💡 aha**：所谓"记忆"没有魔法，就是把信息**落盘、下次塞回 context**。API 依然无状态。

### 6.2 多 Agent 协作 ⭐（无新依赖，代码量最大）
**建**：一个"协调者"agent，它的工具不是文件操作，而是**别的 agent**——比如 `researcher(question)` 和 `writer(notes)`。这两个子 agent 内部各自跑一遍你阶段 5 的 `run_agent` 循环（各配专职的工具 + system prompt）。
**✅ 验证**：给协调者一个复合任务（"调研 sandbox 项目、写一段 README 草稿"），看它把活拆给 researcher 收集、交给 writer 成文、最后合并。
**💡 aha**：一个 sub-agent 本质就是"一个会自己跑循环的工具"——你阶段 5 的 `run_agent` 直接就能当子 agent 用。这正是 **Claude Code 的 subagents** 背后的模型。

### 6.3 RAG（检索增强）
**建**：一个 `retrieve(query)` 工具，在你的私有文档（`docs/` 目录）里找出最相关的片段喂进 context，再让 agent **带出处**作答。起步用「关键字检索」即可——你阶段 5 的 `search_files` 几乎就是雏形（RAG lite）；进阶再上「向量检索」（embeddings：文本转向量、按相似度召回）。
**⚠️ 注意**：真正的向量检索要调 **embeddings API**，和 `web_search` 一样属于服务端能力，你当前的代理不一定支持——先用关键字版打通，确认代理支持 embeddings 再升级。
**✅ 验证**：问一个只有私有文档里才有答案的问题，agent 先检索、再作答，并指出答案来自哪个文档。
**💡 aha**：RAG = **回答前先检索、把原文塞进 prompt**，解决"模型不知道你的私有/最新数据"。

### 6.4 评估（Evals，无新依赖）
**建**：其实你这一路的 `test.py` 就是评估！现在把它一般化：准备 ≥5 个 `(问题, 期望答案要点)` 用例，让 agent 逐个跑、自动判对错（关键字命中，或 **LLM-as-judge**：再叫一个模型判"答得对不对"），打出一张分数表。
**✅ 验证**：跑出一张 5/5 记分卡；改一下 `SYSTEM_PROMPT` 或工具描述，重跑，看分数怎么变——**用数据驱动改进，而不是凭感觉**。
**💡 aha**：没有 eval，你永远说不清"改了 prompt 到底变好还是变坏"。这是玩具走向生产的分水岭。

### 6.5 安全护栏（Guardrails，无新依赖）
**建**：在 `execute` 里，遇到"危险工具"（写/删文件、发请求、花钱）先暂停，打印"即将执行 X，确认吗？(y/n)"，等人确认再跑。你阶段 5 的 `MAX_STEPS` 已是一种护栏，这里加"人在环 (human-in-the-loop)"。
**✅ 验证**：让 agent 尝试写/删文件，它会先停下等你确认；输入 `n` 就跳过，并把"用户拒绝"作为 tool_result 回给模型。
**💡 aha**：agent 越自主，越要在**不可逆/有代价**的动作上留一道人工闸门。

> 还有一个按需了解、不必动手的话题：**上下文管理 / compaction**——对话太长会超出上下文窗口，框架会自动把旧历史压缩成摘要。做多 agent 或长对话遇到瓶颈时再看。

建议从 **6.1（热身）** 开始，按顺序做到 **6.5**。每关目录：`exercises/stage6_1_memory` … `exercises/stage6_5_guardrails`。卡住随时找我要"一点提示"。

---

## 备忘

- 便宜练手模型：`claude-haiku-4-5`；复杂 agent 任务：`claude-opus-4-8`
- 关键心智模型：API 无状态 → 每轮发完整历史；agent = LLM + 工具 + 循环
- 起步文件建议：`hello.py`(阶段0) → `chat.py`(阶段1) → `tool_use.py`(阶段2) → `agent.py`(阶段3)
- 远端 github 仓库： https://github.com/Tsukishiro-Hitomi/my-agent-learning.git