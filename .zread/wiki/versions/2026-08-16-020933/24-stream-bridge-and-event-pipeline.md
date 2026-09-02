# 流桥接与事件管道

## 架构概述

## Stream Bridge 协议

### 核心数据类型

| 类型 | 用途 | 关键字段 |
|---|---|---|
| StreamEvent | 单个可分发事件 | id (单调递增的 SSE ID), event (SSE 事件名称), data (JSON 负载) |
| StreamGap | 订阅者落后于留存的历史记录 | requested_event_id, earliest_available_event_id, latest_available_event_id |
| StreamItem | subscribe() 产出的联合类型 | StreamEvent \| StreamGap |

### 抽象接口契约

## MemoryStreamBridge：进程内实现

### 事件 ID 方案与重放

```
Event ID: 1718437200000-42
                       ^^-- seq = 42 = 运行内的绝对偏移量
```

### 有界留存与订阅者延迟检测

## RedisStreamBridge：跨进程实现

### Redis Stream 映射

| StreamBridge 概念 | Redis 原语 |
|---|---|
| StreamEvent.id | Redis Stream 条目 ID ({ms}-{seq}) |
| 有界缓冲区 (queue_maxsize) | XADD ... MAXLEN N |
| publish_end() | 带有 kind=end 字段的 XADD |
| subscribe() 重放 | XREAD ... AFTER {last_event_id} |
| subscribe() 实时追踪 | XREAD ... BLOCK {ms} |
| 基于 TTL 的清理 | EXPIRE key {ttl} (默认 86400s) |
| Gap 检测 | 原子化 XRANGE + XREVRANGE + XREAD 管道 |

### 原子化 Gap 检测

### 瞬时错误韧性

## Stream Bridge 工厂与配置

| 配置字段 | 默认值 | 描述 |
|---|---|---|
| type | "memory" | bridge 后端："memory" 或 "redis" |
| queue_maxsize | 256 | 每次运行保留的最大事件数 |
| redis_url | "redis://localhost:6379/0" | Redis 连接 URL（仅限 redis 类型） |
| max_connections | None (无限制) | Redis 连接池上限（仅限 redis 类型） |
| stream_ttl_seconds | 86400 (24小时) | 用于自动清理的 Redis Stream TTL（仅限 redis 类型） |

## RunJournal：基于回调的事件生产

### 回调到事件的映射

| LangChain 回调 | 事件类型 | 类别 | 内容 |
|---|---|---|---|
| on_chain_start(parent=None) | run.start | trace | {"chain": chain_name} |
| on_chain_end(parent=None) | run.end | outputs | 不透明的根图输出 |
| on_chain_error | run.error | error | str(error) |
| on_chat_model_start | llm.human.input | message | 第一个持久化的 HumanMessage.model_dump() |
| on_llm_end | llm.ai.response | message | 包含 tool_calls 的 AIMessage.model_dump() |
| on_tool_end | llm.tool.result | message | ToolMessage.model_dump() |
| on_llm_error | llm.error | trace | str(error) |

### 写入缓冲与刷新

### Token 使用量累积

## 事件契约：固定的 Schema 与类别

### 兼容性规则

| 变更类型 | 是否允许？ | 示例 |
|---|---|---|
| 新增事件类型 | ✅ 是 | 可以引入新的事件类型 |
| 新增可选负载字段 | ✅ 是 | content/metadata 中的新可选字段 |
| 新增信封字段 | ✅ 是 | 新的顶层记录字段 |
| 移除事件类型 | ❌ 否 | 破坏性变更 —— 消费者依赖现有类型 |
| 重命名事件类型 | ❌ 否 | 破坏性变更 —— 会中断所有消费者 |
| 更改事件类别 | ❌ 否 | 破坏性变更 —— 类别会驱动投影过滤器 |
| 移除必需字段 | ❌ 否 | 破坏性变更 —— 消费者期望必需字段存在 |
| 更改必需字段类型 | ❌ 否 | 破坏性变更 —— 类型预设会失效 |

### 事件类别

| 类别 | 用途 | 事件类型 |
|---|---|---|
| trace | 从消息投影中排除的执行证据 | run.start, llm.error |
| message | 候选消息投影（仍需应用可见性过滤器） | llm.human.input, llm.ai.response, llm.tool.result |
| outputs | 根图完成输出（非权威生命周期状态） | run.end |
| error | 回调观察到的运行或链失败证据 | run.error |
| middleware | 中间件状态变更审计证据 | middleware:{tag} (动态) |
| context | 关于有效隐藏上下文的仅标识证据 | context:memory |
| subagent | subagent 生命周期和持久化步骤证据 | subagent.start, subagent.step, subagent.end |
| workspace | 运行作用域内的 workspace 和输出文件变更证据 | workspace_changes |

### 动态中间件事件

### 记录 Schema

### 已知缺陷

- **混合的事件名称分隔符** —— 为了兼容性，现有的点号、冒号及纯单词事件名称保持原样。规范化处理需要进行版本化的迁移。
- **工具调用意图** —— 工具调用请求内嵌在 `llm.ai.response` 内容中；缺失或超时的工具结果可能不会产生专门的产出事件。
- **终止运行状态** —— `run.end` 始终显示为 `success`（它仅是根图完成的标志）。关于 success、error、interrupted 和 timeout 状态，`RunRow.status` 才是权威来源。
- **依赖后端的序列化** —— 内存模式在 `run.end` 内容中保留嵌套的 Python 值；而 JSONL 和数据库持久化则通过 `json.dumps(default=str)` 将非 JSON 值字符串化。
- **中间件覆盖范围** —— 循环检测和延迟工具提升目前不会发出中间件事件。

## Subagent 事件生命周期

| 事件 | 触发条件 | 必需内容字段 |
|---|---|---|
| subagent.start | task_started | task_id, description |
| subagent.step | task_running | task_id, message_index, kind (ai/tool), text, truncated |
| subagent.end | task_completed / task_failed / task_cancelled / task_timed_out | task_id, status |

## 事件存储后端

## Workspace 变更事件

## 端到端事件流

## 实现对比

| 维度 | MemoryStreamBridge | RedisStreamBridge |
|---|---|---|
| 跨进程 | ❌ 否 | ✅ 是 |
| 底层存储 | asyncio.Condition + list | Redis Streams (XADD/XREAD) |
| 事件 ID 格式 | {ts_ms}-{seq} | Redis 原生 ({ms}-{seq}) |
| 重放解析 | 基于 seq 的 O(1) 算术运算 | XREAD AFTER {id} |
| Gap 检测 | 比较 seq 与 start_offset | 原子化 XRANGE + XREVRANGE + XREAD 管道 |
| 留存策略 | 有界列表（默认 256） | MAXLEN N + TTL（默认 24h） |
| 心跳机制 | asyncio.wait_for 超时 | XREAD BLOCK {ms} 超时 |
| 错误韧性 | 不适用（进程内） | 指数退避，最大重试 3 次 |
| 清理操作 | 字典弹出 | DEL key（在可选延迟之后） |
| 依赖项 | 无（仅标准库） | 可选额外依赖 redis |
| 导入策略 | 立即导入（始终可用） | 懒加载（仅在配置时） |

## 相关页面

- **** — 介绍网关如何暴露 SSE 端点并管理流连接的身份验证
- **** — 介绍检查点器如何补充事件管道以实现状态恢复
- **** — 介绍 subagent 生命周期事件的产生与消费方式
- **** — 介绍中间件事件的生成方式及其含义
- **** — 介绍前端如何消费 SSE 事件并处理重连
