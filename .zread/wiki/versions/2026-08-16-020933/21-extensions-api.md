# 扩展 API

## 架构概览

## 公共契约接口

### API 版本控制与 `@extension` 装饰器

### 版本兼容性规则

| 契约阶段 | 兼容窗口 | 原因 |
|---|---|---|
| 1.0 之前 (0.x.y) | 相同的 major.minor，宿主 ≥ 声明 | 小版本可能包含破坏性变更；补丁为增量更新 |
| 1.0 及之后 (x.y.z) | 相同的主版本，宿主 ≥ 声明 | 同一主版本内契约只增不减 |
| 无法解析的版本 | 拒绝 | 不对无效标记进行静默放行 |

### 贡献者协议

| 协议 | 用途 | 关键方法 | 接收的数据 |
|---|---|---|---|
| MiddlewareContributor | 将中间件注入 Agent 栈 | contribute_middlewares(app_store, ctx) → Sequence[MiddlewarePlacement] | ExtensionData (app store), AgentBuildContext |
| TaskLifecycleContributor | 观察任务启动/停止事件 | on_task_start(app_store, task_store, info), on_task_stop(app_store, task_store, info, outcome) | ExtensionData (app + task), TaskInfo, TaskOutcome |
| SystemModelCallObserver | 观察系统级的 LLM 调用 | on_system_model_call(app_store, task_store, kind, request, result) | ExtensionData, SystemOperationKind, SystemModelRequest, SystemModelResult |

### 注册表协议

## 放置语义：中间件落点

### Placement 枚举

| 放置位置 | 轴 | 保证 |
|---|---|---|
| MODEL_LOGICAL | 模型，外层 | 位于重试和错误处理的外层。无论重试多少次，每次逻辑决策仅触发一次。 |
| MODEL_PHYSICAL | 模型，内层 | 位于每个转换请求的中间件内层。每次物理提供者调用均会触发；重试会重新进入此处。 |
| TOOL_VISIBLE | 工具，外层 | 位于截断、清理和错误包装的外层。观察模型最终看到的内容。 |
| TOOL_RAW | 工具，内层 | 紧邻真实的可调用边界。在任何处理之前观察工具的原始返回值。 |
| STANDARD | 两者均可 | 无前置/后置处理要求。不保证相对于其他 STANDARD 贡献者的相对顺序。 |

### AgentScope 与 MiddlewarePlacement

### 锚点表：从语义到索引

## 加载生命周期

### ExtensionSpec 与配置

| 字段 | 类型 | 默认值 | 描述 |
|---|---|---|---|
| use | str | （必填） | 入口点路径，例如 my_extension:install |
| config | dict[str, Any] | {} | 扩展私有配置，原样传递给 install() |
| required | bool | False | 当为 True 时，加载失败会中止启动，而不是被跳过 |

### 加载流程

### 故障放行与故障阻断

## 隔离机制：故障放行的中间件包装

### 接口镜像

### 故障遏制策略

| 故障点 | 行为 | 原因 |
|---|---|---|
| 前置处理程序（调用内部之前） | 调用下游处理程序一次 | 避免真实处理程序的重复执行 |
| 后置处理程序（内部返回之后） | 返回内部捕获的结果 | 防止扩展错误污染结果 |
| 处理程序故障 | 由图（Graph）的错误策略接管 | 扩展隔离机制不得掩盖真实的处理程序 Bug |

## 顺序不变性

## 状态管理：ExtensionData

### 类型键控存储

| 方法 | 签名 | 用途 |
|---|---|---|
| get | get[T](typ: type[T]) → T \| None | 读取类型化的值 |
| get_or_init | get_or_init[T](typ: type[T], init: Callable[[], T]) → T | 读取或延迟创建（init 在锁下运行） |
| set | set[T](value: T) → None | 按 type(value) 存储 |
| remove | remove[T](typ: type[T]) → T \| None | 移除并返回 |

### 运行时桥接

## 宿主策略投影

| 字段 | 类型 | 描述 |
|---|---|---|
| token_budget_enabled | bool | Token 预算是否启用 |
| max_input_tokens | int \| None | 输入 Token 限制 |
| max_output_tokens | int \| None | 输出 Token 限制 |
| max_total_tokens | int \| None | 总 Token 限制 |
| budget_warn_fraction | float \| None | 警告阈值比例 |
| budget_hard_fraction | float \| None | 硬性停止阈值比例 |
| max_subagents_per_run | int \| None | 每次主 Agent 运行的最大子 Agent 数 |

## 生命周期通知管道

### 通知函数

| 函数 | 触发条件 | 调用的贡献者 |
|---|---|---|
| notify_task_start() | 主 Agent 或子 Agent 执行开始 | TaskLifecycleContributor.on_task_start |
| notify_task_stop() | 主 Agent 或子 Agent 执行结束 | TaskLifecycleContributor.on_task_stop |
| notify_system_model_call() | 系统级模型调用完成 | SystemModelCallObserver.on_system_model_call |
| observe_system_model_call() | 包装系统模型调用 | 观察成功和失败路径 |

### 事件循环绑定

## 配置参考

## 整合起来：一个最小扩展

## 诊断与可观测性接口

## 接下来去哪

- **** —— 涵盖了 MCP 服务器配置、会话池和工具路由，它们与扩展在同一个 `extensions_config.json` 中并行运行
- **** —— 详细介绍了注入扩展贡献的宿主中间件栈，包括放置表引用的锚点中间件类型
- **** —— 通过统一的 `ExtensionsConfig` 配置的另一个扩展接口，专注于声明式技能包而不是编程式中间件贡献
- **** —— 获取完整的系统上下文，展示扩展如何处于 Agent 运行时和网关之间
