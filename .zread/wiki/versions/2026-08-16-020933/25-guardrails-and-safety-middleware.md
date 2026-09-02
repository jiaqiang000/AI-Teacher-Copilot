# 护栏与安全中间件

## 架构概述：四层防御模型

## GuardrailMiddleware：工具调用拦截器

### GuardrailMiddleware 数据流转

### GuardrailRequest：授权上下文

| 字段 | 来源 | 用途 |
|---|---|---|
| tool_name | request.tool_call["name"] | 主要评估目标 |
| tool_input | request.tool_call["args"] | 基于参数的限制 |
| agent_id | passport 参数 | 用于多 Agent 范围界定的 Agent 身份 |
| thread_id | context["thread_id"] | 会话级别的策略控制 |
| is_subagent | context["is_subagent"] | 针对子 Agent 的特定限制 |
| user_id / user_role | context["user_id"] / context["user_role"] | 基于身份的 RBAC |
| oauth_provider / oauth_id | 运行时上下文 | SSO 身份关联 |
| run_id | context["run_id"] | 审计轨迹关联 |
| channel_user_id | context["channel_user_id"] | IM 渠道身份 |
| is_internal | context["is_internal"] | 内部调用者旁路逻辑 |
| authz_attributes | context["authz_attributes"] (规范化处理后) | 基于自定义属性的策略 |

### 故障关闭与故障开启语义

- **`fail_closed=True`**：中间件会生成一个拒绝决策，附带原因码 `oap.evaluator_error`，并在 RunJournal 中记录该事件且标记 `provider_error=True`，最后返回一个错误 `ToolMessage`，指示 Agent 选择替代方案。
- **`fail_closed=False`**：中间件会生成一个放行决策，附带相同的原因码，记录事件后，将调用转发给处理器。

### 审计轨迹：RunJournal 集成

## GuardrailProvider 协议：可插拔授权契约

### 内置提供者：AllowlistProvider

| 配置模式 | allowed_tools | denied_tools | 行为表现 |
|---|---|---|---|
| 全部允许（默认） | None | None/[] | 所有工具均放行 |
| 显式白名单 | ["web_search", "read_file"] | [] | 仅列表中的工具放行 |
| 显式拒绝 | None | ["update_agent"] | 除被拒绝的工具外均放行 |
| 全部拒绝 | [] | [] | 拒绝所有工具 |

## 两层授权架构

### 第一层：组装期能力过滤

### 第二层：运行时执行拒绝

### 基础设施工具旁路

### 异常传播设计

## RBAC 提供者：内置策略引擎

### 策略编译与校验

| 取值 | 语义 |
|---|---|
| 省略 | 允许全部（拒绝规则依然生效） |
| "*" 或 True | 允许全部（拒绝规则依然生效） |
| False | 拒绝全部 |
| ["tool_a", "tool_b"] | 显式白名单 |

### 资源类型映射

| 请求 resource | 配置键 | 示例 |
|---|---|---|
| tool | tools | web_search, read_file |
| model | models | gpt-4, claude-3 |
| skill | skills | code_review, translate |
| sandbox | sandbox | 沙箱访问 |
| mcp_server | mcp_servers | MCP server 名称 |
| route | routes | threads:read, runs:create |

### 决策语义

## 主体构建：单一身份构造器

## 网关认证：第一道防线

### 可信调用者的内部认证

### CSRF 防护：双重提交 Cookie 模式

## 路由授权：按资源粒度强制执行权限

### 基于提供者缓存的权限解析

| 场景 | 故障关闭行为 | 故障开启行为 |
|---|---|---|
| 提供者解析失败 | []（拒绝所有路由） | _ALL_PERMISSIONS（遗留的允许全部） |
| 提供者 aauthorize 抛出异常 | 权限拒绝 | 权限授予 |
| filter_resources 返回非列表类型 | 拒绝所有工具 | 保留原始工具集 |

## 沙箱边界安全

### 主机 Bash 管控

### 输出路径掩码

## 提供者解析与配置

| 配置字段 | 类型 | 默认值 | 作用 |
|---|---|---|---|
| enabled | bool | False | 主开关；为 False 时，所有授权逻辑将被旁路 |
| provider.use | str | — | 提供者的类路径（如 deerflow.authz.rbac:RbacAuthorizationProvider） |
| provider.config | dict | — | 提供者构造器的关键字参数（如 RBAC 的 roles 映射） |
| default_role | str | "user" | 当 user_role 缺失或为空时分配的角色 |
| fail_closed | bool | True | 决定提供者发生错误时的行为 |

## 跨层安全特性

## 延伸阅读

- **** — 探讨 `GuardrailMiddleware` 如何与 Agent 执行链中的其他中间件协同工作
- **** — 深入解析沙箱提供者架构与路径虚拟化机制
- **** — 详述包含 JWT、OIDC 及会话管理的完整网关认证流程
- **** — 了解防护事件如何通过 `MIDDLEWARE_GUARDRAIL_TAG` 在链路追踪流水线中呈现
