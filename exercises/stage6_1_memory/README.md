# 阶段 6.1 · 给 agent 加「记忆」🧠（动手练习）

阶段 6 的第一关。你阶段 5 的 agent 有"失忆症"：每次重新运行都是全新进程，上次说的全忘了
（API 无状态，历史一直靠你带；进程一关就没了）。这一关给它加上**跨会话记忆**。

**记忆的全部秘密就一句话：把要记住的东西写到磁盘文件，下次启动再读回来。** 没有魔法。

## 这一关轻松点：循环已经给你了
和阶段 5 不同——这次 `execute` 和 `run_agent`（就是你阶段 5 那套）我**直接给好**，你不用碰。
你只专注写「记忆」本身这一个新东西。

## 你要做的
1. 打开 `exercise.py`，完成 3 个 Part（每个 `raise NotImplementedError` 都删掉再写）：
   - **Part A**：`save_memory(key, value)` / `recall_memory()`——真正读写 `memory.json`。
   - **Part B**：给这两个工具各写一份 `schema`（写法同阶段 5）。
   - **Part C**：写 `SYSTEM_PROMPT`——教 agent 什么时候存、什么时候查。
2. 先跑离线段（不花钱）：`./run.sh 6.1`。全过了才跑真调模型的在线段。
3. 看到 ❌ 就改，直到全绿。

## 核心心智模型
```
save_memory(k, v):  读出 memory.json(没有就当空 {}) → 改 dict[k]=v → 写回文件
recall_memory():    读出 memory.json → 组织成文字返回
```
关键：`memory.json` 是一个 JSON 字典。存之前**先把整个字典读出来再改**，不是往文件末尾追加——
否则同一个 key 会堆成好几条。

**💡 恍然大悟点：** 会话 2 是全新的一轮，`run_agent` 内部重开了 `messages`，**没有任何上文**。
它还能答出"你叫小明"，唯一的原因就是它从 `memory.json` 把这条读回来了。
——"记忆"不过是**把信息存盘、下次塞回 context**。API 依然是无状态的。

## 通关标准
**离线段（不花钱）**
- `save_memory` 真的写进 `memory.json`（合法 JSON）；同一个 key 再存是**覆盖**不是堆叠；能记多条。
- `recall_memory` 能读回；没记忆时不崩、给个空提示。
- 两个 `schema`（参数名对得上）+ `SYSTEM_PROMPT` 都写了。

**在线段（真调模型）**
- 会话 1 告诉它信息 → 它调 `save_memory` 存下。
- 会话 2（全新一轮、不带历史）→ 它调 `recall_memory`，答出"小明 / 订单服务"。

## 手动试玩（最能体会"跨会话"）
```bash
cd exercises/stage6_1_memory
set -a && source ../../.env && set +a
python3 exercise.py "我叫小明，在做一个叫订单服务的项目"   # 第一次：告诉它
python3 exercise.py "我叫什么？在做什么项目？"              # 第二次(新进程)：它还记得！
cat memory.json                                            # 看看它到底存了啥
```

## 卡住了怎么办
`json.load` / `json.dump` 是这一关的主角；文件可能还不存在，想好那一步怎么兜。
schema 忘了长啥样就翻阶段 5。实在卡住，让我给**一点提示**（针对你卡的那一处），别要整段答案。

## 🎯 做完你就理解了
所有"记忆 / 长期记忆 / 持久化"功能，拆开看都是这一招：**存盘 + 读回 context**。
数据库、向量库只是把"文件"换成更强的存储，思路一模一样。
