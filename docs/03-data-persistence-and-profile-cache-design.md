# AI Teacher Copilot：数据沉淀与画像缓存设计

## 1. 设计目标

本阶段解决的问题是：一次 `Submission` 完成批改并生成 `GradingResult` 后，如何把题目级事实可靠沉淀下来，并进一步生成学生画像和班级学情画像。

核心数据链路固定为：

```text
GradingResult
    ↓
MySQL：题目级业务事实
    ↓
定时聚合计算
    ├── Student Profile（学生画像）
    └── Class Profile（班级画像）
              ↓
            Redis
```

当前设计明确：

> **MySQL 只保存原始业务事实，不保存 Student Profile / Class Profile 这类聚合结果。画像由 MySQL 中的事实数据计算得到，并缓存到 Redis；Redis 中的数据可以删除、过期、重算。**

---

## 2. 核心原则

### 2.1 MySQL 是唯一事实源

系统中真实发生过的业务行为和批改结果必须进入 MySQL。

包括：

```text
Teacher
Student
Class
Homework
Question
Submission
GradingResult
```

其中本阶段最核心的是：

```text
Submission
    ↓
GradingResult
```

`GradingResult` 表示一次真实批改产生的题目级事实。

例如：

```text
Submission sub_10001
    ↓
GradingResult gr_10001

score（得分） = 8 / 10
difficulty（难度） = medium

knowledge_points（知识点）
├── 一元一次方程 → correct
└── 移项 → incorrect

errors（错误）
└── SIGN_ERROR
```

这些事实一旦产生，就不能因为学生后续学习状态变化而被覆盖。

例如学生后来掌握了“移项”，也不能把历史记录中的：

```text
移项 → incorrect
```

改成：

```text
移项 → correct
```

因为历史 `GradingResult` 记录的是**当时真实发生的批改结果**。

### 2.2 Grading Record 不单独设计成新的业务对象

文档中如果出现 `Grading Record`，它表示：

```text
GradingResult
    ↓
持久化到 MySQL
    ↓
题目级批改事实记录
```

因此当前系统不再额外增加一个与 `GradingResult` 平行的 `GradingRecord` 业务对象。

### 2.3 Student Profile / Class Profile 都是派生数据

```text
GradingResult
= 这一次做得怎么样

Student Profile
= 这个学生长期学得怎么样

Class Profile
= 这个班整体学得怎么样
```

后两者都不是事实源，而是根据 MySQL 中历史事实计算得到的结果。

因此它们允许：

```text
更新
重新计算
算法升级后整体重算
Redis 丢失后重建
```

### 2.4 Class Profile 不依赖 Redis 中的 Student Profile 作为事实源

逻辑上可以理解为：

```text
GradingResult
    ↓
Student Profile
    ↓
Class Profile
```

但工程实现中，为了避免画像缓存之间相互依赖、放大过期数据，两个画像都以 MySQL 为最终计算依据：

```text
                  MySQL
                    │
          historical GradingResult
              ↙             ↘
 Student Profile           Class Profile
       ↓                        ↓
     Redis                    Redis
```

`Class Profile` 可以复用同一套聚合逻辑，但不能把 Redis 中的 `Student Profile` 当作不可替代的数据源。

---

## 3. 三层数据模型

### 3.1 第一层：题目级业务事实

第一层负责回答：

> **某个学生在某一次 Submission 中到底发生了什么？**

主要包括：

```text
Question
   ↓
Submission
   ↓
GradingResult
```

`GradingResult` 中用于后续统计的核心事实包括：

```text
score（得分）
difficulty（难度）
knowledge_points（知识点及当前表现）
errors（错误类型与错误证据）
math_detail（数学详情）
english_essay_detail（英语作文详情）
execution_meta（执行元数据）
created_at（创建时间）
```

完整逻辑 Schema 见：

`docs/02-grading-result-schema.md`

### 3.2 第二层：Student Profile（学生画像）

第二层负责回答：

> **这个学生经过多次作答后，在各知识点上的长期学习状态如何？**

例如：

```text
Student Profile

学生：stu_001
学科：math

知识点：移项
├── attempt_count（作答次数）
├── correct_count（正确次数）
├── accuracy（总体正确率）
├── recent_accuracy（近期正确率）
├── mastery（掌握度）
├── trend（趋势）
└── common_errors（高频错误）
```

