# 长期记忆后端

## 架构概述

## MemoryManager 契约

### 第一层：抽象方法（必需）

| 方法 | 签名 | 用途 |
|---|---|---|
| add | (thread_id, messages, *, agent_name, user_id, trace_id) → None | 将对话排入异步记忆更新队列。实现内部会将消息过滤为用户输入 + 最终助手回复。 |
| get_context | (user_id, *, agent_name, thread_id) → str | 返回可直接注入的记忆文本。具体格式由后端自行决定——DeerMem 会加载事实并执行 format_memory_for_injection；其他后端可进行自定义搜索与格式化。 |

### 第二层：管理操作（带默认实现）

| 方法 | 默认实现 | 调用方 |
|---|---|---|
| add_nowait | 委托给 add() | 摘要钩子——在消息从状态中移除前捕获内容 |
| search | raise NotImplementedError | 工具模式的 memory_search 工具；网关搜索端点 |
| get_memory | raise NotImplementedError | 网关 /memory GET——返回完整记忆文档 |
| clear_memory | raise NotImplementedError | 网关 /memory DELETE——清空存储桶，返回空文档 |
| import_memory | raise NotImplementedError | 网关 /memory/import POST |
| shutdown_flush | 返回 True | 网关生命周期——在优雅关闭时对挂起的更新进行有界排空 |
| delete_memory / export_memory | raise NotImplementedError | 废弃契约（零调用方）；通过默认抛出异常保持可用 |

### 第三层：可选钩子（带默认实现）

| 钩子 | 默认实现 | 用途 |
|---|---|---|
| warm | None（无需预热） | 网关启动时的一次性资源预热（例如 tiktoken 缓存） |
| reload_memory | raise NotImplementedError | 丢弃缓存的记忆文档并从存储重新加载 |
| create_fact | raise NotImplementedError | 前端添加事实按钮（返回 (memory_data, fact_id)） |
| delete_fact | raise NotImplementedError | 前端删除事实按钮 |
| update_fact | raise NotImplementedError | 前端编辑事实按钮 |
| on_pre_compress | ""（无增强） | 记忆 → 压缩器反馈，用于摘要增强 |
| on_turn_start | None（空操作） | 轮次开始时的提醒，用于未来的后台审查 |

## 操作模式：中间件 vs. 工具

## 后端发现与工厂解析

- **注册的短名称**：如果 `manager_class` 匹配到已发现的后端文件夹，则直接使用该类。
- **点号导入路径**：如果不是注册名称，则视为 `pkg.mod:Cls` 或 `pkg.mod.Cls` 并尝试 `importlib` 解析。

## 宿主共享配置架构

| 字段 | 类型 | 默认值 | 描述 |
|---|---|---|---|
| enabled | bool | True | 记忆机制的主调用门控 |
| mode | Literal["middleware", "tool"] | "middleware" | 操作模式（被动 vs. 模型引导） |
| injection_enabled | bool | True | 是否将记忆注入系统提示词 |
| shutdown_flush_timeout_seconds | float | 30.0 | 关闭时排空挂起更新的硬性时间预算 |
| manager_class | str | "deermem" | 后端选择器（注册名称或点号路径） |
| backend_config | dict[str, Any] | {} | 后端私有配置，原样传递给后端的 __init__ |

## 内置后端

### DeerMem（默认）

| 字段 | 默认值 | 范围 | 描述 |
|---|---|---|---|
| max_facts | 100 | 10–500 | 最大存储事实数 |
| fact_confidence_threshold | 0.7 | 0.0–1.0 | 事实存储的最低置信度 |
| max_injection_tokens | 2000 | 100–8000 | 记忆注入的 Token 预算 |
| token_counting | tiktoken | tiktoken / char | 注入预算的 Token 计数策略 |
| guaranteed_categories | ["correction"] | — | 无论 Token 预算如何始终注入的类别 |
| guaranteed_token_budget | 500 | 50–2000 | 保证类别事实的 Token 上限 |
| debounce_seconds | 30 | 1–300 | 队列防抖延迟 |
| queue_max_depth | 1000 | 0+ | 背压上限（0 = 无限） |
| retrieval_adapter | fts5 | — | 检索工厂：fts5、""（禁用）或点号路径 |

### Noop（模板）

### mem0（远程 HTTP）

