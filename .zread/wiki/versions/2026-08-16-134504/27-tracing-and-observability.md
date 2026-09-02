---
slug:27-tracing-and-observability
blog_type:normal
---


DeerFlow 的可观测性栈围绕三个正交层构建：**请求链路关联**（通过单一关联 ID 将日志、HTTP 标头与外部追踪平台串联起来）；**单次运行追踪回调**（将 LangChain 执行事件接入 LangSmith 或 Langfuse）；以及**进程级 OTel 插桩**（通过 Monocle 进行深度 Agent 内省）。面向运维人员的诊断层 —— 包含 `make doctor` 健康检查与 `make support-bundle` 证据收集工具 —— 则完善了整个体系，在确保不泄露敏感信息的前提下，提供可操作的故障排查产物。本页涵盖了这四个子系统的架构、配置及运维使用说明。

## 架构概述

可观测性系统采用分层设计，每一层针对不同粒度的可见性需求 —— 从单次 HTTP 请求关联，细化至单次 LLM token 插桩。

```mermaid
graph TB
    subgraph "Gateway Entry"
        REQ["HTTP Request<br/>(optional X-Trace-Id header)"]
        TM["TraceMiddleware<br/>Binds trace_id to ContextVar"]
    end

    subgraph "Trace Context Layer"
        TC["trace_context.py<br/>ContextVar-based correlation"]
        TCF["TraceContextFilter<br/>Injects trace_id into LogRecords"]
        TFF["TraceTextFormatter /<br/>JsonTraceFormatter"]
    end

    subgraph "Per-Run Tracing Callbacks"
        TF["tracing/factory.py<br/>build_tracing_callbacks()"]
        LS["LangSmithTracer"]
        LF["LangfuseCallbackHandler"]
        TM2["tracing/metadata.py<br/>inject_langfuse_metadata()"]
    end

    subgraph "Process-Global OTel"
        MONO["tracing/monocle.py<br/>setup_monocle_tracing_if_enabled()"]
        OTel["Global TracerProvider<br/>(shared span processors)"]
    end

    subgraph "Diagnostics"
        DOC["make doctor<br/>Health check"]
        SB["make support-bundle<br/>Redacted evidence zip"]
    end

    REQ --> TM
    TM --> TC
    TC --> TCF
    TCF --> TFF
    TC -->|deerflow_trace_id metadata| TM2
    TF --> LS
    TF --> LF
    TM2 --> LF
    MONO --> OTel
    LF -->|coexists on| OTel

    DOC -.->|runs at startup| SB
```

关键的设计决策在于将**链路关联**（DeerFlow 内部概念，始终可用，由 `logging.enhance.enabled` 控制）与**追踪提供者**（外部平台，由环境变量控制）解耦。链路关联确保每条日志、每个 HTTP 响应及 Langfuse 追踪都携带一致的 `deerflow_trace_id`，使你能够跨子系统追踪单一请求。追踪提供者则消费该关联 ID，并在各自的后端额外捕获执行级别的细节 —— 如 LLM 输入/输出、工具调用及链式嵌套。

