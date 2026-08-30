# AI Teacher Copilot：03–05 数据基础、学习画像与 Teacher Agent Tools

## 3. 数据基础与学习画像模型

### 3.1 整体数据架构

```text
                        MySQL 数据层
                           │
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
Student Profile      Class Profile      即时分析
（学生画像）          （班级画像）          │
          │                │          ┌─────┴─────┐
          │                │          ↓           ↓
          │                │    Homework      Question
          │                │    Analysis      Analysis
          │                │   （作业分析）   （题目分析）
          │                │
          └────── Redis ───┘
                           │
                           ↓
                    Teacher Tools
                           ↓
                  Skills / Agent
```

核心原则：

```text
MySQL
= 业务事实的唯一事实源
+ Knowledge Point / Error Type 标准参考字典
+ Question Bank（题库资源）

Redis
= Student Profile（学生画像）
+ Class Profile（班级画像）的可重算缓存

Homework Analysis（作业分析）
Question Analysis（题目分析）
= 根据 MySQL 指定范围即时聚合

LLM
= 不负责计算业务事实
= 基于结构化数据进行解释、规划和生成
```

这里需要明确三类 MySQL 数据：

```text
业务事实
= Teacher / Student / Class / Homework / Question / Submission / GradingResult 等

标准参考字典
= Knowledge Point / Error Type Taxonomy

题库资源
= QuestionBankItem 及其知识点关联
```

题库资源不是“某个学生发生了什么”的业务事实，也不是画像缓存；它是系统可反复检索和复用的教学资源。

#### DeerFlow 数据职责边界

DeerFlow 在本项目中承担 Agent Harness、Tool / Skill Runtime、Memory、HITL、Sub-Agent、Streaming 和 Trace 等基础设施，但不替代本节定义的教育业务数据层。

```text
MySQL / Redis Profile / Analysis
= Teacher Copilot 教育业务事实与确定性派生学习状态

DeerFlow Memory
= 教师长期会话上下文

DeerFlow RunEventStore / Langfuse
= Agent 执行证据与 Trace
```

尤其必须区分：

```text
Redis Student Profile / Class Profile
≠ DeerFlow Memory
```

Profile 由 `ProfileAlgorithmV1` 基于当前有效 MySQL 事实确定性计算，可以删除并重算；Memory 保存教师偏好、教学风格等长期上下文，不能成为学生成绩、掌握度或薄弱知识点的事实源。

---

### 3.2 MySQL 数据模型：业务事实 + 标准参考字典 + 题库资源

保留业务事实表：

```text
teacher
student
class
class_student

homework
question
submission
ocr_result

grading_result
grading_result_knowledge_point
grading_result_error
```

当前不建立独立 `grading_task` 表。学生批改生命周期直接由 `submission` 保存：

```text
submission
= 当前答案
+ status
+ current_stage
+ error_code / error_message
+ submitted_at / started_at / finished_at / updated_at
```

同一学生同一道题只保留一个当前 Submission：

```text
UNIQUE(student_id, question_id)
```

重新提交规则与 `docs/01-business-domain-and-grading-workflow.md` 保持一致：

```text
PENDING / RUNNING
→ 禁止重新提交

SUCCEEDED / FAILED
→ 复用同一 Submission
→ 替换 image_url
→ 清除旧 OCRResult / GradingResult
→ 重置为 PENDING / QUEUED
→ 重新执行 Workflow
```

其中 `ocr_result` 保存当前 Submission 当前答案对应的 OCR 核心识别证据：

```text
Submission
    ↓
OCRResult
    ↓
GradingResult
```

当前 MVP 只要求持久化 OCR 的核心结果：

```text
md_results
layout_details
```

`layout_details` 直接以 JSON 保存，不拆分独立 `ocr_block` 表。数学 Workflow 会使用其中的 `index / label / content / bbox2d / width / height` 进行 Block 拼装和原图错误定位；完整 OCR Contract 与数学步骤评分流程统一见 `docs/01-business-domain-and-grading-workflow.md`，本文件不重复定义。

除业务事实外，MySQL 维护两张标准参考字典：

```text
knowledge_point
error_type
```

这两张表不是“某个学生发生了什么”的业务事实，而是整个系统用于生成、校验、统计和检索的稳定 Taxonomy（标准分类体系）。

MySQL 还维护独立题库资源：

```text
question_bank_item
question_bank_item_knowledge_point
```

它们与 Homework 中的 `question` 明确分离：

```text
question
= 已经属于某个 Homework、真正布置给学生的题

question_bank_item
= 系统题库中的可复用候选题
```

#### 3.2.1 Taxonomy 总体规则

Knowledge Point（知识点）与 Error Type（错误类型）统一采用两级结构：

```text
subject（学科）
    ↓
level = 1  大类
    ↓
level = 2  小类
    └── OTHER 兜底小类
```

`subject` 只是学科范围，不计算为分类层级。当前 MVP 不建设无限层级知识图谱，也不引入独立 Normalizer Agent、Mapping Agent、Embedding Mapping 或第二次 LLM 分类。

真正进入 `GradingResult`、Profile、Analysis 和 Tool 查询条件的，只允许是 `level = 2` 的标准 `knowledge_point_key / error_code`。

标准化发生在 Grading Workflow 内：

```text
Question.subject
        ↓
读取当前学科 Knowledge Point / Error Type Taxonomy
        ↓
将允许的标准 level=2 候选注入 Grading Prompt / Structured Output
        ↓
Grading Model
├── 选择 knowledge_point_key / error_code
└── 生成 raw_name / raw_type
        ↓
TaxonomyValidator
├── key / code 是否存在
├── subject 是否一致
└── 是否 level = 2
        ↓
GradingResultAssembler
        ↓
MySQL
```

这里不是“模型先自由生成名称，再由另一个 LLM 做语义映射”。模型在批改时直接从系统提供的标准候选中选择稳定 `key / code`，同时保留本次实际识别出的自然语言语义。

#### 3.2.2 Knowledge Point（知识点）标准字典

逻辑结构：

```text
knowledge_point
├── key
├── name
├── subject
├── parent_key
├── level
└── is_other
```

字段职责：

```text
key
= 稳定知识点标识

name
= 标准展示名称

subject
= math / english

parent_key
= level=2 指向所属 level=1 大类；level=1 为 null

level
= 1 / 2

is_other
= 是否为该大类的 OTHER 兜底项
```

例如数学：

```text
math.linear_equation（一元一次方程）          level=1
├── math.linear_equation.transposition（移项） level=2
├── math.linear_equation.combine_like_terms（合并同类项） level=2
└── math.linear_equation.other（其他）          level=2 / is_other=true
```

例如英语：

```text
english.grammar（语法）                       level=1
├── english.grammar.past_tense（一般过去时）   level=2
├── english.grammar.subject_verb_agreement（主谓一致） level=2
└── english.grammar.other（其他语法知识点）    level=2 / is_other=true
```

