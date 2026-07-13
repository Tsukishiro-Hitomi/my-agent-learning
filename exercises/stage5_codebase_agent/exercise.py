"""
阶段 5 · 综合项目（capstone）：从零搭一个多工具「代码库问答 agent」

这是把前 4 阶段全部串起来的收官项目。你会做出一个迷你版 Claude Code：
给它几个操作文件的工具，它就能【自主探索一个真实目录】来回答你的问题——
    先列目录 / 搜关键字 → 定位到相关文件 → 读文件细节 → 基于内容作答。

它比阶段 3 的文件 agent 多了三件「真实 agent 必备」的事：
    1) 多个会「失败」的工具：文件不存在怎么办？工具出错要【回传给模型】，而不是让程序崩。
    2) 一个「加固版」循环：系统提示词(system) + 最大步数护栏(MAX_STEPS) + 多工具分发。
    3) 让它探索的对象是 sandbox/ 这个真实的小项目（不是造一个假字符串）。

★ 和前几阶段最大的不同：这次【不把答案写在注释里】。
  每个函数只给你「契约」——签名、要返回什么、要处理哪些边界、评测会怎么查。
  怎么实现，你自己决定。卡住了先回去翻阶段 2/3，别急着要答案。

怎么做：把下面 Part A / B / C 里所有 `raise NotImplementedError` 换成你的实现。
写完后在项目根目录运行：
    ./run.sh 5
（评测分两段：先跑不花钱的「离线单测」，全过了再跑「在线端到端」。）
"""

import os

import anthropic

# 模型名：和前面几个阶段一样；也可在 .env 里加一行 MODEL=... 覆盖
MODEL = os.environ.get("MODEL", "anthropic/claude-haiku-4.5")
MAXSIZE = 4000

# ============================================================================
# Part A：三个工具的「真实实现」（你来写函数体）
#
# 注意参数名是契约的一部分：schema 里的参数名、execute 传的 key、都要和这里对上。
# 三个函数都【不允许因为坏输入而抛异常】——预期内的错误（如文件不存在）要
# 返回一句以「错误：」开头的字符串，让模型看得懂、能自己换个法子重试。
# ============================================================================


def list_dir(path: str) -> str:
    """列出 path 目录下的直接条目（文件与子目录），每行一个。

    契约：
      - 目录存在：每行一个条目；子目录名后面加一个 "/" 以便模型区分（如 "config/"）。
      - path 不存在、或不是目录：返回一句「错误：……」的说明，不要抛异常。
    评测会查：能列出 sandbox 顶层已知条目（app / config / utils / README.md），
              也能列出子目录（如 sandbox/config 里的 settings.py）；
              对不存在的路径返回「错误：」开头的字符串。
    """
    try:
        files = os.listdir(path)
    except FileNotFoundError:
        return "错误：该路径不存在"
    except NotADirectoryError:
        return "错误：这不是一个目录"
    except PermissionError:
        return "错误：无访问权限"
    except:
        return "错误：未知错误"
    
    result = ""
    for file in files:
        result += str(file)
        result += '/\n'
    return result


def read_file(path: str) -> str:
    """读取文本文件的全部内容并返回。

    契约：
      - 文件存在：返回其文本内容（用 utf-8）。
      - 文件不存在 / 打不开：返回「错误：……」的说明，不要抛异常。
      - 防止撑爆上下文：内容超过 4000 字时，只返回前 4000 字，并在末尾加 "…（已截断）"。
    评测会查：能读到已知文件内容；不存在的路径返回「错误：」；超长内容会截断（含「已截断」）。
    """
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
            if len(content) > MAXSIZE:
                content = content[: MAXSIZE - 1]
                content += "...（已截断）"
            return content
    except FileNotFoundError:
        return "错误：文件不存在"
    except:
        return "错误：未知错误"

