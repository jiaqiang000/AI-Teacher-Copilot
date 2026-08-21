# AI Teacher Copilot：03–05 数据基础、学习画像与 Teacher Agent Tools

## 3. 数据基础与学习画像模型

### 3.1 整体数据架构

```text
                    MySQL 业务事实层
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
= 唯一业务事实源

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

### 3.2 MySQL 事实模型

保留业务事实表：

```text
teacher
student
class
class_student

homework
question
submission

grading_result
grading_result_knowledge_point
grading_result_error
```

新增标准化字典：

```text
knowledge_point
error_type
```

知识点和错误类型进入统计体系前必须完成标准化：

```text
模型原始输出
    ↓
知识点 / 错误类型标准化
    ↓
knowledge_point_key
error_code
    ↓
MySQL
```

统计和画像计算不长期依赖自由文本知识点名称或错误名称，而以标准化的 `knowledge_point_key（知识点标识）` 和 `error_code（错误类型编码）` 为主要统计依据。

---

### 3.3 Student Profile（学生画像）

定位：描述一个学生在某个学科上的长期学习状态。

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
├── 所有业务事实
├── GradingResult
├── Knowledge Point 事实
├── Error 事实
└── Homework / Question / Submission 等

Redis
├── Student Profile（学生画像）
└── Class Profile（班级画像）

实时聚合
├── Homework Analysis（作业分析）
└── Question Analysis（题目分析）
```

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

Teacher Agent 对业务数据的访问统一通过 7 个核心 Tool（工具）完成。Tool 按业务对象和能力边界划分，不按单个统计字段拆分。

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
knowledge_point_key（知识点标识）     可选
error_code（错误类型）                可选
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
知识点表现
错误
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

---

### 5.4 `get_homework_analysis`

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

### 5.5 `get_question_analysis`

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

### 5.6 `search_teaching_materials`

**作用**

查询与知识点、年级和教学目标相关的教学材料，为后续讲解、教学建议和教学内容生成提供资料依据。

**输入参数**

```text
query（查询内容）                       必填

subject（学科）                         可选
knowledge_point_key（知识点标识）       可选
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

**数据来源**

```text
教材知识库 / RAG
```

该 Tool（工具）不读取学生业务事实。

---

### 5.7 `search_question_bank`

**作用**

根据知识点、难度和题型检索练习题，为学生个性化练习和班级分层练习提供候选题目。

**输入参数**

```text
subject（学科）                        必填
knowledge_point_keys（知识点）        必填

difficulty（难度）                    可选
question_type（题型）                 可选
count（数量）                         可选
exclude_question_ids（排除题目）      可选
```

**输出**

```text
Question[]（题目列表）
├── question_id（题目ID）
├── content（题目内容）
├── knowledge_points（知识点）
├── difficulty（难度）
├── question_type（题型）
└── answer / reference_answer（参考答案）
```

**数据来源**

```text
Question Database（题库）
/
RAG
```

---

## 03–05 整体关系

```text
03 数据基础与学习画像模型
│
├── MySQL 事实模型
├── Knowledge Point / Error 标准化
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
├── get_homework_analysis
├── get_question_analysis
├── search_teaching_materials
└── search_question_bank
          │
          ↓
06 Skills + Agent Memory
          ↓
07 Multi-Agent
```
