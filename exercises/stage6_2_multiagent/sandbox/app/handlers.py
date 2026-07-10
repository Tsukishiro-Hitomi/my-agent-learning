"""订单相关的请求处理器。"""


def handle_order(order_id: str) -> dict:
    """根据订单号返回订单详情（示例桩实现）。"""
    return {"order_id": order_id, "status": "created"}
