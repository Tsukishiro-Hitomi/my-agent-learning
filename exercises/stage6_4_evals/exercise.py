"""
阶段 6.4 · 评估（Evals）：用分数科学衡量 agent 好不好

到目前为止，你判断 agent"行不行"全靠自己看几眼——但改了 prompt 之后到底变好还是变坏？
你说不清。**评估**就是给 agent 出一批固定的题、自动判分、算出一个分数。
有了分数，你才能"改一版 → 重跑 → 看分数涨没涨"，用数据驱动改进。

（其实你这一路用的 test.py 就是评估的雏形——现在你亲手把它做成一个通用小框架。）

你要做的：
    Part A: TEST_CASES     —— 准备 ≥5 道题（问题 + 期望答案里该出现的关键词）
    Part B: judge_keyword  —— 最朴素的判分：答案里有没有那个关键词
    Part C: judge_llm      —— LLM-as-judge：再叫一个模型来判"这个回答对不对"
    Part D: run_evals      —— 把每道题跑一遍、判分、打印记分卡、返回统计
（被评估的 demo_agent 我已给好，见下方。）

写完运行： ./run.sh 6.4
"""

import os

import anthropic

MODEL = os.environ.get("MODEL", "anthropic/claude-haiku-4.5")
client = anthropic.Anthropic()


# ============================================================================
# Part A：测试集（你来写）
# ============================================================================
# 每条一个 dict：{"question": 问题, "expect": 正确答案里应出现的关键词}。至少 5 条。
# 建议选"答案明确、好判分"的题，例如常识题（首都、简单算术、名著人物…）。
TEST_CASES = [
    # {"question": "中国的首都是哪座城市？", "expect": "北京"},
]


# ============================================================================
# Part B / C：两种判分器（你来写）——注意两者签名一致，都是 (question, answer, expect)
# ============================================================================


def judge_keyword(question: str, answer: str, expect: str) -> bool:
    """最朴素的判分：answer 里是否包含关键词 expect。（不看 question，只看关键词。）"""
    raise NotImplementedError("实现 judge_keyword（删掉这行）")


def judge_llm(question: str, answer: str, expect: str) -> bool:
    """LLM-as-judge：再叫一个模型来判断 answer 对不对，返回 True/False。

    契约：
      - 拼一个 prompt 给模型：包含 question、期望要点 expect、待判的 answer；
        要求它【只回答一个字：是 / 否】。
      - 调 client.messages.create(...)，据模型回答返回布尔（回答含"是"→True）。
    为什么要它：很多答案关键词对不上但意思对（同义、换算、改写），关键词判分会误杀，
               让模型来判更接近人的判断。
    """
    raise NotImplementedError("实现 judge_llm（删掉这行）")


# ============================================================================
# Part D：评估主循环（你来写）
# ============================================================================


def run_evals(agent_fn, judge=None) -> dict:
    """把每道 TEST_CASE 跑一遍，判分，打印记分卡，返回统计。

    契约：
      - judge 默认用 judge_keyword（judge 可传 judge_llm 换一种判法）。
      - 对每条：ans = agent_fn(question)；ok = judge(question, ans, expect)。
      - 逐条打印一行（✅/❌ + 问题），最后打印"通过 X / 共 Y（通过率 Z%）"。
      - 返回 {"passed": 通过数, "total": 总数, "rate": 通过率(0~1 的小数)}。
    评测会查：统计数对得上（拿一个"故意对一半"的假 agent 来数）。
    """
    raise NotImplementedError("实现 run_evals（删掉这行）")


# ============================================================================
# ↓↓↓ 已给好：一个"被评估"的简单问答 agent（就调一次模型）——不用改 ↓↓↓
# ============================================================================
def demo_agent(question: str) -> str:
    resp = client.messages.create(
        model=MODEL, max_tokens=512, messages=[{"role": "user", "content": question}])
    return next((b.text for b in resp.content if b.type == "text"), "")


if __name__ == "__main__":
    import _trace; _trace.on()  # 观察：把模型思考痕迹写入 output.txt
    print("用关键词判分跑一遍：")
    print(run_evals(demo_agent, judge=judge_keyword))
    # 想体验 LLM-as-judge，把上面换成： run_evals(demo_agent, judge=judge_llm)
