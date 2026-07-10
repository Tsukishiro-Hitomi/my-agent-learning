"""
阶段 4 评测：验证用 Tool Runner 重写的 run_agent() 行为和阶段 3 一致。

评测思路：给一个必须【先写文件、再读回来】的任务。
  - 先写后读之间有数据依赖 → 只有循环真的转起来才能完成。
  - 阶段 4 的循环是 SDK 的 tool_runner 自动跑的，你没写 while。
  - 验证手段：把 exercise 里的两个工具函数换成"带记录"的同名版本
    （run_agent 里 tools=[write_file, read_file] 引用的是模块全局名，
     这里重新赋值即可被用到，不依赖 SDK 内部实现）。据此确认：
       write_file、read_file 都被调过（read 必在 write 之后 → 循环多步转了）、
       文件真被创建、最终回答用上了读到的内容。

运行： ./run.sh 4   （需已配置好 .env）
"""

import os
import sys

import anthropic
from anthropic import beta_tool

import exercise

TEST_FILE = "agent_demo.txt"
MAGIC = "我是一个 agent"
TASK = (
    f"请在当前目录创建文件 {TEST_FILE}，往里面写入这句话（一字不差）：{MAGIC}。"
    f"写完之后，把 {TEST_FILE} 读回来，告诉我文件里到底写了什么。"
)

# 记录工具调用次数
write_calls = []
read_calls = []
_MAX_CALLS = 8


def _guard():
    if len(write_calls) + len(read_calls) > _MAX_CALLS:
        raise RuntimeError("工具调用超过 8 次，循环可能没正常结束——检查 run_agent()。")


@beta_tool
def write_file(path: str, content: str) -> str:
    """把文本内容写入指定路径的文件（会覆盖同名文件）。

    Args:
        path: 文件路径，例如 notes.txt
        content: 要写入的文本内容
    """
    write_calls.append(path)
    _guard()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已写入 {path}（{len(content)} 字）"


@beta_tool
def read_file(path: str) -> str:
    """读取指定路径文本文件的全部内容。

    Args:
        path: 文件路径
    """
    read_calls.append(path)
    _guard()
    with open(path, encoding="utf-8") as f:
        return f.read()


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

    # 把 exercise 里的工具替换成"带记录"的同名工具，用来观察循环。
    exercise.write_file = write_file
    exercise.read_file = read_file

    client = anthropic.Anthropic()

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
    print(f"（write_file 调用 {len(write_calls)} 次，read_file 调用 {len(read_calls)} 次）\n")

    file_content = ""
    if os.path.exists(TEST_FILE):
        with open(TEST_FILE, encoding="utf-8") as f:
            file_content = f.read()

    passed = True
    passed &= check(
        "调用了 write_file 写文件",
        len(write_calls) >= 1,
        "TODO 1：write_file 上加了 @beta_tool 吗？TODO 2：tools=[write_file, read_file] 传了吗？",
    )
    passed &= check(
        "调用了 read_file 读回来（证明循环多步转了）",
        len(read_calls) >= 1,
        "read 必在 write 之后：SDK 把写完那轮的结果回传后，模型才会再要求读。",
    )
    passed &= check(
        f"文件 {TEST_FILE} 真的被创建，且内容含「{MAGIC}」",
        MAGIC in file_content,
        "确认模型确实调用了 write_file 并传对了 content。",
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
