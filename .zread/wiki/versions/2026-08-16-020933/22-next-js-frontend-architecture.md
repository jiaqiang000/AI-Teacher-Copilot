# Next.js 前端架构

## 技术栈与构建配置

| 关注点 | 技术 | 作用 |
|---|---|---|
| 框架 | Next.js 16 (App Router, Turbopack) | 路由、SSR、API 重写 |
| 运行时 | React 19 | UI 渲染 |
| Agent 流式传输 | @langchain/langgraph-sdk | 基于 SSE 的运行流式传输、线程状态 |
| 数据获取 | @tanstack/react-query | REST 缓存、变更、无限滚动查询 |
| 设计系统 | Radix UI 原语 + Tailwind CSS v4 + class-variance-authority | 无障碍、可主题化组件 |
| Markdown 渲染 | streamdown + rehype-katex + remark-gfm | 富 AI 消息渲染 |
| 流程可视化 | @xyflow/react | Agent 图 / 思维链 |
| 代码编辑 | CodeMirror 6 + @uiw/react-codemirror | Artifact 编辑、多语言支持 |
| 环境变量校验 | @t3-oss/env-nextjs + zod | 类型安全的环境变量 |
| 测试 | Rstest (单元) + Playwright (E2E) | 测试金字塔覆盖率 |

## App Router 拓扑与路由段

| result.tag | 动作 | 渲染的组件 |
|---|---|---|
| authenticated | 继续 | AuthProvider → WorkspaceContent |
| needs_setup | 重定向至 /setup | — |
| system_setup_required | 重定向至 /setup | — |
| unauthenticated | 重定向至 /login | — |
| gateway_unavailable | 渲染降级 UI | GatewayOfflineFallback → WorkspaceContent |
| config_error | 抛出错误 | — |

## Provider 层次结构与状态管理

## API 客户端架构与流式处理管道

### 感知 CSRF 的请求获取

### LangGraph SDK 客户端包装

| 被打补丁的方法 | 解决的问题 | 机制 |
|---|---|---|
| runs.stream | SSE 缓存被清除导致的流重放间隙 | recoverStreamReplayGaps 异步生成器：拦截 gap 事件，通过 threads.getState 重新加载持久化检查点状态，然后从 latest_available_event_id 恢复（最多重试 5 次） |
| runs.joinStream | 重连到已终止的运行会导致永久阻塞 | shouldSkipReconnect 预检：获取运行状态，若为 success/error/timeout/interrupted 则短路返回 |
| runs.cancel | 停止已完成的运行会抛出 409 错误 | isRunNotCancellableError 匹配器：吞掉终端状态的 409 冲突，清除过期的重连密钥 |
| runs.stream (非活跃) | 运行存在于存储中但未在此 Worker 上激活 | handleInactiveRunStream：捕获“未在此 Worker 上激活”的 409 错误，静默返回空流 |

### useThreadStream Hook

## 身份验证流程

## 国际化架构

## 静态模式与静态网站生成

## 核心领域模块

| 模块 | 职责 | 核心模式 |
|---|---|---|
| core/threads/ | 线程 CRUD、流式传输、搜索、Token 使用量 | useThreadStream 包装 LangGraph SDK 的 useStream |
| core/tasks/ | 子任务生命周期、步骤解析、展示 | 使用 Context + ref 模式实现异步安全状态 |
| core/agents/ | Agent 配置、特性缓存 | 带有特性缓存层的 TanStack Query |
| core/skills/ | 技能目录、斜杠命令解析 | slash.ts 用于解析 /skill 输入 |
| core/memory/ | 长期记忆管理 | 位于 app/api/memory/[...path] 的 API 路由处理器 |
| core/scheduled-tasks/ | 基于 Cron 的任务调度 | 预设方案 + Cron 表达式构建器 |
| core/channels/ | IM 渠道连接 | 基于轮询的连接状态检查 |
| core/uploads/ | 文件上传校验与处理 | 文件类型校验 + 提示词附件 |
| core/sidecar/ | 参考面板上下文 | 由线程元数据驱动的 Sidecar 状态 |
| core/streamdown/ | Markdown 渲染管道 | 自定义插件 + Mermaid 集成 |

## 组件架构

## 环境配置

| 变量 | 作用域 | 用途 |
|---|---|---|
| NEXT_PUBLIC_BACKEND_BASE_URL | 客户端 | 直接的后端 URL（绕过重写代理） |
| NEXT_PUBLIC_LANGGRAPH_BASE_URL | 客户端 | 直接的 LangGraph API URL（绕过重写代理） |
| NEXT_PUBLIC_STATIC_WEBSITE_ONLY | 客户端 | 启用静态演示模式 |
| GITHUB_OAUTH_TOKEN | 服务端 | 用于博客内容的 GitHub OAuth |
| NODE_ENV | 服务端 | 运行环境 |

## 后续步骤

- —— 重写代理目标的后端网关，包括 CSRF 中间件和认证端点
- —— `useThreadStream` 消费的服务端 SSE 基础设施，包括流重放间隙机制
- —— 展示前端、网关和 Agent 运行时如何连接的全栈架构图
- —— BrowserView 和代码编辑器组件与之交互的沙箱执行环境
