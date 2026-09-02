# 社区搜索提供商

## 提供者架构：`community` 模块契约

### 配置模式：如何声明提供者

| 字段 | 用途 | 示例 |
|---|---|---|
| name | LLM 看到的标准化工具名称 | web_search, web_fetch, image_search |
| group | 用于访问控制/过滤的工具组 | web, browser |
| use | 指向工具函数的点分导入路径 | deerflow.community.brave.tools:web_search_tool |
| model_extra | 特定于提供者的配置（API 密钥、限制等） | api_key, max_results, base_url, region |

### 运行时配置解析模式

## 提供者目录

| 提供者 | 工具 | 需要验证 | 默认？ | 核心特性 |
|---|---|---|---|---|
| DuckDuckGo (ddg_search) | web_search | 无 | ✅ 是 | 零配置，多后端聚合 |
| SearXNG (searxng) | web_search | 无（自托管） | 否 | 注重隐私的元搜索聚合 |
| Serper (serper) | web_search, image_search | SERPER_API_KEY | 否 | 通过 JSON API 获取实时 Google 搜索结果 |
| Brave Search (brave) | web_search, image_search | BRAVE_SEARCH_API_KEY | 否 | 独立索引，SSRF 安全的图片 URL |
| Tavily (tavily) | web_search, web_fetch | TAVILY_API_KEY | 否 | AI 优化的搜索与页面提取 |
| Exa (exa) | web_search, web_fetch | EXA_API_KEY | 否 | 神经网络与关键词搜索模式 |
| Firecrawl (firecrawl) | web_search, web_fetch | FIRECRAWL_API_KEY | 否 | 带内容提取的网页抓取 |
| GroundRoute (groundroute) | web_search, web_fetch | GROUNDROUTE_API_KEY | 否 | 跨 6 个引擎的元路由，支持故障转移 |
| InfoQuest (infoquest) | web_search, web_fetch, image_search | InfoQuest API key | 否 | 支持时间范围过滤的多工具提供者 |
| fastCRW (fastcrw) | web_search, web_fetch | CRW_API_KEY（仅云端） | 否 | 兼容 Firecrawl，可自托管的单一二进制文件 |
| Jina AI (jina_ai) | web_fetch | 无（免费层级） | ✅ 是（抓取） | 轻量级阅读器 API |
| Browserless (browserless) | web_fetch, web_capture | BROWSERLESS_TOKEN（云端） | 否 | 针对重 JS 页面的无头 Chrome |
| Crawl4AI (crawl4ai) | web_fetch | CRAWL4AI_TOKEN (≥0.9) | 否 | 自托管 Chromium，服务端清洗的 Markdown |
| DuckDuckGo Images (image_search) | image_search | 无 | ✅ 是 | 零配置图片搜索 |

## 深入解析：DuckDuckGo —— 默认搜索提供者

## 深入解析：Brave Search —— 带有 SSRF 防护的双工具提供者

## 深入解析：GroundRoute —— 带有引擎故障转移的元搜索

## 网页抓取提供者：页面提取层

| 提供者 | 渲染引擎 | 最适用场景 | SSRF 防护 |
|---|---|---|---|
| Jina AI | 服务端阅读器 API | 静态内容、文章、文档 | — |
| Tavily | client.extract() API | AI 摘要页面内容 | — |
| Exa | get_contents() API | 神经网络内容提取 | — |
| Browserless | 无头 Chrome | 重 JavaScript 单页应用 (SPA) | ✅ allow_private_addresses: false |
| Crawl4AI | 自托管 Chromium | 服务端清洗的 Markdown 输出 | ✅ allow_private_addresses: false |
| Firecrawl | 云端抓取器 | 结构化内容提取 | — |
| GroundRoute | 元层（mode=page） | 跨提取引擎的故障转移 | — |
| fastCRW | 可自托管二进制文件 | 兼容 Firecrawl，低开销 | ✅ allow_private_addresses: false |

## 提供者对比：结果标准化

| 提供者 | 标题字段 | URL 字段 | 内容/摘要字段 |
|---|---|---|---|
| DuckDuckGo | title | href / link | body / snippet |
| Brave | title | url | description |
| Serper | title | link | snippet |
| Tavily | title | url | content |
| Exa | title | url | highlights（拼接后） |
| SearXNG | title | url | content |
| GroundRoute | title | url | snippet |

## API 密钥解析策略

## 切换提供者：配置示例

## 下一步

- — 阐述外部 MCP 来源的工具如何与社区提供者一同加载、缓存，并在同一工具组装流水线中标记 MCP 元数据。
- — 介绍 LLM 提供者的并行架构，该架构同样采用 `use:` 导入路径模式和 `config.yaml` 声明策略。
- — 说明 Brave 和 Serper 提供者内置的 SSRF 防护如何与更广泛的安全中间件流水线协同运作，在工具输出到达 LLM 之前对其进行检查。
