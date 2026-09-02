# Agent 中间件管道

## 流水线架构：两条组装路径



## RuntimeFeatures：声明式功能开关

| 功能开关 | 类型 | 默认值 | 内置中间件 | 说明 |
|---|---|---|---|---|
| sandbox | bool \| AgentMiddleware | True | ThreadDataMiddleware → UploadsMiddleware → SandboxMiddleware | 三中间件集群 |
| memory | bool \| AgentMiddleware | False | MemoryMiddleware | 感知配置：工具模式 vs. 被动写入 |
| summarization | Literal[False] \| AgentMiddleware | False | 无（需自定义实例） | 需要模型参数 |
| subagent | bool \| AgentMiddleware | False | SubagentLimitMiddleware | 同时注入 task_tool |
| vision | bool \| AgentMiddleware | False | ViewImageMiddleware | 同时注入 view_image_tool |
| auto_title | bool \| AgentMiddleware | False | TitleMiddleware | — |
| guardrail | Literal[False] \| AgentMiddleware | False | 无（需自定义实例） | 暂无内置默认值 |
| loop_detection | bool \| AgentMiddleware | True | LoopDetectionMiddleware | 基于配置的默认值 |
| token_budget | bool \| AgentMiddleware | False | TokenBudgetMiddleware | 单次运行 Token 限制 |



## SDK 中间件链：固定顺序组装



## `@Next` / `@Prev` 定位协议

| 装饰器 | 语义 | 示例 |
|---|---|---|
| @Next(AnchorMiddleware) | 插入到链中锚点的之后 | @Next(ToolErrorHandlingMiddleware) 将自定义中间件放置在 ToolErrorHandlingMiddleware 紧随其后 |
| @Prev(AnchorMiddleware) | 插入到链中锚点的之前 | @Prev(ClarificationMiddleware) 将自定义中间件放置在 ClarificationMiddleware 正前方 |
| (无装饰器) | 作为默认回退，插入到 ClarificationMiddleware 之前 | 未指定锚点的中间件将被集中放置在澄清拦截器之前 |

- **校验** —— 拒绝任何同时声明 `@Next` 和 `@Prev` 的中间件
- **冲突检测** —— 若存在针对同一锚点的额外中间件（即便方向相反），则抛出 `ValueError`
- **无锚点插入** —— 放置在 `ClarificationMiddleware` 之前
- **有锚点插入** —— 支持跨外部锚点（一个额外中间件以另一个额外中间件的类型为锚点）的迭代式多轮解析，并带有循环依赖检测



## Lead Agent 中间件链：完整应用级组装

### 第 1 层：常驻运行时核心

### 第 2 层：条件功能中间件

| 顺序 | 中间件 | 条件 | 目的 |
|---|---|---|---|
| 1 | DynamicContextMiddleware | 始终加载 | 将日期/记忆作为 <system-reminder> 注入首条 HumanMessage |
| 2 | SkillActivationMiddleware | 始终加载 | 在 /skill-name 斜杠命令时加载 SKILL.md |
| 3 | SkillToolPolicyMiddleware | 始终加载 | 运行时强制执行各技能允许使用的工具 |
| 4 | DurableContextMiddleware | 始终加载 | 在摘要压缩前捕获委派/技能信息 |
| 5 | SummarizationMiddleware | summarization 配置开启 | 通过模型摘要进行上下文压缩 |
| 6 | TodoMiddleware | is_plan_mode == True | 结构化任务列表追踪 |
| 7 | TokenUsageMiddleware | token_usage.enabled | Token 用量统计 |
| 8 | TitleMiddleware | 始终加载 | 首次交互后自动生成对话标题 |
| 9 | MemoryMiddleware | 始终加载（行为随配置而异） | 将对话排入长期记忆队列 |
| 10 | ViewImageMiddleware | 模型支持视觉 | 在 LLM 读取历史前注入图像细节 |
| 11 | MCPRoutingMiddleware | 提供了 mcp_routing_middleware | 自动提升延迟加载的 MCP 架构 |
| 12 | DeferredToolFilterMiddleware | deferred_setup 包含延迟名称 | 在模型绑定时隐藏延迟工具架构 |
| 13 | SystemMessageCoalescingMiddleware | 始终加载 | 合并多条 SystemMessages 为一条（兼容不同提供商） |
| 14 | SubagentLimitMiddleware | subagent_enabled == True | 截断超额的并行任务调用 |
| 15 | LoopDetectionMiddleware | loop_detection.enabled | 中断重复的工具调用循环 |
| 16 | TokenBudgetMiddleware | token_budget.enabled | 强制执行单次运行 Token 限制 |
| 17 | 自定义中间件 | 提供了 custom_middlewares | 用户提供的扩展 |
| 18 | 配置的扩展中间件 | 存在扩展配置 | 从扩展配置中加载 |
| 19 | TerminalResponseMiddleware | 始终加载 | 重试空的最终响应；持久化可见的兜底响应 |
| 20 | ModelLengthFinishReasonMiddleware | 始终加载 | 为触及长度上限的补全标记 stop_reason |
| 21 | SafetyFinishReasonMiddleware | safety_finish_reason.enabled | 在提供商因安全原因终止时抑制工具执行 |
| 22 | ClarificationMiddleware | 始终加载（末尾） | 在模型调用后拦截澄清请求 |

### 第 3 层：扩展组合



## 中间件顺序不变量

