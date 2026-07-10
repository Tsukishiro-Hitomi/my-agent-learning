"""通用小工具。"""

import datetime


def now_iso() -> str:
    """返回当前时间的 ISO 字符串（示例）。"""
    return datetime.datetime.now().isoformat()
