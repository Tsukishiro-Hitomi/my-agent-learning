# my-agent · 从零手写一个 AI Agent

**注意：本 readme 文档 由 claude code 帮我生成**

这个仓库记录了我**不依赖任何 agent 框架、用 Claude API + Python 从零把一个 agent 亲手搭出来**的完整过程。

我没有直接上 LangChain 之类的框架，而是选择先自己实现 agent 的核心——一个"模型 + 工具 + 循环"的引擎——从最基础的一次 API 调用，一路做到一个能自主探索代码库的迷你版 Claude Code，再给它加上记忆、多 agent 协作、RAG、评估和安全护栏。仓库里每个阶段的实现代码都是我自己写的，配套的 `test.py` 是用来验证我写对了没有的评测。

> **我最大的收获,浓缩成一句话:**
> **Agent = 一个大模型(LLM) + 工具 + 一个循环。**
> 模型在循环里不断「观察 → 想该做什么 → 调工具行动 → 看结果 → 再想」,直到任务完成。理解了这一点,再看任何 agent 框架都只是"帮我省事",而不再是黑盒。

---

## 我的学习路径

我把学习拆成了循序渐进的几个阶段,每一步都在上一步的基础上加一个真实能力。下面这张表是我走过的路,以及**每一步我真正理解到的东西**:

| 阶段 | 我实现了什么 | 我理解到的关键点 |
|------|--------------|------------------|
| 1 · LLM 基础 | 一个能记住上文的命令行聊天机器人 | **API 是无状态的**——模型不会自己记得上文,是我每轮把完整历史发过去,它才"有记忆" |
| 2 · 工具调用 | 给模型接了第一个工具,跑通一次完整的工具调用 | 模型**不会自己执行工具**,它只会告诉我"想调哪个、传什么参数",执行和回传结果是我代码的活 |
| 3 · 手写 Agent 循环 ⭐ | 把工具调用包进 `while` 循环,让模型连续多步完成任务 | 我没写"先做 A 再做 B"的流程代码,是**模型在循环里自己规划了步骤**——这就是 agent 和普通脚本的本质区别 |
| 4 · 用 SDK 简化 | 用官方 `tool_runner` 重写了阶段 3 | SDK 的自动循环,内部做的**就是我阶段 3 手写的那个循环**;因为先手写过,我是"知道盒子里装了什么"的人 |
| 5 · 综合项目 🏁 | 一个多工具、能自主探索真实目录回答代码问题的 agent（迷你版 Claude Code）| 真实 agent 要能扛住"不顺利":**工具失败要把错误回传给模型让它重试**、循环要有 `MAX_STEPS` 护栏、用 `system` 提示词塑造它的工作策略 |
| 6.1 · 记忆 | 给 agent 加了跨会话的持久化记忆 | 所谓"记忆"没有魔法,就是把信息**落盘、下次再塞回 context**;API 依然是无状态的 |
| 6.2 · 多 Agent 协作 ⭐ | 一个协调者把任务拆给 researcher / writer 两个子 agent | 一个子 agent 本质就是**"一个会自己跑循环的工具"**,所以 agent 是可以嵌套的——这正是 Claude Code subagents 背后的模型 |
| 6.3 · RAG 检索增强 | 一个先从私有文档检索、再带出处作答的 agent | RAG = **回答前先检索、把相关原文塞进 prompt**,用来解决"模型不知道我的私有/最新数据" |
| 6.4 · 评估 Evals | 一套跑多用例、自动打分的评测(含 LLM-as-judge) | 没有 eval,我永远说不清"改了 prompt 到底变好还是变坏";这是从玩具走向可靠的分水岭 |
| 6.5 · 安全护栏 | 给危险操作加了"人在环"的确认闸门 | agent 越自主,越要在**不可逆 / 有代价**的动作上留一道人工闸门 |

阶段 5 的综合项目(`exercises/stage5_codebase_agent/`)和阶段 6.2 的多 agent(`exercises/stage6_2_multiagent/`)是我投入最多、也最能体现理解的两块,推荐从这两处看起。

---

## 代码怎么读

仓库按阶段组织,每个阶段一个独立目录:

```
my-agent/
├── LEARNING_PLAN.md         # 我给自己定的完整学习方案（每阶段的目标与验证标准）
├── run.sh                   # 一键跑某个阶段的评测
└── exercises/
    ├── stage1_chat/
    │   ├── exercise.py      # ← 我的实现代码（每个阶段看这个）
    │   ├── test.py          # 评测：验证我写对了没有（离线 + 在线两段）
    │   ├── README.md        # 这一阶段的目标和通关标准
    │   └── _trace.py        # 我写的观察工具，把模型每轮的思考痕迹导出来复盘
    ├── stage2_tools/  …  stage4_tool_runner/
    ├── stage5_codebase_agent/
    │   └── sandbox/         # 给 agent 探索的示例项目（一个订单服务）
    └── stage6_1_memory/  …  stage6_5_guardrails/
```

想看某个阶段我怎么实现的,直接读该目录下的 `exercise.py`。

> `_trace.py` 是我为了看懂"模型每一步在想什么"写的小工具:在 SDK 的 `messages.create` 那层拦一道,把每次发出的请求(system / messages / tools)和收回的响应(content / stop_reason / usage)导成可读文本,方便复盘一次多步任务里模型到底怎么规划的。

---

## 跑起来试试

```bash
# 1. 环境
python3 -m venv .venv && .venv/bin/pip install anthropic

# 2. 配置 API Key（写进 .env，run.sh 会自动读取）
echo 'ANTHROPIC_API_KEY="你的key"' > .env

# 3. 跑某个阶段的评测（数字自动匹配对应目录）
./run.sh 5        # 阶段 5；子阶段用 ./run.sh 6.2
```

评测分两段:**离线段**是纯 Python 单测,不调模型不花钱;**离线全过**后才跑**在线段**,真调一次模型做端到端验证。

也可以直接运行看 agent 自己跑:

```bash
cd exercises/stage5_codebase_agent
set -a && source ../../.env && set +a
python3 exercise.py       # 看它自己分几步探索 sandbox 找到答案
```

---

## 技术栈

- **语言**:Python 3
- **模型**:Claude(`anthropic` SDK);练手用 `claude-haiku-4-5`,复杂任务用 `claude-opus-4-8`
- **依赖**:仅 `anthropic` 一个——刻意保持极简,核心逻辑全部自己实现
