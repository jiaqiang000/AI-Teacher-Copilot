# 子 Agent 执行引擎

## 架构概述

## 配置解析与子代理注册中心

| 字段 | 类型 | 默认值 | 用途 |
|---|---|---|---|
| name | str | — | 唯一标识符；由主控 Agent 的委派逻辑进行匹配 |
| description | str | — | 委派指南；告知主控 Agent 何时 使用该子代理 |
| system_prompt | str \| None | None | 作为单个 SystemMessage 注入的行为指令 |
| tools | list[str] \| None | None | 允许列表；None 表示继承所有父级工具 |
| disallowed_tools | list[str] \| None | ["task"] | 拒绝列表；始终在允许列表之后应用 |
| skills | list[str] \| None | None | 技能白名单；None = 启用所有，[] = 禁用所有 |
| model | str | "inherit" | 模型名称或 "inherit"（使用父级模型） |
| max_turns | int | 50 | 图递归限制；控制执行深度 |
| timeout_seconds | int | 900 | 基础兜底挂钟时间上限（内置代理会被全局默认值覆盖） |

## SubagentExecutor：生命周期与隔离

### 隔离事件循环架构

### 代理构建与工具组装

## 执行流程：从任务派发到结果传递

### 初始状态构建

### 流式循环

### 结果提取与防护上限处理

## 线程安全的结果管理

| 状态 | 终止状态 | 含义 |
|---|---|---|
| PENDING | 否 | 已创建但尚未启动 |
| RUNNING | 否 | 正在执行 |
| COMPLETED | 是 | 已完成并带有可用输出（可能带有 stop_reason） |
| FAILED | 是 | 在无可用输出情况下终止 |
| CANCELLED | 是 | 被父级/用户中断 |
| TIMED_OUT | 是 | 超出挂钟时间超时 |

## 步骤事件捕获与持久化

### 基于游标的去重系统

-
-
-

### 步骤载荷结构

## Token 用量收集

| 字段 | 来源 | 用途 |
|---|---|---|
| source_run_id | LangGraph run_id | 去重键；防止重放时重复计数 |
| caller | 构造器参数 ("subagent:<name>") | 父级日志的归属标签 |
| model_name | response_metadata.model_name | 产生响应的实际模型 |
| input_tokens | usage_metadata.input_tokens | 提示词 token 计数 |
| output_tokens | usage_metadata.output_tokens | 补全 token 计数 |
| total_tokens | usage_metadata.total_tokens | 总和（或计算的回退值） |
| cache_read_tokens | input_token_details.cache_read | 稀疏数据；仅在提供商报告缓存命中时出现 |

## 跨语言状态契约

### 契约字段

| 键 | 类型 | 必填 | 描述 |
|---|---|---|---|
| subagent_status | enum | 是 | 枚举值之一：completed、failed、cancelled、timed_out、polling_timed_out |
| subagent_stop_reason | enum | 否 | 上限原因：token_capped、turn_capped、loop_capped（v2 新增） |
| subagent_error | string | 否 | 人类可读的错误信息块（仅在非完成状态下出现） |
| subagent_result_brief | string | 否 | 有界（2000 字符）的结果预览（仅在 completed 时出现） |
| subagent_result_sha256 | string | 否 | 完整结果的 SHA-256 摘要（64 位小写十六进制字符） |
| subagent_model_name | string | 否 | 本次运行使用的实际模型标识符 |
| subagent_token_usage | object | 否 | 累积的 {input_tokens, output_tokens, total_tokens} |

### 遗留状态归一化

### 校验与完整性

## 工具过滤与授权

## 扩展生命周期集成

## 追踪与可观测性

## 超时与取消语义