这些值全部由多个历史 `GradingResult` 聚合得到。

例如：

```text
GradingResult 1 → 移项 incorrect
GradingResult 2 → 移项 incorrect
GradingResult 3 → 移项 partial
GradingResult 4 → 移项 correct

                 ↓ 聚合

Student Profile
移项
├── attempt_count = 4
├── recent_accuracy = ...
├── mastery = ...
└── trend = improving
```

`mastery`、`recent_accuracy`、`trend` 的具体算法在下一阶段“个性化反馈和薄弱点分析”中定义，本文件只确定其数据来源和存储边界。

### 3.3 第三层：Class Profile（班级画像）

第三层负责回答：

> **整个班级在某个学科、知识点、题目或错误类型上的整体表现如何？**

例如：

```text
Class Profile

班级：class_03
学科：math

知识点：移项
├── attempt_count（总作答次数）
├── avg_accuracy（平均正确率）
├── avg_mastery（平均掌握度）
├── weak_student_count（薄弱学生数）
├── common_errors（高频错误）
└── high_error_questions（高错题）
```

典型教师查询可以直接建立在这一层：

```text
三班最近哪些知识点最薄弱？
哪些题错误率最高？
哪些学生在同一个知识点上持续出错？
最近全班最常见的错误类型是什么？
```

---

## 4. MySQL 持久化边界

MySQL 只负责保存**可追溯的业务事实**。

不在 MySQL 中持久化：

```text
Student Profile
Class Profile
mastery 聚合结果
recent_accuracy 聚合结果
trend 聚合结果
班级薄弱知识点排行
高错题排行
```

这些都是可从事实数据重新计算得到的派生数据。

### 4.1 GradingResult 主记录

建议使用：

```text
grading_result
```

保存适合直接查询和关联的顶层事实，例如：

| 字段 | 含义 |
|---|---|
| `id（批改结果ID）` | GradingResult 唯一标识 |
| `submission_id（学生提交ID）` | 对应的 Submission |
| `subject（学科）` | math / english |
| `question_type（题型）` | calculation / solution / essay 等 |
| `difficulty（难度）` | easy / medium / hard |
| `difficulty_reason（难度判断原因）` | 小模型给出的简短判断依据 |
| `score_earned（实际得分）` | 当前题实际得分 |
| `score_max（满分）` | 当前题满分 |
| `score_rate（得分率）` | earned / max |
| `feedback_json（当前题反馈）` | 当前题展示型反馈 |
| `detail_json（学科详情）` | math_detail 或 english_essay_detail |
| `execution_meta_json（执行元数据）` | 路由、实际模型等执行信息 |
| `schema_version（Schema版本）` | GradingResult Schema 版本 |
| `created_at（创建时间）` | 批改结果生成时间 |

这里的原则是：

- 高频查询、过滤、排序使用的字段放普通列。
- 展示型、学科特有、嵌套较深的数据可以先放 JSON。
- 后续真正需要高频统计的嵌套字段，再拆成独立关系表。

### 4.2 Knowledge Point 事实表

`knowledge_points[]` 需要频繁用于学生画像和班级分析，不建议只埋在 JSON 中。

建议拆成：

```text
grading_result_knowledge_point
```

逻辑字段：

| 字段 | 含义 |
|---|---|
| `id（记录ID）` | 当前知识点事实记录ID |
| `grading_result_id（批改结果ID）` | 所属 GradingResult |
| `knowledge_point_key（知识点标识）` | 可标准化知识点 Key |
| `knowledge_point_name（知识点名称）` | 面向人的知识点名称 |
| `performance（当前表现）` | correct / partial / incorrect |
| `evidence（判断证据）` | 当前题上的判断证据 |

例如：

```text
gr_10001
├── math.linear_equation → correct
└── math.linear_equation.transposition → incorrect
```

### 4.3 Error 事实表

错误类型同样需要跨题、跨学生、跨班级统计，因此建议拆成：

```text
grading_result_error
```

逻辑字段：

| 字段 | 含义 |
|---|---|
| `id（错误记录ID）` | 当前错误记录ID |
| `grading_result_id（批改结果ID）` | 所属 GradingResult |
| `error_code（错误编码）` | 标准错误类型编码 |
| `error_type（错误类型）` | 面向教师/学生的名称 |
| `knowledge_point_key（关联知识点）` | 当前错误关联的知识点 |
| `description（错误描述）` | 错误原因 |
| `evidence（错误证据）` | 学生作答中的证据 |

