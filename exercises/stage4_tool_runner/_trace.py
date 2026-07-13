"""
观察小工具：把模型的“思考痕迹”写进同目录 output.txt，方便回看学习。

原理：在 anthropic SDK 的 messages.create 那一层做一次拦截，
      每次调用模型时，把【发出去的请求】(system / messages / tools)
      和【收回来的响应】(resp.content / stop_reason / usage) 以可读文本写进文件。
      因为所有 stage 最终都走这个方法，一处拦截即可覆盖全部
      （含 stage4 的 tool_runner、stage6_2 的子 agent 递归调用）。

用法：只在直接运行 exercise.py 时启用——在 __main__ 里加一行 `import _trace; _trace.on()`。
      评测（test.py 里 `import exercise`）不会触发，不受影响。
"""
import functools
import json
import os
from datetime import datetime

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.txt")
_installed = False
_call_no = 0
_last_system = None


def _get(b, key, default=None):
    """统一读取 block 字段：兼容 pydantic 对象 / dict / SimpleNamespace。"""
    if isinstance(b, dict):
        return b.get(key, default)
    return getattr(b, key, default)


def _clip(s, n=1800):
    s = str(s)
    return s if len(s) <= n else s[:n] + f"\n      …(还有 {len(s) - n} 字省略)"


def _w(text=""):
    with open(_OUT, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def _render_blocks(content, indent="    "):
    """渲染一段 content（可能是字符串，或 block 列表）。"""
    if isinstance(content, str):
        _w(indent + _clip(content).replace("\n", "\n" + indent))
        return
    for b in content or []:
        t = _get(b, "type")
        if t == "text":
            _w(indent + "• text: " + _clip(_get(b, "text", "")).replace("\n", "\n" + indent + "        "))
        elif t == "tool_use":
            args = json.dumps(_get(b, "input", {}), ensure_ascii=False, default=str)
            _w(f"{indent}• tool_use: {_get(b, 'name')}({_clip(args, 400)})  #{_get(b, 'id')}")
        elif t == "tool_result":
            rc = _get(b, "content", "")
            if isinstance(rc, list):  # 有时 content 是 block 列表
                rc = "".join(_get(x, "text", "") if _get(x, "type") == "text" else str(x) for x in rc)
            _w(f"{indent}• tool_result #{_get(b, 'tool_use_id')}:")
            _w(indent + "    " + _clip(rc).replace("\n", "\n" + indent + "    "))
        elif t == "thinking":
            _w(indent + "• thinking: " + _clip(_get(b, "thinking", "")))
        else:
            _w(f"{indent}• {t}: {_clip(b)}")


def _wrap(orig):
    @functools.wraps(orig)
    def create(self, *args, **kwargs):
        global _call_no, _last_system
        _call_no += 1
        n = _call_no
        _w("\n" + "=" * 80)
        _w(f"CALL #{n}   model={kwargs.get('model', '?')}")
        _w("-" * 80)
        system = kwargs.get("system")
        if system is not None and system != _last_system:
            _w("system ▸")
            _render_blocks(system if isinstance(system, list)
                           else [{"type": "text", "text": system}], "    ")
            _last_system = system
        tools = kwargs.get("tools")
        if tools:
            _w("tools ▸ " + ", ".join(_get(t, "name", "?") for t in tools))
        msgs = kwargs.get("messages", [])
        _w(f"messages ▸ 共 {len(msgs)} 条")
        for i, m in enumerate(msgs, 1):
            _w(f"  [{i}] {_get(m, 'role')}:")
            _render_blocks(_get(m, "content", ""), "      ")
        _w("-" * 80)
        try:
            resp = orig(self, *args, **kwargs)
        except Exception as e:
            _w(f"← 调用抛异常：{type(e).__name__}: {_clip(e, 600)}")
            _w("=" * 80)
            raise
        usage = _get(resp, "usage")
        u = f"   usage: in={_get(usage, 'input_tokens')} out={_get(usage, 'output_tokens')}" if usage else ""
        _w(f"← response  stop_reason={_get(resp, 'stop_reason')}{u}")
        _render_blocks(_get(resp, "content", []), "    ")
        _w("=" * 80)
        return resp
    return create


def on(path=None):
    """启用追踪。可选 path 覆盖默认输出文件（默认：本文件同目录 output.txt）。"""
    global _installed, _OUT, _call_no, _last_system
    if path:
        _OUT = os.path.abspath(path)
    _call_no = 0
    _last_system = None
    with open(_OUT, "w", encoding="utf-8") as f:  # 每次运行覆盖，只留最近一次
        f.write(f"# 模型思考痕迹（本次运行：{datetime.now():%Y-%m-%d %H:%M:%S}）\n")
        f.write("# 由 _trace.on() 记录；每次运行覆盖。仅供观察学习。\n")
    if not _installed:
        import anthropic.resources.messages.messages as _M
        _M.Messages.create = _wrap(_M.Messages.create)
        try:
            import anthropic.resources.beta.messages.messages as _BM
            _BM.Messages.create = _wrap(_BM.Messages.create)
        except Exception:
            pass
        _installed = True
    print(f"[trace] 已开启，思考痕迹将写入 {_OUT}")
