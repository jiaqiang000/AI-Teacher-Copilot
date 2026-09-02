# 网关 API 与认证

## 网关应用架构

## 三种认证信任源

| 信任源 | Header / Cookie | 验证方式 | 用例 | auth_source 值 |
|---|---|---|---|---|
| 内部 | X-DeerFlow-Internal-Token | 通过 secrets.compare_digest 进行常数时间比较 | IM 渠道工作进程、调度器、受信任的后端服务 | AUTH_SOURCE_INTERNAL |
| 会话 | access_token (HttpOnly cookie) | JWT 解码 + 数据库用户查找 + token_version 匹配 | 浏览器前端、拥有登录会话的 API 客户端 | AUTH_SOURCE_SESSION |
| 禁用认证 | 无 | 环境变量标志 DEER_FLOW_AUTH_DISABLED=1 | 本地开发、单用户测试 | AUTH_SOURCE_AUTH_DISABLED |

### 内部认证 — 受信任的后端调用方

### 会话认证 — HttpOnly Cookie 中的 JWT

### 禁用认证 — 开发旁路

## 请求认证管道

## JWT 令牌生命周期

## 会话 Cookie 策略

| 场景 | secure | max_age | 原因 |
|---|---|---|---|
| HTTPS + 记住我 | true | token_expiry_days * 86400 | secure_persistent |
| HTTP + localhost | false | token_expiry_days * 86400 | localhost_persistent |
| HTTP + DEER_FLOW_AUTH_ALLOW_INSECURE_PERSISTENT_COOKIE=1 | false | token_expiry_days * 86400 | operator_insecure_persistent |
| HTTP + 公网主机 (无环境变量标志) | false | None (会话) | public_http_session |
| 任意协议 + 禁用记住我 | 依协议而定 | None (会话) | session_requested |

## CSRF 防护

| 豁免路径 | 原因 |
|---|---|
| /api/v1/auth/login/local | 首次登录，尚无 CSRF 令牌 |
| /api/v1/auth/logout | 终止会话，而非创建 |
| /api/v1/auth/register | 首次注册，尚无 CSRF 令牌 |
| /api/v1/auth/initialize | 首次启动管理员设置 |
| /api/v1/auth/me | 只读端点 (GET) |
| /api/webhooks/* | 通过特定提供商的签名进行认证，而非 CSRF |

## 认证路由端点

| 端点 | 方法 | 需要认证 | 用途 |
|---|---|---|---|
| /api/v1/auth/login/local | POST | 否 | 带速率限制的邮箱/密码登录 |
| /api/v1/auth/register | POST | 否 | 自行注册（受 auth.local.allow_registration 控制） |
| /api/v1/auth/logout | POST | 否 | 清除会话 + CSRF Cookie |
| /api/v1/auth/me | GET | 是 | 当前用户信息 |
| /api/v1/auth/change-password | POST | 是 | 更改密码 + 使旧令牌失效 |
| /api/v1/auth/setup-status | GET | 否 | 是否存在管理员（按 IP 缓存，60秒 TTL） |
| /api/v1/auth/initialize | POST | 否 | 首次启动创建管理员（如已存在返回 409） |
| /api/v1/auth/providers | GET | 否 | 列出已启用的 SSO 提供商 |
| /api/v1/auth/oauth/{provider} | GET | 否 | 发起 OIDC 流程（302 重定向） |
| /api/v1/auth/callback/{provider} | GET | 否 | OIDC 回调（状态验证、令牌交换） |

### 速率限制

### 密码强度

## OIDC / SSO 集成

- **状态验证**：state 参数存储在已签名的 Cookie 中，并使用 `secrets.compare_digest` 进行比较以防止时序攻击。不匹配则返回 403。
- **PKCE (Proof Key for Code Exchange)**：当提供商配置中的 `pkce_enabled` 为 true 时，会生成一个 code verifier，并将其 SHA-256 挑战发送到授权请求中。verifier 存储在 state Cookie 中，并在令牌交换期间重放。
- **Nonce**：当 `nonce_enabled` 为 true 时，授权请求中会包含一个 nonce，并根据 ID 令牌的 `nonce` 声明进行验证。
- **签发方锁定**：发现响应的 `issuer` 字段必须与配置的签发方 URL 完全匹配，防止被篡改的发现文档将令牌验证重定向到攻击者控制的 JWKS URI。
- **防止开放重定向**：`next` 参数通过 `validate_next_param` 进行验证，仅允许同源的相对路径。

## 授权框架

### 权限模型

| 权限 | 资源 | 操作 | 用途 |
|---|---|---|---|
| threads:read | threads | read | 查看线程 |
| threads:write | threads | write | 创建/更新线程 |
| threads:delete | threads | delete | 删除线程 |
| runs:create | runs | create | 运行 agent |
| runs:read | runs | read | 查看运行 |
| runs:cancel | runs | cancel | 取消运行 |

### 主体构造

## AuthContext 与请求状态

## 首次启动设置流程

## 错误响应分类

| AuthErrorCode | HTTP 状态码 | 触发条件 |
|---|---|---|
| not_authenticated | 401 | 非公开路径上无有效会话 |
| invalid_credentials | 401 | 邮箱/密码错误，或禁用认证下更改密码 |
| token_expired | 401 | JWT exp 声明已过期 |
| token_invalid | 401 | JWT 签名不匹配、令牌格式错误或未找到用户 |
| email_already_exists | 400 | 使用已存在的邮箱注册 |
| system_already_initialized | 409 | 管理员已存在时调用 /initialize |
| registration_disabled | 403 | 配置阻止自行注册 |
| provider_not_found | 400 | 未知的 SSO 提供商 ID |

## 用户模型与提供者抽象

## 公开路径豁免

## 网关后续步骤
