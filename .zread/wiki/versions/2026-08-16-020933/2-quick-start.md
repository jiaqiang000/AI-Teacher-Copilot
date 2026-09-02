# 快速开始

## 前置条件一览

| 工具 | 最低版本 | 用途 | 安装链接 |
|---|---|---|---|
| Python | 3.12+ | 后端 Agent 运行时、设置向导、诊断工具 | python.org |
| Node.js | 22+ | 前端开发服务器、pnpm 生态系统 | nodejs.org |
| pnpm | 10.26.2+ | 前端包管理器（支持 Corepack 回退） | pnpm.io |
| uv | 最新版 | 用于管理后端依赖的 Python 包管理器 | docs.astral.sh/uv |
| nginx | 任意版本 | 本地反向代理，将前端和 API 统一在 2026 端口 | nginx.org |
| Docker（可选） | 任意较新版本 | 基于容器的部署与沙箱隔离 | docker.com |

### 部署规模规划

| 部署目标 | 起步配置 | 推荐配置 | 备注 |
|---|---|---|---|
| 本地评估 (make dev) | 4 vCPU, 8 GB 内存, 20 GB SSD | 8 vCPU, 16 GB 内存 | 适用于单开发者或使用托管模型 API 的轻量会话 |
| Docker 开发 (make docker-start) | 4 vCPU, 8 GB 内存, 25 GB SSD | 8 vCPU, 16 GB 内存 | 镜像构建、绑定挂载和沙箱容器需要更多空间 |
| 长期运行服务器 (make up) | 8 vCPU, 16 GB 内存, 40 GB SSD | 16 vCPU, 32 GB 内存 | 推荐用于共享使用、多 Agent 运行和报告生成 |

## 第一步：克隆代码仓库

## 第二步：运行设置向导

### 向导步骤详解

### 向导中可用的 LLM 提供商

| 提供商 | 显示名称 | 主要模型 | 环境变量 | 思考支持 |
|---|---|---|---|---|
| 火山引擎豆包 | Volcengine Doubao | doubao-seed-1-8-251228 | VOLCENGINE_API_KEY | ✓ (OpenAI 兼容) |
| 火山引擎 Coding Plan | Volcengine Coding Plan | 豆包/GLM/DeepSeek/Kimi/MiniMax (11 个模型) | VOLCENGINE_API_KEY | ✓ (按模型区分) |
| OpenAI | OpenAI | gpt-5, gpt-5-mini, gpt-4.1, gpt-4o | OPENAI_API_KEY | 可配置 |
| OpenAI Responses API | OpenAI Responses API | gpt-5, gpt-5-mini | OPENAI_API_KEY | 可配置 |
| OpenRouter | OpenRouter | 通过 base_url 支持多家服务商 | OPENROUTER_API_KEY | 提示输入 |
| Anthropic | Anthropic | Claude 模型 | ANTHROPIC_API_KEY | ✓ (budget_tokens) |
| vLLM | vLLM (自托管) | 自定义模型名称 | VLLM_API_KEY | 提示输入 |
| 自定义 OpenAI 兼容 | 任意 OpenAI 兼容 | 用户指定 | 用户指定 | 提示输入 |

### 手动配置替代方案

## 第三步：验证你的设置

## 第四步：选择你的部署路径

### 选项 1：Docker（推荐）

### 选项 2：本地开发

### 启动模式参考

|  | 本地前台 | 本地守护进程 | Docker 开发 | Docker 生产 |
|---|---|---|---|---|
| 开发 | make dev | make dev-daemon | make docker-start | — |
| 生产 | make start | make start-daemon | — | make up |

| 操作 | 本地 | Docker 开发 | Docker 生产 |
|---|---|---|---|
| 停止 | make stop | make docker-stop | make down |
| 重启 | ./scripts/serve.sh --restart [flags] | ./scripts/docker.sh restart | — |
| 日志 | 查看终端或 logs/ | make docker-logs | docker logs |

## 架构一览

## 配置文件概述