每个 level=1 大类至少保留一个 level=2 `OTHER`，用于覆盖当前标准字典尚未细分的具体知识点。第一版不继续向下建设第三层。

#### 3.2.3 Error Type（错误类型）标准字典

逻辑结构：

```text
error_type
├── code
├── name
├── subject
├── parent_code
├── level
└── is_other
```

例如数学：

```text
CALCULATION_ERROR（计算错误）          level=1
├── SIGN_ERROR（符号错误）             level=2
├── ARITHMETIC_ERROR（算术错误）       level=2
└── CALCULATION_OTHER（其他计算错误）  level=2 / is_other=true

REASONING_ERROR（推理错误）            level=1
├── INVALID_TRANSFORMATION（错误变形） level=2
├── MISSING_STEP（关键步骤缺失）       level=2
└── REASONING_OTHER（其他推理错误）    level=2 / is_other=true
```

例如英语：

```text
GRAMMAR_ERROR（语法错误）              level=1
├── TENSE_ERROR（时态错误）            level=2
├── SUBJECT_VERB_ERROR（主谓一致错误） level=2
├── ARTICLE_ERROR（冠词错误）          level=2
└── GRAMMAR_OTHER（其他语法错误）      level=2 / is_other=true
```

同样，每个大类保留一个 `OTHER` 兜底项；未被当前字典精确覆盖的错误不能自行创造新的 `error_code`。

#### 3.2.4 GradingResult 诊断事实表

`grading_result_knowledge_point` 保存某次当前有效批改中实际识别出的知识点事实：

```text
grading_result_knowledge_point
├── grading_result_id
├── knowledge_point_key
├── raw_name
├── performance
└── evidence
```

其中：

```text
knowledge_point_key
= 标准 level=2 key，用于聚合、检索和关联字典

raw_name
= 模型对本次实际知识点语义的自然语言概括
= 每条知识点事实都保存，不只在 OTHER 时保存
```

标准 `name` 不在事实表重复保存，需要展示时根据 `knowledge_point_key` 从 `knowledge_point` 字典读取。

`grading_result_error` 保存某次当前有效批改中实际识别出的错误事实：

```text
grading_result_error
├── grading_result_id
├── error_code
├── raw_type
├── knowledge_point_key
├── description
└── evidence
```

其中：

```text
error_code
= 标准 level=2 code，用于聚合、检索和关联字典

raw_type
= 模型对本次实际错误语义的简短自然语言概括
= 每条错误事实都保存，不只在 OTHER 时保存

description
= 对本次错误原因的展开说明

evidence
= 学生当前作答中的直接证据
```

标准 `type / name` 不在事实表重复保存，需要展示时根据 `error_code` 从 `error_type` 字典读取。

`raw_name / raw_type` 的职责是保留标准化没有表达完的具体语义，方便教师查看、事实下钻、工程排查和未来扩充 Taxonomy；它们不是长期统计主键。

#### 3.2.5 TaxonomyValidator

`TaxonomyValidator` 是普通后端确定性校验代码：

```text
TaxonomyValidator
≠ Agent
≠ Tool
≠ LLM
```

只负责检查：

```text
knowledge_point_key / error_code 是否存在
subject 是否与当前 Question.subject 一致
是否为 level = 2 可落库小类
```

非法 `key / code` 不允许原样写入 `grading_result_knowledge_point / grading_result_error`，应视为 Grading Output Contract 校验失败。具体模型重试策略属于 Workflow 工程实现，不在本数据模型中继续扩展。

#### 3.2.6 聚合与查询统一规则

后续 Student Profile、Class Profile、Homework Analysis、Question Analysis 和 Teacher Agent Tool 的统计维度统一使用：

```text
knowledge_point_key
error_code
```

需要按大类查看时，通过：

```text
knowledge_point.parent_key
error_type.parent_code
```

向上聚合。

以下字段不作为主要 `GROUP BY` / 画像聚合键：

```text
raw_name
raw_type
description
evidence
```

它们用于保留和展示具体业务语义。

#### 3.2.7 Question Bank（题库资源）

Question Bank 与 Homework Question 是两个不同对象。

```text
QuestionBankItem
= 系统可复用题库资源
= 可被多次检索和加入不同 Homework

Question
= 某次 Homework 中实际布置出去的题
= 学生 Submission 的直接目标
```

题库主表：

```text
question_bank_item
├── question_bank_item_id
├── subject
├── grade
├── question_type
├── difficulty
├── content
├── image_url
├── reference_answer
├── tags
├── created_at
└── updated_at
```

字段职责：

```text
question_bank_item_id
= 题库题稳定 ID

subject
= math / english

grade
= 年级标签，用于题库筛选

question_type
= 题型

difficulty
= 题库预先维护的稳定难度标签
= 当前数学使用 easy / medium / hard
= 英语作文当前可为 null

content
= 题目正文

image_url
= 题库题原图，可选

reference_answer
= 参考答案 / 参考作答

tags
= 其他自由辅助标签
= 不作为学习画像和主要统计主键
```

题库知识点不塞进自由 `tags`，统一关联已经存在的 Knowledge Point Taxonomy：

```text
question_bank_item_knowledge_point
├── question_bank_item_id
└── knowledge_point_key
```

约束：

```text
knowledge_point_key
= 必须引用标准 level=2 Knowledge Point

UNIQUE(question_bank_item_id, knowledge_point_key)
```

这样 Student / Class Profile 得到的标准 `knowledge_point_key` 可以直接用于题库检索，不需要再维护第二套知识点映射。

#### QuestionBankItem → Question

教师从题库中选择题目加入 Homework 时，不让 Homework 实时引用题库题，而是复制成新的 `Question`：

```text
QuestionBankItem qb_001
        ↓ Copy
Question q008
```

复制的核心题目属性：

```text
subject
question_type
difficulty
content
image_url
```

Homework 场景自己生成 / 确定：

```text
question_id
homework_id
question_no
max_score
```

并记录：

```text
Question.source_question_bank_item_id = qb_001
```

该字段只用于追踪来源，不形成实时同步关系：

```text
后续 QuestionBankItem 被修改
≠
已经存在 / 已经发布的 Question 跟着变化
```

当前 MVP 的 Question Bank 只要求系统预置 / Seed Data + MySQL 条件查询，不建设教师题库管理、题库审核、题库版本、自动生成、去重、向量检索或 RAG。

---

### 3.3 Student Profile（学生画像）

定位：描述一个学生在某个学科上的长期学习状态。

本节及后续 Profile / Analysis 中出现的 `knowledge_point_key / common_error_codes / error_code`，均指标准 Taxonomy 中可落库的 `level = 2` 编码；需要大类统计时通过标准字典父级关系向上聚合。

当前算法版本固定为：

```text
algorithm_version = profile_v1
```

