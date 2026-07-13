"""
阶段 2 练习：工具调用 Tool Use

目标：让模型学会"请求调用你的函数"，你执行后把结果回传，它再据此回答。
核心考点 —— tool_use 的一来一回：
  1) 你把工具说明书随请求发给模型
  2) 模型返回 stop_reason == "tool_use"，说明它想调工具（并给出参数）
  3) 你的代码执行工具，把结果用 tool_result 回传（必须带 tool_use_id）
  4) 再请求一次，模型根据结果给出最终答案

怎么做：补全 answer() 里的 5 个 TODO（自己写，别抄）。写完后在项目根目录运行：
    ./run.sh 2
"""

import os

import anthropic

# 模型名：默认用你阶段 1 跑通的那个；也可在 .env 里加一行 MODEL=... 覆盖
MODEL = os.environ.get("MODEL", "anthropic/claude-haiku-4.5")

# ---- 工具定义（已给好，不用改）----
TOOLS = [{
    "name": "get_weather",
    "description": "获取某个城市的当前天气。当用户询问天气时调用此工具。",
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名，例如 北京"},
        },
        "required": ["city"],
    },
}]


def get_weather(city: str) -> str:
    """真正执行天气查询（这里用假数据，重点是打通流程）。"""
    return f"{city}：晴，气温 25°C"


def answer(client, user_message: str) -> str:
    """处理一次可能用到工具的问答，返回模型最终的文字回答。"""
    messages = [{"role": "user", "content": user_message}]

    # 第一次请求：把工具说明书一起发给模型
    resp = client.messages.create(
        model=MODEL, max_tokens=1024, tools=TOOLS, messages=messages,
    )

    # 如果模型没打算用工具，直接返回它的文字
    if resp.stop_reason != "tool_use":
        return next((b.text for b in resp.content if b.type == "text"), "")

    # ↓↓↓ 模型要求调用工具，下面由你补全 ↓↓↓

    # TODO 1: 模型这条"要调工具"的回复也要进历史（后面还要接着对话，历史不能断）。
    #         把 resp.content 作为一条 assistant 消息追加进 messages。
    messages.append({"role": "assistant", "content": resp.content})
    # TODO 2: 遍历 resp.content 里所有 block，挑出 block.type == "tool_use" 的：
    #           - 用 get_weather(**block.input) 执行，拿到结果
    #           - 组装成这个格式的字典（这是 API 规定的结构，照着搭）：
    #               {"type": "tool_result", "tool_use_id": block.id, "content": 结果}
    #         把这些字典收集进一个列表，命名为 results。
    results = []
    for b in resp.content:
        if b.type == "tool_use":
            result = get_weather(**b.input)
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": result})
    # TODO 3: 工具结果是"用户方"回传给模型的，所以把 results 作为一条
    #         role 为 "user" 的消息追加进 messages。
    messages.append({"role": "user", "content": results})
    # TODO 4: 再请求一次 client.messages.create(...)，参数和第一次相同
    #         （model / max_tokens / tools / messages），结果存回 resp。
    resp = client.messages.create(
        model=MODEL, max_tokens=1024, tools=TOOLS, messages=messages,
    )
    # TODO 5: 从 resp 取出最终文字并 return（写法同上面那句 next(...)）。
    return next((b.text for b in resp.content if b.type == "text"), "")
    raise NotImplementedError("请完成 answer() 里的 5 个 TODO")


# 手动试玩（可选）：set -a && source ../../.env && set +a && python3 exercise.py
if __name__ == "__main__":
    import _trace; _trace.on()  # 观察：把模型思考痕迹写入 output.txt
    client = anthropic.Anthropic()
    print(answer(client, "北京今天天气怎么样？"))
