# 阶段 3 · 手写 Agent 循环 ⭐（动手练习）

从"一次工具调用"（阶段 2）到"自主多步"（真正的 agent）。这是最关键的一课。

## 你要做的
1. 打开 `exercise.py`，**先删掉那行 `raise NotImplementedError`（保险丝）**，
   再把 `run_agent()` 里的 4 个 `TODO` 补全 —— 自己写，别抄。
   - 编辑器会提示第 67 行下面"代码无法访问"，这是保险丝造成的，删掉它就好。
2. 运行评测：`./run.sh 3`（会自动读 `.env`）。
3. 看到 ❌ 就改，直到全部 ✅。

## 核心心智模型
```
messages = [任务]
while True:
    resp = 请求模型(历史 + 工具)
    如果 resp 不再要工具 → 存下最终文字，break
    否则：把 assistant 回复入历史 → 执行工具 → 把 tool_result 入历史 → 回到循环顶
```
关键 aha：**你没写"先做 A 再做 B"的流程**——是模型在循环里自己规划了步骤。
这就是 agent 和普通脚本的本质区别。

## 通关标准
- 模型请求了 **≥ 2 轮**（说明循环真的转起来了，不是一锤子买卖）
- `write_file` 和 `read_file` **都被调用**过（先写后读 = 多步）
- 目标文件被真正创建，内容正确
- 最终回答用上了"读回来"的内容

## 手动试玩
```bash
cd exercises/stage3_agent_loop
set -a && source ../../.env && set +a   # 记得先加载 .env（阶段 2 踩过的坑）
python3 exercise.py                      # 会创建 todo.txt，看模型分几步完成
```

## 卡住了怎么办
先别看答案。回到 `../../LEARNING_PLAN.md` 阶段 3 重读"要点"，
想清楚"循环什么时候该停（stop_reason）"，再回来写。
实在卡住，让我给**一点提示**（而不是直接给答案）。
