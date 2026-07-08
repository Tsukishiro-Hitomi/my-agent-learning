"""
阶段 1 练习：带记忆的聊天机器人

目标：实现一个 Chatbot 类，能记住多轮对话历史。
核心考点：Claude API 是无状态的 —— 你必须自己维护 messages 历史，
         每次请求都把完整历史发过去，模型才"记得"上文。

怎么做：把下面带 TODO 的地方补全（自己写，别抄现成代码）。
        写完后在本目录运行： python test.py
        让评测全部通过就算过关。
"""
import anthropic
MODEL = "anthropic/claude-haiku-4.5"

class Chatbot:
    def __init__(self, system="你是一个友好的中文助手，回答简洁。"):
        self.client = anthropic.Anthropic()  # 自动读取 ANTHROPIC_API_KEY
        self.system = system
        self.messages = []  # 对话历史：user / assistant 交替

    def send(self, user_message: str) -> str:
        """发送一条用户消息，返回助手回复；并把这一轮存进 self.messages。"""

        # TODO 1: 把用户这条消息追加到 self.messages
        #         格式：{"role": "user", "content": user_message}
        message = {"role": "user", "content": user_message}
        self.messages.append(message)
        # TODO 2: 调用 self.client.messages.create(...)，存到变量 resp
        #         参数：model=MODEL, max_tokens=1024,
        #               system=self.system, messages=self.messages
        resp = self.client.messages.create(model = MODEL, max_tokens = 1024, system = self.system, messages = self.messages)
        # TODO 3: 从 resp 取出回复文本（resp.content[0].text），存到变量 reply
        reply = resp.content[0].text
        # TODO 4: 把助手回复也追加到 self.messages
        #         格式：{"role": "assistant", "content": reply}
        reply_message = {"role": "assistant", "content": reply}
        self.messages.append(reply_message)
        # TODO 5: return reply
        return reply
        raise NotImplementedError("请完成 send 方法（把上面 5 个 TODO 补全）")


# 手动试玩（可选）：python exercise.py
if __name__ == "__main__":
    bot = Chatbot()
    while True:
        text = input("你: ")
        if text == "quit":
            break
        print("AI:", bot.send(text))