```text
StudentProfile（学生画像）
│
├── basic（基础信息）
│   ├── student_id（学生ID）
│   ├── subject（学科）
│   ├── generated_at（生成时间）
│   ├── source_data_until（事实数据截止时间）
│   └── algorithm_version（算法版本；当前为 profile_v1）
│
├── overview（整体表现）
│   ├── attempt_count（累计作答次数）
│   ├── avg_score_rate（历史平均得分率）
│   ├── recent_score_rate（近期得分率，可为 null）
│   └── trend（学习趋势；证据不足时为 null）
│
├── knowledge_points[]（知识点画像）
│   ├── knowledge_point_key（知识点标识）
│   ├── attempt_count（作答次数）
│   ├── mastery（掌握度）
│   ├── recent_performance（近期表现，可为 null）
│   ├── trend（学习趋势；证据不足时为 null）
│   ├── last_practiced_at（最近练习时间）
│   └── common_error_codes[]（常见错误类型）
│
├── weak_points[]（薄弱知识点）
│   ├── knowledge_point_key（知识点标识）
│   ├── mastery（掌握度）
│   ├── trend（学习趋势；可为 null）
│   └── evidence_count（证据数量）
│
├── recurring_errors[]（重复错误）
│   ├── error_code（错误类型）
│   ├── knowledge_point_key（关联知识点）
│   ├── occurrence_count（累计出现次数）
│   ├── recent_occurrence_count（最近 28 天出现次数）
│   └── last_occurred_at（最近出现时间）
│
└── difficulty_performance（不同难度表现；英语为 null）
    ├── easy
    │   ├── attempt_count
    │   ├── avg_score_rate
    │   └── recent_score_rate
    ├── medium
    │   ├── attempt_count
    │   ├── avg_score_rate
    │   └── recent_score_rate
    └── hard
        ├── attempt_count
        ├── avg_score_rate
        └── recent_score_rate
```

数学返回上述 `easy / medium / hard` 三组统计；英语作文当前 `difficulty = null`，因此：

```text
difficulty_performance = null
```

---

### 3.4 Class Profile（班级画像）

定位：描述一个班级在某个学科上的长期整体学习状态。

```text
ClassProfile（班级画像）
│
├── basic（基础信息）
│   ├── class_id（班级ID）
│   ├── subject（学科）
│   ├── generated_at（生成时间）
│   ├── source_data_until（事实数据截止时间）
│   └── algorithm_version（算法版本；当前为 profile_v1）
│
├── overview（整体表现）
│   ├── student_count（学生总数）
│   ├── active_student_count（有效学习学生数）
│   ├── avg_score_rate（历史平均得分率）
│   ├── recent_score_rate（近期得分率，可为 null）
│   └── trend（学习趋势；证据不足时为 null）
│
├── knowledge_points[]（知识点画像）
│   ├── knowledge_point_key（知识点标识）
│   ├── participating_student_count（参与学生数）
│   ├── attempt_count（总作答次数）
│   ├── avg_mastery（平均掌握度）
│   ├── recent_performance（近期表现，可为 null）
│   ├── weak_student_count（薄弱学生数）
│   ├── trend（学习趋势；证据不足时为 null）
│   └── common_error_codes[]（常见错误）
│
├── weak_points[]（班级薄弱知识点）
│   ├── knowledge_point_key（知识点标识）
│   ├── avg_mastery（平均掌握度）
│   ├── weak_student_count（薄弱学生数）
│   └── trend（学习趋势；可为 null）
│
├── common_errors[]（班级常见错误）
│   ├── error_code（错误类型）
│   ├── affected_student_count（涉及学生数）
│   ├── occurrence_count（出现次数）
│   └── knowledge_point_key（关联知识点）
│
└── attention_students[]（重点关注学生）
    ├── student_id（学生ID）
    ├── weak_point_count（薄弱知识点数量）
    ├── recent_score_rate（近期整体得分率，可为 null）
    ├── trend（学习趋势；可为 null）
    └── reason_codes[]（关注原因）
```

Class Profile（班级画像）中不保存：

```text
某次作业情况
高错题
某次作业完成率
某次作业分数分布
```

这些数据属于 Homework Analysis（作业分析）。

---

### 3.5 Homework Analysis（作业分析）

定位：分析某个班级的一次具体作业。

```text
HomeworkAnalysis（作业分析）
│
├── homework_id（作业ID）
├── class_id（班级ID）
├── subject（学科）
│
├── completion（完成情况）
│   ├── assigned_student_count（布置人数）
│   ├── submitted_student_count（提交人数）
│   └── completion_rate（完成率）
│
├── performance（成绩表现）
│   ├── graded_student_count（完整批改学生数）
│   ├── avg_score_rate（平均得分率）
│   └── score_distribution（成绩分布）
│       ├── below_60
│       ├── from_60_to_79
│       ├── from_80_to_89
│       └── from_90_to_100
│
├── knowledge_points[]（知识点表现）
│   ├── knowledge_point_key（知识点标识）
│   ├── participating_student_count（参与学生数）
│   ├── avg_performance（本次平均表现）
│   └── low_performance_student_count（本次低表现学生数）
│
├── questions[]（题目表现）
│   ├── question_id（题目ID）
│   ├── question_no（题号）
│   ├── attempt_count（有效作答人数）
│   ├── avg_score_rate（平均得分率）
│   ├── error_student_count（出现结构化错误的学生数）
│   ├── error_rate（错误率）
│   └── common_error_codes[]（常见错误）
│
└── attention_students[]（本次作业即时异常候选学生）
    ├── student_id（学生ID）
    ├── homework_score_rate（本次作业得分率；未完整批改时可为 null）
    ├── reason_codes[]（即时异常原因）
    └── related_question_ids[]（关联异常题目）
```

Homework Analysis（作业分析）默认从 MySQL 当前有效事实即时计算，不作为长期画像持久化。

其中：

```text
low_performance_student_count
= 只表示本次 Homework 中该知识点表现较低的学生数量

attention_students
= 只表示本次 Homework 的即时异常候选学生
```

它们均不等于 `ProfileAlgorithmV1` 的长期：

```text
weak_point
ClassProfile.attention_students
```

具体计算口径统一由 3.8 `AnalysisCalculationV1` 定义。

---

### 3.6 Question Analysis（题目分析）

定位：分析某个班级在某次作业中的一道具体题。

分析范围：

```text
class
+
homework
+
question
```

结构：

```text
QuestionAnalysis（题目分析）
│
├── question_id（题目ID）
├── question_no（题号）
├── homework_id（作业ID）
├── class_id（班级ID）
│
├── attempt_count（有效作答人数）
├── avg_score_rate（平均得分率）
├── error_student_count（出现结构化错误的学生数）
├── error_rate（错误率）
│
├── knowledge_points[]（涉及知识点）
│   ├── knowledge_point_key（知识点标识）
│   ├── participating_student_count（参与学生数）
│   ├── avg_performance（本题平均表现）
│   └── low_performance_student_count（本题低表现学生数）
│
├── common_errors[]（常见错误）
│   ├── error_code（错误类型）
│   ├── knowledge_point_key（关联知识点）
│   ├── occurrence_count（出现次数）
│   └── affected_student_count（涉及学生数）
│
└── representative_errors[]（典型错误证据）
    ├── student_id（学生ID）
    ├── error_code（错误类型）
    ├── knowledge_point_key（关联知识点）
    ├── raw_type（本次原始错误语义）
    ├── description（错误描述）
    └── evidence（真实错误证据）
```

