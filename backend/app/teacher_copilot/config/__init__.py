"""Teacher Copilot 环境配置。

仅从环境变量读取(便于本地开发与部署),必要时向前端暴露带默认值的配置。
数据库默认 SQLite 文件(开发零依赖),可通过 teacher_copilot.database.url 切换
MySQL 异步方言(如 mysql+asyncmy://...)。
"""
