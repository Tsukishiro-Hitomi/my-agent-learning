# 阶段 6.4 · 评估 Evals 📊（动手练习）

你改了 prompt、换了工具描述之后——agent 到底变好了还是变坏了？光凭"我觉得"说不清。
**评估**就是给 agent 出一批固定的题、自动判分、算出一个分数。有了分数，才能用数据驱动改进。

> 其实你这一路跑的 `test.py` 就是评估的雏形。这一关你亲手把它做成一个**通用小框架**。

## 心智模型
```
一批测试题(TEST_CASES)
      │  对每道题
      ▼
   ans = agent(question)        ← 让被测 agent 作答
   ok  = judge(q, ans, expect)  ← 判分（关键词 / 或叫模型来判）
      │
      ▼
  记分卡：通过 4 / 共 5（80%）   ← 一个能对比的数字
```

## 你要做的（Part A / B / C / D）
- **A** `TEST_CASES`：≥5 道题，每条 `{"question": ..., "expect": 答案里应出现的关键词}`。选好判分的常识题。
- **B** `judge_keyword(question, answer, expect)`：答案里有没有那个关键词。最朴素。
- **C** `judge_llm(question, answer, expect)`：**LLM-as-judge**——再叫一个模型判"这回答对不对"，只回答是/否。
- **D** `run_evals(agent_fn, judge=None)`：跑完所有题、判分、打印记分卡、返回 `{passed, total, rate}`。

两个判分器**签名一样**（都是 `question, answer, expect`），所以 `run_evals` 能随意换着用。
被测的 `demo_agent` 已给好。写完 `./run.sh 6.4`。

## 为什么要两种判分器？
- **关键词**：快、免费、确定，但会误杀——答案意思对、但没用那个词（同义/换算/改写）。
- **LLM-as-judge**：让模型来判，更接近人的判断，代价是要花钱、也可能出错。
真实项目里常两者结合。

## 通关标准
**离线**：`judge_keyword` 判断正确；`run_evals` 统计准确（用"故意对一半"的假 agent 数）；`TEST_CASES` ≥5 且结构合规。
**在线**：`judge_llm` 能把对的判 True、错的判 False；`run_evals` 用真 agent 跑出完整记分卡。

## 手动试玩
```bash
cd exercises/stage6_4_evals
set -a && source ../../.env && set +a
python3 exercise.py        # 看记分卡；把 judge 换成 judge_llm 再跑一次，对比两种判法
```

## 🎯 做完你就理解了
"这个 agent 到底行不行"从此不靠感觉，靠一个能复现、能对比的**分数**。
这正是把 agent 从"demo"推向"上线"的分水岭。