题目分析用于作业分析后的进一步下钻：

```text
Homework Analysis（作业分析）
        ↓
发现某道题异常
        ↓
Question Analysis（题目分析）
        ↓
继续下钻具体错误和学生
```

所有字段的确定性计算规则统一由 3.8 `AnalysisCalculationV1` 定义。

---

### 3.7 存储与计算边界

```text
MySQL
├── 业务事实
│   ├── Teacher / Student / Class / Homework / Question
│   ├── Submission / OCRResult / GradingResult
│   ├── GradingResult Knowledge Point 事实
│   └── GradingResult Error 事实
│
├── 标准参考字典
│   ├── Knowledge Point Taxonomy
│   └── Error Type Taxonomy
│
└── 题库资源
    ├── question_bank_item
    └── question_bank_item_knowledge_point

Redis
├── Student Profile（学生画像）
└── Class Profile（班级画像）

实时聚合
├── Homework Analysis（作业分析）
└── Question Analysis（题目分析）
```

其中：

```text
Submission
= 学生当前答案
+ 当前批改 status / current_stage

OCRResult
= OCR 对当前 Submission 当前答案识别出的证据

GradingResult
= 当前 Submission 成功完成 Workflow 后的最终批改事实

Knowledge Point / Error Type Taxonomy
= 系统标准参考字典
= 不表示某个学生本次发生了什么

QuestionBankItem
= 系统可复用题库资源
= 不等于某次 Homework 中已经布置的 Question
```

`Submission` 是学生侧当前批改状态事实源，不另建 `grading_task` 事实表。`OCRResult` 属于可追溯的批改证据数据，不进入 Student / Class Profile 聚合核心指标；Profile 仍以 `GradingResult` 的稳定结构化事实作为主要输入。

Student Profile（学生画像）与 Class Profile（班级画像）的生成方式：

```text
MySQL Facts
    ↓
ProfileAlgorithmV1
    ↓
Redis Snapshot
```

两类画像均为可重算派生数据，可以删除、重新生成和升级算法版本，不承担业务事实的审计职责。

Class Profile（班级画像）直接从 MySQL 事实聚合，不以 Redis 中的 Student Profile（学生画像）作为事实源。

```text
MySQL
├──→ Student Profile（学生画像）
└──→ Class Profile（班级画像）
```

为保证重新提交后画像不会继续引用已删除的旧批改结果，缓存失效规则固定为：

```text
新的当前 GradingResult 成功写入
OR
重新提交时旧 GradingResult 被删除
        ↓
删除 / 失效对应 Student Profile 缓存
+
删除 / 失效对应 Class Profile 缓存
        ↓
下次 Tool 读取 Redis Miss
        ↓
从 MySQL 当前有效事实重新计算
```

当前 MVP 不为画像刷新额外引入 MQ、定时任务或独立后台计算系统，使用“事实变化时失效 + 下次读取惰性重算”即可。

再次明确：DeerFlow Memory 不参与上述 Profile 计算，也不保存 Student / Class Profile Snapshot。画像缓存只属于 Teacher Copilot Redis 数据层。

---

### 3.8 AnalysisCalculationV1

`AnalysisCalculationV1` 是当前 Homework Analysis / Question Analysis 的唯一确定性即时聚合规则。

```text
MySQL 当前有效事实
        ↓
AnalysisCalculationV1
        ↓
HomeworkAnalysis / QuestionAnalysis
        ↓
Teacher Agent Tool
```

LLM、Skill 和 Agent 不得在运行时重新定义本节公式或阈值。

#### 3.8.1 有效事实范围

成绩、知识点和错误统计只使用：

```text
Submission.status = SUCCEEDED
AND
当前 GradingResult 仍然存在
```

以下数据不进入这些统计：

```text
PENDING
RUNNING
FAILED
重新提交时已删除的旧 GradingResult
```

本节不重新定义 `completion.assigned_student_count / submitted_student_count / completion_rate` 的业务口径。

#### 3.8.2 Question 基础统计

对指定 `class_id + homework_id + question_id`：

```text
attempt_count
= 存在当前有效 SUCCEEDED GradingResult 的不同学生数

avg_score_rate
= 所有当前有效 GradingResult.score.rate 的算术平均
= attempt_count = 0 时为 null

error_student_count
= diagnosis.errors[] 非空的不同学生数

error_rate
= error_student_count / attempt_count
= attempt_count = 0 时为 null
```

`error_student_count` 不使用 `score.rate < 1` 判断。是否存在结构化错误统一以 `diagnosis.errors[]` 为准。

#### 3.8.3 performance 标准化

Analysis 与 Profile 使用相同的单次表现值映射：

```text
correct   → 1.0
partial   → 0.5
incorrect → 0.0
```

但 Analysis 不使用 Profile 的时间权重和难度权重。

#### 3.8.4 Question Knowledge Point

对当前题某个 `knowledge_point_key`：

```text
participating_student_count
= 至少有 1 条该知识点 observation 的学生数

avg_performance
= participating students 的 performance 数值算术平均

low_performance_student_count
= performance < 0.60 的学生数
```

这里的 `low_performance_student_count` 只表示当前题表现，不产生长期 `weak_point`。

#### 3.8.5 Homework Knowledge Point

同一个知识点可能出现在 Homework 的多道 Question。

先对每个：

```text
student_id + homework_id + knowledge_point_key
```

计算：

```text
student_homework_kp_performance
= 该学生本次 Homework 中
  该知识点所有当前有效 performance 数值的算术平均
```

然后：

```text
participating_student_count
= 至少有 1 条该知识点有效 observation 的学生数

avg_performance
= participating students 的
  student_homework_kp_performance
  再取算术平均

low_performance_student_count
= student_homework_kp_performance < 0.60
  的学生数
```

这里同样不得把一次作业的低表现直接升级为长期 `weak_point`。

#### 3.8.6 Homework 成绩表现

只有 Homework 中每一道 Question 都存在该学生当前有效 SUCCEEDED GradingResult 时，该学生才属于：

```text
fully graded student
```

因此：

```text
graded_student_count
= fully graded students 数量
```

对一个 fully graded student：

```text
student_homework_score_rate
=
Σ GradingResult.score.earned
/
Σ GradingResult.score.max
```

Homework：

```text
avg_score_rate
= 所有 fully graded students 的
  student_homework_score_rate
  算术平均
```

如果：

```text
graded_student_count = 0
```

则：

```text
avg_score_rate = null
```

#### 3.8.7 Score Distribution

只统计 fully graded students。

```text
[0.00, 0.60)
→ below_60

[0.60, 0.80)
→ from_60_to_79

[0.80, 0.90)
→ from_80_to_89

[0.90, 1.00]
→ from_90_to_100
```

