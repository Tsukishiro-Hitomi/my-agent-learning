"""
阶段 6.1 评测：验证你的「记忆」实现。

分两段：
  【离线单测】不花钱，纯 Python：save_memory 真写进 memory.json、recall_memory 真读回来、
             同一个 key 是覆盖不是堆叠、没记忆时不崩、schema 和 SYSTEM_PROMPT 写了。
  【在线端到端】真调模型，模拟"跨会话记忆"：
             会话 1 告诉它信息（它应 save_memory）→ 会话 2 是全新一轮、【不带任何历史】，
             只靠磁盘上的 memory.json，问它同样的信息，它应 recall_memory 后答得出。

运行： ./run.sh 6.1   （会自动读 .env）
只想先验证离线部分（不花钱）：直接 python3 test.py，没有 API key 会自动跳过在线段。
"""

import json
import os
import sys

import exercise

MEM = exercise.MEMORY_FILE  # "memory.json"


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


def _raw():
    if not os.path.exists(MEM):
        return ""
    with open(MEM, encoding="utf-8") as f:
        return f.read()


def _clean():
    if os.path.exists(MEM):
        os.remove(MEM)


def run_offline():
    print("── 离线单测（不花钱）──────────────────────────")
    ok = True
    _clean()

    r = safe(exercise.save_memory, "name", "小明")
    ok &= check("save_memory 把信息真的写进了 memory.json",
                isinstance(r, str) and r != "__NOT_IMPL__" and "小明" in _raw(),
                "读出旧内容(没有就当空 {}) → 设 key=value → json.dump 写回文件。")

    valid = False
    try:
        with open(MEM, encoding="utf-8") as f:
            json.load(f)
        valid = True
    except Exception:
        valid = False
    ok &= check("memory.json 是合法 JSON", valid,
                "用 json.dump 写，别自己拼字符串。")

    ok &= check("recall_memory 能读回刚存的信息（含「小明」）",
                "小明" in safe(exercise.recall_memory),
                "json.load 读出字典，再组织成文字返回。")

    safe(exercise.save_memory, "name", "小红")
    rec = safe(exercise.recall_memory)
    ok &= check("同一个 key 再存是【覆盖】（只剩小红，没有小明）",
                isinstance(rec, str) and "小红" in rec and "小明" not in rec,
                "存之前先读出整个字典，改 key 再写回——不是往文件末尾追加。")

    safe(exercise.save_memory, "project", "订单服务")
    rec2 = safe(exercise.recall_memory)
    ok &= check("能同时记住多条（小红 + 订单服务都在）",
                isinstance(rec2, str) and "小红" in rec2 and "订单服务" in rec2,
                "字典里多个 key 共存。")

    _clean()
    empty = safe(exercise.recall_memory)
    ok &= check("没有任何记忆时，recall 不崩、给个空提示",
                isinstance(empty, str) and empty != "__NOT_IMPL__" and "小红" not in empty,
                "文件不存在时别直接 open 崩掉——先判断或 try 一下。")

    tools = getattr(exercise, "TOOLS", [])
    by_name = {t.get("name"): t for t in tools} if isinstance(tools, list) else {}
    ok &= check("两个工具的 schema 都写了（save_memory / recall_memory）",
                {"save_memory", "recall_memory"} <= set(by_name),
                "参考阶段 5：每个 {name, description, input_schema}。")

    def props(n):
        return ((by_name.get(n, {}) or {}).get("input_schema") or {}).get("properties") or {}

    ok &= check("save_memory 的 schema 参数名对得上（有 key 和 value）",
                {"key", "value"} <= set(props("save_memory")),
                "input_schema.properties 里要有 key、value，和函数参数名一致。")
    ok &= check("每个 schema 都有非空 description",
                bool(by_name) and all((by_name[n].get("description") or "").strip() for n in by_name),
                "description 是模型判断「何时用这个工具」的依据。")

    ok &= check("SYSTEM_PROMPT 写了（非空）",
                isinstance(getattr(exercise, "SYSTEM_PROMPT", ""), str) and exercise.SYSTEM_PROMPT.strip(),
                "教 agent：听到用户信息就 save，答问前先 recall。")

    _clean()
    return ok


