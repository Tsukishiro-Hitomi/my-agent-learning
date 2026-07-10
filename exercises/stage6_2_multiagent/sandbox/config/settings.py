"""order-service 运行配置。"""

DEBUG = False
DATABASE_URL = "postgres://db.internal/orders"

# 生产环境部署时，HTTP 服务监听的端口
DEPLOY_PORT = 8721

# 工作进程数
WORKERS = 4