每个字段保存学生人数。

#### 3.8.8 Common Errors

QuestionAnalysis `common_errors[]` 按精确二元组：

```text
(error_code, knowledge_point_key)
```

聚合。

```text
occurrence_count
= 当前题该错误二元组的 Error 事实出现次数

affected_student_count
= 出现过该错误二元组的不同学生数
```

排序：

```text
affected_student_count DESC
→ occurrence_count DESC
→ error_code ASC
→ knowledge_point_key ASC
```

HomeworkAnalysis `questions[].common_error_codes[]` 是题目摘要，只按 `error_code` 聚合：

```text
affected_student_count DESC
→ occurrence_count DESC
→ error_code ASC
```

最多返回 Top 3。

HomeworkAnalysis `questions[]` 默认按：

```text
question_no ASC
```

返回。

#### 3.8.9 Representative Errors

QuestionAnalysis 从已经排好序的 `common_errors[]` 中取 Top 3 error group。

每个 error group 返回 1 条真实 `grading_result_error` 证据。

候选学生按：

```text
当前题 score.rate ASC
→ student_id ASC
```

选择。

返回：

```text
student_id
error_code
knowledge_point_key
raw_type
description
evidence
```

所有 representative error 必须来自真实 MySQL Error 事实，不允许 LLM 生成。

#### 3.8.10 Homework Attention Students

`HomeworkAnalysis.attention_students` 只表示当前 Homework 的即时异常候选，不等于长期 `ClassProfile.attention_students`，也不等于最终 `weekly_attention_students`。

原因码固定为：

```text
LOW_HOMEWORK_SCORE
HIGH_ERROR_QUESTION
```

`LOW_HOMEWORK_SCORE`：

```text
fully graded
AND
student_homework_score_rate < 0.60
```

首先定义：

```text
high_error_question
=
QuestionAnalysis.error_rate != null
AND
QuestionAnalysis.error_rate >= 0.50
```

某学生如果：

```text
在 high_error_question 上
diagnosis.errors[] 非空
```

则：

```text
reason_codes += HIGH_ERROR_QUESTION
related_question_ids += 当前 question_id
```

`homework_score_rate`：

```text
fully graded
→ student_homework_score_rate

不是 fully graded
→ null
```

`attention_students[]` 返回全部命中候选，不在 Analysis 层截断 Top N。

排序固定为：

```text
reason_codes 数量 DESC
→ homework_score_rate ASC（null 排最后）
→ student_id ASC
```

#### 3.8.11 即时与长期语义边界

必须严格区分：

```text
Homework / Question low_performance
= 当前一次作业 / 当前一道题表现

HomeworkAnalysis.attention_students
= 当前一次作业即时异常候选

ProfileAlgorithmV1 weak_point
= 长期薄弱知识点

ClassProfile.attention_students
= 长期画像重点关注学生

weekly_attention_students
= Teacher Lead Agent 综合长期画像
  + 本周多份 Homework Analysis
  后形成的周度业务结果
```

AnalysisCalculationV1 不产生长期画像结论。

#### 3.8.12 精度与空值

以下数值对外输出统一四舍五入到 4 位小数：

```text
avg_score_rate
student_homework_score_rate
avg_performance
error_rate
```

所有阈值判断必须使用未四舍五入的原始值。

没有有效数据时使用：

```text
null
```

不得自动写成 `0`。

---

## 4. 学习画像算法与长期个性化

### 4.1 ProfileAlgorithmV1

`ProfileAlgorithmV1` 是当前 Student Profile / Class Profile 的唯一确定性画像算法定义：

```text
algorithm_version = profile_v1
```

Agent、Skill 和 Tool 不得在运行时自行修改这些公式或阈值。

#### 4.1.1 输入与有效事实范围

画像只使用 MySQL 中**当前有效、成功完成**的批改结果：

```text
Submission.status = SUCCEEDED
AND
当前 GradingResult 仍然存在
```

以下数据不进入画像：

```text
PENDING
RUNNING
FAILED
重新提交时已删除的旧 GradingResult
```

三类输入职责严格分开：

```text
GradingResult.score.rate
→ overview / difficulty_performance

grading_result_knowledge_point.performance
→ knowledge point mastery / recent_performance / trend / weak_point

grading_result_error.error_code + knowledge_point_key
→ recurring_error / common_error
```

知识点画像不得用整题 `score.rate` 代替 `performance`。

#### 4.1.2 时间窗口

所有时间窗口相对于本次画像计算的 `as_of`（默认等于 `generated_at`）确定：

```text
recent window
= (as_of - 14 days, as_of]

previous window
= (as_of - 28 days, as_of - 14 days]

recurring error recent window
= (as_of - 28 days, as_of]
```

测试环境必须固定 `as_of`，避免同一 Fixture 在不同日期产生不同结果。

#### 4.1.3 performance 标准化

`GradingResult.diagnosis.knowledge_points[].performance` 固定映射为：

```text
correct   → 1.0
partial   → 0.5
incorrect → 0.0
```

记一次知识点观察的标准表现值为 `p_i`。

#### 4.1.4 Student Overview

对某个 `student_id + subject`：

```text
attempt_count
= 当前有效成功 GradingResult 数量

avg_score_rate
= 所有当前有效 GradingResult.score.rate 的算术平均

recent_score_rate
= recent window 内 score.rate 的算术平均
= recent window 无数据时为 null
```

Student Overview 的 `trend` 同样采用 4.1.6 的趋势规则，但输入信号使用整题 `score.rate`，不是知识点 `performance`。

#### 4.1.5 Knowledge Point Mastery

对某个 `student_id + subject + knowledge_point_key` 的每一次知识点观察：

```text
p_i = performance 映射值
w_i = time_weight_i × difficulty_weight_i
```

时间权重固定为：

```text
距 as_of <= 14 天      → 1.0
15–28 天               → 0.8
> 28 天                → 0.6
```

难度权重固定为：

```text
Math easy    → 0.8
Math medium  → 1.0
Math hard    → 1.2
English null → 1.0
```

掌握度公式：

```text
mastery
= Σ(p_i × w_i) / Σ(w_i)
```

示例：

```text
最近 easy correct
p1 = 1.0, w1 = 1.0 × 0.8 = 0.8

20 天前 medium partial
p2 = 0.5, w2 = 0.8 × 1.0 = 0.8

40 天前 hard incorrect
p3 = 0.0, w3 = 0.6 × 1.2 = 0.72

mastery
= (1.0×0.8 + 0.5×0.8 + 0×0.72) / (0.8+0.8+0.72)
= 1.2 / 2.32
= 0.5172
```

`attempt_count` 为该知识点当前有效历史观察次数；`last_practiced_at` 为最近一次该知识点观察时间。

#### 4.1.6 Recent Performance 与 Trend

Knowledge Point 的 `recent_performance`：

```text
= recent window 内该知识点 p_i 的算术平均
```

这里**不使用时间权重和难度权重**；它只表达最近两周学生在该知识点上的直接近期状态。

