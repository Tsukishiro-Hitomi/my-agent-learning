# 阶段 4 · 用 SDK 简化循环（动手练习）

阶段 3 你手写了 agent loop。这一阶段用 SDK 的 **Tool Runner** 把同一个循环自动跑起来——
你只管写工具函数，"调用→执行→回传→再调用" 全部交给 SDK。

## 你要做的
1. 打开 `exercise.py`，**先删掉那行 `raise NotImplementedError`（保险丝）**，
   再补全 3 个 `TODO` —— 自己写，别抄。
2. 运行评测：`./run.sh 4`（会自动读 `.env`）。
3. 看到 ❌ 就改，直到全部 ✅。

## 阶段 3 vs 阶段 4（一眼看懂框架省了什么）
```
阶段 3（手写）                          阶段 4（Tool Runner）
────────────────────────────           ────────────────────────────
TOOLS = [{name, description, ...}]  →   @beta_tool 装饰函数，自动生成 schema
def execute(name, args): ...        →   （不需要，SDK 直接调你的函数）
while True:                         →   runner = client.beta.messages.tool_runner(...)
    resp = create(...)                     for message in runner:
    if 不要工具: break                         ...（循环、break、回传都由 SDK 做）
    执行工具、拼 tool_result、回传
```
两边行为完全一样，代码却少一半。

## 核心心智模型
- `@beta_tool`：从你的**函数签名 + 类型标注 + docstring** 自动生成工具说明书，
  取代阶段 3 手写的 `TOOLS` dict。所以 docstring 要认真写——那是模型读的"说明书"。
- `tool_runner(...)`：取代阶段 3 的 `while` 循环，自动完成"看到 tool_use → 执行 → 回传 → 再问"。
- 遍历 `runner`：每次拿到一条 `message`，取法和阶段 3 一样（看 `block.type`）。

## 通关标准（和阶段 3 一致）
- 模型请求了 **≥ 2 轮**（循环真的转起来了）
- `write_file` 和 `read_file` **都被调用**过
- 目标文件被真正创建，内容正确
- 最终回答用上了"读回来"的内容

## 手动试玩
```bash
cd exercises/stage4_tool_runner
set -a && source ../../.env && set +a
python3 exercise.py                      # 会创建 todo.txt，看模型分几步完成
```

## 卡住了怎么办
先别看答案。回到 `../../LEARNING_PLAN.md` 阶段 4 对照示例，想清楚：
`@beta_tool` 替代了阶段 3 的什么？`tool_runner` 又替代了什么？
实在卡住，让我给**一点提示**（而不是直接给答案）。

## 🎯 重点
做完对比阶段 3 和阶段 4——你现在**知道框架背后到底做了什么**，
比一上来就学框架的人理解深得多。
