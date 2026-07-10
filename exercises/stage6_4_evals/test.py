"""
阶段 6.4 评测：验证你的评估框架。

分两段：
  【离线单测】不花钱：judge_keyword 判分对不对；run_evals 的统计对不对
             （拿一个"故意答对一半"的假 agent，数它的通过数）；TEST_CASES 结构合规。
  【在线端到端】真调模型：judge_llm 能正确判对/判错；run_evals 用真 agent 跑出一张记分卡。

运行： ./run.sh 6.4
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

    cases = getattr(exercise, "TEST_CASES", [])
    ok &= check("TEST_CASES 至少 5 条，且每条都有 question 和 expect",
                isinstance(cases, list) and len(cases) >= 5
                and all(isinstance(c, dict) and c.get("question") and c.get("expect") for c in cases),
                "每条形如 {'question': '...', 'expect': '答案里应出现的关键词'}。")

    ok &= check("judge_keyword：关键词在答案里 → True",
                safe(exercise.judge_keyword, "首都?", "答案是北京。", "北京") is True,
                "return expect in answer。")
    ok &= check("judge_keyword：关键词不在答案里 → False",
                safe(exercise.judge_keyword, "首都?", "答案是上海。", "北京") is False,
                "同上。")

    # run_evals 统计是否正确：造一个"偶数题答对、奇数题答错"的假 agent
    if isinstance(cases, list) and len(cases) >= 5 and all(c.get("question") for c in cases):
        order = {c["question"]: i for i, c in enumerate(cases)}

        def fake_agent(q):
            i = order.get(q, 1)
            return cases[i]["expect"] if i % 2 == 0 else "＠一定不对的答案＠"

        expected_pass = sum(1 for i in range(len(cases)) if i % 2 == 0)
        res = safe(exercise.run_evals, fake_agent, judge=exercise.judge_keyword)
        ok &= check("run_evals 返回统计字典（passed / total / rate）",
                    isinstance(res, dict) and {"passed", "total", "rate"} <= set(res),
                    "返回 {'passed':.., 'total':.., 'rate':..}。")
        if isinstance(res, dict):
            ok &= check(f"run_evals 数得对（假 agent 应通过 {expected_pass}/{len(cases)}）",
                        res.get("total") == len(cases) and res.get("passed") == expected_pass,
                        "对每条 ans=agent_fn(q)、ok=judge(q,ans,expect)，统计 True 的个数。")
            rate = res.get("rate")
            ok &= check("run_evals 的 rate = passed/total",
                        isinstance(rate, (int, float)) and abs(rate - expected_pass / len(cases)) < 1e-6,
                        "rate 是 0~1 的小数。")
    return ok


def run_online():
    print("\n── 在线端到端（真调模型）─────────────────────")
    ok = True
    try:
        good = exercise.judge_llm("2 加 2 等于几？", "2 加 2 等于 4。", "4")
        bad = exercise.judge_llm("2 加 2 等于几？", "2 加 2 等于 5。", "4")
    except Exception as e:  # noqa: BLE001
        print(f"❌ judge_llm 在线出错：{type(e).__name__}: {e}")
        return False
    ok &= check("judge_llm 把正确回答判为 True", good is True,
                "prompt 要让模型只回答 是/否，再据此返回布尔。")
    ok &= check("judge_llm 把错误回答判为 False", bad is False,
                "同上；注意把'是/否'解析成 True/False。")

    print("\n用真 agent 跑一张记分卡：")
    try:
        res = exercise.run_evals(exercise.demo_agent, judge=exercise.judge_keyword)
    except Exception as e:  # noqa: BLE001
        print(f"❌ run_evals 在线出错：{type(e).__name__}: {e}")
        return False
    ok &= check("run_evals 用真 agent 跑出了完整记分卡",
                isinstance(res, dict) and res.get("total") == len(exercise.TEST_CASES),
                "每条都要真的调 agent_fn 并判分。")
    ok &= check("真 agent 至少答对 1 题（说明整条评估链路是通的）",
                isinstance(res, dict) and res.get("passed", 0) >= 1,
                "选些常识题、demo_agent 应答得对；判分器也要正常。")
    return ok


def main():
    if "填" in exercise.MODEL or not exercise.MODEL.strip():
        print("⚠️  请先设置一个可用的 MODEL。")
        sys.exit(1)
    if not run_offline():
        print("\n离线单测没全过——先把上面 ❌ 改对（这一段不花钱）。改完重跑 ./run.sh 6.4")
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n✅ 离线单测全过！未检测到 ANTHROPIC_API_KEY，跳过在线段。完整评测用：./run.sh 6.4")
        return
    if not run_online():
        print("\n在线段没过——多半是 judge_llm 没把'是/否'解析对，改改再来。")
        sys.exit(1)
    print()
    print("🎉 阶段 6.4 通过！你有了一把'尺子'——改完 agent 能用分数看出是变好还是变坏。")
    print("   这是从'玩具'走向'生产'的关键：凭数据决策，不凭感觉。")
    print("   下一关 6.5 护栏：危险操作前先让人确认。想做了跟我说。")


if __name__ == "__main__":
    main()
