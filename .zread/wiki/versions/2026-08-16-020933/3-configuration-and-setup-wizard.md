# 配置与设置向导

## 向导架构一览

## 向导的项目结构

```
scripts/
├── setup_wizard.py          ← 入口点：验证 TTY，编排 5 个步骤
├── configure.py             ← 非交互式引导 (make config)
├── doctor.py                ← 健康检查 (make doctor)
├── check.py                 ← 依赖检查器 (make check)
├── config-upgrade.sh        ← 配置版本迁移 (make config-upgrade)
└── wizard/
    ├── __init__.py
    ├── providers.py          ← 所有 LLM/搜索/抓取提供商定义
    ├── ui.py                 ← 终端 UI 基础组件 (箭头、密码输入、菜单)
    ├── writer.py             ← config.yaml + .env 文件生成
    └── steps/
        ├── __init__.py
        ├── llm.py            ← 步骤 1：LLM 提供商与模型选择
        ├── search.py         ← 步骤 2：网络搜索与抓取提供商
        ├── execution.py      ← 步骤 3：沙箱模式与工具权限
        └── channels.py       ← 步骤 4：IM 渠道启用
```

## Make 目标概览

| Make 目标 | 调用的脚本 | 用途 | 产出 |
|---|---|---|---|
| make setup | scripts/setup_wizard.py | 交互式 5 步向导 | config.yaml, .env, frontend/.env |
| make config | scripts/configure.py | 非交互式模板拷贝 | config.yaml (源自 config.example.yaml), .env, frontend/.env |
| make config-upgrade | scripts/config-upgrade.sh | 将新字段合并到旧配置中 | 更新后的 config.yaml + .bak 备份 |
| make check | scripts/check.py | 验证系统依赖 | 针对 Node.js 22+, pnpm, uv, nginx 的通过/失败报告 |
| make doctor | scripts/doctor.py | 深度配置 + 环境健康检查 | 包含可执行修复建议的多段落报告 |
| make install | Makefile 内联 | 安装所有项目依赖 | 后端 (uv sync), 前端 (pnpm install), pre-commit hooks |
| make setup-sandbox | scripts/setup-sandbox.sh | 预拉取沙箱容器镜像 | 本地缓存的 Docker 镜像 |

## 步骤 1：LLM 提供商选择

### 支持的 LLM 提供商

| 提供商 | 显示名称 | 默认模型 | API 密钥环境变量 | 思考 | 视觉 | 认证类型 |
|---|---|---|---|---|---|---|
| 火山引擎豆包 | Volcengine Doubao | doubao-seed-1-8-251228 | VOLCENGINE_API_KEY | ✅ | ✅ | API 密钥 |
| 火山引擎编程计划 | Volcengine Coding Plan | glm-5.2 | VOLCENGINE_API_KEY | ✅ | 视模型而定 | API 密钥 (多供应商) |
| OpenAI | OpenAI | gpt-5 | OPENAI_API_KEY | ❌ | ✅ | API 密钥 |
| OpenAI Responses API | OpenAI Responses API | gpt-5 | OPENAI_API_KEY | ❌ | ✅ | API 密钥 |
| Anthropic | Anthropic | claude-sonnet-4-20250514 | ANTHROPIC_API_KEY | ✅ | ✅ | API 密钥 |
| DeepSeek | DeepSeek | deepseek-v4-pro | DEEPSEEK_API_KEY | ✅ | ❌ | API 密钥 |
| Google Gemini | Google Gemini | gemini-2.5-pro | GEMINI_API_KEY | ❌ | ✅ | API 密钥 |
| Gemini OpenAI 兼容版 | Gemini OpenAI-compatible | google/gemini-2.5-pro-preview | GEMINI_API_KEY | ✅ | ✅ | API 密钥 + 网关 URL |
| Ollama Qwen3 | Ollama Qwen3 | qwen3:32b | 无 | ✅ | ❌ | 本地 (无密钥) |
| Ollama Gemma | Ollama Gemma | gemma4:27b | 无 | ✅ | ✅ | 本地 (无密钥) |
| 小米 MiMo | Xiaomi MiMo | mimo-v2.5-pro | MIMO_API_KEY | ✅ | ❌ | API 密钥 |
| Moonshot Kimi | Moonshot Kimi | kimi-k2.5 | MOONSHOT_API_KEY | ✅ | ✅ | API 密钥 |
| Novita AI | Novita AI | deepseek/deepseek-v3.2 | NOVITA_API_KEY | ✅ | ✅ | API 密钥 |
| MiniMax | MiniMax | MiniMax-M3 | MINIMAX_API_KEY | ✅ | 视模型而定 | API 密钥 |
| MiniMax CN | MiniMax CN | MiniMax-M3 | MINIMAX_API_KEY | ✅ | 视模型而定 | API 密钥 |
| OpenRouter | OpenRouter | google/gemini-2.5-flash-preview | OPENROUTER_API_KEY | ❌ | ❌ | API 密钥 |
| OrcaRouter | OrcaRouter | openai/gpt-5.5 | ORCAROUTER_API_KEY | ❌ | ❌ | API 密钥 |
| vLLM | vLLM | Qwen/Qwen3-32B | VLLM_API_KEY | ✅ | ❌ | API 密钥 (自托管) |
| MindIE | MindIE | Qwen3-Coder-480B-A35B-Instruct-Client | OPENAI_API_KEY | ❌ | ❌ | API 密钥 (自托管) |
| Codex CLI | Codex CLI | gpt-5.4 | 无 | ✅ | ❌ | 本地授权文件 |
| Claude Code OAuth | Claude Code OAuth | claude-sonnet-4-6 | 无 | ✅ | ❌ | OAuth 凭证 |
| 其他 OpenAI 兼容版 | Other OpenAI-compatible | gpt-4o | OPENAI_API_KEY | 用户指定 | ❌ | API 密钥 + 基础 URL |

