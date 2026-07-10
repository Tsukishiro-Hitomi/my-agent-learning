"""
阶段 5 评测：验证你的多工具代码库 agent。

分两段，第一段不花钱、第二段才调 API：
  【离线单测】纯 Python，验证三个工具、schema、execute 的错误处理，
             以及最关键的——用一个「假模型」证明：MAX_STEPS 护栏会让循环停下来，
             且一轮里多个 tool_use 会被【全部】执行、全部回传。
             这一段全过了，才会进入下一段（先把不花钱的部分写对，别急着烧配额）。
  【在线端到端】真调一次模型：给它一个必须【先探索、再读文件】才能回答的问题，
             确认它自主用了 发现类工具(list_dir/search_files) + read_file、多步完成、答案正确。

运行： ./run.sh 5   （会自动读 .env）
只想先验证离线部分（不花钱）：直接 python3 test.py，没有 API key 会自动跳过在线段。
"""

import os
import re
import sys

import exercise

SANDBOX = "sandbox"
CONFIG_DIR = os.path.join("sandbox", "config")
SETTINGS = os.path.join("sandbox", "config", "settings.py")
PORT = "8721"  # 埋在 sandbox/config/settings.py 里的答案（全项目唯一）

ONLINE_TASK = (
    "项目根目录是 sandbox。请找出这个服务部署到生产环境用的端口号是多少，"
    "并告诉我它定义在哪个文件里。"
)


def check(name, condition, hint=""):
    print(f"{'✅' if condition else '❌'} {name}")
    if not condition and hint:
        print(f"   提示：{hint}")
    return bool(condition)


def safe(fn, *a, **k):
    """调用 fn；若还没实现（NotImplementedError）返回哨兵，让 check 显示成普通 ❌。"""
    try:
        return fn(*a, **k)
    except NotImplementedError:
        return "__NOT_IMPL__"


