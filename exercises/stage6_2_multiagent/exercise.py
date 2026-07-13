"""
阶段 6.2 · 多 Agent 协作：一个 agent 可以当另一个 agent 的「工具」

到现在你的 agent 都是"一个人干所有活"。真实系统里常用**分工**：
一个「协调者(orchestrator)」把任务拆开，交给几个**专职的子 agent**去做，再汇总。

★ 本关的恍然大悟点：
    一个「子 agent」本质上就是——【一个会自己跑 agent 循环、然后返回一段文字的函数】。
    既然它"输入一段文字、输出一段文字"，那它就能像普通工具一样，被协调者调用！
    于是"给协调者的工具"不再是 read_file，而是 researcher / writer 这两个**子 agent**。

这一关的通用循环引擎 agent_loop、给子 agent 用的文件工具，我都给好了（见文件下半部分）。
你要做的（都在 Part A/B/C）：
    Part A: 写两个子 agent —— researcher（会读代码收集信息）和 writer（把笔记写成文）
    Part B: 给这两个子 agent 写 schema（让协调者知道怎么调它们）
    Part C: 写三个 system 提示词（两个子 agent 各自的"人设" + 协调者的"分工说明"）

练习对象还是 sandbox/ 那个订单服务。写完运行： ./run.sh 6.2
"""

import os

import anthropic

MODEL = os.environ.get("MODEL", "anthropic/claude-haiku-4.5")

# 全局 client：协调者和所有子 agent 共用它来调模型
client = anthropic.Anthropic()


# ============================================================================
# Part A：两个子 agent（你来写）
#
# 关键理解：子 agent = 调用下面给好的 agent_loop(...) 跑一轮、返回它最终文字的函数。
#   - agent_loop(task, system, tools, execute_fn) 见文件下半部分（已给好）。
#   - researcher 需要"读代码"的能力 → 给它 FILE_TOOLS + file_execute（都已给好）。
#   - writer 只需要"把笔记写顺" → 不需要任何工具（tools 传 []、execute_fn 传 None）。
# ============================================================================


def researcher(question: str) -> str:
    """调研员子 agent：能用文件工具探索 sandbox、收集信息，返回它查到的内容。
    契约：调用 agent_loop，传入 question、RESEARCHER_SYSTEM、FILE_TOOLS、file_execute，返回其结果。
    """
    return agent_loop(question, RESEARCHER_SYSTEM, FILE_TOOLS, file_execute)


def writer(instruction: str) -> str:
    """写手子 agent：不带任何工具，纯靠模型把给它的笔记/要求整理成通顺文字。
    契约：调用 agent_loop，传入 instruction、WRITER_SYSTEM、空工具列表 []、execute_fn=None，返回结果。
    """
    return agent_loop(instruction, WRITER_SYSTEM, [], None)


# ============================================================================
# Part B：把两个子 agent 写成协调者能调用的「工具」（你来写 schema）
#   - researcher 有一个参数 question；writer 有一个参数 instruction。
#   - description 要写清楚"这个子 agent 擅长什么"，协调者靠它决定把活派给谁。
# ============================================================================
TOOLS = [
    # 你来补：researcher / writer 各一份 schema
    {
        "name": "researcher",
        "description": "调用文件工具探索项目，查找内容",
        "input_schema": {
            "type": "object", 
            "properties": {
                "question": {"type": "string", "description": "用户的问题"}
            },
            "required": ["question"],
        }
    }, 

    {
        "name": "writer", 
        "description": "将笔记整理为通顺、条理清楚的中文",
        "input_schema": {
            "type": "object", 
            "properties": {
                "instruction": {"type": "string", "description": "输入的笔记"},
            },
            "required": ["instruction"],
        },
    },
]


# ============================================================================
# Part C：三个 system 提示词（你来写）
# ============================================================================
# 子 agent 的"人设"：告诉它自己是谁、该怎么干。
RESEARCHER_SYSTEM = "你是调研员，用文件工具探索项目、把关键信息如实收集回来。项目根目录是 sandbox。"  # 例：你是调研员，用文件工具探索项目、把关键信息如实收集回来。项目根目录是 sandbox。
WRITER_SYSTEM = "你是写手，把给你的笔记/要求整理成通顺、条理清楚的中文，不要自己编事实。请务必精炼：全文控制在 1500 字以内，代码只给关键片段（不要逐个文件贴完整实现），并在一次回复内写完整、不要写到一半。"      # 例：你是写手，把给你的笔记整理成通顺、条理清楚的中文，不要自己编事实。

