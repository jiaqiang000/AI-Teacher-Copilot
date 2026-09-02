# 模型提供商集成

## 架构概述

## 配置模式

| 字段 | 类型 | 默认值 | 用途 |
|---|---|---|---|
| name | str | (必填) | Agent 工厂和子 Agent 配置使用的唯一标识符 |
| display_name | str\|None | None | UI 下拉菜单的可读标签 |
| use | str | (必填) | 点分式类路径（例如 langchain_openai:ChatOpenAI） |
| model | str | (必填) | 特定于提供商的模型标识符 |
| supports_thinking | bool | False | 在 UI 和工厂中启用思考模式切换 |
| supports_vision | bool | False | 激活视觉/图像输入工具 |
| supports_reasoning_effort | bool | False | 允许透传 reasoning_effort（low/medium/high） |
| context_window | int\|None | None | 提示词+补全总容量，用于 UI 百分比指示器 |
| when_thinking_enabled | dict\|None | None | 开启思考时注入的额外 kwargs |
| when_thinking_disabled | dict\|None | None | 关闭思考时注入的额外 kwargs |
| stream_chunk_timeout | float\|None | None | 覆盖默认 240 秒的分块间超时时间 |

## 工厂内部机制：规范化流水线

### 思考模式解析

| 提供商家族 | 禁用策略 | 配置触发器 |
|---|---|---|
| OpenAI 兼容网关 | extra_body.thinking.type = "disabled" + reasoning_effort = "minimal" | when_thinking_enabled.extra_body.thinking |
| 原生 Anthropic | thinking = {"type": "disabled"} 作为直接构造函数 kwarg | when_thinking_enabled.thinking.type |
| vLLM / Qwen | chat_template_kwargs.thinking = False + enable_thinking = False | when_thinking_enabled.extra_body.chat_template_kwargs |
| 用户显式 | 用户在 when_thinking_disabled 中填写的任何内容 | when_thinking_disabled 不为 None |

### Base URL 别名规范化

### 流式分块超时注入

## 修补提供商模式

### 共享重放基础设施

### 提供商修补目录

| 提供商类 | 基类 | 保留字段 | 解决的问题 |
|---|---|---|---|
| PatchedChatDeepSeek | ChatDeepSeek | reasoning_content | DeepSeek/Kimi/豆包思考模型在多轮对话的所有助手消息中要求提供 reasoning_content |
| PatchedChatOpenAI | ChatOpenAI | thought_signature | 通过 OpenAI 兼容网关的 Gemini 会在工具调用时返回 thought_signature，必须原样回显 |
| PatchedChatMiMo | ChatOpenAI | reasoning_content | 小米 MiMo 在思考模式下返回 reasoning_content；同时修补流式增量和非流式结果 |
| PatchedChatMiniMax | ChatOpenAI | reasoning_content（来自 reasoning_details） | MiniMax 在 reasoning_split=true 时返回结构化的 reasoning_details；同时剔除不一致的用户消息名称 |
| PatchedChatStepFun | ChatOpenAI | reasoning / reasoning_content | StepFun 在流式和非流式路径下使用两个不同的字段名返回推理内容 |
| VllmChatModel | ChatOpenAI | reasoning | vLLM 0.19.0 丢弃非标准的 reasoning 字段；同时为 Qwen 模板规范化 thinking → enable_thinking |
| MindIEChatModel | ChatOpenAI | (XML 工具调用解析) | MindIE 使用 XML 风格的工具调用而非 OpenAI 函数调用格式；适配器将 XML 解析为 LangChain 字典 |
| ClaudeChatModel | ChatAnthropic | (OAuth + 缓存 + 预算) | Claude Code CLI OAuth 认证，带 4 断点预算的提示词缓存，自动思考预算调整 |
| CodexChatModel | BaseChatModel | (Responses API) | 针对 ChatGPT Codex Responses API 端点的自定义 HTTP 客户端；不兼容 OpenAI |

## 凭证自动加载

### Claude Code OAuth 凭证链

### Codex CLI 凭证

## 模型选择与 Agent 集成

| 调用位置 | 模型名称来源 | 思考状态 | 追踪 |
|---|---|---|---|
| 主 Agent (make_lead_agent) | 显式指定或配置默认值 | UI 切换 | attach_tracing=False (图根节点) |
| 子 Agent 执行器 | inherit 或显式覆盖 | 父级设置 | attach_tracing=True |
| 标题中间件 | 配置默认值 | False | attach_tracing=False (图根节点) |
| 记忆更新器 | 配置默认值 | False | attach_tracing=True |
| 临时工具 (oneshot_llm) | 显式指定 | False | attach_tracing=True |

## 支持的提供商配置示例

| 提供商 | use 类 | 认证密钥字段 | 端点字段 | 思考支持 |
|---|---|---|---|---|
| 火山引擎（豆包） | deerflow.models.patched_deepseek:PatchedChatDeepSeek | api_key: $VOLCENGINE_API_KEY | api_base | ✅ 通过 extra_body.thinking |
| OpenAI | langchain_openai:ChatOpenAI | api_key: $OPENAI_API_KEY | (默认) | ✅ 通过 use_responses_api |
| Anthropic Claude | langchain_anthropic:ChatAnthropic | api_key: $ANTHROPIC_API_KEY | (默认) | ✅ 通过 thinking.budget_tokens |
| Google Gemini（原生） | langchain_google_genai:ChatGoogleGenerativeAI | gemini_api_key: $GEMINI_API_KEY | (默认) | ❌ |
| Google Gemini（网关） | deerflow.models.patched_openai:PatchedChatOpenAI | api_key: $GEMINI_API_KEY | base_url | ✅ 通过 extra_body.thinking |
| Ollama（本地） | langchain_ollama:ChatOllama | (无) | base_url: http://localhost:11434 | ✅ 通过 reasoning: true |
| DeepSeek | deerflow.models.patched_deepseek:PatchedChatDeepSeek | api_key: $DEEPSEEK_API_KEY | (默认) | ✅ 通过 extra_body.thinking |
| Kimi (Moonshot) | deerflow.models.patched_deepseek:PatchedChatDeepSeek | api_key: $MOONSHOT_API_KEY | api_base | ✅ 通过 extra_body.thinking |
| 小米 MiMo | deerflow.models.patched_mimo:PatchedChatMiMo | api_key: $MIMO_API_KEY | base_url | ✅ 通过 extra_body.thinking |
| MiniMax | deerflow.models.patched_minimax:PatchedChatMiniMax | api_key: $MINIMAX_API_KEY | base_url | ✅ 通过 reasoning_details |
| StepFun | deerflow.models.patched_stepfun:PatchedChatStepFun | api_key: $STEPFUN_API_KEY | base_url | ✅ 通过 reasoning 字段 |
| vLLM（自托管） | deerflow.models.vllm_provider:VllmChatModel | (不定) | base_url | ✅ 通过 chat_template_kwargs |
| MindIE（华为） | deerflow.models.mindie_provider:MindIEChatModel | (不定) | base_url | ✅ 通过 XML 工具调用解析 |
| Claude Code (OAuth) | deerflow.models.claude_provider:ClaudeChatModel | (自动加载) | (默认) | ✅ 带有自动预算 |
| Codex CLI | deerflow.models.openai_codex_provider:CodexChatModel | (自动加载) | (固定端点) | ✅ 通过 reasoning_effort |

## 未知键检测与调试

## 后续步骤

- — 主 Agent 如何选择并委派给模型
- — 子 Agent 如何继承或覆盖模型选择
- — `context_window` 如何驱动压缩决策
- — `attach_tracing` 如何控制跨度发送
