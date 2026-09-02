# IM 通道适配器

## 架构概述

## 安全模型：模式 A 与模式 B

| 维度 | 模式 A (Init Container) | 模式 B (Broker Sidecar) |
|---|---|---|
| 凭证位置 | 挂载至沙箱文件系统 | 仅限 sidecar；绝不进入沙箱 |
| CLI 二进制文件 | 通过 init container 暂存至 emptyDir | 由 sidecar 持有；沙箱仅获取 shim |
| 沙箱可见密钥？ | 是 — 可通过 cat 或数据窃取获取 | 否 — 仅可访问命令接口 |
| Shell 注入风险 | 直接执行 lark-cli | shell=False argv 列表；无 shell 解释 |
| 相对于 cwd 的文件 I/O | 支持（二进制文件可访问沙箱文件系统） | 不支持（sidecar 拥有独立文件系统） |
| 子命令黑名单 | 不适用 | 可通过 DEERFLOW_LARK_BROKER_DENY_SUBCOMMANDS 配置 |
| 并发控制 | 无 | 有界信号量（最大并发 8） |
| 请求大小限制 | 不适用 | 请求 1 MiB / 输出 4 MiB |
| 启用机制 | provisioner 上的 LARK_CLI_INIT_IMAGE | provisioner 上的 LARK_CLI_BROKER_IMAGE |
| 优先级 | 配置 broker 后被取代 | 两者均设置时优先生效 |

## Broker HTTP 契约与传输协议

### 端点概览

| 端点 | 方法 | 请求体 | 响应体 | 用途 |
|---|---|---|---|---|
| /v1/exec | POST | {"args": [...], "stdin_b64": "..."} | {"exit_code", "stdout_b64", "stderr_b64", "truncated"} | 执行 lark-cli 命令 |
| /v1/health | GET | — | {"ok": true} | 存活探针 |

### 请求处理流水线

### Shim 架构

## 凭证管理与授权流程

### 凭证目录树结构

```
~/.deer-flow/users/<user_id>/integrations/lark-cli/
├── config/                 │   ├── config.json         # 0o600 — {apps: [...], currentApp: "..."}
│   └── locks/              # 0o700 — per-credential file locks
└── data/                   # 0o700 — OAuth token storage
```

### 授权流程时序

## 技能包管理

### 受管 Lark 技能

| 类别 | 技能 |
|---|---|
| 通讯 | lark-im, lark-mail, lark-event |
| 文档 | lark-doc, lark-sheets, lark-slides, lark-wiki, lark-note, lark-markdown |
| 数据与存储 | lark-base, lark-drive |
| 生产力 | lark-calendar, lark-task, lark-approval, lark-attendance, lark-okr |
| 协作 | lark-contact, lark-apps, lark-shared |
| 会议 | lark-vc, lark-vc-agent, lark-minutes, lark-workflow-meeting-summary, lark-workflow-standup-report |
| 开发 | lark-openapi-explorer, lark-skill-maker |
| 可视化 | lark-whiteboard |

### 完整性校验

## 运行时配置与沙箱模式

### 运行时模式解析

| 模式 | 条件 | 就绪时机 | 凭证处理方式 |
|---|---|---|---|
| none | 非 AIO 沙箱提供者 | 永不就绪（沙箱中无 lark-cli） | 不适用 |
| gateway-download | 本地 AIO（无远程 provisioner） | sandbox-cli 目录校验通过 | 凭证目录挂载至沙箱 |
| init-container | 远程 provisioner，设置了 LARK_CLI_INIT_IMAGE | Provisioner 报告镜像已配置 | 凭证目录挂载至沙箱 |
| broker | 远程 provisioner，设置了 LARK_CLI_BROKER_IMAGE | Provisioner 报告 broker 已配置 | 凭证仅在 sidecar 中；沙箱中只有 shim |

### Broker 模式检测（热路径）

### Docker 镜像架构

## Provisioner 集成

### Provisioner 能力上报

### 环境配置

| 变量 | 作用域 | 默认值 | 用途 |
|---|---|---|---|
| LARK_CLI_INIT_IMAGE | Provisioner | "" (关闭) | 模式 A init container 镜像标签 |
| LARK_CLI_BROKER_IMAGE | Provisioner | "" (关闭) | 模式 B broker sidecar 镜像标签 |
| DEERFLOW_LARK_BROKER_DENY_SUBCOMMANDS | Broker sidecar | "" (无) | 逗号分隔的子命令黑名单 |
| DEERFLOW_LARK_BROKER_URL | Sandbox | http://127.0.0.1:8788 | Shim 用于连接 broker 的回环 URL |
| DEERFLOW_LARK_BROKER_PYTHON | Sandbox | (自动检测) | 为 shim 启动器固定 Python 解释器 |
| LARK_CLI_NPM_VERSION | Gateway Dockerfile | 1.0.65 | 固定的 lark-cli npm 版本 |
| LARK_CLI_VERSION | Broker/init 镜像 | v1.0.65 | 用于二进制文件下载的上游发行版标签 |

## 延伸阅读

- 要了解沙箱容器本身是如何构建的以及代码执行如何在其中流转，请参阅 。
- 有关公开集成状态并触发授权流程的 Gateway API 端点详情，请参阅 。
- 要了解 Redis 流桥接如何跨工作线程交付 SSE 事件（当 IM 通道服务按工作线程运行时相关），请参阅 。
- 有关受管 Lark 技能所插入的更广泛的技能系统架构，请参阅 。