# 协调者的"分工说明"：告诉它手上有 researcher / writer 两个下属，遇到复合任务要先调研、再写作。
ORCHESTRATOR_SYSTEM = "手上有 researcher / writer 两个下属 agent ，前者可以通过文件工具探索项目，返回关键信息；后者可以将关键信息整理为通顺中文。遇到任务时先调用前者收集信息，再调用后者写作。注意必须把 researcher 返回的内容原样输入 instruction。在 writer 写完后，把 writer 返回的全部内容一字不改地作为你的最终回复输出：不要总结、不要精简、不要增删改写，也不要加开场白或结尾。"


# ============================================================================
# 分发器：把协调者的工具调用路由到对应子 agent（你来写）
# ============================================================================
def orchestrator_execute(name: str, args: dict) -> str:
    """协调者调 researcher/writer 时，走这里分发到上面的子 agent 函数。
    契约：name=="researcher" → researcher(args["question"])；
          name=="writer"     → writer(args["instruction"])；
          其它 → 「错误：未知工具 …」；用 try/except 兜住异常（同阶段 5）。
    """
    try:
        if name == "researcher":
            return researcher(args["question"])
        if name == "writer":
            return writer(args["instruction"])
        return f"错误：未知工具 {name}"
    except Exception as e:
        return f"错误：在调用{name}时发生了错误{e}"
    
# ============================================================================
# ↓↓↓ 以下都已给好——不用改 ↓↓↓
# ============================================================================
def agent_loop(task: str, system: str, tools: list, execute_fn, max_steps: int = 8) -> str:
    """通用 agent 循环引擎（就是你阶段 5 那套的精简版）。
    tools=[] 且 execute_fn=None 时，就是"不带工具的一问一答"。返回模型最终文字。"""
    messages = [{"role": "user", "content": task}]
    final_text = ""
    for _ in range(max_steps):
        kwargs = dict(model=MODEL, max_tokens=8192, system=system, messages=messages)
        if tools:
            kwargs["tools"] = tools
        resp = client.messages.create(**kwargs)
        if resp.stop_reason != "tool_use":
            final_text = next((b.text for b in resp.content if b.type == "text"), "")
            break
        messages.append({"role": "assistant", "content": resp.content})
        results = [
            {"type": "tool_result", "tool_use_id": b.id, "content": execute_fn(b.name, b.input)}
            for b in resp.content if b.type == "tool_use"
        ]
        messages.append({"role": "user", "content": results})
    return final_text


# 给"调研员"子 agent 用的文件工具（就是阶段 5 的 list_dir / read_file，已给好）
def _list_dir(path: str) -> str:
    if not os.path.isdir(path):
        return f"错误：{path} 不是目录"
    return "\n".join(sorted(
        n + "/" if os.path.isdir(os.path.join(path, n)) else n for n in os.listdir(path)))


def _read_file(path: str) -> str:
    if not os.path.isfile(path):
        return f"错误：文件不存在 {path}"
    with open(path, encoding="utf-8") as f:
        return f.read()[:4000]


FILE_TOOLS = [
    {"name": "list_dir", "description": "列出某目录下的文件和子目录。",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "read_file", "description": "读取某个文本文件的内容。",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
]


def file_execute(name: str, args: dict) -> str:
    try:
        if name == "list_dir":
            return _list_dir(args["path"])
        if name == "read_file":
            return _read_file(args["path"])
        return f"错误：未知工具 {name}"
    except Exception as e:  # noqa: BLE001
        return f"错误：{name} 执行失败：{e}"


def run_orchestrator(task: str) -> str:
    """顶层入口：让协调者带着 researcher/writer 两个"下属工具"去完成任务。"""
    return agent_loop(task, ORCHESTRATOR_SYSTEM, TOOLS, orchestrator_execute, max_steps=10)


if __name__ == "__main__":
    import _trace; _trace.on()  # 观察：把模型思考痕迹写入 output.txt
    print("\n===== 协调者最终产出 =====")
    print(run_orchestrator("请研究 sandbox 这个项目，然后请为我设计一个补全业务代码的方案。"))