```text
recent window 无该知识点观察
→ recent_performance = null
```

趋势计算：

```text
recent_value
= recent window 内信号平均值

previous_value
= previous window 内信号平均值
```

只有当两个窗口都至少有 `2` 个观察时才计算：

```text
recent_count < 2
OR previous_count < 2
→ trend = null
```

否则：

```text
delta = recent_value - previous_value

delta >= 0.10  → improving
delta <= -0.10 → declining
其他            → stable
```

应用位置：

```text
Student overview trend
→ 信号 = score.rate

Student knowledge point trend
→ 信号 = performance 映射值 p_i
```

Class Profile 的 trend 由 4.1.10 定义的班级聚合信号按同一阈值计算。

#### 4.1.7 Weak Point

某学生某知识点只有同时满足以下条件才进入 `weak_points`：

```text
attempt_count >= 3
AND
mastery < 0.60
```

因此：

```text
attempt_count = 1 或 2
即使 mastery 很低
也不能判定为长期 weak_point
```

字段规则：

```text
weak_points[].evidence_count
= 对应知识点 attempt_count
```

排序固定为：

```text
mastery ASC
→ evidence_count DESC
→ knowledge_point_key ASC
```

#### 4.1.8 Recurring Error

重复错误的统计主键固定为精确二元组：

```text
(error_code, knowledge_point_key)
```

不再使用“相同或相关知识点”这种不可执行判断。

某二元组进入 `recurring_errors` 的条件：

```text
最近 28 天 recent_occurrence_count >= 2
```

字段定义：

```text
occurrence_count
= 当前有效全部历史中的累计出现次数

recent_occurrence_count
= 最近 28 天出现次数

last_occurred_at
= 最近一次出现时间
```

Student `knowledge_points[].common_error_codes` 只统计与该知识点关联的错误，并仅保留：

```text
历史 occurrence_count >= 2
```

按：

```text
occurrence_count DESC
→ error_code ASC
```

最多返回 `3` 个错误编码。

#### 4.1.9 Difficulty Performance

仅数学计算：

```text
difficulty_performance.easy / medium / hard
```

每个难度分别计算：

```text
attempt_count
= 该难度当前有效 GradingResult 数量

avg_score_rate
= 该难度全部 score.rate 平均

recent_score_rate
= recent window 内该难度 score.rate 平均
= recent window 无数据时 null
```

英语作文当前 `difficulty = null`，因此：

```text
difficulty_performance = null
```

#### 4.1.10 Class Aggregation

Class Profile 仍然**直接从 MySQL 当前有效事实计算**：

```text
MySQL Facts
→ ProfileAlgorithmV1
→ Class Profile
```

实现时可以在内存中计算与 Student Profile 同公式的“每学生中间值”，但不得读取 Redis Student Profile 作为 Class Profile 的事实输入。

班级整体：

```text
student_count
= class_student 中当前班级学生数量

active_student_count
= 至少有 1 个当前有效成功 GradingResult 的学生数量
```

为避免做题次数多的学生对班级均值产生过度影响：

```text
class overview.avg_score_rate
= 每个 active student 的个人 avg_score_rate 再取算术平均

class overview.recent_score_rate
= 对 recent_score_rate 非 null 的学生再取算术平均
= 无任何近期学生数据时 null
```

对某个知识点：

```text
participating_student_count
= 至少有 1 条该知识点有效观察的学生数量

attempt_count
= 全班该知识点有效观察总次数

avg_mastery
= participating students 的个人 knowledge point mastery 算术平均

recent_performance
= 对个人 recent_performance 非 null 的 participating students 取算术平均
= 无近期数据时 null

weak_student_count
= 满足个人 weak_point 规则的学生数量
```

班级知识点趋势按“每学生窗口均值 → 班级窗口均值”的方式得到 recent / previous 信号，再使用 4.1.6 的 `±0.10` 阈值；任一窗口没有足够班级证据时 `trend = null`。

Class `common_errors[]` 按精确 `(error_code, knowledge_point_key)` 聚合：

```text
affected_student_count
= 至少出现过该错误二元组的学生数量

occurrence_count
= 全班当前有效历史出现总次数
```

#### 4.1.11 Class Weak Point 与 Attention Students

某知识点进入 Class `weak_points` 需要先满足：

```text
participating_student_count >= 3
```

并且满足以下任一条件：

```text
avg_mastery < 0.60
OR
weak_student_count / participating_student_count >= 0.30
```

Class Profile 的长期 `attention_students` 只基于长期画像规则产生。候选原因码固定为：

```text
LOW_RECENT_SCORE
= recent_score_rate != null AND recent_score_rate < 0.60

DECLINING_TREND
= overview.trend = declining

MULTIPLE_WEAK_POINTS
= weak_point_count >= 2

RECURRING_ERROR
= recurring_errors 非空
```

命中任一原因即成为候选。

最多返回 Top 10，排序固定为：

```text
reason_codes 数量 DESC
→ recent_score_rate ASC（null 排最后）
→ weak_point_count DESC
→ student_id ASC
```

这里的 `ClassProfile.attention_students` 是长期画像关注对象，不等于某一周 Teacher Lead Agent 基于本周 Homework Analysis 再筛选出来的“周度重点学生”。

#### 4.1.12 精度、空值与输出规则

以下数值对外输出统一四舍五入到 `4` 位小数：

```text
mastery
avg_mastery
avg_score_rate
recent_score_rate
recent_performance
```

所有阈值判断必须使用**未四舍五入的原始计算值**，不能先 round 再判断 `< 0.60 / ±0.10`。

没有足够数据时使用 `null` 表达“无法判断”，不要自动写成 `0` 或 `stable`。

---

### 4.2 长期个性化反馈

长期个性化反馈不是持久化业务事实，也不直接写入 Student Profile（学生画像）。

运行时流程：

```text
Current GradingResult（当前批改结果）
        +
当前题 Knowledge Points（知识点）
        +
Student Profile（学生画像）相关部分
        +
Recurring Errors（重复错误）
        +
近期相关 Grading History（批改历史）
        ↓
Personalized Feedback Context
（个性化反馈上下文）
        ↓
LLM
        ↓
长期个性化反馈
```

上下文选择只读取与当前题相关的学生历史状态和事实证据，不将学生完整历史记录全部发送给 LLM。

---

## 5. Teacher Agent Tools（教师 Agent 工具）

Teacher Agent 完整能力规划包含 9 个核心 Tool（工具）。Tool 按业务对象和能力边界划分，不按单个统计字段拆分。

当前阶段暂不建设 RAG / Teaching Knowledge Base，因此 `search_teaching_materials` 仅保留 Tool Contract，不进入当前实现范围。当前阶段实际实现其余 8 个 Tool。

本节所有 `knowledge_point_key / knowledge_point_keys / error_code / common_error_codes` 均使用 3.2 定义的标准 `level = 2` 编码。Tool 不以 `raw_name / raw_type` 作为主要统计或过滤标识；需要返回具体历史诊断证据时，可以同时返回这些 raw 字段。

