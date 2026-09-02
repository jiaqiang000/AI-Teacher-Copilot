# 概述

## DeerFlow 的功能



## 架构概览



## 仓库结构

```
deer-flow/
├── backend/                          │   ├── app/                          # Gateway app, channels, scheduler
│   │   ├── gateway/                  # HTTP API routers, auth, middleware
│   │   ├── channels/                 # IM channel adapters (7 platforms)
│   │   ├── scheduler/                # Scheduled task service
│   │   └── mcp_tasks/               # Durable MCP task service
│   ├── packages/
│   │   ├── harness/deerflow/         # ★ Core agent runtime (the harness)
│   │   │   ├── agents/               # Lead agent, sub-agents, middlewares
│   │   │   ├── tools/                # Built-in tools + MCP bridge
│   │   │   ├── skills/               # Skill catalog, parser, installer
│   │   │   ├── sandbox/              # Sandbox providers & security
│   │   │   ├── models/               # Model provider integrations
│   │   │   ├── runtime/              # Checkpointing, streams, goals
│   │   │   ├── persistence/          # Database models & migrations
│   │   │   ├── memory/               # Long-term memory backends
│   │   │   ├── guardrails/           # Safety middleware
│   │   │   ├── extensions/           # Plugin/middleware loading
│   │   │   ├── community/            # Search & sandbox providers
│   │   │   ├── tui/                  # Terminal UI (Textual)
│   │   │   └── client.py             # ★ Embedded Python client
│   │   └── extension-api/            # Plugin contract package
│   ├── langgraph.json                # LangGraph Server config
│   └── pyproject.toml
├── frontend/                         # Next.js frontend
│   ├── src/
│   │   ├── app/                      # Routes: workspace, auth, blog
│   │   ├── components/               # UI: workspace, ai-elements, landing
│   │   └── core/                     # State: agents, skills, memory, tools
│   └── package.json
├── skills/public/                    # 20+ built-in skills (SKILL.md)
├── docker/                           # Docker Compose & container configs
├── deploy/helm/                      # Helm charts for Kubernetes
├── scripts/                          # Setup wizard, doctor, deployment
├── config.example.yaml               # Full configuration reference (2560 lines)
├── Makefile                          # Unified dev commands
└── contracts/                        # API contracts & schemas
```



## 核心能力

| 能力 | 描述 | 配置位置 | 关键文件 |
|---|---|---|---|
| 技能系统 | 渐进式加载结构化能力模块（基于 Markdown 定义的工作流）。内置 20+ 技能。支持通过 /skill-name 激活自定义技能。 | extensions_config.json + config.yaml → skills | skills/public/ |
| Sub-Agents | 主 Agent 可委派任务给拥有独立上下文、工具和终止条件的隔离子 Agent。支持在有益时并行执行。 | config.yaml → subagents | subagents/ |
| 沙盒与文件系统 | 提供具备完整文件系统的按任务隔离执行环境。支持 Local、Docker、E2B 和 Kubernetes 配置模式。 | config.yaml → sandbox | sandbox/ |
| 长期记忆 | 跨会话持久化用户画像、偏好和知识。支持 DeerMem（默认）、mem0 或 OpenViking 后端。 | config.yaml → memory | agents/memory/ |
| 上下文工程 | 激进的内容摘要、上下文压缩（/compact）、子 Agent 上下文隔离、严格的工具调用恢复机制。 | config.yaml → summarization | runtime/context_compaction.py |
| IM 渠道集成 | 从 7 个消息平台接收任务，支持自动启动，无需公网 IP。 | config.yaml → channels | app/channels/ |

### 内置技能目录

| 技能 | 用途 |
|---|---|
| deep-research | 结合网络搜索与合成的多步骤研究 |
| data-analysis | 使用 Python 脚本进行 CSV/数据分析 |
| chart-visualization | 生成图表与可视化 |
| ppt-generation | 创建 PowerPoint 演示文稿 |
| image-generation | AI 图像生成工作流 |
| video-generation | AI 视频生成工作流 |
| music-generation | AI 音乐创作 |
| podcast-generation | 生成播客音频内容 |
| newsletter-generation | 基于研究内容创建时事通讯 |
| frontend-design | 构建前端 UI 组件 |
| web-design-guidelines | 网页设计最佳实践 |
| code-documentation | 生成代码文档 |
| academic-paper-review | 审阅学术论文 |
| consulting-analysis | 商业咨询分析 |
| systematic-literature-review | 系统性学术文献综述 |
| github-deep-research | 针对 GitHub 仓库的深度研究 |
| vercel-deploy-claimable | 部署至 Vercel 并生成可认领的 URL |
| skill-creator | 编写新的自定义技能 |
| skill-reviewer | 审查技能质量（只读） |
| claude-to-deerflow | 从 Claude Code 与 DeerFlow 交互 |
| bootstrap | 项目初始化模板 |
| find-skills | 发现并搜索可用技能 |
| surprise-me | 创意惊喜任务 |



## 技术栈

| 层级 | 技术 | 详情 |
|---|---|---|
| Agent 运行时 | Python 3.12+ · LangGraph · LangChain | LangGraph 用于有状态图执行；LangChain 用于模型抽象 |
| 后端 API | FastAPI · Uvicorn | 具备身份验证、CORS、CSRF 及运行生命周期管理的网关 |
| 前端 | Next.js · React · TypeScript · pnpm | 具备实时流式传输的工作区 UI |
| 数据库 | SQLite（默认） · PostgreSQL（生产环境） | 供检查点存储、LangGraph Store 和应用数据共享使用 |
| 沙盒 | Docker · E2B · Local · Kubernetes | 按任务隔离执行 |
| 包管理器 | uv（后端） · pnpm（前端） | 快速依赖解析 |
| 反向代理 | Nginx | 运行在 2026 端口的同源统一端点 |
| 可观测性 | LangSmith · Langfuse · Monocle | 可插拔的链路追踪后端 |
| 终端 UI | Textual | 基于 DeerFlowClient 的内嵌 TUI |



## 部署模式

|  | 本地前台运行 | 本地守护进程 | Docker 开发环境 | Docker 生产环境 |
|---|---|---|---|---|
| 开发环境 | make dev | make dev-daemon | make docker-start | — |
| 生产环境 | make start | make start-daemon | — | make up |
| 热重载 | ✅ | ✅ | ✅ | ❌ |
| 沙盒隔离 | 宿主机（受限） | 宿主机（受限） | Docker 容器 | Docker 容器 |



## 配置理念



## 进阶指南

- **动手实践** →  — 在 10 分钟内克隆、配置并运行 DeerFlow
- **配置环境** →  — 深入了解 `config.yaml`、模型提供商和设置向导
- **理解架构** →  — 详细的系统设计与组件交互
- **探索 Agent 编排** →  →  →
- **基于技能构建** →  →  →
- **部署至生产环境** →  →
