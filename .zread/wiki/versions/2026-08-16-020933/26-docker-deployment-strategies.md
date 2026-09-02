# Docker 部署策略

## 容器构建流水线：多阶段 Dockerfile

### 后端 Dockerfile —— 三阶段渐进瘦身

### 前端 Dockerfile —— 四阶段 Next.js 流水线

## Docker Compose 架构：基础文件与 Overlay

### 生产环境 Compose：服务拓扑

| 服务 | 镜像 | 端口 | 角色 |
|---|---|---|---|
| nginx | nginx:alpine | 2026 (宿主机) | 反向代理，基于路径的路由 |
| frontend | 基于 frontend/Dockerfile 构建 (target: prod) | 3000 (内部) | Next.js 生产服务器 |
| gateway | 基于 backend/Dockerfile 构建 | 8001 (内部) | FastAPI 网关 + 内嵌 Agent 运行时 |
| redis | redis:7-alpine | 6379 (内部) | 用于 SSE 流桥接的 Redis Streams 后端 |
| provisioner | 基于 docker/provisioner/Dockerfile 构建 | 8002 (内部) | 沙箱 Pod 生命周期管理（仅限 Kubernetes 模式） |

### 开发环境 Compose：热重载 Bind Mount

### Overlay 系统：DooD、CLI Auth 与 OpenViking

## 沙箱模式检测：驱动运行时拓扑

| 模式 | Provider | Docker 套接字 | Provisioner | 适用场景 |
|---|---|---|---|---|
| local | LocalSandboxProvider | 不挂载 | 不启动 | 默认；沙箱在进程内运行 |
| aio | AioSandboxProvider (无 provisioner_url) | 通过 DooD overlay 挂载 | 不启动 | 通过宿主机 Docker 实现的基于容器的沙箱 |
| provisioner | AioSandboxProvider (有 provisioner_url) | 不挂载 | 启动 | 原生 Kubernetes 沙箱 Pod |

## Nginx 反向代理：基于路径的路由与 SSE

-
-
-

## Provisioner 服务：Kubernetes 沙箱生命周期

| 模式 | 机制 | 镜像 | 安全性 |
|---|---|---|---|
| A (Init) | Init 容器 + 共享的 emptyDir 暂存 lark-cli 二进制文件 | docker/lark-cli-init/Dockerfile | 仅含二进制文件；沙箱内无凭据 |
| B (Broker) | Init 容器写入垫片；长期运行的 sidecar 通过回环地址持有凭据 | docker/lark-cli-broker/Dockerfile | 明文配置/数据绝不挂载至沙箱；取代模式 A |

## 部署脚本与 Makefile 集成

| Makefile 目标 | 脚本 | Compose 文件 | 环境 |
|---|---|---|---|
| make up | scripts/deploy.sh | docker-compose.yaml | 生产环境 |
| make down | scripts/deploy.sh down | docker-compose.yaml | 生产环境 |
| make docker-init | scripts/docker.sh init | docker-compose-dev.yaml | 开发环境 |
| make docker-start | scripts/docker.sh start | docker-compose-dev.yaml | 开发环境 |
| make docker-stop | scripts/docker.sh stop | docker-compose-dev.yaml | 开发环境 |

### deploy.sh —— 生产环境编排

### docker.sh —— 开发环境编排

## Kubernetes 部署：Helm Chart

### 关键 Helm 配置维度

### Kubernetes 安全姿态

| 工作负载 | runAsUser | fsGroup | Capabilities | 权限提升 |
|---|---|---|---|---|
| gateway | 1000 | 1000 | ALL dropped | false |
| frontend | 1000 (node) | 1000 | ALL dropped | false |
| nginx | 101 (nginx) | 101 | ALL dropped | false |
| provisioner | 1000 | — | ALL dropped | false |
| postgres | 999 (postgres) | 999 | ALL dropped | false |
| redis | 999 (redis) | 999 | ALL dropped | false |

## 环境变量契约

| 变量 | 作用域 | 默认值 | 用途 |
|---|---|---|---|
| DEER_FLOW_PROJECT_ROOT | 网关 | /app | 相对运行时路径的项目根目录 |
| DEER_FLOW_HOME | 全部 | $REPO_ROOT/backend/.deer-flow | 运行时数据目录（sqlite、记忆、自定义 Agent） |
| DEER_FLOW_CONFIG_PATH | 网关 | $REPO_ROOT/config.yaml | config.yaml 的路径 |
| DEER_FLOW_EXTENSIONS_CONFIG_PATH | 网关 | $REPO_ROOT/extensions_config.json | MCP 服务器 + 技能状态 |
| DEER_FLOW_STREAM_BRIDGE_REDIS_URL | 网关 | redis://redis:6379/0 | 用于 SSE 桥接的 Redis Streams URL |
| BETTER_AUTH_SECRET | 前端 | 自动生成 | 认证/会话安全所需 |
| DEER_FLOW_INTERNAL_AUTH_TOKEN | 网关 | 自动生成 | 用于多工作进程通道的共享内部认证 |
| GATEWAY_WORKERS | 网关 | 1 | Uvicorn 工作进程数（为运行控制安全请保持为 1） |
| BIND_HOST | nginx | 127.0.0.1 | 宿主机绑定地址（默认仅回环） |
| PORT | nginx | 2026 | 外部端口 |
| UV_EXTRAS | 构建 | 自动检测 | 可选依赖组（逗号分隔） |
| DEER_FLOW_DOCKER_SOCKET | DooD overlay | /var/run/docker.sock | 宿主机 Docker 套接字路径（仅限 aio 模式） |

## 部署路径选择
