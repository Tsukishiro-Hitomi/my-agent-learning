"""
阶段 3 评测：验证 run_agent() 是否是一个能"多步自主完成任务"的 agent 循环。

评测思路：给它一个必须【先写文件、再读回来】的任务。
  - 先写后读之间有数据依赖 → 模型没法一步做完 → 只有循环在转才能完成。
  - 于是我们检查：模型请求了多轮、write_file 和 read_file 都被调过、
    文件真的被创建、最终回答用上了读到的内容。

运行： ./run.sh 3   （需已配置好 .env）
"""

import os
import sys

import anthropic

import exercise

TEST_FILE = "agent_demo.txt"
MAGIC = "我是一个 agent"
TASK = (
    f"请在当前目录创建文件 {TEST_FILE}，往里面写入这句话（一字不差）：{MAGIC}。"
    f"写完之后，把 {TEST_FILE} 读回来，告诉我文件里到底写了什么。"
)


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

    # 干净起步：删掉上次可能残留的测试文件
    if os.path.exists(TEST_FILE):
        os.remove(TEST_FILE)

    # 监视 execute：记录每一步调用了哪个工具、传了什么参数
    calls = []
    _orig_execute = exercise.execute

    def spy(name, args):
        calls.append((name, args))
        return _orig_execute(name, args)

    exercise.execute = spy

    client = anthropic.Anthropic()

    # 安全阀：包住 client.messages.create，统计请求次数；超过 8 次就中断，
    # 防止 break 条件写错导致死循环把配额烧光。
    n_requests = [0]
    _orig_create = client.messages.create

    def limited_create(**kwargs):
        n_requests[0] += 1
        if n_requests[0] > 8:
            raise RuntimeError(
                "模型请求超过 8 次，循环可能没正常结束——检查 TODO 1 的 break 条件。"
            )
        return _orig_create(**kwargs)

    client.messages.create = limited_create

    try:
        final = exercise.run_agent(client, TASK)
    except NotImplementedError as e:
        print(f"📝 还没写完：{e}")
        print("   打开 exercise.py，补全 run_agent() 里的 4 个 TODO，再重新运行。")
        sys.exit(1)
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print("\n最终回答:", final)
    print(f"（模型共请求 {n_requests[0]} 次，工具调用序列：{[c[0] for c in calls]}）\n")

    tool_names = [c[0] for c in calls]
    file_content = ""
    if os.path.exists(TEST_FILE):
        with open(TEST_FILE, encoding="utf-8") as f:
            file_content = f.read()

    passed = True
    passed &= check(
        "循环跑了多步（模型请求 ≥ 2 次）",
        n_requests[0] >= 2,
        "调完工具后要回到循环顶部再请求一次——这正是 agent loop 和阶段 2 的区别。",
    )
    passed &= check(
        "调用了 write_file 写文件",
        "write_file" in tool_names,
        "看 TODO 3：是否遍历 tool_use 块并用 execute(block.name, block.input) 执行？",
    )
    passed &= check(
        "调用了 read_file 读回来",
        "read_file" in tool_names,
        "先写后读证明循环在继续：写完那轮的 tool_result 回传后，模型才会再要求读。",
    )
    passed &= check(
        f"文件 {TEST_FILE} 真的被创建了，且内容含「{MAGIC}」",
        MAGIC in file_content,
        "execute 已实现好写入；确认模型确实调用了 write_file 并传对了 content。",
    )
    passed &= check(
        "最终回答用上了读到的内容（含「agent」）",
        "agent" in (final or ""),
        "TODO 1：break 之前把最后一轮的文字取出来存进 final_text 并 return。",
    )

    # 清理测试文件
    if os.path.exists(TEST_FILE):
        os.remove(TEST_FILE)

    print()
    if passed:
        print("🎉 阶段 3 通过！你已经亲手搭出了一个会自主多步的 agent。")
        print("   去 LEARNING_PLAN.md 勾掉进度，进入阶段 4（用 SDK 的 tool_runner 简化循环）。")
    else:
        print("改改 exercise.py，再重新运行 ./run.sh 3")
        sys.exit(1)


if __name__ == "__main__":
    main()