## 步骤 2：网络搜索与抓取配置

### 网络搜索提供商

| 提供商 | 描述 | 需要 API 密钥 | 环境变量 |
|---|---|---|---|
| DuckDuckGo | 免费，无需密钥 | 否 | 无 |
| Tavily | 推荐，提供免费额度 | 是 | TAVILY_API_KEY |
| InfoQuest | 更高质量的垂直搜索 | 是 | INFOQUEST_API_KEY |
| Exa | 神经网络 + 关键词网络搜索 | 是 | EXA_API_KEY |
| Firecrawl | 通过 Firecrawl API 搜索与爬取 | 是 | FIRECRAWL_API_KEY |
| fastCRW | 兼容 Firecrawl，自托管或云端 | 是 | CRW_API_KEY |
| Brave Search | 独立索引，官方 API | 是 | BRAVE_SEARCH_API_KEY |
| GroundRoute | 一个密钥覆盖六大引擎并支持故障转移 | 是 | GROUNDROUTE_API_KEY |

### 网络抓取提供商

| 提供商 | 描述 | 需要 API 密钥 | 环境变量 |
|---|---|---|---|
| Jina AI Reader | 优秀的默认阅读器 | 否 | 无 |
| Exa | 需要 API 密钥 | 是 | EXA_API_KEY |
| InfoQuest | 需要 API 密钥 | 是 | INFOQUEST_API_KEY |
| Firecrawl | 搜索级爬取，输出 Markdown | 是 | FIRECRAWL_API_KEY |
| GroundRoute | 通过路由引擎抓取页面 | 是 | GROUNDROUTE_API_KEY |
| fastCRW | 兼容 Firecrawl 的抓取器，自托管或云端 | 是 | CRW_API_KEY |
| Crawl4AI | 自托管无头 Chromium，无需密钥 | 否 | 无 |

## 步骤 3：执行与安全配置

### 沙箱模式

| 模式 | 提供商类 | 隔离级别 | 适用场景 |
|---|---|---|---|
| 本地沙箱 | deerflow.sandbox.local:LocalSandboxProvider | 低 — 使用宿主机文件系统路径 | 最快的本地开发，受信任的工作流 |
| 容器沙箱 | deerflow.community.aio_sandbox:AioSandboxProvider | 较高 — 需要 Docker 或 Apple Container | 不受信任的代码，多租户，生产环境 |

### 工具权限开关

