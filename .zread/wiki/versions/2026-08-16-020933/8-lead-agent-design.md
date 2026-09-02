# 主 Agent 设计

## 工厂入口点与 Agent 生命周期

## 模型解析与授权

## 中间件管道

### 完整中间件顺序

| 位置 | 中间件 | 条件 | 职责 |
|---|---|---|---|
| 0 | ThreadDataMiddleware | 始终 | 惰性初始化线程上下文；必须在 sandbox 之前 |
| 1 | UploadsMiddleware | 始终 | 从 ThreadData 访问 thread_id |
| 2 | SandboxMiddleware | 始终 | 惰性初始化 sandbox 环境 |
| 3 | DanglingToolCallMiddleware | 始终 | 在模型查看历史记录前修补缺失的 ToolMessages |
| 4 | ToolErrorHandlingMiddleware | 始终 | 将工具异常转换为 ToolMessages |
| 5 | DynamicContextMiddleware | 始终 | 将日期/内存作为 <system-reminder> 注入到首个 HumanMessage 中 |
| 6 | SkillActivationMiddleware | 始终 | 确定性的斜杠技能激活 |
| 7 | SkillToolPolicyMiddleware | 始终 | 在技能激活后于运行时强制执行允许的工具列表 |
| 8 | DurableContextMiddleware | 始终 | 在压缩前捕获委派账本和技能文件 |
| 9 | DeerFlowSummarizationMiddleware | 配置启用 | 在其他处理前进行上下文压缩 |
| 10 | TodoMiddleware | is_plan_mode | 结构化任务跟踪 |
| 11 | TokenUsageMiddleware | 配置启用 | Token 使用量核算 |
| 12 | TitleMiddleware | 始终 | 在首次交互后生成对话标题 |
| 13 | MemoryMiddleware | 配置启用 | 将对话排入记忆更新队列 |
| 14 | ViewImageMiddleware | 模型支持视觉 | 在 LLM 处理前注入图像细节 |
| 15 | MCPRoutingMiddleware | 存在延迟 MCP 工具时 | 自动提升延迟的 MCP schema |
| 16 | DeferredToolFilterMiddleware | 存在延迟名称时 | 在提升前隐藏延迟的工具 schema |
| 17 | SystemMessageCoalescingMiddleware | 始终 | 将 SystemMessages 合并为单个前导消息 |
| 18 | SubagentLimitMiddleware | subagent_enabled | 截断多余的并行任务调用 |
| 19 | LoopDetectionMiddleware | 配置启用 | 检测并打破重复的工具调用循环 |
| 20 | TokenBudgetMiddleware | 配置启用 | 强制执行单次运行的 Token 限制 |
| 21 | 自定义中间件 | 若已提供 | 用户注入的中间件 |
| 22 | 配置的扩展中间件 | 若已配置 | 扩展贡献的中间件 |
| 23 | TerminalResponseMiddleware | 始终 | 重试空的 AIMessage；持久化可见的错误降级方案 |
| 24 | ModelLengthFinishReasonMiddleware | 始终 | 为因长度限制而截断的补全打上运行级 stop_reason 标记 |
| 25 | SafetyFinishReasonMiddleware | 配置启用 | 在 provider 安全终止时抑制工具执行 |
| 26 | ClarificationMiddleware | 始终最后 | 在模型调用后拦截澄清请求 |

### 顺序不变量

-
-
-

### 扩展中间件组装

## 动态系统提示词组装

### 提示词部分架构

| 部分 | 来源 | 缓存策略 | 目的 |
|---|---|---|---|
| {soul} | load_agent_soul(agent_name) | 无 | 来自 SOUL.md 的 Agent 个性（HTML 转义） |
| {self_update_section} | _build_self_update_section() | 无 | 教导自定义 Agent 通过 update_agent 持久化更改 |
| {subagent_section} | _build_subagent_section() | 无 | 带有动态限制的委派路由规则 |
| {skills_section} | get_skills_prompt_section() | LRU 缓存 | 可用/禁用的技能元数据 |
| {memory_tool_section} | _build_memory_tool_section() | 无 | 工具模式下的记忆指引 |
| {deferred_tools_section} | get_deferred_tools_prompt_section() | 无 | 延迟 MCP 工具发现提示 |
| {mcp_routing_hints_section} | get_mcp_routing_hints_prompt_section() | 无 | MCP 自动提升提示 |
| {acp_section} | _build_acp_section() | 无 | ACP agent 任务指引 |

### 技能提示词缓存

## 子代理委派模型

### 委派决策框架

```
预期收益 = 并行延迟节省 + 专家能力 + 上下文隔离
预期成本 = 委派开销 + 重复上下文发现 + 协调/综合 + 状态冲突风险 + 副作用风险
```

### 动态限制配置

| 配置 | 来源 | 默认值 | 对提示词的影响 |
|---|---|---|---|
| max_concurrent_subagents | 运行时配置 | 3 | 设置单次响应的 task 调用限制；当为 1 时，省略并行调度指引 |
| max_total_subagents | 运行时配置 / 应用配置 | DEFAULT_MAX_TOTAL_SUBAGENTS_PER_RUN | 设置单次运行的 task 调用限制 |
| subagent_enabled | 运行时配置 | False | 控制是否存在 task 工具和 SubagentLimitMiddleware |

### 可用子代理发现

## 工具解析与授权

### 工具组装管道

- **原始工具** — `get_available_tools()` 返回基础工具集，并根据模型名称、工具组（来自 Agent 配置）和子代理启用情况进行过滤。
- **额外工具** — 为自定义 Agent（非引导、非 Webhook 渠道）追加 `update_agent`。为引导 Agent 追加 `setup_agent`。
- **迟到的工具** — 技能描述工具和记忆工具作为授权候选被追加。
- **授权** — `apply_tool_authorization()` 根据 RBAC 策略过滤工具，返回已授权的工具和解析出的授权 provider。该 provider 会被中间件链的执行时授权复用。
- **延迟工具组装** — `assemble_deferred_tools()` 根据 `tool_search.enabled` 将工具拆分为即时集合和延迟集合。延迟工具在通过 `tool_search` 或 MCP 路由提升之前，对模型绑定不可见。

### Webhook 渠道安全

## 澄清优先工作流

## 引导 Agent 变体

## SDK 工厂与特性组装

| 特性 | 位置 | 支持 True | 额外工具 |
|---|---|---|---|
| sandbox | 0-2 | 是 | — |
| guardrail | 4 | 否（需自定义实例） | — |
| summarization | 6 | 否（需模型参数） | — |
| auto_title | 8 | 是 | — |
| memory | 9 | 是 | 记忆工具（工具模式） |
| vision | 10 | 是 | view_image_tool |
| subagent | 11 | 是 | task_tool |
| loop_detection | 12 | 是 | — |
| token_budget | 13 | 是 | — |
| (始终) | 3, 5, 14 | — | ask_clarification_tool |

## 检查点模式集成

## 后续步骤
