# 内置技能目录

## 技能架构概览

```
skill-name/
├── SKILL.md              ← 必需：YAML 前置元数据 + Markdown 指令
├── scripts/              ← 可选：用于确定性任务的可执行 Python/JS 脚本
├── references/           ← 可选：按需加载的详细规范
├── templates/            ← 可选：输出模板
└── assets/               ← 可选：静态文件（图标、字体、报告模板）
```



## 技能分类概览

| 类别 | 技能 | 主要用例 |
|---|---|---|
| 调研与分析 | deep-research, github-deep-research, data-analysis, consulting-analysis | 多角度网络调研、仓库调查、结构化数据查询、咨询报告 |
| 学术 | academic-paper-review, systematic-literature-review | 单篇论文同行评审、多篇文献综述 |
| 内容生成 | newsletter-generation, podcast-generation, ppt-generation, code-documentation | 简报、音频播客、演示文稿、软件文档 |
| 媒体生成 | image-generation, music-generation, video-generation | AI 图像、歌曲和视频 |
| 设计与前端 | frontend-design, chart-visualization, web-design-guidelines | 生产级 UI、数据图表、UI 合规审查 |
| 技能元管理 | skill-creator, skill-reviewer, find-skills | 创建、审查和发现技能 |
| 平台与工具 | bootstrap, surprise-me, claude-to-deerflow, vercel-deploy-claimable | Agent 引导、创意组合、API 桥接、即时部署 |



## 调研与分析技能

### 深度调研

| 阶段 | 目标 | 关键动作 |
|---|---|---|
| 阶段 1：广泛探索 | 绘制领域全景 | 初步调查、确定维度、记录视角 |
| 阶段 2：深入挖掘 | 针对各维度进行定向调研 | 具体查询、多种表述、获取完整内容 |
| 阶段 3：多样性与验证 | 全面覆盖 | 事实/数据、示例、专家观点、趋势、对比、挑战 |
| 阶段 4：综合检查 | 验证充分性 | 检查清单：3-5 个角度？读取了完整来源？有具体数据？观点平衡？ |

### GitHub 深度调研

| 轮次 | 重点 | 使用的工具 |
|---|---|---|
| 第 1 轮 | GitHub API 原始数据 | github_api.py 脚本 |
| 第 2 轮 | 发现与概览 | 3-5 次网络搜索 |
| 第 3 轮 | 深入调查 | 5-10 次搜索 + web_fetch |
| 第 4 轮 | 深度分析 | 提交历史、Issue/PR 审查 |

### 数据分析

| 参数 | 必需 | 描述 |
|---|---|---|
| --files | 是 | Excel/CSV 文件的空格分隔路径 |
| --action | 是 | inspect、query 或 summary |
| --sql | 仅 query 时 | 要执行的 SQL 查询 |
| --table | 仅 summary 时 | 要汇总的表/工作表名称 |
| --output-file | 否 | 导出路径（自动识别 CSV/JSON/MD 格式） |

### 咨询分析

| 领域 | 典型框架 |
|---|---|
| 市场分析 | TAM-SAM-SOM、产品生命周期 |
| 品牌分析 | SWOT、蓝海战略 |
| 消费者洞察 | RFM 模型、消费者决策旅程 |
| 财务分析 | 杜邦分析、DCF、可比公司分析 |
| 行业研究 | 波特五力模型、产业价值链 |
| 投资尽职调查 | VRIO、基准对比 |



## 学术技能

### 学术论文评审

### 系统性文献综述

| 论文数量 | 批次 | 轮次 | 每轮子 Agent 数 |
|---|---|---|---|
| 1–5 | 1 | 1 | 1 |
| 6–10 | 2 | 1 | 2 |
| 11–15 | 3 | 1 | 3 |
| 16–20 | 4 | 2 | 3 + 1 |
| 21–25 | 5 | 2 | 3 + 2 |
| 26–30 | 6 | 2 | 3 + 3 |



## 内容生成技能

### 简报生成

### 播客生成

| 提供商 | 必需的环境变量 | 备注 |
|---|---|---|
| 火山引擎（默认） | VOLCENGINE_TTS_APPID, VOLCENGINE_TTS_ACCESS_TOKEN | VOLCENGINE_TTS_CLUSTER 可选 |
| MiniMax | MINIMAX_API_KEY | 单线程，可配置语音模型 |
| 强制覆盖 | PODCAST_GENERATION_PROVIDER=volcengine\|minimax | 显式指定提供商 |

### PPT 生成

