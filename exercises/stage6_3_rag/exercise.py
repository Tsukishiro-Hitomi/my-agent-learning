"""
阶段 6.3 · RAG（检索增强生成）：让 agent 回答它本来不知道的私有知识

模型没读过你公司的内部资料，所以直接问它"云雀 CDN 单节点最大并发是多少"，它只能瞎编。
RAG 的套路就三步（记住这三步就懂 RAG 了）：
    1) 检索(Retrieve)：先从你的私有文档里，找出和问题最相关的几段。
    2) 增强(Augment) ：把这几段原文塞进 prompt，作为"资料"。
    3) 生成(Generate)：让模型【只依据这份资料】作答，并注明出处。

练习对象：docs/ 目录里三份"云雀 CDN"内部资料（里面的数字都是编的，模型不可能提前知道——
所以它要是答对了，就证明你的检索真的起作用了）。

你要做的：
    Part A: 写 retrieve(query)      —— 从 docs/ 里捞出最相关的几段（带来源文件名）
    Part B: 写 answer_with_rag(...) —— 把上面三步串起来
    Part C: 写 SYSTEM_PROMPT        —— 约束模型"只依据资料作答、注明出处"
（把文档切成"段"的读取工作 _load_chunks() 我已给好，见下方。）

写完运行： ./run.sh 6.3
"""

import os

import anthropic

MODEL = os.environ.get("MODEL", "anthropic/claude-haiku-4.5")
client = anthropic.Anthropic()

DOCS_DIR = "docs"


# ============================================================================
# Part A：检索（你来写）
# ============================================================================


def retrieve(query: str, top_k: int = 3) -> str:
    """从 docs/ 里找出和 query 最相关的【最多 top_k 段】，返回带来源文件名的文字。

    契约：
      - 用下面给好的 _load_chunks() 拿到所有 (文件名, 段落)。
      - 给每一段打一个"相关度"分——简单启发式就行，例如：query 里的字/词，有多少出现在这段里。
      - 取分数最高的前 top_k 段（分数为 0 的丢掉）；每段前面标上来源，如「【来自 product.md】...」。
      - 一段都不相关：返回一句「没有找到相关资料」。
    评测会查：问"并发"能捞到 product.md 里含 3200 的段；问"年费"能捞到 pricing.md 含 128000 的段；
              且返回的是【相关片段的子集】，不是把所有文档原样倒出来。
    """
    chunks = _load_chunks()
    counts = [0] * len(chunks)

    def _bigrams(s):
        s = "".join(s.lower().split())              # 去掉所有空白
        return {s[i:i+2] for i in range(len(s) - 1)} # 相邻两字为一个词，用 set 去重
    
    # 原来的逐字匹配过于粗糙。改用 bigram 方式：用二元词作匹配
    qb = _bigrams(query)
    for i, (fn, para) in enumerate(chunks):
        p = para.lower()
        counts[i] = sum(1 for b in qb if b in p)  
    
    # 获取 counts 中最大的 k 个的索引
    # 根据 key = lambda i : counts[i] 排序，倒序输出，只取前 top_k 个
    indices = sorted((i for i in range(len(counts)) if counts[i] != 0), key=lambda i: counts[i], reverse=True)[:top_k]
    return_chunks = [chunks[i] for i in indices]
    if len(return_chunks) == 0:
        return "没有找到相关资料！"
    result = ""
    for fn, para in return_chunks:
        result += f"来自资料【{fn}】：{para}\n"
    return result


# ============================================================================
# Part B：把 检索→增强→生成 串起来（你来写）
# ============================================================================


def answer_with_rag(question: str) -> str:
    """RAG 三步走，返回模型的最终回答。

    契约：
      1) 检索：context = retrieve(question)
      2) 增强：拼一个 prompt——把 context 作为"资料"给模型，
              要求它【只依据资料】回答、并说明答案来自哪个文件。
      3) 生成：调一次 client.messages.create(...)（带上 system=SYSTEM_PROMPT），返回模型的文字回答。
    评测会查：问一个只有 docs 里才有的事实（模型自己不可能知道），它能答对且指出来源文件。
    """
    context = retrieve(question)
    content = question + "\n请根据以下资料回答，不要自己编造\n" + context
    messages = [{"role": "user", "content": content}]
    resp = client.messages.create(
            model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT, messages=messages,
        )
    return next((b.text for b in resp.content if b.type == "text"), "")

# ============================================================================
# Part C：系统提示词（你来写）
# ============================================================================
# 约束模型的行为：只根据给它的"资料"回答；资料里没有就说不知道，别编；回答要注明来自哪个文件。
SYSTEM_PROMPT = "只根据给你的资料回答，回答时注明资料来源的文件。资料里没有就说不知道，不准胡编乱造。"  # 你来写


# ============================================================================
# ↓↓↓ 已给好：把 docs/ 切成"段"——不用改 ↓↓↓
# ============================================================================
def _load_chunks() -> list:
    """把 docs/ 下每个文件按空行切成若干段，返回 [(文件名, 段落文字), ...]。"""
    chunks = []
    for fn in sorted(os.listdir(DOCS_DIR)):
        path = os.path.join(DOCS_DIR, fn)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for para in text.split("\n\n"):
            para = para.strip()
            if para:
                chunks.append((fn, para))
    return chunks


if __name__ == "__main__":
    import _trace; _trace.on()  # 观察：把模型思考痕迹写入 output.txt
    # 第 3 个问题应该返回：“无法找到相应结果”
    for q in ["单节点最大并发连接数是多少？在哪个文件里？",
              "企业版年费是多少？", 
              "个人版月费是多少？"]:
        print(f"\n===== 问：{q} =====")
        print(answer_with_rag(q))