| 部分 | 用途 | 是否必需？ |
|---|---|---|
| config_version | 用于检测升级的架构版本 | 是（自动生成） |
| log_level | 日志详细程度（debug/info/warning/error） | 是（默认：info） |
| models | LLM 模型定义，包含提供商、密钥、能力 | 是 — 至少需要一个模型 |
| tools | Agent 工具注册表（搜索、沙箱、文件操作） | 由向导自动生成 |
| sandbox | 执行隔离提供商（本地或容器） | 由向导自动生成 |
| database | 用于 checkpointer 和 store 的持久化后端 | 可选（默认：基于文件） |
| channel_connections | 启用 IM 渠道（Telegram、Slack 等） | 可选 |
| token_budget | 单次运行的令牌限制，防止成本失控 | 可选（默认禁用） |
| token_usage | 令牌使用量收集与展示 | 可选（默认启用） |
| max_recursion_limit | Agent 递归深度的上限 | 可选（默认：1000） |

## 项目结构

```
deer-flow/
├── Makefile                    # 统一的开发命令（setup, dev, docker 等）
├── config.example.yaml         # 完整配置模板（2560 行）
├── config.yaml                 # 你的配置文件（由 `make setup` 生成）
├── .env                        # API 密钥（由向导生成）
├── Install.md                  # Agent 可读的引导说明
│
├── backend/                    # Python 后端 — 网关 API + Agent 运行时
│   ├── app/                    # FastAPI 应用、网关、Agent 逻辑
│   ├── packages/               # 内部 Python 包
│   ├── pyproject.toml          # 后端依赖（由 uv 管理）
│   ├── langgraph.json          # LangGraph Studio 集成配置
│   └── Dockerfile              # 后端容器镜像
│
├── frontend/                   # Next.js 16 前端
│   ├── src/                    # App Router 页面、组件、核心逻辑
│   ├── package.json            # 前端依赖（由 pnpm 管理）
│   ├── Dockerfile              # 前端容器镜像
│   └── .env                    # 前端环境变量（由向导生成）
│
├── docker/                     # Docker Compose 配置
│   ├── docker-compose-dev.yaml # 开发环境（热重载）
│   ├── docker-compose.yaml     # 生产环境
│   ├── nginx/                  # Nginx 配置模板
│   └── dev-entrypoint.sh       # 容器启动脚本
│
├── scripts/                    # 自动化与工具脚本
│   ├── setup_wizard.py         # 交互式设置向导（`make setup`）
│   ├── doctor.py               # 健康诊断（`make doctor`）
│   ├── check.py                # 前置条件检查器（`make check`）
│   ├── serve.sh                # 本地服务启动器（`make dev/start`）
│   ├── docker.sh               # Docker 服务管理器（`make docker-*`）
│   ├── deploy.sh               # 生产 Docker 部署器（`make up`）
│   └── wizard/                 # 设置向导模块（LLM、搜索、执行、渠道）
│
├── skills/                     # 技能定义（公开 + 自定义）
└── docs/                       # 额外文档
```

## 常见问题排查

| 问题 | 可能原因 | 解决方案 |
|---|---|---|
| make setup 提示 "Non-interactive environment" | 在管道或非 TTY 环境中运行 | 请在支持 TTY 的终端中直接运行 |
| make check 报告缺少 uv | uv 未安装或不在 PATH 中 | 安装命令：curl -LsSf https://astral.sh/uv/install.sh \| sh |
| make check 报告缺少 nginx | nginx 未安装 | macOS: brew install nginx · Ubuntu: sudo apt install nginx |
| make docker-start 因权限不足失败 | Docker 守护进程 Socket 权限问题 | 执行 sudo usermod -aG docker $USER 后重新登录 |
| Agent 返回缺少模型的错误 | config.yaml 中未配置模型 | 在 config.yaml 的 models: 下添加至少一个条目 |
| .env 引用了未解析的 $OPENAI_API_KEY | 环境变量未设置 | 在项目根目录的 .env 文件中填入真实值 |
| 2026 端口已被占用 | 之前的 DeerFlow 实例仍在运行 | 运行 make stop（本地）或 make docker-stop（Docker） |
| 修改配置后前端未加载 | 浏览器缓存了旧版本构建 | 强制刷新（Ctrl+Shift+R）或使用 make dev 重启 |

## 单行 Agent 设置（面向编程 Agent）

## 后续步骤

-
-
-
-
-