| 风格 | 美学特征 | 最适用场景 |
|---|---|---|
| 玻璃拟物风 | 磨砂玻璃面板，鲜艳渐变 | 科技产品、AI/SaaS 演示 |
| 深色高级风 | 纯粹深黑，明亮点缀 | 高管演示、奢侈品牌 |
| 渐变现代风 | 大胆的网格渐变 | 初创企业、创意机构 |
| 新粗野主义风 | 原生态粗犷排版，高对比度 | 前卫品牌、面向 Z 世代 |
| 3D 轴测风 | 干净的轴测插图 | 科技讲解、产品特性 |
| 杂志编辑风 | 杂志级排版 | 年度报告、思想领导力 |
| 极简瑞士风 | 网格精准，负空间 | 建筑、设计公司 |
| 主题演讲风 | 苹果风格，电影感 | 主题演讲、产品发布 |

### 代码文档



## 媒体生成技能

### 图像生成

| 参数 | 必需 | 描述 |
|---|---|---|
| --prompt-file | 是 | JSON 提示词文件的绝对路径 |
| --reference-images | 否 | 空格分隔的参考图像路径 |
| --output-file | 是 | 输出图像的绝对路径 |
| --aspect-ratio | 否 | 宽高比（默认：16:9） |

### 音乐生成

### 视频生成



## 设计与前端技能

### 前端设计

### 图表可视化

| 类别 | 图表类型 |
|---|---|
| 时间序列 | 折线图、面积图、双轴图 |
| 比较类 | 条形图、柱状图、直方图 |
| 局部与整体 | 饼图、矩形树图 |
| 关系与流向 | 散点图、桑基图、韦恩图 |
| 地图 | 行政区划图、标点地图、路径地图 |
| 层级与树状 | 组织结构图、思维导图 |
| 专用图表 | 雷达图、漏斗图、水球图、词云图、箱线图、小提琴图、网络关系图、鱼骨图、流程图、电子表格 |

### Web 设计指南



## 技能元管理技能

### 技能创建器

| 操作 | skill_manage 动作 |
|---|---|
| 创建技能 | action="create" |
| 替换 SKILL.md | action="edit" |
| 局部编辑 | action="patch" |
| 删除技能 | action="delete" |
| 添加辅助文件 | action="write_file" |
| 移除辅助文件 | action="remove_file" |

### 技能审查器

### 技能发现



## 平台与工具技能

### 初始化引导

| 阶段 | 目标 | 关键提取信息 |
|---|---|---|
| 1. 你好 | 语言 + 第一印象 | 偏好语言 |
| 2. 关于你 | 身份特征与消耗精力的事物 | 角色、痛点、AI 名字、关系设定 |
| 3. 个性 | AI 应有的行为方式 | 核心特质、沟通风格、自主程度、反驳偏好 |
| 4. 深度 | 愿景、盲区与底线 | 长期愿景、失败哲学、边界 |

### 给我惊喜

### Claude 接入 DeerFlow

| 上下文模式 | 思维链 | 规划模式 | 子 Agent |
|---|---|---|---|
| Flash | ❌ | ❌ | ❌ |
| Standard | ✅ | ❌ | ❌ |
| Pro | ✅ | ✅ | ❌ |
| Ultra | ✅ | ✅ | ✅ |

### Vercel 部署 (可认领)



## 斜杠命令集成

| 保留标记 | 用途 |
|---|---|
| bootstrap, goal, help, memory, models, new, status | 系统控制命令 |



## 提供商依赖汇总

| 技能 | 默认提供商 | 备选提供商 | 关键环境变量 |
|---|---|---|---|
| image-generation | Gemini | MiniMax (image-01) | GEMINI_API_KEY / MINIMAX_API_KEY |
| video-generation | Gemini Veo | MiniMax (MiniMax-Hailuo-2.3) | GEMINI_API_KEY / MINIMAX_API_KEY |
| podcast-generation | 火山引擎 TTS | MiniMax TTS (speech-2.6-hd) | VOLCENGINE_TTS_APPID / MINIMAX_API_KEY |
| music-generation | MiniMax（仅此一项） | — | MINIMAX_API_KEY |



## 后续步骤

- **了解加载这些技能的系统**：阅读 ，以了解技能匹配、渐进式披露和技能生命周期在底层的运作方式。
- **构建你自己的技能**：遵循  指南，获取有关使用 `skill-creator` 元技能创建、测试和发布自定义技能的分步指南。
- **探索执行环境**：技能在沙盒文件系统中运行——请参阅 ，以了解本目录中提及的 `/mnt/skills/`、`/mnt/user-data/` 和 `/mnt/user-data/outputs/` 路径规范。
