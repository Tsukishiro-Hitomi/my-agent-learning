"""
阶段 1 评测：验证你的 Chatbot 是否真的"记得"上文。

运行：  python test.py   （需在本目录，且已 export ANTHROPIC_API_KEY）
"""

import os
import sys

from exercise import Chatbot


def check(name, condition, hint=""):
    print(f"{'✅' if condition else '❌'} {name}")
    if not condition and hint:
        print(f"   提示：{hint}")
    return condition


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  未检测到 ANTHROPIC_API_KEY，请先 export 你的 key。")
        sys.exit(1)

    bot = Chatbot()

    try:
        reply1 = bot.send("我叫小明，请记住我的名字。")
        print("第1轮回复:", reply1)

        reply2 = bot.send("我叫什么名字？")
        print("第2轮回复:", reply2)
    except NotImplementedError as e:
        print(f"📝 还没写完：{e}")
        print("   打开 exercise.py，补全 send() 里的 5 个 TODO，再重新运行。")
        sys.exit(1)
    print()

    passed = True
    passed &= check(
        "能记住上文（第二轮回复包含'小明'）",
        "小明" in reply2,
        "把每一轮的 user 和 assistant 都追加进 self.messages 了吗？",
    )
    passed &= check(
        "历史正确维护（共 4 条：2 user + 2 assistant）",
        len(bot.messages) == 4,
        "每轮要追加 2 条：用户消息 + 助手回复。",
    )

    print()
    if passed:
        print("🎉 阶段 1 通过！去 LEARNING_PLAN.md 勾掉进度，进入阶段 2。")
    else:
        print("改改 exercise.py，再重新运行 python test.py")
        sys.exit(1)


if __name__ == "__main__":
    main()