后续统计时优先使用：

```text
knowledge_point_key
error_code
performance
score_rate
```

而不是依赖自然语言评语。

### 4.4 当前 MySQL 核心结构

```text
Submission
    │
    │ 1 : 1
    ↓
grading_result
    │
    ├── 1 : N → grading_result_knowledge_point
    │
    └── 1 : N → grading_result_error
```

其中：

```text
grading_result
→ 保存一次批改的主体事实

grading_result_knowledge_point
→ 保存知识点级事实

grading_result_error
→ 保存错误级事实
```

`Teacher / Student / Class / Homework / Question / Submission` 等业务表属于前置业务模型，本文件不重复展开完整字段。

---

## 5. Redis 画像缓存

Redis 中只保存可重建的聚合结果。

推荐逻辑 Key：

```text
student_profile:v1:{student_id}:{subject}
class_profile:v1:{class_id}:{subject}
```

例如：

```text
student_profile:v1:stu_001:math
class_profile:v1:class_03:math
```

其中 `v1` 表示画像结构或算法版本，后续算法发生较大变化时可以通过版本隔离旧缓存。

### 5.1 Student Profile 缓存结构

逻辑结构：

```text
StudentProfile
├── student_id（学生ID）
├── subject（学科）
├── knowledge_points（知识点画像）
│   └── knowledge_point_key
│       ├── attempt_count（作答次数）
│       ├── correct_count（正确次数）
│       ├── accuracy（总体正确率）
│       ├── recent_accuracy（近期正确率）
│       ├── mastery（掌握度）
│       ├── trend（趋势）
│       └── common_errors（高频错误）
├── generated_at（画像生成时间）
├── source_data_until（使用事实数据截止时间）
└── algorithm_version（聚合算法版本）
```

### 5.2 Class Profile 缓存结构

逻辑结构：

```text
ClassProfile
├── class_id（班级ID）
├── subject（学科）
├── knowledge_points（知识点画像）
│   └── knowledge_point_key
│       ├── attempt_count（作答次数）
│       ├── avg_accuracy（平均正确率）
│       ├── avg_mastery（平均掌握度）
│       ├── weak_student_count（薄弱学生数）
│       └── common_errors（高频错误）
├── high_error_questions（高错题）
├── generated_at（画像生成时间）
├── source_data_until（使用事实数据截止时间）
└── algorithm_version（聚合算法版本）
```

Redis 中的画像不承担审计责任，也不保证永久存在。

即使整个 Redis 被清空，也可以通过：

```text
MySQL historical GradingResult
            ↓
       重新聚合
            ↓
         Redis
```

完整恢复。

---

## 6. 聚合更新机制

当前方案采用：

> **GradingResult 实时落 MySQL，Student Profile / Class Profile 定时重新聚合并写入 Redis。**

不要求每产生一个 `GradingResult` 就同步更新完整画像。

### 6.1 批改完成时

```text
Submission
    ↓
完整 Grading Workflow
    ↓
GradingResult
    ↓
事务写入 MySQL
    ├── grading_result
    ├── grading_result_knowledge_point
    └── grading_result_error
    ↓
学生立即获得当前题批改结果
```

此时不阻塞学生请求去重新计算整个 Student Profile / Class Profile。

### 6.2 定时聚合任务

```text
定时任务触发
    ↓
查询 MySQL 中新增/近期 GradingResult
    ↓
确定受影响的 Student / Class
    ↓
从 MySQL 查询对应事实数据
    ↓
重新计算 Student Profile
    ↓
重新计算 Class Profile
    ↓
原子替换 Redis 缓存
```

这里推荐采用：

> **“增量发现受影响对象 + 对受影响对象重新计算画像”**

而不是直接对 mastery 等值做不可逆的增量修改。

例如新增一条：

```text
stu_001
class_03
math
```

新的 `GradingResult` 后，定时任务只需要把：

```text
stu_001 的 math Student Profile
class_03 的 math Class Profile
```

标记为需要重算，然后重新从 MySQL 读取该画像所需的历史事实。

这样既避免每次扫描全库，也保留完整可重算能力。

### 6.3 为什么不直接增量修改 mastery？

如果直接：

```text
旧 mastery
+
当前一题
↓
覆盖新 mastery
```

