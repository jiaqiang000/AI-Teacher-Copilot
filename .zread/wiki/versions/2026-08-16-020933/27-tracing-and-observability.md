# 链路追踪与可观测性

## 架构概述

## 请求链路关联

### Trace ID 生命周期

- **提取**传入的 `X-Trace-Id` 标头，并通过 `normalize_trace_id()` 进行规范化。该函数强制要求可打印 ASCII 字符（0x20–0x7E）且长度上限为 512 字符 —— 此限制源于 Starlette 的 latin-1 标头编码以及中间代理对 C1 控制字符的剥离行为。
- **绑定**通过 `request_trace_context()` 将 trace ID 绑定至当前异步上下文，该操作会设置一个 `ContextVar` token，且该 token 始终在 `finally` 块中被恢复。
- **回传**通过 `send_with_trace` 包装器，将 trace ID 写入 HTTP 响应的 `X-Trace-Id` 标头返回，以便调用方将其响应与自身日志进行关联。

### Trace ID 解析优先级

| 优先级 | 来源 | 条件 |
|---|---|---|
| 1 | 入站 X-Trace-Id 标头 | is_trace_id_from_request_header() 返回 True |
| 2 | 调用方提供的 metadata.deerflow_trace_id | normalize_trace_id() 接受该值 |
| 3 | 当前请求的追踪上下文 | get_current_trace_id() 返回非 None 值 |

### 增强日志配置

- **`TraceTextFormatter`** —— 生成格式如 `2025-01-15 10:30:00 - deerflow.agents - INFO - [trace_id=abc123] - message` 的日志行
- **`JsonTraceFormatter`** —— 输出结构化 JSON，包含 `timestamp`、`logger`、`level`、`trace_id` 和 `message` 字段，以及可选的 `exc_info` 与 `stack_info`

## 单次运行追踪提供者

### 提供者配置模型

| 提供者 | 启用环境变量 | 所需凭证 | 默认端点 |
|---|---|---|---|
| LangSmith | LANGSMITH_TRACING 或 LANGCHAIN_TRACING_V2 | LANGSMITH_API_KEY 或 LANGCHAIN_API_KEY | https://api.smith.langchain.com |
| Langfuse | LANGFUSE_TRACING | LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY | https://cloud.langfuse.com |
| Monocle | MONOCLE_TRACING | 依赖导出器（例如 OKAHU_API_KEY） | 本地文件 |

### 回调构建与注入

### Langfuse 元数据增强

| 元数据键 | Langfuse 效果 | DeerFlow 来源 |
|---|---|---|
| langfuse_session_id | 将追踪分组为会话 | LangGraph thread_id |
| langfuse_user_id | 填充至 Users 页面 | 有效用户 ID（在无鉴权模式下回退至 DEFAULT_USER_ID） |
| langfuse_trace_name | 易读的追踪名称 | Agent/助手 ID（默认为 "lead-agent"） |
| langfuse_tags | 用于过滤的追踪标签 | env:<environment>, model:<model_name> |
| deerflow_trace_id | 自定义关联属性 | 解析后的 trace ID（标头 > 元数据 > 上下文） |

## Monocle OTel 插桩

### 生命周期与初始化

- 通过 `monocle.validate()` **验证** Monocle 配置，检查未知的导出器名称及缺失的凭证（例如，选择了 `okahu` 导出器时缺少 `OKAHU_API_KEY`）。验证在此处进行 —— 而非单次运行的回调路径中 —— 确保配置拼写错误不会中断 Agent 运行。
- 当激活了离机导出器时**记录警告**，因为追踪数据（提示词、补全结果）将离开本地机器。当 Langfuse 同时被启用时，警告会提示 Langfuse 的 span 也会通过 Monocle 的导出器导出，因为两者共享全局 OTel `TracerProvider`。
- **延迟导入** `monocle_apptrace`，若未安装 `monocle` 扩展依赖，则抛出附带安装说明的明确 `RuntimeError`。
- **调用** `setup_monocle_telemetry(workflow_name="deer-flow", monocle_exporters_list=exporters)`，该函数根据上游库的约定具有幂等性。

### Monocle 导出器选项

| 导出器 | 目的地 | 需要凭证 | 数据离开本机 |
|---|---|---|---|
| file | 本地 .monocle/ 目录 | 否 | 否 |
| console | stdout | 否 | 否 |
| okahu | Okahu 云端 | OKAHU_API_KEY | 是 |
| s3 | AWS S3 存储桶 | AWS 凭证 | 是 |
| blob | Azure Blob Storage | Azure 凭证 | 是 |
| gcs | Google Cloud Storage | GCP 凭证 | 是 |

## Run Worker 中的追踪

## Gateway 中间件集成

