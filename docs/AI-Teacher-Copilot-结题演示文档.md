# AI Teacher Copilot 结题演示文档

> 项目:AI Teacher Copilot(智能作业批改系统)
> 技术底座:DeerFlow 2.0 就地扩展
> 文档日期:2026-09-02
> 数据与配置:真实 DeepSeek Anthropic API + 智谱 GLM-OCR + 阿里云 OSS 图片

---

## 1. 项目定位

面向中学教师的 **AI 作业批改与学情助手**:教师创建作业 → 学生上传单题图片 →
系统真实 OCR + AI 批改(数学步骤分 / 英语作文四维评分)→ 结果沉淀为结构化画像
与学情分析 → 教师通过自然语言提问(Copilot)获得诊断 / 讲评 / 分层练习建议。

- 场景:教师与班级(30 人),数学计算/解答题 + 英语作文
- 核心:确定性算法(ProfileAlgorithmV1 / AnalysisCalculationV1)+ 可解释批改

## 2. 技术架构(DeerFlow 底座 + 就地扩展)

```
DeerFlow 2.0(复用,核心零改动)
│
├── Agent 运行时(Lead Agent / Custom Agent)→ teacher-copilot
├── Tool/Skill 运行时 → 8 个业务 Tool + 4 个 SKILL.md
├── StreamBridge / Chat / HITL / Memory / Sub-Agent / Langfuse
│
├── Teacher Copilot(本项目,就地扩展 backend/app/teacher_copilot/)
│   ├── db(15 表 + 标准字典 + 题库 + 演示数据)
│   ├── grading(OCR → 数学步骤批改 / 英语两阶段 → 组装校验)
│   ├── services(ProfileAlgorithmV1 / AnalysisCalculationV1)
│   ├── tools(8 个 @tool)/ agents(SOUL/Middleware/对象解析/周度复盘/分层/审核)
│   └── api(作业/提交/批改/画像/分析路由,gateway 仅加一行 include_router)
│
├── 前端(frontend/src,对照 Figma 01-08 八页)
└── evals(评测世界 + 算法门禁 + 核心用例 + Behavior/Judge)
```

**关键决策**:DeerFlow 作为代码底座,Teacher Copilot 通过 Custom Agent / Tool /
Skill / Middleware / 业务模块 / 前端页面就地扩展;业务事实(Schema/算法)由本项目实现。

## 3. 交付的 8 个功能模块

| # | 模块 | 说明 |
|---|---|---|
| 1 | 作业创建/发布 | 三种出题来源(手动/图片/题库),数学难度预判,发布校验,可选截止时间 |
| 2 | 学生提交+真实批改 | 单图提交,后台异步,实时进度(SSE),刷新恢复,409 拦截,重交重置 |
| 3 | 数学批改 | OCR Block 证据 → LLM 动态步骤分(学生解法自由),错误 Block 原图定位 |
| 4 | 英语作文批改 | 固定四维 Rubric(内容/结构/语法/词汇,总分 20),两阶段(证据→评分) |
| 5 | 学情分析 | 作业分析(完成率/成绩分布/高错题/异常学生)+ 题目下钻 |
| 6 | 学生/班级画像 | mastery/weak/recurring/trend/难度表现(确定性算法) |
| 7 | 教师工作台 | 摘要卡/我的班级/最近作业(对照 Figma 01) |
| 8 | Teacher Copilot | 8 Tool + 4 Skill,对象解析/HITL,按需 Sub-Agent(周度复盘/分层/审核) |

## 4. 真实运行验证结果(2026-09-02)

**数据**:阿里云 OSS 图片(https://macro-oss1069.oss-cn-beijing.aliyuncs.com/sample_05_img_480_pert_5.1.png)
    真实 OCR(智谱 glm-ocr)+ 真实 LLM(DeepSeek anthropic v1/messages,deepseek-v4-flash)

| 链路 | 结果 |
|---|---|
| 教师建作业 | ✅ DRAFT → 加题(`difficulty:easy` 预判)→ PUBLISHED |
| 学生提交(数学) | ✅ OCR 2.2s / 11 blocks → LLM 批改 **10/10**,4 步骤,知识点 `transposition`=correct |
| 学生提交(英语) | ✅ 两阶段 → **5/20**,四维 1/1/2/1,3 语言错误,3 知识点 |
| 画像 API | ✅ attempt=1, avg=1.0, weak=0(单次成功不升级,符合金标准) |
| 作业分析 API | ✅ completion=0.0333, q001 attempt=1 avg=1.0 |
| 算法门禁 | ✅ Profile 6/6 + Analysis 5/5 |
| 后端模块 | ✅ 47/47 导入成功 |

## 5. 演示步骤(一键)

```bash
# 1. 后端(业务 API 独立入口,无需完整 Gateway)
cd deer-flow/backend && source .env
uvicorn app.teacher_copilot.api.app:app --port 8100

# 2. 前端(已 npm install)
cd frontend && npm run dev   # 打开 http://localhost:3000/workspace/teacher-copilot/dashboard

# 3. 演示主线
教师工作台 → 建作业/出题/发布 → 学生上传(OSS 图)→ 实时批改进度
→ 结果(数学步骤分/英语四维)→ 作业分析 → 班级/学生画像 → Copilot 提问
```

> 前端页面为对照 Figma 01-08 的演示实现;真实 Agent 对话经 DeerFlow Thread
> 接入后展示执行过程(当前 MVP 页面含占位)。

## 6. 关键排障记录(可复现)

**问题**:数学批改 LLM 返回空文本(JSON 解析失败),浪费 5 轮。

**根因**:DeepSeek Anthropic 兼容端点默认返回 `thinking` 块;长批改提示时
thinking 占满 `max_tokens`,text 块被截断为空。

**修复**:
```python
# llm.py 请求体
"thinking": {"type": "disabled"}   # 关键
"max_tokens": 8192
```
实测关闭 thinking 后 6 秒出完整 JSON(此前 60-140s 均失败)。

## 7. 宪法遵循摘要(10 条)

I 中文注释 ✓ II 中文文档 ✓ III DeerFlow 复用(21 点验证,核心零改动)
IV 图谱探索(codebase-memory)✓ V 不过度设计(mock 退路,无队列,无 RAG)
VI 参考 docs/00-08 ✓ VII 卡点及时上报(密钥/OSS 均报)✓ VIII Figma 设计稿对照
IX/X 长任务可观察(每阶段日志/耗时/重试)。

## 8. 待办 / 后续

- **图片上传**:学生图传 OSS 得公网 URL 后接入(已标注,ocr.py 待办)。
- **前端联调**:已完成 npm install;页面连 8100 API(见第 5 节)。
- **完整 DeerFlow Gateway**:`uv sync` + `make dev` 后 Agent 对话/工具真实接入。
- **评测增强**:L1-L7 Agent 核心用例待真实 Agent 运行后接入 Behavior Checker。
