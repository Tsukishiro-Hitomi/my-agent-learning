"""
阶段 3 练习：手写 Agent 循环（最关键的一课）

阶段 2 只处理了"一次"工具调用。真正的 agent 会连续多步：
    观察 → 思考 → 调工具 → 看结果 → 再思考 …… 直到任务完成。

做法：把阶段 2 那套"调用→执行→回传"包进一个 while 循环，
      直到模型不再要工具（stop_reason != "tool_use"）就结束。
      这就是 agent loop，也叫 ReAct 模式（Reason + Act）。

怎么做：补全 run_agent() 里的 4 个 TODO（自己写，别抄）。写完后在项目根目录运行：
    ./run.sh 3
"""

import os

import anthropic

# 模型名：默认用你前面跑通的那个；也可在 .env 里加一行 MODEL=... 覆盖
MODEL = os.environ.get("MODEL", "anthropic/claude-haiku-4.5")

# ---- 工具定义（已给好，不用改）：给 agent 两个操作文件的能力 ----
TOOLS = [
    {
        "name": "write_file",
        "description": "把文本内容写入指定路径的文件（会覆盖同名文件）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径，例如 notes.txt"},
                "content": {"type": "string", "description": "要写入的文本内容"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "读取指定路径文本文件的全部内容。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
            },
            "required": ["path"],
        },
    },
]


def execute(name: str, args: dict) -> str:
    """真正执行工具，返回给模型的文字结果（已给好，不用改）。"""
    if name == "write_file":
        with open(args["path"], "w", encoding="utf-8") as f:
            f.write(args["content"])
        return f"已写入 {args['path']}（{len(args['content'])} 字）"
    if name == "read_file":
        with open(args["path"], encoding="utf-8") as f:
            return f.read()
    return f"未知工具：{name}"


def run_agent(client, task: str) -> str:
    """让模型在循环里自主多步完成任务，返回它最终的文字回答。"""
    # ↓↓↓ 开始写之前，先删掉下面这行"保险丝"（防止没写完时空循环反复请求烧配额）↓↓↓
    raise NotImplementedError("请完成 run_agent() 里的 4 个 TODO（写完删掉这一行 raise）")

    messages = [{"role": "user", "content": task}]
    final_text = ""

    # 真实项目里通常还会加一个"最大步数上限"防止跑飞（阶段 6 的护栏话题）；
    # 这里为了聚焦循环本身，先用最朴素的 while True。
    while True:
        # 每一轮：把【完整历史 + 工具】发给模型（API 无状态，历史要自己带）
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, tools=TOOLS, messages=messages,
        )

        # 打印这一步 agent 在想什么 / 要调什么工具（方便你观察它"自己规划步骤"）
        for b in resp.content:
            if b.type == "text":
                print("🤖", b.text)
            if b.type == "tool_use":
                print(f"🔧 调用 {b.name}({b.input})")

        # TODO 1（本阶段核心 = 循环出口）：
        #   如果这一轮模型不再要工具（resp.stop_reason != "tool_use"），说明任务做完了：
        #     - 把这一轮的文字取出来存进 final_text
        #       （取法同阶段 2：next((b.text for b in resp.content if b.type == "text"), "")）
        #     - 然后 break 跳出循环
        pass

        # TODO 2: 模型这条"要调工具"的回复要进历史（否则下一轮它就忘了自己要调什么）。
        #   把 resp.content 作为一条 role="assistant" 的消息追加进 messages。

        # TODO 3: 遍历 resp.content 里所有 block，挑出 block.type == "tool_use" 的：
        #     - 用 execute(block.name, block.input) 执行，拿到结果
        #     - 组装成 {"type": "tool_result", "tool_use_id": block.id, "content": 结果}
        #   全部收集进一个列表，命名为 results。

        # TODO 4: 把 results 作为一条 role="user" 的消息追加进 messages。
        #   追加完，while 会自动回到顶部，带着新结果再问模型 —— 这就是 agent loop 在转。

    return final_text


# 手动试玩（可选）：set -a && source ../../.env && set +a && python3 exercise.py
if __name__ == "__main__":
    client = anthropic.Anthropic()
    task = "创建一个 todo.txt，写入三件今天要做的事，然后把它读回来确认写对了。"
    final = run_agent(client, task)
    print("\n===== 最终回答 =====")
    print(final)
