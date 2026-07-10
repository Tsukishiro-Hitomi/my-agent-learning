"""
阶段 4 练习：用 SDK 的 Tool Runner 简化循环

阶段 3 你亲手搭出了 agent loop（while 循环 + 手动回传 tool_result）。
理解透之后，SDK 提供了 Tool Runner 帮你把整个循环自动跑起来：
    你只管写工具函数，"调用→执行→回传→再调用" 全部由 SDK 完成。

对比一下你会发现：
    阶段 3 需要 —— TOOLS 说明书 dict + execute 分发器 + while True 循环 + 手动拼 tool_result
    阶段 4 只需要 —— 两个用 @beta_tool 装饰的函数 + 一次 tool_runner 调用
两者行为完全一致，但代码少一半。这就是"先懂原理，再用框架"的价值。

怎么做：补全下面的 3 个 TODO（自己写，别抄）。写完后在项目根目录运行：
    ./run.sh 4
"""

import os

import anthropic
from anthropic import beta_tool

# 模型名：和前面几个阶段一样；也可在 .env 里加一行 MODEL=... 覆盖
MODEL = os.environ.get("MODEL", "anthropic/claude-haiku-4.5")


# ---- 工具函数：函数体已给好（就是阶段 3 execute 里的那两段文件操作）----
#
# 关键区别：阶段 3 要另写一份 TOOLS 说明书（name / description / input_schema）。
# 这里不用！@beta_tool 会自动从你的【函数签名 + 类型标注 + docstring】生成 schema：
#     函数名        → 工具名
#     docstring 首行 → 工具描述
#     参数 + 类型    → input_schema
#     Args: 下的说明 → 各参数的 description
# 所以 docstring 不是写给人看的注释，而是模型据以决策的"说明书"，要认真写。
#
# TODO 1（本阶段核心之一）：给下面两个函数各加上一行 @beta_tool 装饰器。
#   加完后，write_file / read_file 就从普通函数变成了"工具"，可以直接交给 tool runner。


@beta_tool
def write_file(path: str, content: str) -> str:
    """把文本内容写入指定路径的文件（会覆盖同名文件）。

    Args:
        path: 文件路径，例如 notes.txt
        content: 要写入的文本内容
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已写入 {path}（{len(content)} 字）"


@beta_tool
def read_file(path: str) -> str:
    """读取指定路径文本文件的全部内容。

    Args:
        path: 文件路径
    """
    with open(path, encoding="utf-8") as f:
        return f.read()


def run_agent(client, task: str) -> str:
    """用 Tool Runner 跑循环：你只提供工具函数，SDK 自动完成整个 agent loop。
    返回模型最终的文字回答。"""

    # TODO 2（本阶段核心之二）：创建 tool runner。
    #   调用 client.beta.messages.tool_runner(...)，传这些参数：
    #       model=MODEL, max_tokens=1024,
    #       tools=[write_file, read_file],   # 直接传函数本身，schema 已由 @beta_tool 生成
    #       messages=[{"role": "user", "content": task}],
    #   把返回值存进变量 runner。
    #   注意：这一步不会真的发请求，只是把循环"准备好"，真正跑起来是在下面的遍历里。
    runner = client.beta.messages.tool_runner(model = MODEL, max_tokens = 1024, tools = [write_file, read_file], messages = [{"role": "user", "content": task}])
    # TODO 3：遍历 runner 拿到最终回答。
    #   runner 是可迭代的：每迭代一次给你一条 message（模型这一轮的完整回复）。
    #   SDK 已经在背后替你做了阶段 3 的那套：看到 tool_use 就执行工具、回传 tool_result、再问模型。
    #   你只需要像阶段 3 那样，从每条 message 里把内容取出来打印/记录：
    #       for message in runner:
    #           for b in message.content:
    #               if b.type == "text":     → print("🤖", b.text)，并存进 final_text
    #               if b.type == "tool_use": → print(f"🔧 调用 {b.name}({b.input})")
    #   循环自然结束时（模型不再要工具），final_text 里就是最后那句回答。
    #   最后 return final_text。
    final_text = ""
    for message in runner:
        for b in message.content:
            if b.type == "text":
                print("🤖", b.text)
                final_text = b.text
            if b.type == "tool_use":
                print(f"🔧 调用 {b.name}({b.input})")
    return final_text
                      
                
    raise NotImplementedError("请完成 run_agent() 里的 TODO 2、3（先删掉这行保险丝）")


# 手动试玩（可选）：set -a && source ../../.env && set +a && python3 exercise.py
if __name__ == "__main__":
    client = anthropic.Anthropic()
    task = "创建一个 todo.txt，写入三件今天要做的事，然后把它读回来确认写对了。"
    final = run_agent(client, task)
    print("\n===== 最终回答 =====")
    print(final)
