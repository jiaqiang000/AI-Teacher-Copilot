# 上下文工程与压缩

## 架构概述

## 摘要配置模型

| 参数 | 类型 | 默认值 | 描述 |
|---|---|---|---|
| enabled | bool | False | 自动摘要的主开关 |
| model_name | str \| None | None | 专用摘要模型；None = 使用运行自身的模型 |
| trigger | ContextSize \| list[ContextSize] \| None | None | 触发摘要的一个或多个阈值 |
| keep | ContextSize | messages: 20 | 压缩后的保留策略 |
| trim_tokens_to_summarize | int \| None | 4000 | 摘要提示词输入的最大 Token 数；None = 跳过裁剪 |
| summary_prompt | str \| None | None | 自定义提示词模板；None = 默认 LangChain 提示词 |
| skill_file_read_tool_names | list[str] | ["read_file", "read", "view", "cat"] | 被视为技能文件读取的工具名称，用于持久化上下文捕获 |

| 类型 | 值语义 | 示例 | 使用场景 |
|---|---|---|---|
| messages | 绝对消息数量 | {"type": "messages", "value": 50} | 可预测、与模型无关的压缩节奏 |
| tokens | 绝对 Token 数量 | {"type": "tokens", "value": 4000} | 精确到 Token 的预算控制 |
| fraction | 模型最大输入 Token 的百分比 | {"type": "fraction", "value": 0.8} | 适配不同模型的上下文窗口 |

## 摘要中间件引擎

### 模型解析与降级链

### 压缩状态机

### 动态上下文提醒保留

- `SystemMessage(id=X)` — 标记为 `dynamic_context_reminder=True`
- `HumanMessage(id=X__memory)` — 标记为 `dynamic_context_reminder=True`
- `HumanMessage(id=X__user)` — 携带原始用户内容，**未标记**

### 摘要提示词构建与安全性

- `"No previous conversation history."` — 当 `messages_to_summarize` 为空时
- `"Previous conversation was too long to summarize."` — 当裁剪后无内容留存时

### 摘要前置钩子

## 手动线程压缩

### 压缩流程

### 手动压缩的模型解析

- **显式请求的模型覆盖** — 根据已配置的模型进行校验
- **线程自定义 Agent 的已配置模型** — 通过 `_safe_load_agent_config` 在事件循环外使用 `asyncio.to_thread` 加载
- **`config.models[0]`** — 默认模型

### 结果上报与错误语义

| 字段 | 类型 | 描述 |
|---|---|---|
| thread_id | str | 被压缩的线程 |
| compacted | bool | 是否实际发生了压缩 |
| reason | str \| None | 跳过压缩的原因（例如 "not_enough_messages"） |
| removed_message_count | int | 被摘要移除的消息数 |
| preserved_message_count | int | 保留在活动尾部的消息数 |
| summary_updated | bool | 是否写入了新摘要 |
| checkpoint_id | str \| None | 写入后的新检查点 ID |
| total_tokens | int | 压缩时的 Token 数量 |

- **`compacted=False, reason="not_enough_messages"`** — 线程消息不足，无法压缩；这是正常的空操作
- **`ContextCompactionDisabled`** — 配置中未启用摘要功能
- **`ContextCompactionFailed`** — 线程本可压缩，但在穷尽所有模型候选后，摘要 LLM 生成失败；此错误表现为 HTTP 500 → 前端错误提示，与“无内容可压缩”的结果截然不同

## Token 预算限制

| 参数 | 类型 | 默认值 | 描述 |
|---|---|---|---|
| enabled | bool | False | 单次运行预算限制的主开关 |
| max_tokens | int | 200000 | 每次运行的最大总 Token 数（输入 + 输出） |
| max_input_tokens | int \| None | None | 可选的独立输入 Token 限制 |
| max_output_tokens | int \| None | None | 可选的独立输出 Token 限制 |
| warn_threshold | float | 0.8 | 触发软警告注入时的 max_tokens 百分比 |
| hard_stop_threshold | float | 1.0 | 剥离工具调用并强制 Agent 生成最终答案时的 max_tokens 百分比 |

## 中间件管道集成

| 中间件 | 角色 | 关键行为 |
|---|---|---|
| token_usage_middleware.py | 统计 | 跟踪每次运行的累计 Token 消耗 |
| token_budget_middleware.py | 限制 | 阈值处警告，超限时硬停机 |
| tool_output_budget_middleware.py | 压缩 | 在工具输出进入消息缓冲区前进行限制与压缩 |
| tool_output_synopsis.py | 压缩 | 为大型工具输出生成摘要 |
| tool_result_sanitization_middleware.py | 清理 | 剥离工具结果中的敏感数据 |
| system_message_coalescing_middleware.py | 去重 | 合并冗余的系统消息 |
| dynamic_context_middleware.py | 注入 | 注入日期、记忆及运行时上下文提醒 |
| durable_context_middleware.py | 持久化 | 将技能文件读取捕获至持久化 skill_context 通道 |
| summarization_middleware.py | 压缩 | 摘要旧消息，保留活动尾部 |
| dangling_tool_call_middleware.py | 修复 | 修复孤立的工具调用/响应对 |
| model_length_finish_reason_middleware.py | 恢复 | 处理模型最大长度截断 |

## 扩展系统集成

## 延伸阅读

- **** — 了解 `create_chat_model` 如何构建摘要中间件所使用的模型，包括受保护的构建模式与思维模式禁用机制。
- **** — 手动压缩路径通过 `CheckpointStateAccessor` 读写检查点状态；此页面介绍了检查点生命周期及压缩期间使用的 `Overwrite` 语义。
- **** — `memory_flush_hook` 将压缩前消息持久化至持久化记忆；此页面详述了记忆后端架构。
- **** — 完整的中间件顺序与生命周期，包括 `before_model` 钩子如何链接在一起。
