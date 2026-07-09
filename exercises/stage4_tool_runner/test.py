"""
阶段 4 评测：验证用 Tool Runner 重写的 run_agent() 行为和阶段 3 一致。

评测思路和阶段 3 相同：给一个必须【先写文件、再读回来】的任务。
  - 先写后读之间有数据依赖 → 只有循环真的转起来才能完成。
  - 区别在于：阶段 4 的循环是 SDK 的 tool_runner 自动跑的，你没写 while。
  - 我们照样检查：模型请求了多轮、write_file 和 read_file 都被调过、
    文件真的被创建、最终回答用上了读到的内容。

运行： ./run.sh 4   （需已配置好 .env）
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

    client = anthropic.Anthropic()

    # tool_runner 在内部反复调用 client.beta.messages.create 跑循环。
    # 我们包住它：统计请求次数（≥2 说明循环真的转起来了），顺便记录每一轮
    # 模型请求了哪些工具；超过 8 次就中断，防止死循环烧配额。
    n_requests = [0]
    tool_names = []
    _orig_create = client.beta.messages.create

    def spy_create(*args, **kwargs):
        n_requests[0] += 1
        if n_requests[0] > 8:
            raise RuntimeError("模型请求超过 8 次，循环可能没正常结束——检查 run_agent()。")
        resp = _orig_create(*args, **kwargs)
        for b in resp.content:
            if b.type == "tool_use":
                tool_names.append(b.name)
        return resp

    client.beta.messages.create = spy_create

    try:
        final = exercise.run_agent(client, TASK)
    except NotImplementedError as e:
        print(f"📝 还没写完：{e}")
        print("   打开 exercise.py，补全 3 个 TODO（别忘了 TODO 1 的 @beta_tool），再重新运行。")
        sys.exit(1)
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print("\n最终回答:", final)
    print(f"（模型共请求 {n_requests[0]} 次，工具调用序列：{tool_names}）\n")

    file_content = ""
    if os.path.exists(TEST_FILE):
        with open(TEST_FILE, encoding="utf-8") as f:
            file_content = f.read()

    passed = True
    passed &= check(
        "循环跑了多步（模型请求 ≥ 2 次）",
        n_requests[0] >= 2,
        "tool_runner 会自动在调完工具后再问一次模型——这正是它替你跑的循环。",
    )
    passed &= check(
        "调用了 write_file 写文件",
        "write_file" in tool_names,
        "TODO 1：write_file 上面加了 @beta_tool 吗？TODO 2：tools=[write_file, read_file] 传了吗？",
    )
    passed &= check(
        "调用了 read_file 读回来",
        "read_file" in tool_names,
        "先写后读证明循环在继续：SDK 把写完那轮的结果回传后，模型才会再要求读。",
    )
    passed &= check(
        f"文件 {TEST_FILE} 真的被创建了，且内容含「{MAGIC}」",
        MAGIC in file_content,
        "函数体已实现好写入；确认模型确实调用了 write_file 并传对了 content。",
    )
    passed &= check(
        "最终回答用上了读到的内容（含「agent」）",
        "agent" in (final or ""),
        "TODO 3：遍历 runner 时把最后一条 message 的 text 存进 final_text 并 return。",
    )

    # 清理测试文件
    if os.path.exists(TEST_FILE):
        os.remove(TEST_FILE)

    print()
    if passed:
        print("🎉 阶段 4 通过！同样的行为，代码却少了一半——因为你已经懂循环在背后怎么转。")
        print("   去 LEARNING_PLAN.md 勾掉进度，进入阶段 5（综合小项目）。")
    else:
        print("改改 exercise.py，再重新运行 ./run.sh 4")
        sys.exit(1)


if __name__ == "__main__":
    main()
