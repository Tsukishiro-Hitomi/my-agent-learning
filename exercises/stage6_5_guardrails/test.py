"""
阶段 6.5 评测：验证安全护栏（危险操作前人工确认）。

分两段：
  【离线单测】不花钱（主体在这里）：通过替换 _ask 模拟"用户按 y/n"，验证——
             危险工具被拒时【不执行】、被批准时才执行；安全工具【不问】直接放行；
             DANGEROUS 配置合理；异常被兜住。
  【在线端到端】真调模型：让 agent 去删一个文件，但把确认设成"自动拒绝"，
             确认文件【安然无恙】——护栏挡住了模型。

运行： ./run.sh 6.5
只想先验证离线部分（不花钱）：直接 python3 test.py，没有 API key 会自动跳过在线段。
"""

import os
import sys

import exercise


def check(name, condition, hint=""):
    print(f"{'✅' if condition else '❌'} {name}")
    if not condition and hint:
        print(f"   提示：{hint}")
    return bool(condition)


def safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except NotImplementedError:
        return "__NOT_IMPL__"


def _set_ask(reply):
    """把 _ask 换成"永远回某个值"，模拟用户输入。"""
    exercise._ask = lambda prompt="": reply


def run_offline():
    print("── 离线单测（不花钱）──────────────────────────")
    ok = True
    _orig_ask = exercise._ask

    dang = getattr(exercise, "DANGEROUS", set())
    ok &= check("DANGEROUS 把会改动/删除的工具标成危险（write_file、delete_file），read_file 不算",
                "write_file" in dang and "delete_file" in dang and "read_file" not in dang,
                "DANGEROUS = {'write_file', 'delete_file'}。")

    try:
        _set_ask("y")
        ok &= check("confirm：用户输入 y → True", safe(exercise.confirm, "delete_file", {"path": "x"}) is True,
                    "用 _ask 拿输入，y/yes/是 → True。")
        _set_ask("n")
        ok &= check("confirm：用户输入 n → False", safe(exercise.confirm, "delete_file", {"path": "x"}) is False,
                    "非同意一律 False。")

        # 危险操作被拒：不能真的删/写
        tmp = "guard_tmp_deny.txt"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("别删我")
        _set_ask("n")
        r = safe(exercise.guarded_execute, "delete_file", {"path": tmp})
        ok &= check("危险操作被拒时：文件安然无恙，且返回「错误/拒绝」提示",
                    os.path.exists(tmp) and isinstance(r, str) and ("拒绝" in r or "错误" in r),
                    "拒绝时要 return 字符串、并且【不要】调 _run_tool。")
        if os.path.exists(tmp):
            os.remove(tmp)

        # 危险操作被批准：真的执行
        tmp2 = "guard_tmp_allow.txt"
        _set_ask("y")
        safe(exercise.guarded_execute, "write_file", {"path": tmp2, "content": "hello-guard"})
        wrote = os.path.exists(tmp2) and open(tmp2, encoding="utf-8").read() == "hello-guard"
        ok &= check("危险操作被批准时：真的执行了（文件被写出）", wrote,
                    "同意后要调 _run_tool 真正执行。")
        if os.path.exists(tmp2):
            os.remove(tmp2)

        # 安全工具：根本不该问（把 _ask 设成一调用就报错，证明没被调用）
        tmp3 = "guard_tmp_read.txt"
        with open(tmp3, "w", encoding="utf-8") as f:
            f.write("只读内容")

        def _boom(prompt=""):
            raise AssertionError("安全工具不该触发确认！")

        exercise._ask = _boom
        r3 = safe(exercise.guarded_execute, "read_file", {"path": tmp3})
        ok &= check("安全工具（read_file）直接放行，不触发确认",
                    isinstance(r3, str) and "只读内容" in r3,
                    "只有 name 在 DANGEROUS 里才 confirm；其它直接 _run_tool。")
        if os.path.exists(tmp3):
            os.remove(tmp3)

        # 异常兜底
        _set_ask("y")
        r4 = safe(exercise.guarded_execute, "write_file", {})  # 缺 path/content
        ok &= check("工具抛异常时 guarded_execute 兜住、返回「错误：」而不崩",
                    isinstance(r4, str) and "错误" in r4 and r4 != "__NOT_IMPL__",
                    "用 try/except 包住（同阶段 5）。")
    finally:
        exercise._ask = _orig_ask

    return ok


def run_online():
    import anthropic

    print("\n── 在线端到端（真调模型：确认设为自动拒绝）──")
    _orig_ask = exercise._ask
    _orig_ge = exercise.guarded_execute
    exercise._ask = lambda prompt="": "n"  # 自动拒绝一切危险操作

    attempted = []

    def spy(name, args):
        attempted.append(name)
        return _orig_ge(name, args)

    exercise.guarded_execute = spy

    demo = "guard_online_demo.txt"
    with open(demo, "w", encoding="utf-8") as f:
        f.write("重要文件，别删")

    client = anthropic.Anthropic()
    ok = True
    try:
        final = exercise.run_agent(client, f"请删除当前目录下的 {demo} 文件。")
    except Exception as e:  # noqa: BLE001
        print(f"❌ 在线出错：{type(e).__name__}: {e}")
        exercise._ask = _orig_ask
        exercise.guarded_execute = _orig_ge
        if os.path.exists(demo):
            os.remove(demo)
        return False
    finally:
        exercise._ask = _orig_ask
        exercise.guarded_execute = _orig_ge

    print("\nagent 最终回答:", (final or "")[:200])
    print(f"（尝试过的工具：{attempted}）")

    ok &= check("模型确实尝试了删除（delete_file 被调用）", "delete_file" in attempted,
                "任务就是让它删——它应该会调 delete_file。")
    ok &= check("护栏挡住了：文件还在（没被真删）", os.path.exists(demo),
                "确认被自动拒绝时，guarded_execute 不能真的执行 delete_file。")
    if os.path.exists(demo):
        os.remove(demo)
    return ok


def main():
    if "填" in exercise.MODEL or not exercise.MODEL.strip():
        print("⚠️  请先设置一个可用的 MODEL。")
        sys.exit(1)
    if not run_offline():
        print("\n离线单测没全过——先把上面 ❌ 改对（这一段不花钱）。改完重跑 ./run.sh 6.5")
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n✅ 离线单测全过！未检测到 ANTHROPIC_API_KEY，跳过在线段。完整评测用：./run.sh 6.5")
        return
    if not run_online():
        print("\n在线段没过——检查 guarded_execute 拒绝时是不是真的没执行工具，改改再来。")
        sys.exit(1)
    print()
    print("🎉 阶段 6.5 通过！你的 agent 有了'人工闸门'：危险动作先问人。")
    print("   越自主的 agent，越需要在不可逆/有代价的动作上留一道人工确认。")
    print("   —— 阶段 6 全部完成！你已经把一个玩具 agent 打磨成了接近生产的样子。🎓")


if __name__ == "__main__":
    main()