## 诊断工具

### 健康检查：`make doctor`

| 检查项 | 验证内容 | 失败修复建议 |
|---|---|---|
| Python | 版本 ≥ 3.12 | 从 python.org 安装 |
| Node.js | 版本 ≥ 22 | 从 nodejs.org 安装 |
| pnpm | 可通过 scripts/pnpm.py 解析 | 安装 pnpm 或 Corepack |
| uv | 已安装且在 PATH 中 | curl -LsSf https://astral.sh/uv/install.sh \| sh |
| nginx | 已安装（适用于 Docker/代理模式） | 根据特定平台进行安装 |
| config.yaml | 存在于项目根目录 | make setup |
| config.yaml 版本 | 与 config.example.yaml 匹配 | make config-upgrade |
| config.yaml 可加载 | AppConfig.from_file() 成功执行 | make setup 或与示例文件对比 |
| 模型已配置 | 至少存在一个模型条目 | make setup |
| LLM API 密钥 | 每个 $ENV_VAR 引用均已设置 | 添加至 .env |
| LLM 包 | 每个 use: 包均可导入 | cd backend && uv add <package> |

### 支持包：`make support-bundle`

| 文件 | 内容 | 敏感信息处理 |
|---|---|---|
| README.md | 易读的入口说明 | N/A |
| issue-summary.md | 用于粘贴至 GitHub issue 的 Markdown | 已脱敏 |
| ai-issue-draft.md | 带占位符的 AI 辅助 issue 草稿 | 已脱敏 |
| triage.json | 机器可读的故障分类摘要 | 已脱敏 |
| manifest.json | 打包文件结构、时间戳、隐私声明 | N/A |
| environment.json | 操作系统、Python、工具链版本 | 主目录路径已脱敏 |
| config-summary.json | 脱敏后的 config.yaml 结构 | 深度脱敏 |
| extensions-summary.json | 脱敏后的 extensions_config.json | 深度脱敏 |
| git.json | 分支、提交、状态、diff-stat | 主目录路径已脱敏 |
| doctor.json | 脱敏后的 make doctor 输出 | 已脱敏 |
| thread-summary.json | 线程文件清单（仅元数据） | 无文件内容 |

## 配置参考

### 环境变量

| 变量 | 提供者 | 用途 | 适用条件 |
|---|---|---|---|
| LANGSMITH_TRACING / LANGCHAIN_TRACING_V2 / LANGCHAIN_TRACING | LangSmith | 启用标志 | — |
| LANGSMITH_API_KEY / LANGCHAIN_API_KEY | LangSmith | 身份验证 | enabled=true |
| LANGSMITH_PROJECT / LANGCHAIN_PROJECT | LangSmith | 项目名称（默认：deer-flow） | — |
| LANGSMITH_ENDPOINT / LANGCHAIN_ENDPOINT | LangSmith | API 端点 | — |
| LANGFUSE_TRACING | Langfuse | 启用标志 | — |
| LANGFUSE_PUBLIC_KEY | Langfuse | 公钥 | enabled=true |
| LANGFUSE_SECRET_KEY | Langfuse | 密钥 | enabled=true |
| LANGFUSE_BASE_URL | Langfuse | 自托管端点（默认：cloud.langfuse.com） | — |
| MONOCLE_TRACING | Monocle | 启用标志 | — |
| MONOCLE_EXPORTERS | Monocle | 逗号分隔的导出器列表（默认：file） | — |
| OKAHU_API_KEY | Monocle | Okahu 云端鉴权 | 导出器中包含 okahu |
| DEER_FLOW_ENV / ENVIRONMENT | 全部 | 用于 langfuse_tags 的环境标签 | — |

### config.yaml 设置

## 运维场景

### 启用全链路可观测性

-
-
-

### TUI 与嵌入式使用

### 诊断生产环境问题

- 运行 `make doctor` 验证环境、配置及提供者连通性。
- 若问题可复现，运行 `make support-bundle` 生成已脱敏的证据 ZIP 包。
- 将生成的 `issue-summary.md` 粘贴至 GitHub issue 中；仅在维护者要求时才附上 ZIP 包。
- 若已启用链路关联，请附上失败请求的 `X-Trace-Id` 标头值 —— 这使维护者能够利用 `deerflow_trace_id` 属性将 Gateway 日志与 Langfuse 追踪关联起来。

## 相关页面

- —— 运行事件如何从 worker 流向客户端，以及追踪回调在执行生命周期中的附着点
- —— 与追踪 Agent 执行并行的持久化层
- —— `TraceMiddleware` 在中间件栈中相对于鉴权与 CSRF 的位置
- —— token 使用情况的可观测性如何反馈至上下文窗口管理
