"""
阶段 6.2 评测：验证多 Agent 协作。

分两段：
  【离线单测】不花钱：用一个"假的 agent_loop"验证你的接线对不对——
             researcher 是否带上了文件工具、writer 是否不带工具；schema / 分发 / 三个 system 是否写了。
  【在线端到端】真调模型：让协调者完成"研究 sandbox + 写介绍"，
             确认它把活【既派给了 researcher 又派给了 writer】，且最终产出用上了项目里的真实信息。

运行： ./run.sh 6.2
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


def run_offline():
    print("── 离线单测（不花钱）──────────────────────────")
    ok = True

    # 用"假 agent_loop"记录：子 agent 到底带着什么工具/什么 system 去跑循环
    rec = []

    def fake_loop(task, system, tools, execute_fn, max_steps=8):
        rec.append({"task": task, "system": system, "tools": tools, "execute_fn": execute_fn})
        return f"[fake-loop 结果 for: {task[:20]}]"

    _orig_loop = exercise.agent_loop
    exercise.agent_loop = fake_loop
    try:
        rec.clear()
        r = safe(exercise.researcher, "sandbox 里有什么？")
        rok = (r != "__NOT_IMPL__") and len(rec) == 1
        tool_names = {t.get("name") for t in (rec[0]["tools"] or [])} if rok else set()
        ok &= check("researcher 是一个会跑 agent_loop 的子 agent，且带上了【文件工具】",
                    rok and tool_names == {"list_dir", "read_file"}
                    and rec[0]["execute_fn"] is exercise.file_execute
                    and bool((rec[0]["system"] or "").strip()),
                    "researcher 里应 return agent_loop(question, RESEARCHER_SYSTEM, FILE_TOOLS, file_execute)。")

        rec.clear()
        w = safe(exercise.writer, "把这些笔记写成一段话")
        wok = (w != "__NOT_IMPL__") and len(rec) == 1
        ok &= check("writer 也是子 agent，但【不带任何工具】（纯写作）",
                    wok and not rec[0]["tools"] and rec[0]["execute_fn"] is None
                    and bool((rec[0]["system"] or "").strip()),
                    "writer 里应 return agent_loop(instruction, WRITER_SYSTEM, [], None)。")
    finally:
        exercise.agent_loop = _orig_loop

    # schema
    tools = getattr(exercise, "TOOLS", [])
    by_name = {t.get("name"): t for t in tools} if isinstance(tools, list) else {}
    ok &= check("协调者的两个工具 schema 写了（researcher / writer）",
                {"researcher", "writer"} <= set(by_name),
                "协调者的工具不是文件操作，而是这两个子 agent。")

    def props(n):
        return ((by_name.get(n, {}) or {}).get("input_schema") or {}).get("properties") or {}

    ok &= check("schema 参数名对得上（researcher 有 question、writer 有 instruction）",
                "question" in props("researcher") and "instruction" in props("writer"),
                "参数名要和函数参数一致。")

    # 分发器：monkeypatch 两个子 agent 成"罐头"，验证 orchestrator_execute 路由正确
    _r, _w = exercise.researcher, exercise.writer
    exercise.researcher = lambda question: f"R:{question}"
    exercise.writer = lambda instruction: f"W:{instruction}"
    try:
        ok &= check("orchestrator_execute 能把调用路由给 researcher",
                    safe(exercise.orchestrator_execute, "researcher", {"question": "q"}) == "R:q",
                    "name=='researcher' → researcher(args['question'])。")
        ok &= check("orchestrator_execute 能把调用路由给 writer",
                    safe(exercise.orchestrator_execute, "writer", {"instruction": "i"}) == "W:i",
                    "name=='writer' → writer(args['instruction'])。")
        ok &= check("orchestrator_execute 对未知/坏输入返回「错误：」而不崩",
                    "错误" in str(safe(exercise.orchestrator_execute, "nope", {}))
                    and "错误" in str(safe(exercise.orchestrator_execute, "researcher", {})),
                    "未知工具 + try/except 兜住异常（同阶段 5 的 execute）。")
    finally:
        exercise.researcher, exercise.writer = _r, _w

    ok &= check("三个 system 提示词都写了（researcher / writer / orchestrator）",
                all((getattr(exercise, n, "") or "").strip()
                    for n in ("RESEARCHER_SYSTEM", "WRITER_SYSTEM", "ORCHESTRATOR_SYSTEM")),
                "子 agent 的人设 + 协调者的分工说明，见 README。")
    return ok


def run_online():
    print("\n── 在线端到端（真调模型）─────────────────────")
    calls = []
    _orig = exercise.orchestrator_execute

    def spy(name, args):
        calls.append(name)
        return _orig(name, args)

    exercise.orchestrator_execute = spy

    # 安全阀：多 agent 会嵌套调用，请求数会多一些，给宽一点上限
    n = [0]
    _oc = exercise.client.messages.create

    def limited(**kwargs):
        n[0] += 1
        if n[0] > 30:
            raise RuntimeError("模型请求超过 30 次，检查子 agent 是否停不下来。")
        return _oc(**kwargs)

    exercise.client.messages.create = limited

    ok = True
    try:
        final = exercise.run_orchestrator(
            "请研究 sandbox 这个项目，然后写一段简短介绍给新同事。")
    except Exception as e:  # noqa: BLE001
        print(f"❌ 在线出错：{type(e).__name__}: {e}")
        return False
    finally:
        exercise.orchestrator_execute = _orig
        exercise.client.messages.create = _oc

    print("\n协调者最终产出:", (final or "")[:400])
    print(f"（模型共请求 {n[0]} 次，协调者派活序列：{calls}）\n")

    ok &= check("协调者把活派给了【调研员】researcher", "researcher" in calls,
                "ORCHESTRATOR_SYSTEM 要说清楚：复合任务先让 researcher 收集信息。")
    ok &= check("协调者把活派给了【写手】writer", "writer" in calls,
                "收集完信息，要交给 writer 成文——别自己写。")
    ok &= check("最终产出用上了项目里的真实信息（订单/服务/端口等）",
                any(k in (final or "") for k in ("订单", "order", "服务", "端口", "8721")),
                "说明 researcher 真的读了 sandbox、信息流到了 writer。")
    return ok


def main():
    if "填" in exercise.MODEL or not exercise.MODEL.strip():
        print("⚠️  请先设置一个可用的 MODEL。")
        sys.exit(1)
    if not run_offline():
        print("\n离线单测没全过——先把上面 ❌ 改对（这一段不花钱）。改完重跑 ./run.sh 6.2")
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n✅ 离线单测全过！未检测到 ANTHROPIC_API_KEY，跳过在线段。完整评测用：./run.sh 6.2")
        return
    if not run_online():
        print("\n在线段没过——多半是 ORCHESTRATOR_SYSTEM 没把「先调研、再写作」讲清楚，改改再来。")
        sys.exit(1)
    print()
    print("🎉 阶段 6.2 通过！你造出了一个'团队'：协调者把活拆给子 agent。")
    print("   核心：一个子 agent 就是'一个会跑循环、返回文字的函数'，所以它能当工具用。")
    print("   下一关 6.3 RAG：回答前先从你的私有文档里检索。想做了跟我说。")


if __name__ == "__main__":
    main()