def search_files(query: str, path: str) -> str:
    """在 path 目录树下【递归】搜索：找出哪些文件的哪一行包含 query（子串匹配即可）。

    契约：
      - 命中：每行返回 "文件路径:行号: 该行内容"（该行去掉首尾空白），最多返回前 50 条。
        （文件路径用 os.path.join(根目录, 文件名) 这种相对形式即可；行号从 1 开始。）
      - 一条都没命中：返回一句普通说明（如「没有找到包含 xxx 的内容」）。
      - 只处理文本文件；遇到读不了的文件（二进制/无权限）跳过即可，别让整个搜索崩掉。
    评测会查：能在 sandbox 里搜到已埋好的关键字，且结果指向正确的文件（settings.py）。
    """
    hits = []                                          # 收集命中的行
    for dirpath, dirnames, filenames in os.walk(path): # 递归走遍每一层
        for name in filenames:
            filepath = os.path.join(dirpath, name)     # 这个文件的路径
            try:
                with open(filepath, encoding="utf-8") as f:
                    for lineno, line in enumerate(f, 1):   # 行号从 1 开始
                        if query in line:
                            hit = str(filepath) + ":" + str(lineno) + ": " + line.strip()
                            if len(hits) < 50:
                                hits.append(hit)
            except UnicodeDecodeError:
                return "错误：二进制文件，无法访问"
            except PermissionError:
                return "错误：无访问权限"
            except:
                return "错误：未知错误"

    if len(hits) == 0:
        return f"没有找到包含{query}的内容"
    result = ""
    for hit in hits:
        result = result + hit + "\n"
    return result

# ============================================================================
# Part B：工具说明书(schema) + 分发器(execute)
# ============================================================================

# TOOLS：把上面三个函数写成模型能读懂的「说明书」。写法参考阶段 2/3 的 TOOLS。
#   每个元素形如 {"name": ..., "description": ..., "input_schema": {...}}。
#   - name 必须和函数名一致（list_dir / read_file / search_files）。
#   - input_schema 里的参数名必须和函数参数名一致（path / query）。
#   - description 要写清楚「这个工具是干嘛的、什么时候用」——模型全靠它决定调哪个。
TOOLS = [
    # 你来补：list_dir / read_file / search_files 各一份 schema
    {
        "name": "list_dir",
        "description": "列出指定路径目录下的所有条目（文件和子目录）",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径，例如 config/"},
            },
            "required": ["path"],
        },
    },

    {
        "name": "read_file",
        "description": "读取指定路径文本文件的全部内容。",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径，例如 readme.md"},
            },
            "required": ["path"],
        },
    },

    {
        "name": "search_files",
        "description": "搜索指定路径目录下的所有包含 query 内容的行（最多50行）",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询内容，例如 hello"},
                "path": {"type": "string", "description": "文件路径，例如 config/"}
            },
            "required": ["query", "path"],
        }
    },
]


def execute(name: str, args: dict) -> str:
    """按工具名把调用分发到对应函数，返回给模型的文字结果。

    契约（这是真实 agent 的关键一环）：
      - 按 name 调用 list_dir / read_file / search_files（参数从 args 里取）。
      - name 不认识：返回「错误：未知工具 <name>」。
      - 用 try/except 兜住工具执行时抛出的【任何异常】，转成「错误：……」字符串返回。
        —— 一个工具炸了不该让整个 agent 崩；模型拿到错误信息还能自己重试或换路。
    评测会查：未知工具返回「错误：」；某工具抛异常时 execute 不崩、返回「错误：」字符串。
    """
    try:
        if name == "list_dir":
            return list_dir(args["path"])
        if name == "read_file":
            return read_file(args["path"])
        if name == "search_files":
            return search_files(args["query"], args["path"])
        return f"错误： 未知工具{name}"
    except Exception as e:
        return f"错误：在调用{name}时发生了{e}"


# ============================================================================
# Part C：加固版 agent 循环
# ============================================================================

