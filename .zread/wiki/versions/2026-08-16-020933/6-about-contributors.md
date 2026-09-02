# 关于贡献者

## 核心维护者圈子

### Willem Jiang (@WillemJiang) —— 开源老兵

### MagicCube —— 架构师

### Henry Li (@henry19840301)

### xunliu (@xunliu)

## 博士级驱动的工程核心

### Daoyuan Li

### Nan Gao (@ggnnggez)

## 社区贡献者

| 贡献者 | 近期核心工作 | 领域 |
|---|---|---|
| ajayr | Honcho 记忆后端 (#4730) | 记忆系统 |
| Hao Zhe | OpenViking MCP 工具集成 (#4745) | MCP / 工具桥接 |
| ChiHaYa | 子 Agent 后台任务隔离 (#4758) | 子 Agent 执行 |
| AoHanBei | 企业微信 websocket 关闭 (#4762), Discord 输入状态清理 (#4752) | IM 渠道适配器 |
| Baldwinzc | Gateway turn_duration 戳记 (#4755) | Gateway / 消息管道 |
| icn5381 | E2B 沙箱账本元字段命名 (#4764) | 沙箱 |
| Ryker_Feng | Buzz 前端 (#4727), Lark 授权剪贴板 (#4767) | 前端 |
| MasonWight | 诊断路径解析 (#4736) | 开发工具 |

### Honcho 记忆后端：社区贡献质量的案例研究

- 实现了完整的 `HonchoMemoryManager`，支持用户级工作空间隔离、故障关闭身份验证，并通过 `asyncio.to_thread` 实现异步卸载
- 修复了评审中发现的**两个严重 Bug**：一是 `sanitize_id` 丢失精度导致的跨用户记忆泄漏；二是 `JSONDecodeError` 可能逃脱 `add()` 方法且无上游处理程序的异常遏制问题
- 新增了使用 SHA-256 后缀的防冲突 `_stable_id()` 派生方法
- 提供了 **37 个测试**，覆盖写入/读取/异步/生命周期/工厂发现等环节
- 更新了 README、配置示例和 AGENTS.md 中的文档

## AI 辅助开发的真实现状

## 治理演进

## 贡献者周围的生态系统

## 贡献者折射出的项目特质