# ---------------------------------------------------------------------------
# 一个「假模型」：不联网，每轮都回【两个】tool_use（要求调 list_dir）。
#   - 每轮都要工具 → 用来证明 MAX_STEPS 护栏会让循环停下来（而不是无限转）。
#   - 每轮两个块  → 用来证明 run_agent 把一轮里的多个 tool_use 全部执行、全部回传
#                   （max_tool_results 记录学习者每轮回传了几个 tool_result）。
#   - 顺便记录最后一次请求带了哪些参数（system / tools / model / max_tokens）。
# ---------------------------------------------------------------------------
class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Resp:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self):
        self.calls = 0
        self.last_kwargs = {}
        self.max_tool_results = 0  # 学习者在一条 user 消息里回传的 tool_result 最多几个

    def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        # 数一下上一轮学习者回传了几个 tool_result（应等于上一轮的 tool_use 块数 = 2）
        msgs = kwargs.get("messages", [])
        if msgs and isinstance(msgs[-1], dict) and isinstance(msgs[-1].get("content"), list):
            n = sum(1 for b in msgs[-1]["content"]
                    if isinstance(b, dict) and b.get("type") == "tool_result")
            self.max_tool_results = max(self.max_tool_results, n)
        # 无限循环保险：护栏写对的话，请求次数不会逼近这里。
        if self.calls > (exercise.MAX_STEPS or 0) + 3:
            raise RuntimeError(
                "假模型被请求了太多次——run_agent 没有遵守 MAX_STEPS，循环可能停不下来。"
            )
        return _Resp(
            [
                _Block(type="text", text="我先看看目录结构。"),
                _Block(type="tool_use", name="list_dir",
                       input={"path": SANDBOX}, id=f"toolu_{self.calls}a"),
                _Block(type="tool_use", name="list_dir",
                       input={"path": CONFIG_DIR}, id=f"toolu_{self.calls}b"),
            ],
            stop_reason="tool_use",
        )


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def run_offline():
    print("── 离线单测（不花钱）──────────────────────────")
    ok = True

    # --- Part A：三个工具 ---
    ld = safe(exercise.list_dir, SANDBOX)
    ok &= check("list_dir 能列出 sandbox 顶层的条目（app / config / utils / README.md）",
                isinstance(ld, str) and all(x in ld for x in ("app", "config", "utils", "README.md")),
                "标准库里有直接列出目录内容的函数；想想怎么让模型区分文件和子目录。")
    ok &= check("list_dir 能真的遍历子目录：列 sandbox/config 时含 settings.py",
                "settings.py" in safe(exercise.list_dir, CONFIG_DIR),
                "别硬编码顶层结果——要根据传入的 path 真的去列那个目录。")
    ok &= check("list_dir 对不存在的目录返回「错误：」而不是抛异常",
                isinstance(ld, str) and "错误" in safe(exercise.list_dir, "no/such/dir"),
                "先判断 path 是不是一个存在的目录，不是就返回一句「错误：……」。")

    rf = safe(exercise.read_file, SETTINGS)
    ok &= check(f"read_file 能读到 {SETTINGS} 的内容（含 {PORT}）",
                isinstance(rf, str) and PORT in rf,
                "把文件内容读出来返回即可。")
    ok &= check("read_file 对不存在的文件返回「错误：」而不是抛异常",
                "错误" in safe(exercise.read_file, "sandbox/nope.py"),
                "文件可能不存在或打不开——想清楚怎么兜住，返回「错误：……」而不是崩。")
    _big = "big_tmp_for_test.txt"
    try:
        with open(_big, "w", encoding="utf-8") as f:
            f.write("x" * 5000)
        rbig = safe(exercise.read_file, _big)
        ok &= check("read_file 对超长文件会截断（含「已截断」，且明显短于原文）",
                    isinstance(rbig, str) and "已截断" in rbig and len(rbig) < 5000,
                    "内容可能很长、会撑爆上下文——设个长度上限，并让模型知道被截断了。")
    finally:
        if os.path.exists(_big):
            os.remove(_big)

    # search_files：正向 + 格式 + 换个关键字（防止硬编码 settings.py）+ 无命中
    sf = safe(exercise.search_files, PORT, SANDBOX)
    ok &= check(f"search_files 能在 sandbox 里搜到 {PORT}，指向 settings.py，且带行号",
                isinstance(sf, str) and PORT in sf and "settings.py" in sf and re.search(r":\d+:", sf),
                "在目录树里逐行找子串命中；标准库里有递归遍历目录的工具。")
    sf2 = safe(exercise.search_files, "handle_order", SANDBOX)
    ok &= check("search_files 搜别的关键字(handle_order)会指向对应文件，而不是老是回 settings.py",
                isinstance(sf2, str) and ("handlers.py" in sf2 or "main.py" in sf2)
                and "settings.py" not in sf2 and PORT not in sf2,
                "结果要真的来自搜索命中，别硬编码固定字符串。")
    sf3 = safe(exercise.search_files, "绝不可能出现的字符串_zqxjk", SANDBOX)
    ok &= check("search_files 搜不到时不乱指（不含 settings.py / 端口号）",
                isinstance(sf3, str) and "settings.py" not in sf3 and PORT not in sf3,
                "没命中就返回一句普通说明，别返回一个假的命中。")

    # --- Part B：schema + execute ---
    tools = getattr(exercise, "TOOLS", [])
    by_name = {t.get("name"): t for t in tools} if isinstance(tools, list) else {}
    ok &= check("TOOLS 里三个工具的 schema 都写了（名字对得上函数）",
                {"list_dir", "read_file", "search_files"} <= set(by_name),
                "每个函数一份 {name, description, input_schema}，name 和函数名一致。")

    def _props(name):
        t = by_name.get(name, {})
        return (t.get("input_schema") or {}).get("properties") or {}

    ok &= check("每个 schema 的 description 非空、参数名和函数签名一致（path / query）",
                bool(by_name)
                and all(isinstance(by_name[n].get("description"), str)
                        and by_name[n]["description"].strip() for n in by_name)
                and "path" in _props("list_dir")
                and "path" in _props("read_file")
                and {"query", "path"} <= set(_props("search_files")),
                "input_schema.properties 里的键必须和函数参数名对上，否则模型传的参数你取不到。")

    ok &= check("execute 分发正确：execute('read_file', {'path': 设置文件}) 能读到端口",
                PORT in safe(exercise.execute, "read_file", {"path": SETTINGS}),
                "按 name 调对应函数，参数从 args 里按 key 取。")
    ok &= check("execute 对未知工具返回「错误：」",
                "错误" in safe(exercise.execute, "no_such_tool", {}),
                "name 不在已知列表时 return 一句「错误：未知工具 …」。")

    # execute 必须用 try/except 兜住工具执行时的任何异常：
    # 少传 path，会在 execute 内部取参/调用时抛异常——兜住了就返回「错误：」，没兜住就会崩。
    try:
        guarded = exercise.execute("read_file", {})
        crashed = False
    except NotImplementedError:
        guarded, crashed = "__NOT_IMPL__", False
    except Exception:
        guarded, crashed = None, True
    ok &= check("工具执行抛异常时，execute 兜住并返回「错误：」（不让 agent 崩）",
                (not crashed) and isinstance(guarded, str)
                and "错误" in guarded and guarded != "__NOT_IMPL__",
                "在 execute 里用 try/except 包住工具调用；except 时 return 一句「错误：…」。")

    # --- Part C：护栏 + 多工具（用假模型，不花钱、确定性）---
    ms = getattr(exercise, "MAX_STEPS", 0)
    ok &= check("MAX_STEPS 设成了合理的正整数（1~50）",
                isinstance(ms, int) and 1 <= ms <= 50,
                "给循环一个上限，比如 10。")
    ok &= check("SYSTEM_PROMPT 写了（非空）",
                isinstance(getattr(exercise, "SYSTEM_PROMPT", ""), str)
                and exercise.SYSTEM_PROMPT.strip(),
                "见 README「系统提示词该写什么」。")

    if isinstance(ms, int) and ms >= 1:
        fake = _FakeClient()
        try:
            safe(exercise.run_agent, fake, "随便问点什么")
            stopped = True
        except RuntimeError as e:
            print(f"   ⚠️  {e}")
            stopped = False
        ok &= check("护栏生效：假模型一直要工具时，循环在 MAX_STEPS 轮内停下（没无限转）",
                    stopped and 1 <= fake.messages.calls <= ms + 1,
                    f"你的循环应最多请求模型约 MAX_STEPS(={ms}) 次；实际请求了 {fake.messages.calls} 次。")
        ok &= check("一轮里的多个 tool_use 被全部执行、全部回传（不是只处理第一个）",
                    stopped and fake.messages.max_tool_results >= 2,
                    "遍历 resp.content 里【所有】 tool_use 块，把它们的 tool_result 放进【同一条】 user 消息回传。")
        ok &= check("run_agent 每次请求都带上了 system / tools / model / max_tokens",
                    all(fake.messages.last_kwargs.get(k) for k in ("system", "tools", "model", "max_tokens")),
                    "create(...) 里要有 model=MODEL, max_tokens=…, system=SYSTEM_PROMPT, tools=TOOLS。")

    return ok