# 最大步数护栏：循环最多跑多少「轮」（每轮 = 一次模型请求）。到上限就必须停。
# 阶段 3 里我们用最朴素的 while True 并说「护栏留到阶段 6」——现在你亲手把它加上。
MAX_STEPS = 10  # 你来设一个合理的正整数（比如 10）

# 系统提示词：定义这个 agent 的身份和工作方式。写什么见 README「系统提示词该写什么」。
SYSTEM_PROMPT = "身份：你是一个代码库问答助手，通过调用工具来探索项目，回答用户的问题；" \
"工作方式：先用 'list_dir' / 'search_files' 找到相关文件，再用 'read_file' 阅读文件内容，不允许凭空猜文件名或内容" \
"问答要求：基于文件里真实读到的内容作答，回答之前先通过 'read_file' 打开文件确认，然后再下结论" \
"不允许只凭借一条搜索片段就作答，讲清楚答案在哪个文件。不知道就诚实回答不知道。" \
"工作范围：项目根目录是 'sandbox'" 


def run_agent(client, task: str) -> str:
    """加固版 agent loop：让模型自主用工具多步完成任务，返回它最终的文字回答。

    循环骨架你在阶段 3、4 已经写/用过两遍了——出口、把 assistant 回复入历史、执行工具、
    把 tool_result 入历史，这些自己回忆着写。这里只强调本阶段【新增】的几点：
      · 【新】每次 client.messages.create(...) 除了 model=MODEL, max_tokens=…, messages=…，
             还要带上 system=SYSTEM_PROMPT 和 tools=TOOLS。
      · 【新】最多跑 MAX_STEPS 轮：跑满了还没结束，也要停下并返回目前拿到的文字
             （绝不能无限循环）。
      · 【别退化】一轮里可能有多个 tool_use 块：要全部执行、把全部 tool_result 放进
             【同一条】 user 消息回传（阶段 3 本来就是这样，别写成只处理第一个）。
      · 工具执行统一走 execute()（它已经帮你把错误兜成字符串了）。
      · 沿用阶段 3 的打印，方便观察它自己规划步骤。
    返回：模型最后一轮的文字回答。
    """
    messages = [{"role": "user", "content": task}]
    final_text = ""
    cur_steps = 0
    while True:
        cur_steps += 1
        if cur_steps > MAX_STEPS:
            break

        # 每一轮：把【完整历史 + 工具】发给模型（API 无状态，历史要自己带）
        resp = client.messages.create(
            model=MODEL, max_tokens=1024, tools=TOOLS, messages=messages, system = SYSTEM_PROMPT,
        )

        # 打印这一步 agent 在想什么 / 要调什么工具
        for b in resp.content:
            if b.type == "text":
                print("🤖", b.text)
            if b.type == "tool_use":
                print(f"🔧 调用 {b.name}({b.input})")

        #   如果这一轮模型不再要工具（resp.stop_reason != "tool_use"），说明任务做完了：
        if resp.stop_reason != "tool_use":
            final_text = next((b.text for b in resp.content if b.type == "text"), "")
            break

        #   把 resp.content 作为一条 role="assistant" 的消息追加进 messages。
        messages.append({"role": "assistant", "content": resp.content})

        results = []
        for b in resp.content:
            if b.type == "tool_use":
                result = execute(b.name, b.input)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": result})

        messages.append({"role": "user", "content": results})
    return final_text


# 手动试玩（可选）：set -a && source ../../.env && set +a && python3 exercise.py
if __name__ == "__main__":
    import _trace; _trace.on()  # 观察：把模型思考痕迹写入 output.txt
    client = anthropic.Anthropic()

    # 试玩不同的 task 并观察模型输出：

    # task = (
    #    "项目根目录是 sandbox。请找出这个服务部署到生产环境用的端口号是多少，"
    #   "并告诉我它定义在哪个文件里。"
    # )
    task = (
        "项目根目录是 sandbox. 请你为我讲解这个项目。"
    )
    print("\n===== 最终回答 =====")
    print(run_agent(client, task))