def run_online():
    import anthropic

    print("\n── 在线端到端（真调模型，模拟跨会话记忆）──────")
    _clean()

    calls = []
    _orig = exercise.execute

    def spy(name, args):
        calls.append(name)
        return _orig(name, args)

    exercise.execute = spy

    client = anthropic.Anthropic()
    n = [0]
    _oc = client.messages.create

    def limited(**kwargs):
        n[0] += 1
        if n[0] > 16:
            raise RuntimeError("模型请求过多，检查一下。")
        return _oc(**kwargs)

    client.messages.create = limited

    ok = True
    try:
        print("【会话 1】告诉它：我叫小明，在做订单服务")
        exercise.run_agent(client, "我叫小明，在做一个叫订单服务的项目。")
        s1_tools = list(calls)

        ok &= check("会话 1：agent 调用了 save_memory 把信息记下来",
                    "save_memory" in s1_tools,
                    "SYSTEM_PROMPT 要明确让它「听到用户信息就 save_memory」。")
        ok &= check("会话 1 后，memory.json 里真存下了「小明」",
                    "小明" in _raw(),
                    "确认 save_memory 真的写了文件。")

        # 会话 2：全新一轮，run_agent 内部重开 messages，不带任何上文——只靠 memory.json
        print("\n【会话 2】新的一轮（不带任何历史），问它：我叫什么？做什么项目？")
        calls.clear()
        final = exercise.run_agent(client, "我叫什么名字？我在做什么项目？")
        s2_tools = list(calls)

        print("\n会话 2 最终回答:", final)
        print(f"（会话2 工具调用：{s2_tools}）\n")

        ok &= check("会话 2：agent 调用了 recall_memory 去查记忆",
                    "recall_memory" in s2_tools,
                    "答问前要先 recall——它这一轮没有任何上文，只能靠记忆文件。")
        ok &= check("会话 2 答出了名字「小明」（跨会话记住了）",
                    "小明" in (final or ""),
                    "会话2 是全新进程般的一轮，能答对只可能是从 memory.json 读回来的。")
        ok &= check("会话 2 答出了项目「订单服务」",
                    "订单服务" in (final or ""),
                    "同上，靠的是记忆。")
    except Exception as e:  # noqa: BLE001
        print(f"❌ 在线调用出错：{type(e).__name__}: {e}")
        print('   常见原因：TOOLS 的 input_schema 不合法（如 type 写成了 "str"，应为 "string"）。')
        return False
    finally:
        exercise.execute = _orig
        _clean()

    return ok


def main():
    if "填" in exercise.MODEL or not exercise.MODEL.strip():
        print("⚠️  请先设置一个可用的 MODEL。")
        sys.exit(1)

    if not run_offline():
        print("\n离线单测没全过——先把上面 ❌ 改对（这一段不花钱）。改完重跑 ./run.sh 6.1")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n✅ 离线单测全过！未检测到 ANTHROPIC_API_KEY，跳过在线段。完整评测用：./run.sh 6.1")
        return

    if not run_online():
        print("\n在线段没过——多半是 SYSTEM_PROMPT 没把「何时 save / 何时 recall」讲清楚，改改再来。")
        sys.exit(1)

    print()
    print("🎉 阶段 6.1 通过！你的 agent 有记忆了——关掉再开，它还记得你。")
    print("   这就是所有「记忆 / 持久化」的本质：存盘 + 读回 context。")
    print("   下一关 6.2 多 Agent：一个 agent 可以当另一个 agent 的工具。想做了跟我说。")


if __name__ == "__main__":
    main()
