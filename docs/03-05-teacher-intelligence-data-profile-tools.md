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

---

### 3.2 MySQL 数据模型：业务事实 + 标准参考字典

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

---

### 3.3 Student Profile（学生画像）

定位：描述一个学生在某个学科上的长期学习状态。

本节及后续 Profile / Analysis 中出现的 `knowledge_point_key / common_error_codes / error_code`，均指标准 Taxonomy 中可落库的 `level = 2` 编码；需要大类统计时通过标准字典父级关系向上聚合。

```text
StudentProfile（学生画像）
│
├── basic（基础信息）
│   ├── student_id（学生ID）
│   ├── subject（学科）
│   ├── generated_at（生成时间）
│   ├── source_data_until（事实数据截止时间）
│   └── algorithm_version（算法版本）
│
├── overview（整体表现）
│   ├── attempt_count（累计作答次数）
│   ├── avg_score_rate（历史平均得分率）
│   ├── recent_score_rate（近期得分率）
│   └── trend（学习趋势）
│
├── knowledge_points[]（知识点画像）
│   ├── knowledge_point_key（知识点标识）
│   ├── attempt_count（作答次数）
│   ├── mastery（掌握度）
│   ├── recent_performance（近期表现）
│   ├── trend（学习趋势）
│   ├── last_practiced_at（最近练习时间）
│   └── common_error_codes[]（常见错误类型）
│
├── weak_points[]（薄弱知识点）
│   ├── knowledge_point_key（知识点标识）
│   ├── mastery（掌握度）
│   ├── trend（学习趋势）
│   └── evidence_count（证据数量）
│
├── recurring_errors[]（重复错误）
│   ├── error_code（错误类型）
│   ├── knowledge_point_key（关联知识点）
│   ├── occurrence_count（累计出现次数）
│   ├── recent_occurrence_count（近期出现次数）
│   └── last_occurred_at（最近出现时间）
│
└── difficulty_performance（不同难度表现）
    ├── easy（简单）
    ├── medium（中等）
    └── hard（困难）
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
│   └── algorithm_version（算法版本）
│
├── overview（整体表现）
│   ├── student_count（学生总数）
│   ├── active_student_count（有效学习学生数）
│   ├── avg_score_rate（历史平均得分率）
│   ├── recent_score_rate（近期得分率）
│   └── trend（学习趋势）
│
├── knowledge_points[]（知识点画像）
│   ├── knowledge_point_key（知识点标识）
│   ├── participating_student_count（参与学生数）
│   ├── attempt_count（总作答次数）
│   ├── avg_mastery（平均掌握度）
│   ├── recent_performance（近期表现）
│   ├── weak_student_count（薄弱学生数）
│   ├── trend（学习趋势）
│   └── common_error_codes[]（常见错误）
│
├── weak_points[]（班级薄弱知识点）
│   ├── knowledge_point_key（知识点标识）
│   ├── avg_mastery（平均掌握度）
│   ├── weak_student_count（薄弱学生数）
│   └── trend（学习趋势）
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
    ├── recent_performance（近期表现）
    ├── trend（学习趋势）
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
│   ├── avg_score_rate（平均得分率）
│   └── score_distribution（成绩分布）
│
├── knowledge_points[]（知识点表现）
│   ├── knowledge_point_key（知识点标识）
│   ├── avg_performance（平均表现）
│   └── weak_student_count（薄弱学生数）
│
├── questions[]（题目表现）
│   ├── question_id（题目ID）
│   ├── question_no（题号）
│   ├── avg_score_rate（平均得分率）
│   ├── error_rate（错误率）
│   └── common_error_codes[]（常见错误）
│
└── attention_students[]（重点关注学生）
```