来源：[trace_middleware.py](backend/app/gateway/trace_middleware.py#L1-L75), [trace_context.py](backend/packages/harness/deerflow/trace_context.py#L1-L120), [logging_config.py](backend/packages/harness/deerflow/logging_config.py#L1-L110)

## 请求链路关联

### Trace ID 生命周期

链路关联系统通过三种载体传播请求范围的标识符：**HTTP 响应标头**、**日志记录**和 **Langfuse 追踪元数据**。该标识符由 `trace_context.py` 使用 Python `ContextVar` 实例进行管理，确保在异步任务间正确传递，避免线程局部变量的泄漏。

当 `logging.enhance.enabled` 为 `true` 时，位于 Gateway ASGI 中间件栈中的 `TraceMiddleware` 会对每个 HTTP 请求执行三步绑定操作：

1. **提取**传入的 `X-Trace-Id` 标头，并通过 `normalize_trace_id()` 进行规范化。该函数强制要求可打印 ASCII 字符（0x20–0x7E）且长度上限为 512 字符 —— 此限制源于 Starlette 的 latin-1 标头编码以及中间代理对 C1 控制字符的剥离行为。
2. **绑定**通过 `request_trace_context()` 将 trace ID 绑定至当前异步上下文，该操作会设置一个 `ContextVar` token，且该 token 始终在 `finally` 块中被恢复。
3. **回传**通过 `send_with_trace` 包装器，将 trace ID 写入 HTTP 响应的 `X-Trace-Id` 标头返回，以便调用方将其响应与自身日志进行关联。

若不存在入站标头，`generate_trace_id()` 将生成一个新的 UUID4 十六进制字符串。`mark_trace_id_from_request_header()` 标志至关重要：它记录 trace ID 是否源自合法的入站标头，这决定了 `resolve_deerflow_trace_id()` 函数中的优先级 —— 由标头提供的 trace ID 优先级高于 `config.metadata.deerflow_trace_id`，以确保日志、响应标头和 Langfuse 追踪保持一致。

来源：[trace_middleware.py](backend/app/gateway/trace_middleware.py#L30-L75), [trace_context.py](backend/packages/harness/deerflow/trace_context.py#L70-L120)

### Trace ID 解析优先级

`resolve_deerflow_trace_id()` 函数实现了一种三级优先级机制，用于确定附加到运行操作的有效 `deerflow_trace_id`：

| 优先级 | 来源 | 条件 |
|----------|--------|-----------|
| 1 | 入站 `X-Trace-Id` 标头 | `is_trace_id_from_request_header()` 返回 `True` |
| 2 | 调用方提供的 `metadata.deerflow_trace_id` | `normalize_trace_id()` 接受该值 |
| 3 | 当前请求的追踪上下文 | `get_current_trace_id()` 返回非 `None` 值 |

此解析过程在 Agent 执行开始前于 run worker 中执行，以确保 Langfuse 的 `deerflow_trace_id` 元数据键（一个自定义属性，并非 Langfuse 原生字段）所携带的值，与该请求在 Gateway 日志和 HTTP 标头中可见的值保持一致。

来源：[trace_context.py](backend/packages/harness/deerflow/trace_context.py#L82-L96), [worker.py](backend/packages/harness/deerflow/runtime/runs/worker.py#L59-L66)

### 增强日志配置

日志增强子系统由 `config.yaml` 中的 `logging.enhance` 块控制：

```yaml
logging:
  enhance:
    enabled: false    # Set true to enable trace correlation
    format: text      # "text" or "json"
```

启用后，`configure_logging()` 会在每个根 handler 上安装 `TraceContextFilter`。此过滤器针对每条 `LogRecord` 调用 `get_current_trace_id()`，并将 `record.trace_id` 设置为已绑定的 trace ID 或字面量 `"-"` 哨兵值。有两种格式化器消费该字段：

- **`TraceTextFormatter`** —— 生成格式如 `2025-01-15 10:30:00 - deerflow.agents - INFO - [trace_id=abc123] - message` 的日志行
- **`JsonTraceFormatter`** —— 输出结构化 JSON，包含 `timestamp`、`logger`、`level`、`trace_id` 和 `message` 字段，以及可选的 `exc_info` 与 `stack_info`

<CgxTip>`logging.enhance.enabled` 标志在 `reload_boundary.py` 中被注册为**需重启生效**字段。这意味着在 `config.yaml` 中修改该项后，必须重启 Gateway 才能生效 —— `TraceMiddleware` 会在应用构建时快照该标志的状态，且 `configure_logging()` 仅在生命周期启动阶段安装过滤器/格式化器。这种设计可防止运行时开关导致日志格式化器与中间件写标头的行为产生不同步。</CgxTip>

`apply_logging_level()` 函数仅将 `config.yaml` 中的 `log_level` 应用于 `deerflow` 和 `app` 日志器层级，而不影响第三方库（如 uvicorn、sqlalchemy 等）的日志详细程度。根 handler 的日志级别只会被调低，绝不会被调高，从而确保已配置日志器的消息能够正常传播而不被过滤。

来源：[logging_config.py](backend/packages/harness/deerflow/logging_config.py#L25-L110), [app_config.py](backend/packages/harness/deerflow/config/app_config.py#L140-L175), [config.example.yaml](config.example.yaml#L24-L31)

## 单次运行追踪提供者

### 提供者配置模型

DeerFlow 支持两种基于回调的追踪提供者 —— **LangSmith** 和 **Langfuse** —— 它们完全通过环境变量而非 `config.yaml` 键进行配置。此设计契合 LangChain 自身的追踪规范，并确保敏感凭证不出现在已提交的配置文件中。

| 提供者 | 启用环境变量 | 所需凭证 | 默认端点 |
|----------|---------------|---------------------|-----------------|
| LangSmith | `LANGSMITH_TRACING` 或 `LANGCHAIN_TRACING_V2` | `LANGSMITH_API_KEY` 或 `LANGCHAIN_API_KEY` | `https://api.smith.langchain.com` |
| Langfuse | `LANGFUSE_TRACING` | `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` | `https://cloud.langfuse.com` |
| Monocle | `MONOCLE_TRACING` | 依赖导出器（例如 `OKAHU_API_KEY`） | 本地文件 |

`TracingConfig` 模型区分了 `explicitly_enabled_providers`（已设置 `enabled` 标志的提供者，无论是否提供凭证）和 `enabled_providers`（已启用**且**已配置完整凭证的提供者）。`build_tracing_callbacks()` 工厂使用 `enabled_providers` —— 意味着如果某提供者设置了 `enabled=true` 但缺失凭证，它将被静默排除在回调之外，而不会引发运行时错误。然而，系统会先调用 `validate_enabled_tracing_providers()`，若任何显式启用的提供者缺少必要凭证，该函数将抛出 `ValueError`，从而将静默跳过转变为 Agent 运行时的快速失败机制。

来源：[tracing_config.py](backend/packages/harness/deerflow/config/tracing_config.py#L1-L213), [factory.py](backend/packages/harness/deerflow/tracing/factory.py#L30-L66)

### 回调构建与注入

`tracing/factory.py` 中的 `build_tracing_callbacks()` 函数为每个启用的提供者构建 LangChain 回调 handler 实例。对于 LangSmith，它会使用配置的项目名称创建 `LangChainTracer`。对于 Langfuse v4，它首先使用密钥/公钥对及主机初始化 `Langfuse` 客户端单例，随后将其封装进附加该客户端配置的 `LangfuseCallbackHandler` 中。

这些回调通过 `callbacks` 键注入到 Agent 的 `RunnableConfig` 中。LangChain 执行引擎在执行的每个链步骤（LLM 调用、工具执行及子链调用）都会触发它们。注入点位于 run worker（`runtime/runs/worker.py`）用于 Gateway 提供的运行，而嵌入式使用场景则位于 `DeerFlowClient`。

### Langfuse 元数据增强

`inject_langfuse_metadata()` 函数会在 Agent 执行前，将 Langfuse 特有的追踪属性合并到 `RunnableConfig.metadata` 字典中。当 Langfuse 未在启用的提供者中时，此操作为空操作，因此调用方可以无条件调用它。元数据键映射至 Langfuse 的保留属性名：

| 元数据键 | Langfuse 效果 | DeerFlow 来源 |
|-------------|----------------|----------------|
| `langfuse_session_id` | 将追踪分组为会话 | LangGraph `thread_id` |
| `langfuse_user_id` | 填充至 Users 页面 | 有效用户 ID（在无鉴权模式下回退至 `DEFAULT_USER_ID`） |
| `langfuse_trace_name` | 易读的追踪名称 | Agent/助手 ID（默认为 `"lead-agent"`） |
| `langfuse_tags` | 用于过滤的追踪标签 | `env:<environment>`, `model:<model_name>` |
| `deerflow_trace_id` | 自定义关联属性 | 解析后的 trace ID（标头 > 元数据 > 上下文） |

该函数在合并时使用 `setdefault()`，因此调用方提供的元数据始终具有最高优先级 —— 例如，由前端设置的 `langfuse_session_id` 上游值将保持不变。Gateway run worker 和嵌入式 `DeerFlowClient` 均通过此共享函数进行处理，以防止两种执行路径间产生行为差异。

来源：[metadata.py](backend/packages/harness/deerflow/tracing/metadata.py#L37-L115), [factory.py](backend/packages/harness/deerflow/tracing/factory.py#L1-L66)

## Monocle OTel 插桩

Monocle 提供了一种与基于回调的提供者截然不同的可观测性模式。它不使用单次运行的 LangChain 回调，而是通过 OpenTelemetry 在全局进程级别进行插桩 —— 在 OTel span 级别捕获提示词、工具输入/输出及补全结果。因此，它与 LangSmith/Langfuse 是互补关系，而非竞争关系。

### 生命周期与初始化

Monocle 的设置特意**不**在导入时执行。相反，`setup_monocle_tracing_if_enabled()` 会在 Gateway 生命周期启动阶段、配置加载之后且 LangGraph 运行时初始化之前被调用。这确保了单纯的 `import deerflow.agents` 不会安装进程全局 tracer，避免在测试和脚本环境中造成意外影响。

初始化序列遵循故障安全理念：

1. 通过 `monocle.validate()` **验证** Monocle 配置，检查未知的导出器名称及缺失的凭证（例如，选择了 `okahu` 导出器时缺少 `OKAHU_API_KEY`）。验证在此处进行 —— 而非单次运行的回调路径中 —— 确保配置拼写错误不会中断 Agent 运行。
2. 当激活了离机导出器时**记录警告**，因为追踪数据（提示词、补全结果）将离开本地机器。当 Langfuse 同时被启用时，警告会提示 Langfuse 的 span 也会通过 Monocle 的导出器导出，因为两者共享全局 OTel `TracerProvider`。
3. **延迟导入** `monocle_apptrace`，若未安装 `monocle` 扩展依赖，则抛出附带安装说明的明确 `RuntimeError`。
4. **调用** `setup_monocle_telemetry(workflow_name="deer-flow", monocle_exporters_list=exporters)`，该函数根据上游库的约定具有幂等性。

`_setup_completed` 标志用于跟踪当前进程中是否已执行设置。当 `build_tracing_callbacks()` 检测到 Monocle 已启用但 `_setup_completed` 为 `False` 时，它会记录一条调试信息，引导嵌入式/TUI 调用方自行调用 `setup_monocle_tracing_if_enabled()` —— Gateway 生命周期是唯一的自动设置路径。

<CgxTip>Monocle 与 Langfuse（v4，同样基于 OTel）可以安全共存：后初始化的库会复用现有的全局 `TracerProvider` 并附加自身的 span processor。两个 processor 均可见所有的 span，因此在两者同时启用时，Monocle 的导出器也会捕获 Langfuse 的 span。这意味着在 Langfuse 处于活动状态时，启用带有离机导出器的 Monocle 将导致 Langfuse 的 span 数据也通过 Monocle 的导出器传输出去 —— 请核实这是否符合你的数据治理策略。</CgxTip>

### Monocle 导出器选项

| 导出器 | 目的地 | 需要凭证 | 数据离开本机 |
|----------|------------|---------------------|-----------------|
| `file` | 本地 `.monocle/` 目录 | 否 | 否 |
| `console` | stdout | 否 | 否 |
| `okahu` | Okahu 云端 | `OKAHU_API_KEY` | 是 |
| `s3` | AWS S3 存储桶 | AWS 凭证 | 是 |
| `blob` | Azure Blob Storage | Azure 凭证 | 是 |
| `gcs` | Google Cloud Storage | GCP 凭证 | 是 |

默认导出器字符串为 `"file"`，意味着当设置 `MONOCLE_TRACING=true` 且未配置 `MONOCLE_EXPORTERS` 时，Monocle 仅将追踪数据写入本地文件系统。

来源：[monocle.py](backend/packages/harness/deerflow/tracing/monocle.py#L1-L70), [tracing_config.py](backend/packages/harness/deerflow/config/tracing_config.py#L76-L110), [app.py](backend/app/gateway/app.py#L225-L238)

## Run Worker 中的追踪

Run worker（`runtime/runs/worker.py`）是 Gateway 侧的执行路径。在 Agent 图运行前，追踪回调与 Langfuse 元数据会在此组装完毕。该 worker 从 `trace_context` 导入 `resolve_deerflow_trace_id` 和 `DEERFLOW_TRACE_METADATA_KEY`，并从追踪包导入 `inject_langfuse_metadata`。

worker 的追踪组装遵循以下流程：

```mermaid
flowchart LR
    A["Run request received"] --> B["Resolve deerflow_trace_id<br/>(header > metadata > context)"]
    B --> C["inject_langfuse_metadata()<br/>into RunnableConfig.metadata"]
    C --> D["build_tracing_callbacks()<br/>→ [LangSmithTracer, LangfuseHandler]"]
    D --> E["Set config.callbacks"]
    E --> F["graph.astream() with<br/>traced config"]
```

worker 中的 `is_trace_id_from_request_header()` 检查确保当 Gateway 的 `TraceMiddleware` 绑定了合法的入站 `X-Trace-Id` 时，该值的优先级高于任何调用方提供的元数据。这种对齐保证意味着，带有 `[trace_id=abc123]` 标记的日志行，与 Langfuse 追踪元数据中可见的 `deerflow_trace_id` 以及返回给 HTTP 客户端的 `X-Trace-Id` 响应标头中的值完全一致。

对于嵌入式 `DeerFlowClient` 路径，同样会调用 `inject_langfuse_metadata()` 和 `build_tracing_callbacks()` 函数，但额外传入一个 `environment` 参数，该参数会汇入 `langfuse_tags`（例如 `env:production`）。由于没有 HTTP 中间件自动执行绑定，客户端通过 `set_current_trace_id()` / `reset_current_trace_id()` token 对自行管理其追踪上下文。

来源：[worker.py](backend/packages/harness/deerflow/runtime/runs/worker.py#L59-L66), [client.py](backend/packages/harness/deerflow/client.py#L42-L48), [client.py](backend/packages/harness/deerflow/client.py#L130-L175)

## Gateway 中间件集成

`TraceMiddleware` 通过 `app.add_middleware(TraceMiddleware, enabled=...)` 注册于 `create_app()` 中。`enabled` 标志在应用构建时通过 `_resolve_trace_enabled_for_app_construction()` 解析，后者调用 `resolve_trace_enabled(get_app_config())` —— 这本质上是对 `is_trace_correlation_enabled()` 的轻量级别名。该函数通过 `getattr` 遍历 `config.logging.enhance.enabled` 属性链，若任何中间属性缺失，则优雅降级为 `False`（在使用 `SimpleNamespace` 的测试夹具中非常有用）。

中间件的 `__init__` 将 `enabled` 标志存储为启动快照，而非按请求实时读取。这是刻意为之的：`logging` 在 `STARTUP_ONLY_FIELDS` 中被注册为需重启生效字段，因为 `configure_logging()` 仅在生命周期启动阶段安装追踪上下文过滤器和格式化器。若在此处实时读取，运行时修改配置会使得 `X-Trace-Id` 响应标头和 Langfuse `deerflow_trace_id` 立即生效，而日志格式化器仍停留在启动时的值，这违背了需重启生效的契约。

当 `enabled` 为 `False` 时，中间件将原封不动地放行所有请求 —— 不绑定 trace ID，不写入响应标头，也不设置任何 `ContextVar`。这为未启用该功能的部署保留了原有的 HTTP 与日志输出行为。

来源：[trace_middleware.py](backend/app/gateway/trace_middleware.py#L22-L75), [app.py](backend/app/gateway/app.py#L598-L620), [app_config.py](backend/packages/harness/deerflow/config/app_config.py#L158-L175)

## 诊断工具

### 健康检查：`make doctor`

`doctor.py` 脚本会执行一系列结构化的环境与配置检查，并打印带有彩色状态图标（`✓` 正常，`!` 警告，`✗` 失败，`—` 跳过）的可操作报告。每个 `CheckResult` 包含一个标签、状态、可选的详情字符串，以及带有修复说明的可选 `fix` 提示。

检查范围涵盖：

| 检查项 | 验证内容 | 失败修复建议 |
|-------|-----------------|-------------|
| Python | 版本 ≥ 3.12 | 从 python.org 安装 |
| Node.js | 版本 ≥ 22 | 从 nodejs.org 安装 |
| pnpm | 可通过 `scripts/pnpm.py` 解析 | 安装 pnpm 或 Corepack |
| uv | 已安装且在 PATH 中 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| nginx | 已安装（适用于 Docker/代理模式） | 根据特定平台进行安装 |
| config.yaml | 存在于项目根目录 | `make setup` |
| config.yaml 版本 | 与 `config.example.yaml` 匹配 | `make config-upgrade` |
| config.yaml 可加载 | `AppConfig.from_file()` 成功执行 | `make setup` 或与示例文件对比 |
| 模型已配置 | 至少存在一个模型条目 | `make setup` |
| LLM API 密钥 | 每个 `$ENV_VAR` 引用均已设置 | 添加至 `.env` |
| LLM 包 | 每个 `use:` 包均可导入 | `cd backend && uv add <package>` |

退出码：所有必需检查均通过（允许警告）时为 `0`，任一必需检查失败时为 `1`。

来源：[doctor.py](scripts/doctor.py#L1-L200), [doctor.py](scripts/doctor.py#L200-L399)

### 支持包：`make support-bundle`

`support_bundle.py` 脚本会创建一个经过脱敏的 ZIP 诊断证据归档文件，用于社区故障排查。该脚本在设计上确保了分享的安全性：敏感信息会在多个层级被剥离，绝不包含原始对话消息与用户文件内容，且主目录路径会被匿名化处理。

该打包文件包含以下证据文件：

| 文件 | 内容 | 敏感信息处理 |
|------|----------|----------------|
| `README.md` | 易读的入口说明 | N/A |
| `issue-summary.md` | 用于粘贴至 GitHub issue 的 Markdown | 已脱敏 |
| `ai-issue-draft.md` | 带占位符的 AI 辅助 issue 草稿 | 已脱敏 |
| `triage.json` | 机器可读的故障分类摘要 | 已脱敏 |
| `manifest.json` | 打包文件结构、时间戳、隐私声明 | N/A |
| `environment.json` | 操作系统、Python、工具链版本 | 主目录路径已脱敏 |
| `config-summary.json` | 脱敏后的 `config.yaml` 结构 | 深度脱敏 |
| `extensions-summary.json` | 脱敏后的 `extensions_config.json` | 深度脱敏 |
| `git.json` | 分支、提交、状态、diff-stat | 主目录路径已脱敏 |
| `doctor.json` | 脱敏后的 `make doctor` 输出 | 已脱敏 |
| `thread-summary.json` | 线程文件清单（仅元数据） | 无文件内容 |

脱敏系统采用分层与递归机制。`redact_data()` 会遍历字典、列表、元组和字符串，在每个层级应用基于模式的脱敏处理。`SECRET_KEY_RE` 正则表达式会匹配包含 `api_key`、`token`、`secret`、`password`、`authorization`、`cookie`、`credential` 和 `dsn` 的键名（带有边界保护，以避免误匹配 `keyboard` 或 `passport` 等）。另一组 `NO_FLAG_CREDENTIAL_KEY_NAMES` 冻结集合则用于捕获如 `gh_pat`、`redis_auth` 和 `pgservicefile` 等缺乏明显关键字特征的裸凭证键名。对于文本值，`redact_text()` 会执行 URL 用户信息剥离（`https://user:pass@host` → `https://<redacted>@host`）、bearer token 掩码、OpenAI 密钥模式匹配（`sk-...`）以及 YAML/env 风格的密钥行脱敏。

`build_triage_report()` 函数将收集到的所有证据综合为一种状态分类（`ok`、`needs_user_setup`、`environment_mismatch`、`likely_runtime_issue`、`insufficient_evidence`），并为报告者和维护者提供基于信号的下一步操作建议。此分类层支持 AI 辅助提交 issue：`triage.json` 文件是稳定的机器可读入口，分类机器人或脚本可据此解析，判断该问题属于配置问题、环境不匹配，还是真正的运行时 Bug。

来源：[support_bundle.py](scripts/support_bundle.py#L1-L200), [support_bundle.py](scripts/support_bundle.py#L200-L598)

## 配置参考

### 环境变量

| 变量 | 提供者 | 用途 | 适用条件 |
|----------|----------|---------|---------------|
| `LANGSMITH_TRACING` / `LANGCHAIN_TRACING_V2` / `LANGCHAIN_TRACING` | LangSmith | 启用标志 | — |
| `LANGSMITH_API_KEY` / `LANGCHAIN_API_KEY` | LangSmith | 身份验证 | `enabled=true` |
| `LANGSMITH_PROJECT` / `LANGCHAIN_PROJECT` | LangSmith | 项目名称（默认：`deer-flow`） | — |
| `LANGSMITH_ENDPOINT` / `LANGCHAIN_ENDPOINT` | LangSmith | API 端点 | — |
| `LANGFUSE_TRACING` | Langfuse | 启用标志 | — |
| `LANGFUSE_PUBLIC_KEY` | Langfuse | 公钥 | `enabled=true` |
| `LANGFUSE_SECRET_KEY` | Langfuse | 密钥 | `enabled=true` |
| `LANGFUSE_BASE_URL` | Langfuse | 自托管端点（默认：`cloud.langfuse.com`） | — |
| `MONOCLE_TRACING` | Monocle | 启用标志 | — |
| `MONOCLE_EXPORTERS` | Monocle | 逗号分隔的导出器列表（默认：`file`） | — |
| `OKAHU_API_KEY` | Monocle | Okahu 云端鉴权 | 导出器中包含 `okahu` |
| `DEER_FLOW_ENV` / `ENVIRONMENT` | 全部 | 用于 `langfuse_tags` 的环境标签 | — |

### config.yaml 设置

```yaml
# Request trace correlation for Gateway logs, HTTP response headers, and
# Langfuse metadata. Disabled by default to preserve existing HTTP/log output.
logging:
  enhance:
    enabled: false      # true → bind trace_id per request, write X-Trace-Id header
    format: text        # "text" → [trace_id=xxx] prefix; "json" → structured JSON

# Log level for deerflow/app modules only (third-party libraries unaffected)
log_level: info
```

来源：[config.example.yaml](config.example.yaml#L24-L31), [tracing_config.py](backend/packages/harness/deerflow/config/tracing_config.py#L145-L213), [app_config.py](backend/packages/harness/deerflow/config/app_config.py#L140-L175)

## 运维场景

### 启用全链路可观测性

若要同时激活全部三个可观测性层：

1. **链路关联** —— 在 `config.yaml` 中设置 `logging.enhance.enabled: true` 并重启 Gateway。每条日志将增加 `[trace_id=...]` 字段，每个 HTTP 响应将增加 `X-Trace-Id` 标头。

2. **Langfuse** —— 在 `.env` 中设置 `LANGFUSE_TRACING=true`、`LANGFUSE_PUBLIC_KEY=pk-...`、`LANGFUSE_SECRET_KEY=sk-...`。Agent 运行记录将出现在 Langfuse 中，并按线程 ID 进行会话分组，附带用户归属、模型/环境标签以及 `deerflow_trace_id` 关联属性。

3. **Monocle** —— 设置 `MONOCLE_TRACING=true`（若需远程导出，可选配置 `MONOCLE_EXPORTERS=okahu` 及 `OKAHU_API_KEY=...`）。Gateway 生命周期会在启动时初始化 Monocle，在 OTel span 级别对所有 LLM 调用和工具执行进行插桩。

三个层可共存：链路关联提供跨系统的关联 ID，Langfuse 提供携带丰富元数据的 LangChain 执行追踪，Monocle 则提供 OTel 级别的插桩，能够捕获更多细节并支持导出至多个后端。

### TUI 与嵌入式使用

TUI 和 `DeerFlowClient` 路径不会执行 Gateway 生命周期，因此 Monocle 不会自动初始化。`build_tracing_callbacks()` 函数会通过 `is_monocle_setup_completed()` 检测到此情况，并记录一条调试信息，指引调用方手动调用 `setup_monocle_tracing_if_enabled()`。LangSmith 和 Langfuse 回调在嵌入式模式下可正常工作，因为它们是按运行构建的，而非全局安装。嵌入式客户端通过 `set_current_trace_id()` / `reset_current_trace_id()` token 对显式管理追踪上下文，因为没有 HTTP 中间件来执行绑定。

### 诊断生产环境问题

当 Agent 运行出现异常时，推荐的诊断工作流如下：

1. 运行 `make doctor` 验证环境、配置及提供者连通性。
2. 若问题可复现，运行 `make support-bundle` 生成已脱敏的证据 ZIP 包。
3. 将生成的 `issue-summary.md` 粘贴至 GitHub issue 中；仅在维护者要求时才附上 ZIP 包。
4. 若已启用链路关联，请附上失败请求的 `X-Trace-Id` 标头值 —— 这使维护者能够利用 `deerflow_trace_id` 属性将 Gateway 日志与 Langfuse 追踪关联起来。

支持包中的 `triage.json` 包含一个用于分类问题的 `status` 字段：`needs_user_setup` 表示缺少配置，`environment_mismatch` 表示工具链问题，`likely_runtime_issue` 则暗示存在值得进一步排查的真正 Bug。

来源：[monocle.py](backend/packages/harness/deerflow/tracing/monocle.py#L50-L70), [client.py](backend/packages/harness/deerflow/client.py#L42-L48), [support_bundle.py](scripts/support_bundle.py#L430-L530)

## 相关页面

- [Stream Bridge and Event Pipeline](24-stream-bridge-and-event-pipeline) —— 运行事件如何从 worker 流向客户端，以及追踪回调在执行生命周期中的附着点
- [Checkpointing and State Management](18-checkpointing-and-state-management) —— 与追踪 Agent 执行并行的持久化层
- [Gateway API and Auth](23-gateway-api-and-auth) —— `TraceMiddleware` 在中间件栈中相对于鉴权与 CSRF 的位置
- [Context Engineering and Compaction](16-context-engineering-and-compaction) —— token 使用情况的可观测性如何反馈至上下文窗口管理