| 开关 | 默认值 | 描述 |
|---|---|---|
| 启用 bash 命令执行 | false | 添加 bash 工具 — Agent 可运行任意 Shell 命令 |
| 启用文件写入工具 | true | 添加 write_file 和 str_replace 工具 — Agent 可创建和修改文件 |

## 步骤 4：IM 渠道启用

### 支持的 IM 渠道

| 渠道 | 键值 | 描述 |
|---|---|---|
| Telegram | telegram | 通过你的 DeerFlow Bot 进行私信 |
| Slack | slack | 工作区消息与提及 |
| Discord | discord | 通过你的 DeerFlow Bot 收发服务器消息 |
| 飞书 / Lark | feishu | 通过你的 DeerFlow 应用收发消息 |
| 钉钉 | dingtalk | 通过你的 DeerFlow Bot 推送流消息 |
| 微信 | wechat | 通过你的 DeerFlow Bot 收发 iLink 消息 |
| 企业微信 | wecom | 通过你的 DeerFlow AI Bot 收发消息 |

## 步骤 5：配置文件生成

## 非交互式替代方案：`make config`

## 健康检查：`make doctor`

### Doctor 检查类别

| 类别 | 执行的检查 | 失败严重程度 |
|---|---|---|
| 系统要求 | Python 3.12+, Node.js 22+, pnpm, uv, nginx | 失败 |
| 配置文件 | config.yaml 存在，且可通过 AppConfig.from_file() 加载 | 失败 |
| 配置版本 | 用户 config_version 与 config.example.yaml 版本对比 | 警告 |
| 模型 | config.yaml 中至少存在一个模型条目 | 失败 |
| LLM API 密钥 | 环境中解析出每个 $ENV_VAR 引用 | 失败 |
| LLM 安装包 | 可导入所需的 LangChain 提供商包 | 失败 |
| LLM 认证 | Codex CLI / Claude Code OAuth 凭证文件存在 | 失败 |
| 网络搜索 | web_search 工具配置了有效的提供商 + 密钥 | 警告 |
| 网络抓取 | web_fetch 工具配置了有效的提供商 + 密钥 | 警告 |

## 配置版本升级：`make config-upgrade`

## 配置文件层级结构

| 文件 | 用途 | 创建者 | Git 忽略？ |
|---|---|---|---|
| config.example.yaml | 包含内联文档的完整参考模板 | 随仓库分发 | 否 |
| config.yaml | 你的当前活动配置 | make setup 或 make config | 是 |
| .env | API 密钥与凭证 | make setup 或 make config | 是 |
| frontend/.env | 前端环境变量 | make setup 或 make config | 是 |
| .env.example | .env 的模板 | 随仓库分发 | 否 |
| frontend/.env.example | frontend/.env 的模板 | 随仓库分发 | 否 |

## 终端 UI 体验

- **箭头键导航**：在支持 TTY 的 Unix 终端上，选项会呈现为交互式菜单，使用 `↑/↓` 移动，`Enter` 确认，数字键快速选择。被选中的选项会以反色高亮显示，并带有 `›` 标记。
- **数字回退**：在 Windows 或非 TTY 环境下，选项会呈现为带编号的列表，你只需输入数字并按 Enter 键即可。

## 完整设置演练

- **`make check`** — 验证是否已安装 Node.js 22+、pnpm、uv 和 nginx
- **`make setup`** — 运行交互式向导（5 个步骤，约 3 分钟）
- **`make install`** — 安装后端、前端 (pnpm install) 和 pre-commit hooks
- **`make doctor`** — 验证配置有效性并捕获任何缺失的环境变量
- **`make dev`** — 以开发模式启动所有服务并支持热重载

## 后续去向

- **** — 了解你刚才生成的配置是如何流入 DeerFlow 的 Agent 编排、沙箱和网关层的
- **** — 启动 DeerFlow 并向 Agent 发送你的第一条消息
- **** — 深入了解每个 LLM 提供商的 `use` 路径是如何解析为 LangChain 聊天模型类的，以及思考/视觉/推理标志如何影响运行时行为
- **** — 理解你在步骤 3 中选择的本地沙箱与容器沙箱对安全性的影响
- **** — 学习如何完成你在步骤 4 中发起的 IM 渠道凭证设置
