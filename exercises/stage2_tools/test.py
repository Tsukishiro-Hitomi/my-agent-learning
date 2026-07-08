"""
阶段 2 评测：验证 answer() 是否正确走完 tool_use 一来一回。

运行： ./run.sh 2   （需已配置好 .env）
"""

import os
import sys

import anthropic

import exercise


def check(name, condition, hint=""):
    print(f"{'✅' if condition else '❌'} {name}")
    if not condition and hint:
        print(f"   提示：{hint}")
    return condition


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  未检测到 ANTHROPIC_API_KEY，请用 ./run.sh 运行（会自动读 .env）。")
        sys.exit(1)

    if "填" in exercise.MODEL or not exercise.MODEL.strip():
        print("⚠️  请先在 exercise.py（或 .env）里设置一个可用的 MODEL。")
        sys.exit(1)

    # 监视 get_weather：记录它有没有被真正调用、传进来的城市是什么
    calls = []
    _orig = exercise.get_weather

    def spy(city):
        calls.append(city)
        return _orig(city)

    exercise.get_weather = spy

    client = anthropic.Anthropic()

    try:
        final = exercise.answer(client, "北京今天天气怎么样？")
    except NotImplementedError as e:
        print(f"📝 还没写完：{e}")
        print("   打开 exercise.py，补全 answer() 里的 5 个 TODO，再重新运行。")
        sys.exit(1)

    print("最终回答:", final)
    print()

    passed = True
    passed &= check(
        "模型真的调用了 get_weather 工具",
        len(calls) >= 1,
        "看 TODO 2：是否遍历 resp.content 并对 tool_use 块调用了 get_weather？",
    )
    passed &= check(
        "传给工具的城市是「北京」",
        any("北京" in c for c in calls),
        "block.input 里带着 city，用 get_weather(**block.input) 传进去。",
    )
    passed &= check(
        "最终回答用上了工具结果（含「晴」或「25」）",
        ("晴" in final) or ("25" in final),
        "拿到 tool_result 后要再请求一次模型（TODO 4），并返回它的最终文字（TODO 5）。",
    )

    print()
    if passed:
        print("🎉 阶段 2 通过！去 LEARNING_PLAN.md 勾掉进度，进入阶段 3。")
    else:
        print("改改 exercise.py，再重新运行 ./run.sh 2")
        sys.exit(1)


if __name__ == "__main__":
    main()
