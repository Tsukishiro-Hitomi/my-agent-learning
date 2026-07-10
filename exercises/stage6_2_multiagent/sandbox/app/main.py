"""服务入口：加载配置并启动 HTTP 服务。"""

from config.settings import DEPLOY_PORT, WORKERS
from app.handlers import handle_order


def start():
    print(f"order-service 启动中，监听端口 {DEPLOY_PORT}，进程数 {WORKERS}")
    # 省略：绑定端口、注册路由 handle_order ...


if __name__ == "__main__":
    start()