其中新增的两个业务对象发现 Tool：

```text
list_class_students（查询班级学生列表）
= 枚举一个班级的真实成员

list_class_homeworks（查询班级作业列表）
= 按班级 / 学科 / 时间范围发现作业
```

它们只负责发现业务对象，不负责画像计算或学情分析。

### DeerFlow Tool Runtime 复用边界

本节定义的是 **Teacher Copilot 业务 Tool Contract**；真正的 Tool 注册、Schema 暴露、Agent 调用生命周期直接复用 DeerFlow Harness，不再自建第二套 Tool Registry。

```text
Teacher Lead Agent
        ↓
DeerFlow Tool Runtime
        ↓
Teacher Copilot Tool Adapter
        ↓
Service
        ↓
Repository
        ↓
MySQL / Redis
```

职责固定为：

```text
DeerFlow 负责：
- ToolConfig 配置与 Tool group
- BaseTool 装载
- Tool Schema 暴露给 LLM
- Agent Tool Calling Runtime
- Runtime Context 传递

Teacher Copilot 负责：
- 本节定义的业务输入 / 输出 Contract
- Service 业务逻辑
- ProfileAlgorithmV1
- AnalysisCalculationV1
- 教师数据权限校验
- Repository / MySQL / Redis
```

因此 Tool 层本身保持很薄，不在 DeerFlow Tool 函数中重新堆 SQL、Redis 和画像公式。

### 5.0 业务对象解析边界

Teacher Agent 的正式业务 Tool 仍然使用明确的业务 ID 作为输入，例如：

```text
student_id
class_id
homework_id
question_id
```

教师不需要感知这些内部 ID。教师自然语言中的：

```text
“张三”
“八三班”
“这次作业”
“第 8 题”
```

由 Teacher Lead Agent 在正式 Tool Calling 之前完成业务对象解析。

解析原则固定为：

1. 优先使用当前 Teacher Business Context（教师业务上下文）中已经确定的对象；
2. 需要发现班级学生时使用 `list_class_students`；
3. 需要发现班级作业时使用 `list_class_homeworks`；
4. 唯一匹配时直接继续；
5. 存在多个候选、无法唯一确定时，通过 DeerFlow `ask_clarification` 请求教师确认；
6. Teacher Agent 不得猜测 `student_id`、`class_id`、`homework_id` 或 `question_id`。

例如教师说“第 8 题”时，系统先基于当前 `homework_id` 和 `Question.question_no = 8` 确定真实 `question_id`，再调用 `get_question_analysis`。

Teacher Business Context 通过 DeerFlow `RunCreateRequest.context` 携带；但“把值放进 runtime context”不等于 LLM 自动可见，具体由 `TeacherBusinessContextMiddleware` 注入模型上下文。该 Middleware、Custom Agent 和 HITL 的完整实现统一见 `docs/06-07-业务驱动的设计.md`。

业务对象解析属于正式 Tool Calling 前的参数准备，不改变 Tool 本身的职责，也不新增 Entity Resolution Tool / Skill / Agent。

---

### 5.1 `get_student_profile`

**作用**

获取学生在某个学科上的长期学习状态，包括整体表现、知识点掌握、薄弱知识点、重复错误和不同难度表现。

**输入参数**

```text
student_id（学生ID）        必填
subject（学科）             必填
sections（返回模块）        可选
```

`sections（返回模块）` 支持：

```text
overview（整体表现）
knowledge_points（知识点画像）
weak_points（薄弱知识点）
recurring_errors（重复错误）
difficulty_performance（不同难度表现）
```

**输出**

```text
StudentProfile（学生画像）
```

返回的：

```text
basic.algorithm_version = profile_v1
```

**数据来源**

```text
ProfileService
↓
Redis Student Profile Snapshot
↓ Redis Miss
ProfileAlgorithmV1
↓
MySQL 当前有效事实
```

Tool 不现场临时发明 mastery / weak_point / recurring_error 规则；这些派生字段只能来自 `ProfileAlgorithmV1`。

---

### 5.2 `get_student_grading_history`

**作用**

查询学生真实历史批改事实，为 Student Profile（学生画像）中的结论提供事实证据和下钻能力。

**输入参数**

```text
student_id（学生ID）                  必填
subject（学科）                       可选
knowledge_point_key（标准二级知识点标识） 可选
error_code（标准二级错误类型）        可选
homework_id（作业ID）                 可选
start_time（开始时间）                可选
end_time（结束时间）                  可选
limit（返回数量）                     可选
```

**输出**

```text
GradingResult[]（历史批改结果列表）
```

返回内容包括：

```text
题目
学生作答
得分
知识点表现（含标准 key/name 与 raw_name）
错误（含标准 code/type 与 raw_type）
当前题反馈
批改时间
```

**数据来源**

```text
MySQL
```

定位：

```text
Student Profile（学生画像）
= 长期结论

Grading History（批改历史）
= 原始事实与证据
```

---

### 5.3 `get_class_profile`

**作用**

获取班级在某个学科上的长期整体学习状态，包括整体表现、知识点状态、薄弱知识点、常见错误和重点关注学生。

**输入参数**

```text
class_id（班级ID）          必填
subject（学科）             必填
sections（返回模块）        可选
```

`sections（返回模块）` 支持：

```text
overview（整体表现）
knowledge_points（知识点画像）
weak_points（薄弱知识点）
common_errors（常见错误）
attention_students（重点关注学生）
```

**输出**

```text
ClassProfile（班级画像）
```

返回的：

```text
basic.algorithm_version = profile_v1
```

**数据来源**

```text
ProfileService
↓
Redis Class Profile Snapshot
↓ Redis Miss
ProfileAlgorithmV1
↓
MySQL 当前有效班级事实
```

Class Profile 的计算不读取 Redis Student Profile 作为事实源；Tool 也不允许 Agent 自行重新计算或覆盖 `avg_mastery / weak_points / attention_students` 等确定性画像结论。

边界：`get_class_profile` 回答班级长期学情，不用于枚举完整学生名单；需要班级成员列表时使用 `list_class_students`。

---

### 5.4 `list_class_students`

**作用**

查询指定班级的真实学生成员列表，为全班批量诊断、批量个性化练习等任务提供需要处理的 `student_id` 集合。

**输入参数**

```text
class_id（班级ID）          必填
```

**输出**

```text
ClassStudent[]（班级学生列表）
├── student_id（学生ID）
└── name（学生姓名）
```

**数据来源**

```text
MySQL
class_student
+
student
```

边界：

```text
list_class_students
= 谁在这个班级里

get_class_profile
= 这个班级长期学得怎么样
```

该 Tool 不计算 Student Profile，也不返回学生成绩或掌握度。

---

### 5.5 `list_class_homeworks`

**作用**

查询指定班级在某个学科、某个时间范围内的作业列表，为“本周 / 近期班级复盘”等跨多次作业业务发现需要进一步分析的 `homework_id`。