| 不变量 | 原因 | 强制执行方式 |
|---|---|---|
| ThreadDataMiddleware 位于 SandboxMiddleware 之前 | 沙箱路径解析必须用到 thread_id | 注释说明；顺序追加保证 |
| DanglingToolCallMiddleware 位于模型之前 | 修补缺失的 ToolMessages 以保证模型历史记录一致 | 在 SDK 链中始终处于位置 3 |
| DurableContextMiddleware 位于 SummarizationMiddleware 之前 | 在压缩丢弃前捕获委派/技能信息 | 在 build_middlewares 中顺序追加 |
| MCPRoutingMiddleware 位于 DeferredToolFilterMiddleware 之前 | 路由必须在过滤器决定隐藏架构前先将其提升 | 运行时断言：assert_mcp_routing_before_deferred_filter |
| SystemMessageCoalescingMiddleware 位于提供商调用之前 | 严格的后端（vLLM, SGLang, Qwen, Anthropic）会拒绝非首部的 SystemMessages | 顺序追加；在模型看到请求前完成合并 |
| ClarificationMiddleware 始终位于最后 | 必须在所有其他处理完成后拦截澄清请求 | 在 _assemble_from_features 中显式重定位；在 build_middlewares 中有注释说明 |
| SafetyFinishReasonMiddleware 位于 TerminalResponseMiddleware 之后 | 在终端响应之后注册，使得 LangChain 的逆序 after_model 调度优先运行安全检查 | 顺序追加顺序 + LangChain 逆序调度语义 |



## 中间件分类与职责

### 基础设施中间件

| 中间件 | 文件 | 职责 |
|---|---|---|
| ThreadDataMiddleware | thread_data_middleware.py | 在状态中建立 thread_id；延迟初始化 |
| UploadsMiddleware | uploads_middleware.py | 将上传的文件引用解析为上下文 |
| SandboxMiddleware | (位于 deerflow.sandbox.middleware) | 管理代码执行环境的生命周期 |
| DanglingToolCallMiddleware | dangling_tool_call_middleware.py | 为不完整的工具调用修补缺失的 ToolMessage 响应 |

### 上下文与记忆中间件

| 中间件 | 文件 | 职责 |
|---|---|---|
| DynamicContextMiddleware | dynamic_context_middleware.py | 将日期/记忆作为 <system-reminder> 注入首条 HumanMessage |
| DurableContextMiddleware | durable_context_middleware.py | 在摘要压缩过程中保留委派/技能信息 |
| SummarizationMiddleware | summarization_middleware.py | Token 超出阈值时通过模型进行上下文压缩 |
| MemoryMiddleware | memory_middleware.py | 将对话轮次排入长期记忆后端队列 |
| SystemMessageCoalescingMiddleware | system_message_coalescing_middleware.py | 将所有 SystemMessages 合并为单条首部消息 |

### 技能与工具策略中间件

| 中间件 | 文件 | 职责 |
|---|---|---|
| SkillActivationMiddleware | skill_activation_middleware.py | 在斜杠激活时确定性地加载 SKILL.md |
| SkillToolPolicyMiddleware | skill_tool_policy_middleware.py | 运行时强制执行各技能允许使用的工具 |
| ToolErrorHandlingMiddleware | tool_error_handling_middleware.py | 将工具异常转换为 ToolMessage 响应 |
| DeferredToolFilterMiddleware | deferred_tool_filter_middleware.py | 在 tool_search 提升前隐藏延迟加载的 MCP 工具架构 |
| MCPRoutingMiddleware | mcp_routing_middleware.py | 从 PR1 路由元数据中自动提升延迟加载的 MCP 架构 |

### 安全与限制中间件

| 中间件 | 文件 | 职责 |
|---|---|---|
| LoopDetectionMiddleware | loop_detection_middleware.py | 检测并中断重复的工具调用模式 |
| SubagentLimitMiddleware | subagent_limit_middleware.py | 截断超额的并行子 Agent 任务调用 |
| TokenBudgetMiddleware | token_budget_middleware.py | 强制执行单次运行 Token 消耗限制 |
| SafetyFinishReasonMiddleware | safety_finish_reason_middleware.py | 在提供商因安全原因终止时抑制工具执行 |
| ModelLengthFinishReasonMiddleware | model_length_finish_reason_middleware.py | 为触及长度上限的补全标记运行级 stop_reason |

### 响应与用户体验中间件

| 中间件 | 文件 | 职责 |
|---|---|---|
| ClarificationMiddleware | clarification_middleware.py | 拦截澄清请求；始终处于最后 |
| TerminalResponseMiddleware | terminal_response_middleware.py | 重试空的最终响应；持久化可见的错误兜底 |
| TitleMiddleware | title_middleware.py | 首次交互后自动生成对话标题 |
| TodoMiddleware | todo_middleware.py | 针对计划模式的结构化任务列表管理 |
| TokenUsageMiddleware | token_usage_middleware.py | Token 用量统计与报告 |



## 状态模式归一化



## 扩展中间件集成

- **`scope`**：`AgentScope.LEAD` —— 确保扩展仅作用于相应类型的 Agent
- **`agent_name`**：已解析的 Agent 名称，用于实现针对特定 Agent 的行为
- **`model_name`**：已解析的运行时模型，用于感知模型的扩展
- **`policy`**：投影的宿主策略，包括 Token 预算限制和子 Agent 限制，以便扩展能够遵守或扩充操作约束



## 实践指南：编写自定义中间件



## 后续步骤

- 要了解 Lead Agent 如何配置和调用，请阅读 。
- 关于 `SubagentLimitMiddleware` 管理的子 Agent 执行生命周期，请参见。
- 关于可在位置 4 注入的安全与护栏中间件，请参见。
- 要了解技能如何通过 `SkillActivationMiddleware` 和 `SkillToolPolicyMiddleware` 与流水线交互，请参见。
- 要了解 `SummarizationMiddleware` 背后的上下文压缩机制，请参见。
