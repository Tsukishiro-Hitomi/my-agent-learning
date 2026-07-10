"""
阶段 6.3 评测：验证 RAG（检索增强）。

分两段：
  【离线单测】不花钱：retrieve 能按问题捞到【正确文档】里的正确片段、返回的是子集而非全量；
             answer_with_rag 确实把"资料"塞进了给模型的 prompt（用假模型验证）。
  【在线端到端】真调模型：问一个只有 docs 里才有的编造事实（模型不可能提前知道），
             它能答对并指出来源文件——证明检索真的起了作用。

运行： ./run.sh 6.3
只想先验证离线部分（不花钱）：直接 python3 test.py，没有 API key 会自动跳过在线段。
"""

import json
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


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Resp:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


def run_offline():
    print("── 离线单测（不花钱）──────────────────────────")
    ok = True

    r_conc = safe(exercise.retrieve, "云雀 CDN 单节点最大并发连接数是多少")
    ok &= check("retrieve 问「并发」→ 捞到 product.md 里含 3200 的段",
                isinstance(r_conc, str) and "3200" in r_conc and "product.md" in r_conc,
                "给每段按与 query 的相关度打分，取分最高的几段，并带上来源文件名。")

    r_price = safe(exercise.retrieve, "企业版年费多少钱")
    ok &= check("retrieve 问「年费」→ 捞到 pricing.md 里含 128000 的段",
                isinstance(r_price, str) and "128000" in r_price and "pricing.md" in r_price,
                "不同问题应捞到不同文档——不是永远返回同一个文件。")

    r_faq = safe(exercise.retrieve, "刷新缓存多久生效")
    ok &= check("retrieve 问「刷新缓存」→ 捞到 faq.md 里含 90 的段",
                isinstance(r_faq, str) and "90" in r_faq and "faq.md" in r_faq,
                "同上，检索要按相关度路由到对的文档。")

    total = sum(len(text) for _, text in exercise._load_chunks())
    ok &= check("retrieve 返回的是【相关片段的子集】，不是把所有文档倒出来",
                isinstance(r_conc, str) and len(r_conc) < total,
                "限制只取前 top_k 段，别把整个知识库拼起来返回。")

    r_none = safe(exercise.retrieve, "今天北京天气怎么样")
    ok &= check("retrieve 遇到不相关的问题不乱指（不含 3200/128000）",
                isinstance(r_none, str) and "3200" not in r_none and "128000" not in r_none,
                "打分为 0 的段要丢掉；都不相关就返回「没有找到相关资料」。")

    # answer_with_rag 是否真把"资料"塞进了 prompt（用假模型验证，不花钱）
    _orig_ret = exercise.retrieve
    _orig_create = exercise.client.messages.create
    captured = {}
    MAGIC = "MAGIC_CTX_渡渡鸟_9F"

    def fake_retrieve(q, top_k=3):
        return MAGIC

    def fake_create(**kwargs):
        captured["messages"] = kwargs.get("messages")
        captured["system"] = kwargs.get("system")
        return _Resp([_Block(type="text", text="（假模型回答）")])

    exercise.retrieve = fake_retrieve
    exercise.client.messages.create = fake_create
    try:
        _ = safe(exercise.answer_with_rag, "随便问点啥")
        sent = json.dumps(captured.get("messages"), ensure_ascii=False)
    finally:
        exercise.retrieve = _orig_ret
        exercise.client.messages.create = _orig_create

    ok &= check("answer_with_rag 把检索到的资料塞进了发给模型的 prompt",
                MAGIC in sent,
                "第 2 步：把 retrieve 的结果拼进 messages 再发给模型。")
    ok &= check("answer_with_rag 请求时带上了 system=SYSTEM_PROMPT",
                bool(captured.get("system")),
                "create(...) 里要传 system=SYSTEM_PROMPT。")

    ok &= check("SYSTEM_PROMPT 写了（非空）",
                isinstance(getattr(exercise, "SYSTEM_PROMPT", ""), str) and exercise.SYSTEM_PROMPT.strip(),
                "约束模型：只依据资料回答、注明出处。")
    return ok


def run_online():
    print("\n── 在线端到端（真调模型）─────────────────────")
    calls = []
    _orig_ret = exercise.retrieve

    def spy(q, top_k=3):
        calls.append(q)
        return _orig_ret(q, top_k)

    exercise.retrieve = spy
    ok = True
    try:
        a1 = exercise.answer_with_rag("单节点最大并发连接数是多少？出自哪个文件？")
        a2 = exercise.answer_with_rag("企业版年费是多少？")
    except Exception as e:  # noqa: BLE001
        print(f"❌ 在线出错：{type(e).__name__}: {e}")
        return False
    finally:
        exercise.retrieve = _orig_ret

    print("\n问并发 → 回答:", (a1 or "")[:200])
    print("问年费 → 回答:", (a2 or "")[:200])

    ok &= check("答对了「并发 = 3200」（这数字是编的，答对只可能靠检索）",
                "3200" in (a1 or ""), "确认 retrieve 捞到了 product.md 的那段，并塞进了 prompt。")
    ok &= check("并指出了来源文件 product.md", "product" in (a1 or "").lower() or "product.md" in (a1 or ""),
                "SYSTEM_PROMPT 要求注明答案来自哪个文件。")
    ok &= check("答对了「企业版年费 = 128000」", "128000" in (a2 or ""),
                "换个问题也能检索到对的文档。")
    ok &= check("answer_with_rag 确实调用了 retrieve", len(calls) >= 2,
                "先检索、再作答——不能跳过检索。")
    return ok


def main():
    if "填" in exercise.MODEL or not exercise.MODEL.strip():
        print("⚠️  请先设置一个可用的 MODEL。")
        sys.exit(1)
    if not run_offline():
        print("\n离线单测没全过——先把上面 ❌ 改对（这一段不花钱）。改完重跑 ./run.sh 6.3")
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n✅ 离线单测全过！未检测到 ANTHROPIC_API_KEY，跳过在线段。完整评测用：./run.sh 6.3")
        return
    if not run_online():
        print("\n在线段没过——多半是资料没塞进 prompt，或 SYSTEM_PROMPT 没约束好，改改再来。")
        sys.exit(1)
    print()
    print("🎉 阶段 6.3 通过！你的 agent 能回答私有知识了——靠的是'先检索、再作答'。")
    print("   这就是 RAG 的本质：检索 → 把原文塞进 prompt → 让模型据此作答。")
    print("   下一关 6.4 评估：用分数科学衡量 agent 好不好。想做了跟我说。")


if __name__ == "__main__":
    main()
