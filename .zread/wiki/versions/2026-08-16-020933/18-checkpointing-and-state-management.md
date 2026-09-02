# 检查点与状态管理

## 架构概述

## 后端配置与选择

### 后端对比

| 属性 | memory | sqlite | postgres |
|---|---|---|---|
| 持久化 | 重启后丢失 | 本地文件（WAL 模式） | 网络数据库 |
| 并发性 | 单进程 | 单节点（WAL 多读 + 1 写） | 多节点（连接池） |
| 增量缓存后端 | 仅内存 LRU | 仅内存 LRU | 内存 LRU 或 Redis |
| Schema 隔离 | 不适用 | 单个 .db 文件 | 可配置的 postgres_schema |
| 依赖包 | 内置 | langgraph-checkpoint-sqlite | langgraph-checkpoint-postgres |
| 同步路径 (TUI/内嵌) | ✅ | ✅ | ✅ |
| 异步路径 (Gateway) | ✅ | ✅ | ✅ (带保活的 AsyncConnectionPool) |

## 双模式检查点通道

### 模式冻结与元数据标记

### 快照频率

## CheckpointStateAccessor：唯一瓶颈点

### 状态变更图

## 增量历史缓存：不可变的直读

### 正确性基础：不可变条目

### 缓存后端

| 属性 | memory (LRU) | redis |
|---|---|---|
| 作用域 | 进程本地 | 跨 Worker 共享 |
| 淘汰机制 | LRU (可配置 max_entries，默认 128) | TTL (可配置，默认 86400s) + 服务器 maxmemory |
| 支持同步路径 | ✅ | ❌ (在同步内嵌路径上会抛出异常) |
| 支持异步路径 | ✅ | ✅ |
| 故障行为 | 不适用 | 全部未命中旁路 (绝不影响可用性) |
| 序列化 | 无 (命中路径零拷贝) | LangGraph serde.dumps_typed / loads_typed |
| 线程清理 | 前缀扫描 + 删除 | SCAN + UNLINK (失败时降级为受 TTL 约束的保留) |

### 递归组合策略

## 检查点血缘与重放解析

### 通过 `parent_config` 遍历血缘

- **环路检测**：跟踪每个已访问的检查点标识 `(thread_id, checkpoint_ns, checkpoint_id)`；若出现重复则抛出 `CheckpointLineageIntegrityError`。
- **仅时长检查点**：会跳过仅携带 `runtime_run_duration` 元数据（无对话状态）的检查点——它们不代表可寻址的对话状态。
- **待处理任务**：重放基准必须是线程处于静止状态时的状态。会跳过带有待处理 `next` 节点的检查点，因为从它们恢复会重放重新生成本意要替换的那一轮对话。仅靠消息 ID 无法检测到这一点，因为中间件可能会在产生该消息的同一次运行中重写其 ID。
- **可寻址性验证**：解析出的父节点标识必须与请求的 `parent_config` 标识匹配，以确保血缘链接完整且可安全使用。

### 按时间顺序的后备方案

## 针对 LangGraph 内部的兼容性补丁

### 补丁 1：InMemorySaver 增量历史丢失

### 补丁 2：BinaryOperatorAggregate 覆盖首次写入

## 序列化与状态投影

## 运行事件存储：互补的持久化

## 配置参考

| 键 | 类型 | 默认值 | 需要重启 | 描述 |
|---|---|---|---|---|
| backend | memory \| sqlite \| postgres | memory | 是 | checkpointer 和应用数据的存储后端 |
| checkpoint_channel_mode | full \| delta | full | 是 | 累积通道的检查点表示形式 |
| checkpoint_delta.snapshot_frequency | int ≥ 1 | 10 | 是 | DeltaChannel 全量快照频率（每 N 次写入） |
| checkpoint_cache.type | memory \| redis | memory | 否 | 增量历史缓存后端 |
| checkpoint_cache.max_entries | int ≥ 0 | 128 | 否 | LRU 容量（内存）；0 表示禁用缓存 |
| checkpoint_cache.redis_url | str | 环境变量回退 | 否 | Redis URL (环境变量: DEER_FLOW_CHECKPOINT_CACHE_REDIS_URL → REDIS_URL → redis://localhost:6379/0) |
| checkpoint_cache.ttl_seconds | int ≥ 0 | 86400 | 否 | Redis 条目 TTL（仅作泄漏安全网）；0 表示禁用过期 |
| checkpoint_cache.key_prefix | str | 自动哈希 | 否 | 覆盖 Redis 键前缀（默认为部署标识哈希） |
| checkpoint_graph_cache.accessor_graph_max | int ≥ 1 | 64 | 否 | Gateway 缓存的最大已编译 accessor 图数量 |
| postgres_schema | str | "" | 是 | 用于检查点 + 应用表的 PostgreSQL Schema |
| sqlite_dir | str | .deer-flow/data | 是 | 存放统一 SQLite 文件的目录 |

## 后续步骤

- 如需了解包括长期向量存储在内的更广泛内存架构，请参阅 。
- 如需了解检查点状态如何汇入流式事件管道，请参阅 。
- 如需了解在 Docker 中配置这些后端的部署模式，请参阅 。
- 如需深入了解检查点操作和缓存命中率，请参阅 。