Homework Analysis（作业分析）默认从 MySQL 即时计算，不作为长期画像持久化。

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
├── attempt_count（作答人数）
├── avg_score_rate（平均得分率）
├── error_rate（错误率）
│
├── knowledge_points[]（涉及知识点）
│
├── common_errors[]（常见错误）
│   ├── error_code（错误类型）
│   ├── occurrence_count（出现次数）
│   └── affected_student_count（涉及学生数）
│
└── representative_errors[]（典型错误证据）
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
└── 标准参考字典
    ├── Knowledge Point Taxonomy
    └── Error Type Taxonomy

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
```

`Submission` 是学生侧当前批改状态事实源，不另建 `grading_task` 事实表。`OCRResult` 属于可追溯的批改证据数据，不进入 Student / Class Profile 聚合核心指标；Profile 仍以 `GradingResult` 的稳定结构化事实作为主要输入。

Student Profile（学生画像）与 Class Profile（班级画像）的生成方式：

```text
MySQL Facts
    ↓
确定性聚合算法
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

---

## 4. 学习画像算法与长期个性化

### 4.1 核心画像算法

画像计算固定包含以下 7 类能力：

```text
1. performance（表现值）标准化
2. mastery（掌握度）
3. recent_performance（近期表现）
4. trend（学习趋势）
5. weak_point（薄弱知识点）
6. recurring_error（重复错误）
7. class aggregation（班级聚合）
```

#### performance（表现值）标准化

将 `GradingResult` 中不同题型、不同得分形式转换为画像计算可使用的统一表现值，为后续掌握度、近期表现和班级聚合提供统一输入。

#### mastery（掌握度）

```text
历史知识点表现
+
时间权重
+
题目难度权重
↓
mastery（掌握度）
```

`mastery（掌握度）` 不直接等于历史正确率。

#### recent_performance（近期表现）

使用独立近期窗口计算，只表示学生或班级近期状态，不与长期 `mastery（掌握度）` 混为同一个指标。

#### trend（学习趋势）

```text
近期窗口
vs
上一窗口
↓
improving（提升）
stable（稳定）
declining（下降）
```

#### weak_point（薄弱知识点）

薄弱知识点必须同时满足：

```text
mastery（掌握度）较低
+
足够历史证据
```

单次错误不能直接判定为长期薄弱知识点。

#### recurring_error（重复错误）

重复错误依据：

```text
相同 error_code（错误类型编码）
+
多次出现
+
相同或相关 knowledge_point（知识点）
```

#### class aggregation（班级聚合）

Class Profile（班级画像）直接从 MySQL 中的班级历史事实进行聚合，不通过 Student Profile（学生画像）二次聚合作为事实计算链。

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

**数据来源**

```text
Redis
↓ Redis Miss
MySQL 重算
```

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

**数据来源**

```text
Redis
↓ Redis Miss
MySQL 重算
```

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
MySQL
↓
即时聚合
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
attempt_count（作答人数）
avg_score_rate（平均得分率）
error_rate（错误率）
knowledge_points（涉及知识点）
common_errors（常见错误）
representative_errors（典型错误证据）
```

**数据来源**

```text
MySQL
↓
即时聚合
```

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

根据知识点、难度和题型检索练习题，为学生个性化练习和班级分层练习提供候选题目。

**输入参数**

```text
subject（学科）                        必填
knowledge_point_keys（标准二级知识点标识） 必填

difficulty（难度）                    可选
question_type（题型）                 可选
count（数量）                         可选
exclude_question_ids（排除题目）      可选
```

题库题目的知识点标签与学习画像使用同一套 Knowledge Point Taxonomy，因此 Student / Class Profile 中的标准 `knowledge_point_key` 可以直接作为题库检索条件，不增加额外知识点映射层。

**输出**

```text
Question[]（题目列表）
├── question_id（题目ID）
├── content（题目内容）
├── knowledge_points（标准知识点）
├── difficulty（难度）
├── question_type（题型）
└── answer / reference_answer（参考答案）
```

**数据来源**

```text
MySQL Question Database（题库）
```

---

## 03–05 整体关系

```text
03 数据基础与学习画像模型
│
├── MySQL 业务事实
├── OCRResult 批改证据
├── Knowledge Point / Error Type Taxonomy 标准参考字典
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
├── get_student_profile
├── get_student_grading_history
├── get_class_profile
├── list_class_students
├── list_class_homeworks
├── get_homework_analysis
├── get_question_analysis
├── search_teaching_materials（后续 / 本阶段暂缓）
└── search_question_bank
          │
          ↓
06–07 业务驱动的 Teacher Lead Agent + 按需 Multi-Agent
```