# 终端工作台 (TUI)

## 架构概述

## 启动模式与 CLI 接口

| 标志 | 模式 | 描述 |
|---|---|---|
| (无，检测到 TTY) | tui | 完整的交互式终端 UI |
| --tui | tui | 即使没有 TTY 也强制启动 TUI |
| --tui-transparent | tui | 使用终端的默认背景色 |
| --print [MSG] | print | 无头模式一次性运行：打印最终答案并退出 |
| --json [MSG] | json | 无头流式传输：换行符分隔的 JSON StreamEvents |
| --cli | print | 为单次调用强制使用无头模式 |
| --continue | (任意) | 恢复最近的线程 |
| --resume THREAD | (任意) | 通过 ID 或标题恢复线程 |
| --recursion-limit N | (无头模式) | Agent 循环超级步限制（默认：100） |

## 视图状态 Reducer：纯核心

### 行类型

| 行类型 | 用途 | 关键字段 |
|---|---|---|
| UserRow | 用户输入 | text |
| AssistantRow | Agent 响应（流式或最终） | text, id, error |
| ToolRow | 工具调用生命周期卡片 | tool_call_id, tool_name, title, detail, result, status |
| SystemRow | 系统消息（信息/错误） | text, tone |

### 动作类型与状态转换

## 运行时桥接层：从流式传输到动作

| 流事件类型 | 数据键 | 触发的 Reducer 动作 |
|---|---|---|
| messages-tuple | type=ai | AssistantDelta + ToolStarted（每个工具调用） |
| messages-tuple | type=tool | ToolResult |
| end | usage | RunEnded |
| values | title | ThreadTitle |
| custom | (任意) | (无 —— 不进行增量渲染) |

## Textual 应用外壳

### 组件组合

### 快捷键

| 按键 | 动作 | 上下文 |
|---|---|---|
| Enter | 提交消息 / 接受调色板项 | 输入框（或调色板开启时） |
| Ctrl+C | 中断运行或退出 | 全局（优先） |
| Ctrl+L | 重绘屏幕 | 始终 |
| Ctrl+U | 清空输入框内容 | 始终 |
| ↑ / ↓ | 导航调色板（开启时）或输入历史（关闭时） | 输入框 |
| Tab | 补全高亮命令 | 调色板开启时 |
| Esc | 关闭调色板 / 中断运行 | 调色板开启或流式传输时 |

### 流式工作线程化

## 斜杠命令系统

### 内置命令

| 命令 | 描述 |
|---|---|
| /help | 显示命令和快捷键 |
| /new | 开始新线程 |
| /clear | 清除对话记录显示 |
| /threads 或 /switch | 打开线程切换器模态框 |
| /resume [id\|title] | 通过 ID 或标题恢复线程 |
| /goal [set\|status\|clear] | 管理活动目标 |
| /model | 打开模型选择器模态框 |
| /skills | 列出已启用的技能 |
| /tools | 显示工具信息 |
| /mcp | 显示 MCP 服务器状态 |
| /memory | 显示记忆事实和首要事项 |
| /uploads | 显示此线程的上传文件 |
| /artifacts | 显示生成的产出物 |
| /details | 切换详细渲染模式 |
| /usage | 显示 token 使用量 |
| /config | 显示解析后的配置路径 |
| /quit | 退出 TUI |

## 渲染层

### 工具卡片渲染

| 状态 | 符号 | 颜色 | 含义 |
|---|---|---|---|
| running | ◐ | warning (琥珀色) | 工具正在执行 |
| ok | ✓ | accent (绿色) | 工具成功完成 |
| error | ✗ | error (红色) | 工具返回错误 |

### 主题

| 元素 | 颜色 | 十六进制 |
|---|---|---|
| 背景 | 深海军蓝 | #1a1b26 |
| 面板 | 略浅的海军蓝 | #1f2335 |
| 用户说话者 | 蓝色 | #7aa2f7 |
| 助手说话者 | 浅薰衣草色 | #c0caf5 |
| 工具活动 | 紫色 | #bb9af7 |
| 主色/强调色 | 青色 / 绿色 | #7dcfff / #9ece6a |
| 警告（运行中） | 琥珀色 | #e0af68 |
| 错误 | 红色 | #f7768e |

## 会话与持久化桥接层

## 输入历史

## 模态覆盖层

## 模块依赖关系摘要

| 模块 | 依赖 Textual？ | 依赖 Rich？ | 职责 |
|---|---|---|---|
| cli.py | 否 | 否 | 启动规划，无头调度 |
| session.py | 否 | 否 | 客户端构建，线程解析 |
| persistence.py | 否 | 否 | 用于 Web UI 可见性的共享数据库写入器 |
| runtime.py | 否 | 否 | StreamEvent → Action 转换 |
| view_state.py | 否 | 否 | 纯 reducer，不可变状态 |
| command_registry.py | 否 | 否 | 斜杠命令标准化与解析 |
| message_format.py | 否 | 否 | 工具名称/详情/结果格式化 |
| input_history.py | 否 | 否 | 有界输入导航 |
| theme.py | 否 | 否 | 颜色和符号常量 |
| render.py | 否 | 是 | 从 ViewState 生成 Rich 可渲染对象 |
| widgets/composer.py | 是 | 否 | 自定义 Textual 输入组件 |
| app.py | 是 | 是 | Textual 应用外壳，线程化，快捷键处理 |

## 后续步骤

- 要了解 `DeerFlowClient` 流式事件在上游是如何产生的，请参阅 。
- 有关 TUI 会话层所依赖的检查点器和线程状态，请参阅 。
- 要了解填充 TUI 斜杠命令调色板的技能系统，请参阅 。
- 有关通过持久化桥接层与 TUI 共享线程可见性的 Web UI，请参阅 。
