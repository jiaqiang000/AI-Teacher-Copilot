# 定时任务系统

## 架构概述

## 调度计算

## 任务与运行数据模型

### scheduled_tasks 模式

| 列名 | 类型 | 描述 |
|---|---|---|
| id | String(64) PK | 以 task- 为前缀的 UUID 十六进制字符串 |
| user_id | String(64) | 所有者；所有访问权限均以此进行限定 |
| thread_id | String(64), nullable | 目标线程（fresh_thread_per_run 模式下为 None） |
| context_mode | String(32) | fresh_thread_per_run 或 reuse_thread |
| schedule_type | String(16) | once 或 cron |
| schedule_spec | JSON | {"run_at": "..."} 或 {"cron": "..."} |
| timezone | String(64) | IANA 时区名称 |
| status | String(16) | enabled, running, paused, completed, failed, cancelled |
| overlap_policy | String(16) | skip（MVP 默认值；唯一支持的值） |
| next_run_at | DateTime | 下次触发的 UTC 时间；None 表示终态 |
| last_run_at | DateTime | 上次分发的时间戳 |
| last_run_id | String(64), nullable | 上次启动时 RunManager 的运行 ID |
| last_error | Text, nullable | 上次失败尝试的错误字符串 |
| lease_owner | String(128), nullable | 认领轮询器实例的 Hostname:UUID |
| lease_expires_at | DateTime, nullable | 租约截止时间；未认领时为 None |
| run_count | Integer | 仅在成功启动时递增 |

### scheduled_task_runs 模式

| 列名 | 类型 | 描述 |
|---|---|---|
| id | String(64) PK | 以 task-run- 为前缀的 UUID 十六进制字符串 |
| task_id | String(64) | 指向 scheduled_tasks.id 的外键 |
| thread_id | String(64) | 执行线程（新建或复用） |
| run_id | String(64), nullable | 启动后 RunManager 的运行 ID |
| trigger | String(16) | scheduled 或 manual |
| status | String(16) | queued, running, success, failed, skipped, interrupted |
| error | Text, nullable | 非成功结果的错误详情 |
| started_at | DateTime, nullable | 运行开始执行的时间 |
| finished_at | DateTime, nullable | 运行达到终态的时间 |

## 轮询与认领

-
-
-

## 分发与启动生命周期

### 线程解析

### 重叠处理

- **快速路径**：`has_active_runs(task_id)` 查询任何 `queued`/`running` 行。这是非原子的 —— 它在单独的会话中运行，在检查和随后的 `create()` 之间存在 await 间隙。
- **原子保障**：部分唯一索引 `uq_scheduled_task_run_active` 拒绝第二次并发的 `create()` 调用，并作为 `ActiveScheduledRunConflict` 抛出。此异常会被捕获，并以与快速路径相同的方式处理。

### 启动及启动后的簿记

## 运行完成处理

| RunRecord 状态 | 任务运行状态 | once 任务状态 | cron 任务状态 | 记录错误 |
|---|---|---|---|---|
| success | success | completed | (无变化) | 已清除 |
| error / timeout | failed | failed | (无变化) | 已设置 |
| interrupted | interrupted | cancelled | (无变化) | 从记录中设置 |

## 崩溃恢复与启动协调

-
-

## REST API 接口

| 方法 | 路径 | 权限 | 描述 |
|---|---|---|---|
| GET | /api/scheduled-tasks | threads:read | 列出认证用户的所有任务 |
| POST | /api/scheduled-tasks | threads:write | 创建新的计划任务 |
| GET | /api/scheduled-tasks/{task_id} | threads:read | 按 ID 获取单个任务 |
| PATCH | /api/scheduled-tasks/{task_id} | threads:write | 更新任务字段（提示词、调度、时区等） |
| POST | /api/scheduled-tasks/{task_id}/pause | threads:write | 暂停任务（状态 → paused） |
| POST | /api/scheduled-tasks/{task_id}/resume | threads:write | 恢复已暂停的任务（状态 → enabled） |
| POST | /api/scheduled-tasks/{task_id}/trigger | threads:write | 手动触发立即执行 |
| DELETE | /api/scheduled-tasks/{task_id} | threads:write | 永久删除任务 |
| GET | /api/scheduled-tasks/{task_id}/runs | threads:read | 列出执行历史（分页，最大 200 条） |
| GET | /api/threads/{thread_id}/scheduled-tasks | threads:read | 列出限定于特定线程的任务 |

### 创建请求模式

### 手动触发行为

### 暂停/恢复与可变性保护

## 配置

| 参数 | 来源 | 默认值 | 用途 |
|---|---|---|---|
| poll_interval_seconds | config.scheduler | — | 轮询周期之间的休眠时长 |
| lease_seconds | config.scheduler | — | 认领在变得可被重新认领前持有的时长 |
| max_concurrent_runs | config.scheduler | — | 跨所有任务的活跃计划运行的全局上限 |
| min_once_delay_seconds | config.scheduler | — | 创建 once 任务的最小未来时间 |

## 状态机

## 后续步骤

- **** —— `handle_run_completion` 消费的运行生命周期事件流经 stream bridge。
- **** —— `reuse_thread` 任务的线程上下文依赖于检查点存储。
- **** —— 计划任务路由器所依赖的权限模型和请求级配置解析。
- **** —— 将分发的任务连接到 agent 编排层的 `assistant_id: "lead_agent"` 连接配置。