def run_online():
    import anthropic

    print("\n── 在线端到端（真调一次模型）─────────────────")

    calls = []
    _orig_execute = exercise.execute

    def spy(name, args):
        calls.append(name)
        return _orig_execute(name, args)

    exercise.execute = spy

    client = anthropic.Anthropic()

    # 安全阀：即便 MAX_STEPS 写得偏大，也别把配额烧太多
    n = [0]
    _orig_create = client.messages.create

    def limited_create(**kwargs):
        n[0] += 1
        if n[0] > 12:
            raise RuntimeError("模型请求超过 12 次，检查 MAX_STEPS / 循环出口。")
        return _orig_create(**kwargs)

    client.messages.create = limited_create

    try:
        final = exercise.run_agent(client, ONLINE_TASK)
    except Exception as e:  # noqa: BLE001 - 学习者视角：任何在线错误都清晰报出来，别甩一堆 traceback
        print(f"❌ 在线调用出错：{type(e).__name__}: {e}")
        print("   常见原因：create(...) 少传了 model / max_tokens，或 tool_result 没和 tool_use 一一对上。")
        return False
    finally:
        exercise.execute = _orig_execute

    print("\n最终回答:", final)
    print(f"（模型请求 {n[0]} 次，工具调用序列：{calls}）\n")

    ok = True
    ok &= check("循环多步转起来了（模型请求 ≥ 2 次）", n[0] >= 2,
                "回答这个问题必须先探索再读文件，一步做不完。")
    ok &= check("用了发现类工具（list_dir 或 search_files）来定位文件",
                any(c in calls for c in ("list_dir", "search_files")),
                "system prompt 里引导它先探索目录/搜关键字，别瞎猜文件名。")
    ok &= check("用了 read_file 打开文件确认细节", "read_file" in calls,
                "在 SYSTEM_PROMPT 里要求它「作答前必须 read_file 打开文件确认」，别只凭搜索片段就下结论。")
    ok &= check(f"最终回答给出了正确端口号 {PORT}", PORT in (final or ""),
                "确认它读到了 settings.py，并把答案总结进最后一句回复。")
    return ok


def main():
    if "填" in exercise.MODEL or not exercise.MODEL.strip():
        print("⚠️  请先在 exercise.py（或 .env）里设置一个可用的 MODEL。")
        sys.exit(1)

    if not run_offline():
        print("\n离线单测没全过——先把上面 ❌ 的地方改对（这一段不花钱）。")
        print("改完重新运行 ./run.sh 5")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n✅ 离线单测全过！未检测到 ANTHROPIC_API_KEY，跳过在线端到端测试。")
        print("   想跑完整评测（含真实模型），用：./run.sh 5")
        return

    if not run_online():
        print("\n在线端到端没过——多半是 system prompt / 循环细节的问题，改改再来。")
        sys.exit(1)

    print()
    print("🎉 阶段 5 通过！你从零搭出了一个会自主探索代码库、带错误处理和护栏的 agent。")
    print("   这就是一个迷你版 Claude Code。去 LEARNING_PLAN.md 勾掉进度，")
    print("   剩下的阶段 6（记忆 / RAG / 多 agent / 评估）按兴趣深入即可。")


if __name__ == "__main__":
    main()
