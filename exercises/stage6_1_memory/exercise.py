"""
阶段 6.1 · 给 agent 加「记忆」：让它跨会话记住东西

你阶段 5 的 agent 有个"失忆症"：每次重新 `python exercise.py` 都是一个全新进程，
上次说过的话它全忘了——因为 API 本来就无状态（历史一直靠你自己带），进程一关，
内存里的 messages 就没了。

「记忆」的全部秘密就一句话：**把要记住的东西写到磁盘文件里，下次启动再读回来。**
没有魔法，就是存盘 + 读盘。

这一关你【只写记忆本身】——agent 循环（execute / run_agent）我已经给好了
（就是你阶段 5 那套，原样搬来，不用动）。你要做的是下面 3 个 Part：
    Part A: 写 save_memory / recall_memory 两个工具（真正读写 memory.json）
    Part B: 给它俩写 schema
    Part C: 写 SYSTEM_PROMPT，教 agent 什么时候该存、什么时候该查

写完在项目根目录运行： ./run.sh 6.1
"""

import json
import os

import anthropic

MODEL = os.environ.get("MODEL", "anthropic/claude-haiku-4.5")

# 记忆就存在这个文件里（和 exercise.py 同目录）。它是一个 JSON 字典：{ "键": "值", ... }
MEMORY_FILE = "memory.json"


# ============================================================================
# Part A：两个「记忆」工具（你来写函数体）
# ============================================================================


def save_memory(key: str, value: str) -> str:
    """把一条信息（键值对）记到 memory.json 里。

    契约：
      - 先读出 memory.json 现有内容（文件还不存在时，当成空字典 {}）。
      - 把 key -> value 放进去；key 已存在就【覆盖】它，不要堆成两条。
      - 写回 memory.json。
      - 返回一句确认，例如「已记住：name = 小明」。
    提示：内容是 JSON，用 json.load / json.dump 读写；文件可能还不存在，想好这一步怎么兜。
    评测会查：调用后 memory.json 里真有这条；同一个 key 存两次是覆盖，不是变两条。
    """
    try:
        with open(MEMORY_FILE, encoding='utf-8') as f:
            data = json.load(f)
    # 如果文件还没有找到，说明此时记忆为空，返回空的 data
    except FileNotFoundError:
        data = {}
    except json.JSONDecodeError as e:
        return f"错误：JSON 格式错误: 第 {e.lineno} 行, {e.msg}"
    
    data[key] = value
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return f"已记住：{key} = {value}"
    
def recall_memory() -> str:
    """读出 memory.json 里记住的【所有】信息，返回一段给模型看的文字。

    契约：
      - 文件不存在 / 里面是空的：返回一句说明，例如「（还没有任何记忆）」。
      - 有内容：把所有 键: 值 组织成清楚的文字返回（模型好读）。
    评测会查：之前 save 过的东西，这里能读出来；没记忆时不崩、给个空提示。
    """
    try:
        with open(MEMORY_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return f"还没有任何记忆"
    except json.JSONDecodeError as e:
        return f"错误：JSON 格式错误: 第 {e.lineno} 行, {e.msg}"
    
    result = ""
    # 注意这里遍历字典的方法：.items()
    for key, value in data.items():
        result += f"{key}: {value}\n"
    return result


# ============================================================================
# Part B：工具说明书 schema（你来写）
# ============================================================================
# 参考阶段 5：每个 {name, description, input_schema}。
#   - save_memory 有两个参数：key、value。
#   - recall_memory 没有参数（input_schema 的 properties 写成空对象 {} 即可）。
#   - description 要让模型明白【什么时候用】——和下面 SYSTEM_PROMPT 配合。
TOOLS = [
    {
        "name": "save_memory",
        "description": "将一条信息（键值对）存入记忆",
        "input_schema": {
            "type": "object", 
            "properties": {
                # 注意：对于 json 形式的数据，其 type 为 string 而非 str
                "key": {"type": "string", "description": "信息的键"},
                "value": {"type": "string", "description": "信息的值"},
            },
            "required": ["key", "value"],
        }
    }, 

    {
        "name": "recall_memory", 
        "description": "读取记忆中存储的信息，返回模型可读的文字",
        "input_schema": {
            "type": "object", 
            "properties": {}
        },
    },
]


# ============================================================================
# Part C：系统提示词（你来写）
# ============================================================================
# 教会 agent 主动用记忆。至少讲清楚：
#   - 当用户告诉你关于他自己 / 项目的信息时，用 save_memory 记下来。
#   - 回答关于用户 / 项目的问题前，先用 recall_memory 查一下你记得什么，别凭空猜。
SYSTEM_PROMPT = "当用户告诉你关于他自己/项目的信息时，调用 save_memory 存下来。" \
"在回答用户的问题之前，必须先调用 recall_memory 查询你的记忆，不准瞎猜。如果记忆中没有，如实回答，不允许伪造记忆。"  


# ============================================================================
# ↓↓↓ 以下是 agent 循环，已给好（就是你阶段 5 那套，原样搬来）——不用改 ↓↓↓
# ============================================================================
MAX_STEPS = 10


def execute(name: str, args: dict) -> str:
    try:
        if name == "save_memory":
            return save_memory(args["key"], args["value"])
        if name == "recall_memory":
            return recall_memory()
        return f"错误：未知工具 {name}"
    except Exception as e:  # noqa: BLE001
        return f"错误：工具 {name} 执行失败：{e}"


def run_agent(client, task: str) -> str:
    messages = [{"role": "user", "content": task}]
    final_text = ""
    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages,
        )
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
            {"type": "tool_result", "tool_use_id": b.id, "content": execute(b.name, b.input)}
            for b in resp.content if b.type == "tool_use"
        ]
        messages.append({"role": "user", "content": results})
    return final_text


# 手动试玩：分两次运行，体会"跨会话记忆"——
#   python3 exercise.py "我叫小明，在做一个叫订单服务的项目"   ← 第一次：告诉它
#   python3 exercise.py "我叫什么？在做什么项目？"              ← 第二次(新进程)：它还记得
if __name__ == "__main__":
    import _trace; _trace.on()  # 观察：把模型思考痕迹写入 output.txt
    import sys

    client = anthropic.Anthropic()
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "我叫小明，在做一个叫订单服务的项目。"
    print("\n===== 回答 =====")
    print(run_agent(client, task))