**输入参数**

```text
class_id（班级ID）          必填
subject（学科）             可选
start_time（开始时间）      可选
end_time（结束时间）        可选
limit（返回数量）           可选
```

**输出**

```text
HomeworkSummary[]（作业摘要列表）
├── homework_id（作业ID）
├── name（作业名称）
├── subject（学科）
└── published_at（发布时间）
```

**数据来源**

```text
MySQL
homework
```

边界：

```text
list_class_homeworks
= 这个时间范围有哪些作业

get_homework_analysis
= 某一份已知作业具体表现如何
```

该 Tool 只做作业发现，不计算完成率、成绩分布或知识点表现。

---

### 5.6 `get_homework_analysis`

**作用**

分析某个班级的一次具体作业，包括完成情况、成绩表现、知识点表现、题目表现和重点关注学生。

**输入参数**

```text
homework_id（作业ID）       必填
class_id（班级ID）          必填
sections（返回模块）        可选
```

`sections（返回模块）` 支持：

```text
completion（完成情况）
performance（成绩表现）
knowledge_points（知识点表现）
questions（题目表现）
attention_students（重点关注学生）
```

**输出**

```text
HomeworkAnalysis（作业分析）
```

**数据来源**

```text
MySQL 当前有效事实
        ↓
AnalysisCalculationV1
        ↓
HomeworkAnalysis
```

Tool 必须直接返回 `AnalysisCalculationV1` 的确定性计算结果。

Teacher Agent / Skill 不得重新计算或覆盖：

```text
graded_student_count
avg_score_rate
score_distribution
avg_performance
low_performance_student_count
error_rate
attention_students
```

---

### 5.7 `get_question_analysis`

**作用**

下钻分析某个班级在某次作业中的一道具体题，包括作答人数、平均得分率、错误率、涉及知识点、常见错误和典型错误证据。

**输入参数**

```text
homework_id（作业ID）       必填
class_id（班级ID）          必填
question_id（题目ID）       必填
```

**输出**

```text
QuestionAnalysis（题目分析）
```

返回内容包括：

```text
question_no（题号）
attempt_count（有效作答人数）
avg_score_rate（平均得分率）
error_student_count（出现结构化错误的学生数）
error_rate（错误率）
knowledge_points（涉及知识点）
common_errors（常见错误）
representative_errors（典型错误证据）
```

**数据来源**

```text
MySQL 当前有效事实
        ↓
AnalysisCalculationV1
        ↓
QuestionAnalysis
```

`attempt_count / avg_score_rate / error_student_count / error_rate / knowledge_points / common_errors / representative_errors` 均由后端确定性计算或选择，不允许 LLM 从自然语言结果中估算。

---

### 5.8 `search_teaching_materials`【本阶段暂缓】

> 本阶段暂不实现该 Tool。当前阶段不建设 RAG / Teaching Knowledge Base（教学知识库），因此仅保留接口与职责设计，待后续引入教学资料检索能力后再启用。

**作用**

查询与知识点、年级和教学目标相关的教学材料，为后续讲解、教学建议和教学内容生成提供资料依据。

**输入参数**

```text
query（查询内容）                       必填

subject（学科）                         可选
knowledge_point_key（标准二级知识点标识） 可选
grade（年级）                           可选
```

**输出**

```text
TeachingMaterial[]（教学材料列表）
├── title（标题）
├── content（内容）
├── knowledge_point（知识点）
└── source（来源）
```

**规划数据来源**

```text
教材知识库 / RAG
```

该 Tool（工具）不读取学生业务事实。

---

### 5.9 `search_question_bank`

**作用**

根据标准知识点、难度、题型和年级检索独立 Question Bank 中的练习题，为学生个性化练习和班级分层练习提供候选题目。

**输入参数**

```text
subject（学科）                                   必填
knowledge_point_keys（标准二级知识点标识）       必填

difficulty（难度）                               可选
question_type（题型）                            可选
grade（年级）                                    可选
count（数量）                                    可选
exclude_question_bank_item_ids（排除题库题ID）   可选
```

题库题目的知识点标签与学习画像使用同一套 Knowledge Point Taxonomy，因此 Student / Class Profile 中的标准 `knowledge_point_key` 可以直接作为题库检索条件，不增加额外知识点映射层。

多个 `knowledge_point_keys` 默认表示：

```text
至少命中其中一个标准知识点
```

如果业务要求“给三个知识点分别找题”，Teacher Agent / Skill 应分别按知识点调用 `search_question_bank`，而不是依赖一次查询自动平均分配题目。

**输出**

```text
QuestionBankItem[]（题库题列表）
├── question_bank_item_id（题库题ID）
├── content（题目内容）
├── image_url（题目图片，可选）
├── subject（学科）
├── grade（年级）
├── knowledge_point_keys（标准知识点）
├── difficulty（难度）
├── question_type（题型）
└── reference_answer（参考答案）
```

**数据来源**

```text
MySQL
question_bank_item
+
question_bank_item_knowledge_point
+
knowledge_point
```

边界：

```text
search_question_bank
→ 只返回 QuestionBankItem

不得返回 Homework 中已经布置的 Question
```

---

## 03–05 整体关系

```text
03 数据基础与学习画像模型
│
├── MySQL 业务事实
├── OCRResult 批改证据
├── Knowledge Point / Error Type Taxonomy 标准参考字典
├── Question Bank
│   ├── question_bank_item
│   └── question_bank_item_knowledge_point
├── GradingResult Knowledge Point / Error 诊断事实
├── Student Profile（学生画像）
├── Class Profile（班级画像）
├── Homework Analysis（作业分析）
├── Question Analysis（题目分析）
└── MySQL / Redis / 即时计算边界
          │
          ↓
04 学习画像算法与长期个性化
│
├── ProfileAlgorithmV1（profile_v1）
├── mastery（掌握度）
├── recent_performance（近期表现）
├── trend（学习趋势）
├── weak_point（薄弱知识点）
├── recurring_error（重复错误）
├── class aggregation（班级聚合）
└── personalized feedback context（个性化反馈上下文）
          │
          ↓
05 Teacher Agent Tools（教师 Agent 工具）
│
├── DeerFlow Tool Runtime
│      ↓
│   Teacher Copilot Tool Adapter
│      ↓
│   Service / Repository
│
├── get_student_profile
├── get_student_grading_history
├── get_class_profile
├── list_class_students
├── list_class_homeworks
├── get_homework_analysis
├── get_question_analysis
├── search_teaching_materials（后续 / 本阶段暂缓）
└── search_question_bank → QuestionBankItem[]
          │
          ↓
06–07 DeerFlow Teacher Custom Agent + 按需 Multi-Agent
```

本文件只确定教育业务数据、算法和 Tool Contract。DeerFlow Tool 注册、Skill Runtime、Custom Agent、Teacher Business Context Middleware、HITL 与 Sub-Agent 的详细工程接入分别统一见：

- `docs/05-tool-skill.md`
- `docs/06-07-业务驱动的设计.md`