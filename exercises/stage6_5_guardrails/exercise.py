"""
阶段 6.5 · 安全护栏（Guardrails）：危险操作前先让人确认

agent 越自主，越可能干出"不可逆/有代价"的事——删文件、发邮件、花钱。
你阶段 5 的 MAX_STEPS 是一种护栏（防跑飞）；这一关加另一种更重要的：
    **人在环 (human-in-the-loop)**：碰到危险工具，先停下来问人 "确定吗？(y/n)"，
    人同意才执行；人拒绝就把"被拒绝"当作结果回给模型，让它换个做法——而不是硬干。

你要做的（就三样，都在 Part A/B/C）：
    Part A: DANGEROUS        —— 哪些工具算"危险"（会改动/删除东西）
    Part B: confirm          —— 危险操作前问人，y/是 才算同意
    Part C: guarded_execute  —— 带护栏的执行：危险的先确认，安全的直接放行
（真正干活的工具、询问钩子 _ask、agent 循环，我都给好了，见下方。）

写完运行： ./run.sh 6.5
"""

import os

import anthropic

MODEL = os.environ.get("MODEL", "anthropic/claude-haiku-4.5")


# ============================================================================
# Part A：哪些工具算"危险"（你来定）
# ============================================================================
# 下面给好的工具有：read_file（只读，安全）、write_file（会改文件）、delete_file（会删文件）。
# 把"会改动/删除东西"的那些工具名放进这个集合。
DANGEROUS = set()  # 你来填，例如 {"write_file", "delete_file"}


# ============================================================================
# Part B：危险操作前问人（你来写）
# ============================================================================


def confirm(name: str, args: dict) -> bool:
    """危险操作前征求用户同意，返回 True(同意) / False(拒绝)。

    契约：
      - 用下面给好的 _ask("提示语") 拿到用户输入。
      - 提示语里要说清楚【要执行什么工具、参数是什么】，让用户知道自己在批准什么。
      - 用户输入 y / yes / 是 → True；其它 → False。
    """
    raise NotImplementedError("实现 confirm（删掉这行）")


# ============================================================================
# Part C：带护栏的执行（你来写）
# ============================================================================


def guarded_execute(name: str, args: dict) -> str:
    """在真正执行工具外面套一层"护栏"。

    契约：
      - name 在 DANGEROUS 里：先 confirm(name, args)。
          · 用户拒绝 → 返回字符串「错误：用户拒绝执行 {name}」
            （是【返回结果】不是抛异常——让模型知道被拒了、可以换个做法）。
          · 用户同意 → 往下执行。
      - 工具本就不危险（或已获同意）：调 _run_tool(name, args) 真正执行。
      - 用 try/except 兜住异常（同阶段 5 的 execute）。
    """
    raise NotImplementedError("实现 guarded_execute（删掉这行）")


# ============================================================================
# ↓↓↓ 以下都已给好——不用改 ↓↓↓
# ============================================================================
def _ask(prompt: str) -> str:
    """询问用户的钩子（评测会临时替换它来模拟"用户按了 y 或 n"）。"""
    return input(prompt).strip().lower()


def write_file(path: str, content: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已写入 {path}"


def read_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def delete_file(path: str) -> str:
    os.remove(path)
    return f"已删除 {path}"


def _run_tool(name: str, args: dict) -> str:
    """原始分发：真正干活，不带任何确认。"""
    if name == "write_file":
        return write_file(args["path"], args["content"])
    if name == "read_file":
        return read_file(args["path"])
    if name == "delete_file":
        return delete_file(args["path"])
    return f"错误：未知工具 {name}"


TOOLS = [
    {"name": "write_file", "description": "把内容写入文件（会覆盖）。",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "read_file", "description": "读取文件内容。",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "delete_file", "description": "删除一个文件。",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
]

SYSTEM_PROMPT = "你是一个文件助手，可以按用户要求读、写、删文件。"
MAX_STEPS = 10


def run_agent(client, task: str) -> str:
    """agent 循环（已给好）——注意它执行工具走的是 guarded_execute（带护栏）。"""
    messages = [{"role": "user", "content": task}]
    final_text = ""
    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages)
        for b in resp.content:
            if b.type == "text":
                print("🤖", b.text)
            if b.type == "tool_use":
                print(f"🔧 调用 {b.name}({b.input})")
        if resp.stop_reason != "tool_use":
            final_text = next((b.text for b in resp.content if b.type == "text"), "")
            break
        messages.append({"role": "assistant", "content": resp.content})
        results = [
            {"type": "tool_result", "tool_use_id": b.id, "content": guarded_execute(b.name, b.input)}
            for b in resp.content if b.type == "tool_use"
        ]
        messages.append({"role": "user", "content": results})
    return final_text


if __name__ == "__main__":
    client = anthropic.Anthropic()
    with open("guard_demo.txt", "w", encoding="utf-8") as f:
        f.write("这是一个演示文件。")
    print("（已创建 guard_demo.txt。下面让 agent 删它——它会先问你 y/n）\n")
    print(run_agent(client, "请删除当前目录下的 guard_demo.txt 文件。"))