### Honcho（远程用户模型记忆）

### OpenViking（远程 LangChain 集成）

## DeerMem 数据结构（规范模型）

## 记忆注入流水线

- 基于近期对话上下文的 TF-IDF 余弦相似度召回
- 为 `format_memory_for_injection` 添加 `current_context` 参数
- 加权排序：`final_score = (similarity * 0.6) + (confidence * 0.4)`
- 用于上下文感知事实选择的运行时提取/注入流
- 当上下文不可用时回退到仅基于置信度的排序

## 宿主钩子与可观测性

| 钩子 | 提供者 | 用途 |
|---|---|---|
| callbacks | LangfuseMemoryCallbacks | 在 LLM 调用前合并元数据用于 langfuse 追踪；调用后通过扩展 API 观察结果 |
| should_keep_hidden_message | _host_default_should_keep_hidden_message | 仅当 hide_from_ui 消息携带用户输入的澄清响应时保留 |
| host_llm_factory | _host_default_llm | 为零配置 DeerMem 提取构建宿主默认聊天模型（等效于 model_name: null） |
| trace_context_manager | 宿主追踪上下文 | 为记忆操作绑定追踪上下文 |
| extraction_callback | _host_default_extraction_callback | 记录提取后指标（Token 使用、置信度通过/拒绝率）；标记 >60% 的拒绝率 |

## 添加自定义后端

| 步骤 | 文件 | 操作 |
|---|---|---|
| 1 | backends/<name>/config.py | 声明配置字段 + from_backend_config（解析 backend_config；从中读取 storage_path——切勿导入 deer-flow 路径助手） |
| 2 | backends/<name>/<name>_manager.py | 实现 MemoryManager 子类；在 model_post_init 解析配置；实现 from_config + add + get_context；按需重写第二/三层 |
| 3 | backends/<name>/__init__.py | 设置 MANAGER_CLASS = YourManager（相对导入） |
| 4 | config.yaml（仓库根目录） | 设置 memory.manager_class: <name> + 在 memory.backend_config 下配置参数 |
| 5 | packages/harness/pyproject.toml | 仅当需要外部库时：声明依赖 + 为 vendored 源添加 [tool.uv.sources] |

- **外部依赖必须在 `pyproject.toml` 中声明**——单纯的 `uv pip install` 会在下次 `uv sync` / `langgraph dev` 时被清除。
- **返回 DeerMem 结构**——否则前端会崩溃并提示 `Invalid time value`，且数据会被静默丢弃。
- **未实现的事实 CRUD 返回 501**——实现 `delete_fact` 及相关方法以支持前端按钮。
- **自行限制 `get_context` 长度**——宿主不应用 Token 预算；后端必须截断。
- **修改后重启 deer-flow**——管理器是进程级单例。

## 后端对比矩阵

| 特性 | DeerMem | Noop | mem0 | Honcho | OpenViking |
|---|---|---|---|---|---|
| 存储 | 文件 JSON（按用户） | 无 | 远程服务器 | 远程服务器 | 远程服务器 |
| LLM 提取 | 本地（防抖） | 无 | 服务端 | 服务端推导器 | 服务端 |
| 搜索 | FTS5 + 子字符串 | 返回 [] | 服务端 | 服务端 | — |
| 工具模式 | ✅ (supports_search) | ✅ (returns []) | ✅ (passive writes) | ✅ (passive writes) | — |
| 事实 CRUD | ✅ 完整 | ❌ (501) | ❌ (501) | ❌ (501) | ❌ (501) |
| 陈旧度审查 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 整合 | ✅（显式开启） | ❌ | ❌ | ❌ | ❌ |
| 多 Worker 安全 | ❌（文件锁） | ✅ | ✅（无状态） | ✅（无状态） | ✅ |
| 外部依赖 | tiktoken | 无 | mem0 client | honcho client | langchain-openviking |
| 关闭排空 | ✅（有界排空） | ✅（空操作） | ✅（空操作） | ✅（空操作） | ✅（空操作） |

## 运维考量

## 延伸阅读

- — 对话状态如何持久化与恢复（作为短期持久层补充长期记忆）
- — `MemoryMiddleware` 在 Agent 执行生命周期中的位置
- — 记忆注入如何与上下文窗口管理和摘要化交互
- — 暴露记忆 CRUD 操作的 HTTP 端点
