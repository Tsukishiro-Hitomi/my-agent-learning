# 阶段 6.2 · 多 Agent 协作 👥（动手练习）

到现在你的 agent 都是"一个人干所有活"。真实系统常用**分工**：一个「协调者」把任务拆开，
交给几个**专职子 agent**，再汇总。这一关你造一个小团队。

## 💡 本关最重要的一句话
> **一个"子 agent"，本质就是一个【会自己跑 agent 循环、然后返回一段文字的函数】。**

既然它"输入一段文字 → 输出一段文字"，那它就和 `read_file` 一样，能被协调者当**工具**来调！
所以协调者的工具不再是文件操作，而是 `researcher` 和 `writer` 这两个**子 agent**。

```
          你: 研究 sandbox 并写份介绍
                 │
         ┌───协调者(orchestrator)───┐
         │  我先派调研员，再派写手   │
         ▼                          ▼
   researcher(带文件工具)      writer(不带工具)
   读代码、收集信息  ──笔记──▶  整理成通顺的介绍
```

## 这一关给你了什么（不用改）
文件下半部分已给好：通用循环引擎 `agent_loop(...)`、给调研员用的文件工具、顶层入口 `run_orchestrator`。
你只写"团队怎么分工"这部分。

## 你要做的（Part A / B / C）
- **A**：写 `researcher` / `writer` 两个子 agent——各自调用 `agent_loop(...)`。
  想清楚：**调研员需要哪些工具？写手需要工具吗？**（这决定你传给 agent_loop 的 tools）
- **B**：给这两个子 agent 各写一份 `schema`（参数：researcher→`question`，writer→`instruction`）。
- **C**：写三个 `system`——两个子 agent 的"人设" + 协调者的"分工说明"；再写分发器 `orchestrator_execute`。

然后 `./run.sh 6.2`（先离线不花钱，全过再跑在线）。

## 通关标准
**离线**：`researcher` 带了文件工具、`writer` 没带工具（用假循环验证接线）；两份 schema、分发、三个 system 都写了。
**在线**：协调者完成"研究+写介绍"时，**既派了 researcher 又派了 writer**，最终产出用上了 sandbox 里的真实信息。

## 手动试玩
```bash
cd exercises/stage6_2_multiagent
set -a && source ../../.env && set +a
python3 exercise.py     # 看协调者怎么把活拆给两个子 agent
```

## 卡住了怎么办
先想清楚"子 agent = 调用 agent_loop 的函数"这件事。研究员和写手的区别，就在于**给不给它工具**。
schema/分发忘了长啥样就翻阶段 5。实在卡住，让我给**一点提示**。

## 🎯 做完你就理解了
这正是 **Claude Code 的 subagents**、以及"研究员/写手/审校"这类多 agent 系统背后的模型：
**把一个大 agent 拆成几个各司其职的小 agent，用一个协调者串起来。** agent 是可以嵌套的。