长期容易遇到：

```text
算法升级后难以恢复
历史数据修正后难以纠正
缓存异常造成累计误差
部分任务失败导致状态漂移
```

当前方案更强调：

```text
MySQL facts
    ↓
确定性聚合算法
    ↓
Redis snapshot
```

因此画像缓存始终可以从事实层重新生成。

---

## 7. 查询路径

### 7.1 查询某一次批改结果

直接查询 MySQL：

```text
submission_id
    ↓
grading_result
    ↓
当前题完整批改结果
```

### 7.2 查询学生长期画像

优先查询 Redis：

```text
Teacher / Teacher Agent
        ↓
student_profile:v1:{student_id}:{subject}
        ↓
Student Profile
```

### 7.3 查询班级学情

优先查询 Redis：

```text
Teacher / Teacher Agent
        ↓
class_profile:v1:{class_id}:{subject}
        ↓
Class Profile
```

### 7.4 Redis Miss

Redis Miss 不代表数据丢失。

```text
Redis Miss
    ↓
MySQL 事实仍然完整
```

系统可以根据实际工程策略选择：

```text
A. 触发一次重算后回填 Redis
B. 当前请求临时从 MySQL 计算
C. 返回画像正在刷新，等待下一次定时任务
```

具体采用哪一种可以在工程实现阶段根据延迟要求确定。

---

## 8. 数据一致性边界

### 8.1 强一致的数据

以下数据以 MySQL 为准：

```text
Submission
GradingResult
score
knowledge_points
errors
批改时间
模型路由结果
```

### 8.2 最终一致的数据

以下数据允许存在一定刷新延迟：

```text
Student Profile
Class Profile
mastery
trend
recent_accuracy
高频错误排行
高错题排行
```

因此系统的一致性模型可以概括为：

```text
批改事实：强一致 / 持久化
画像结果：最终一致 / 可重算缓存
```

---

## 9. 算法版本与可重算能力

画像算法后续一定可能变化，例如：

```text
mastery
从简单平均
↓
近期加权
↓
时间衰减
↓
难度加权
```

因此 Redis Profile 中建议保留：

```text
algorithm_version（算法版本）
generated_at（生成时间）
source_data_until（事实数据截止时间）
```

例如：

```text
algorithm_version = profile_v2
```

当算法升级时：

```text
MySQL 历史事实
    ↓
profile_v2 算法
    ↓
生成新的 Redis Profile
```

无需修改历史 `GradingResult`。

---

## 10. 当前最终数据架构

```text
                       业务事实层
────────────────────────────────────────────────

Teacher / Student / Class / Homework / Question
                         │
                         ↓
                     Submission
                         ↓
                   GradingResult
                         ↓
                       MySQL
                         │
              ┌──────────┴──────────┐
              │                     │
              ↓                     ↓
grading_result_knowledge_point  grading_result_error


                       聚合计算层
────────────────────────────────────────────────

                定时 Profile Aggregator
                         │
             从 MySQL 读取历史事实
                         │
              ┌──────────┴──────────┐
              ↓                     ↓
       Student Profile         Class Profile
              │                     │
              └──────────┬──────────┘
                         ↓
                       Redis


                       使用层
────────────────────────────────────────────────

              Teacher / Teacher Agent
                         │
             ┌───────────┴───────────┐
             ↓                       ↓
      Student Profile          Class Profile
       学生长期状态              班级整体学情
```

整个设计可以归纳为一句话：

> **MySQL 保存“发生了什么”，Redis 缓存“从这些事实计算出了什么”。GradingResult 是批改事实的 Source of Truth，Student Profile 和 Class Profile 都是可更新、可删除、可重算的派生画像。**

---

## 11. 与后续步骤的边界

本文件已经确定：

```text
GradingResult 如何持久化
哪些字段需要关系化拆表
MySQL 与 Redis 的职责边界
Student / Class Profile 的数据来源
画像如何定时刷新
画像如何支持整体重算
```

本文件暂时不确定以下算法细节：

```text
mastery 到底怎么算
partial 如何折算
recent_accuracy 看最近多少题/多少天
trend 如何判断 improving / stable / declining
多久刷新一次 Redis
薄弱知识点达到什么阈值
weak_student 如何定义
```

这些内容统一进入下一阶段：

> **个性化评语与薄弱点分析 / Student Profile 算法设计。**
