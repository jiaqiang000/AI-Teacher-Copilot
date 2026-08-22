# AI Teacher Copilot：05 Teacher Agent Tool 与 Skill 设计

## 1. Tool 与 Skill 的职责边界

Teacher Agent 完整能力规划包含 9 个 Tool 和 5 个 Skill。9 个 Tool 负责原子业务能力，5 个 Skill 用于完成稳定、可复用的复杂教学任务。

```text
Teacher Agent
│
├── Skills（如何完成教学任务）
│   ├── student-diagnosis（学生学习诊断）
│   ├── class-learning-analysis（班级学情分析）
│   ├── homework-review（作业讲评分析）
│   ├── personalized-intervention（个性化教学干预）
│   └── differentiated-practice（分层练习设计）
│
└── Tools（实际查询和操作数据）
    ├── get_student_profile
    ├── get_student_grading_history
    ├── get_class_profile
    ├── list_class_students
    ├── list_class_homeworks
    ├── get_homework_analysis
    ├── get_question_analysis
    ├── search_teaching_materials
    └── search_question_bank
```

当前阶段暂不建设 RAG / Teaching Knowledge Base（教学知识库），因此：

```text
完整规划
9 Tools + 5 Skills

当前阶段实现
8 Tools + 4 Skills

暂缓实现
├── search_teaching_materials
└── personalized-intervention
    └── 依赖 search_teaching_materials
```

暂缓能力的 Tool Contract 与 Skill SOP 继续保留在本文中，待后续建设教学资料检索能力后启用。

职责划分：

```text
Tool
= 原子业务能力
= 明确输入 → 查询 / 计算 / 检索 → 返回结构化结果

Skill
= 教学任务 SOP
= 规定如何组合多个 Tool、如何分析结果、如何生成最终输出
```

简单问题可以直接调用单个 Tool：

```text
“张三有哪些薄弱知识点？”
→ get_student_profile

“这次作业完成率多少？”
→ get_homework_analysis

“第 8 题错误率多少？”
→ get_question_analysis

“八三班现在有哪些学生？”
→ list_class_students

“八三班这周有哪些数学作业？”
→ list_class_homeworks
```

复杂教学任务通过 Skill 组织多个 Tool：

```text
User
  ↓
Teacher Agent
  ↓
Skill
  ↓
多个 Tools
  ↓
事实验证 / 分析 / 组织
  ↓
Answer
```

Skill 不新增业务事实，不修改 03–05 已确定的数据模型，也不重新实现 Tool 中的数据查询逻辑。

---

## 2. 5 个 Skill 的完整设计

完整规划中的 5 个 Skill 覆盖 Teacher Copilot 的教师任务链路：

```text
发现问题
│
├── student-diagnosis（学生学习诊断）
│   学生哪里有问题？
│
├── class-learning-analysis（班级学情分析）
│   班级哪里有问题？
│
└── homework-review（作业讲评分析）
    这次作业哪里有问题？
          ↓
       采取行动
          │
          ├── personalized-intervention（个性化教学干预）
          │   一个学生怎么干预？
          │
          └── differentiated-practice（分层练习设计）
              不同学生怎么练？
```

### 2.1 `student-diagnosis`（学生学习诊断）

目标：判断一个学生长期哪里薄弱、为什么薄弱、是否存在重复错误和趋势变化，并给出有历史事实支撑的诊断结论。

主要 Tool：

```text
get_student_profile（查询学生画像：获取长期学习状态、薄弱点、趋势等）
get_student_grading_history（查询批改历史：获取真实历史作答与批改记录）
```

固定 SOP：

```text
get_student_profile
        ↓
识别 weak_points（薄弱知识点）
recurring_errors（重复错误）
trend（学习趋势）
        ↓
get_student_grading_history
        ↓
使用历史题目事实验证画像结论
        ↓
区分：
长期薄弱
近期退步
偶发错误
        ↓
输出学生诊断
```

输出结构：

```text
整体状态
薄弱知识点
重复错误
学习趋势
历史证据
诊断结论
```

该 Skill 的核心约束是：画像用于定位问题，Grading History（批改历史）用于提供证据，不能只根据画像结论直接生成诊断。

---

### 2.2 `class-learning-analysis`（班级学情分析）

目标：分析班级长期整体状态、薄弱知识点、共性错误、学习趋势和重点关注学生。

主要 Tool：

```text
get_class_profile（查询班级画像：获取班级整体表现、薄弱点、共性错误等）
get_student_profile（查询学生画像：必要时下钻重点学生的长期学习状态）
```

固定 SOP：

```text
get_class_profile
        ↓
分析：
weak_points（薄弱知识点）
common_errors（常见错误）
attention_students（重点关注学生）
trend（学习趋势）
        ↓
必要时 get_student_profile
下钻重点学生
        ↓
输出班级学情诊断
```

输出结构：

```text
班级整体状态
长期薄弱知识点
共性错误
学习趋势
重点关注学生
教学优先级
```

边界：

```text
class-learning-analysis
= 班级长期状态

homework-review
= 某一次具体作业
```

---

### 2.3 `homework-review`（作业讲评分析）

目标：分析某个班级的一次具体作业，定位高错题、共性错误、薄弱知识点和重点学生，并形成讲评优先级与讲评建议。

主要 Tool：

```text
get_homework_analysis（查询作业分析：分析一次作业的整体表现和关键问题）
get_question_analysis（查询题目分析：下钻分析某道题的错误率和错误原因）
get_class_profile（查询班级画像：判断当前问题是否属于班级长期薄弱问题）
```

固定 SOP：

```text
get_homework_analysis
        ↓
分析完成率 / 成绩 / 知识点 / 题目表现
        ↓
找出关键高错题
        ↓
get_question_analysis
        ↓
分析具体错误原因
        ↓
get_class_profile
        ↓
判断：
本次偶发问题
vs
班级长期薄弱问题
        ↓
生成讲评方案
```

输出结构：

```text
作业总体表现
高错题
共性错误
薄弱知识点
重点学生
讲评优先级
讲评建议
```

该 Skill 是 Homework Analysis（作业分析）与 Class Profile（班级画像）之间的连接层：既分析当前作业，又判断问题是否具有长期性。

---

### 2.4 `personalized-intervention`（个性化教学干预）【本阶段暂缓】

> 本阶段暂不实现该 Skill。该流程依赖 `search_teaching_materials` 提供教学资料检索能力，而当前阶段暂不建设 RAG / Teaching Knowledge Base。本文保留完整 SOP，待后续引入教学资料检索能力后启用。

目标：基于学生长期画像和历史证据，为单个学生生成有针对性的教学干预方案。

主要 Tool：

```text
get_student_profile（查询学生画像：定位学生长期薄弱点和学习趋势）
get_student_grading_history（查询批改历史：获取历史证据并验证薄弱点）
search_teaching_materials（检索教学材料：查找知识点相关讲解和教学资源）
search_question_bank（检索题库：按知识点、难度和题型匹配巩固练习）
```

固定 SOP：

```text
get_student_profile
        ↓
get_student_grading_history
        ↓
确认核心薄弱点及历史证据
        ↓
search_teaching_materials
        ↓
确定讲解 / 干预方式
        ↓
search_question_bank
        ↓
匹配巩固练习
        ↓
生成个性化干预方案
```

输出结构：

```text
干预目标
薄弱点依据
讲解建议
练习建议
难度安排
后续观察指标
```

与 `student-diagnosis`（学生学习诊断）的边界：

```text
student-diagnosis
= 诊断发生了什么、为什么

personalized-intervention
= 决定接下来怎么干预
```

---

### 2.5 `differentiated-practice`（分层练习设计）

目标：根据班级和学生掌握情况，将学生划分为不同学习层次，并为各层匹配不同知识点、难度和题型的练习。

主要 Tool：

```text
get_class_profile（查询班级画像：获取班级整体掌握情况和学生分布）
list_class_students（查询班级学生列表：枚举需要参与分层的完整学生集合）
get_student_profile（查询学生画像：读取具体学生的掌握情况）
search_question_bank（检索题库：按知识点、难度和题型匹配分层练习）
```

固定 SOP：

```text
get_class_profile
        ↓
识别班级整体分布
        ↓
list_class_students
        ↓
获得完整班级学生集合
        ↓
按需 get_student_profile
读取参与分层学生的具体掌握情况
        ↓
划分学生层次
        ↓
确定各组：
knowledge_points（知识点）
difficulty（难度）
question_type（题型）
        ↓
search_question_bank
        ↓
生成分层练习
```

默认形成三个练习层次：

```text
基础组
→ 补基础知识点
→ easy（简单）

巩固组
→ 当前核心知识点
→ medium（中等）

提升组
→ 综合应用
→ hard（困难）
```

输出结构：

```text
学生分层结果
各层训练目标
各层知识点
各层难度
各层题目集合
分层依据
```

`list_class_students` 只补齐“有哪些学生需要参与分层”的数据准备，不改变该 Skill 的核心教学判断逻辑。

---

### 2.6 Skill 边界

以下能力不单独设计为 Skill：

```text
weak-point-analysis
error-analysis
question-analysis
profile-query
class-student-listing
class-homework-listing
teaching-material-search
question-search
report-generation
summary-generation
```

原因：

- 数据查询、对象枚举、题目分析、资源搜索属于 Tool。
- 薄弱点分析和错误分析属于现有 Skill 的内部步骤。
- 报告和总结属于 Skill 的输出阶段，不构成独立教学任务流程。

完整能力规划固定为 5 个 Skill；当前阶段实现其中 4 个，`personalized-intervention` 因依赖暂缓的 RAG 教学资料检索能力而暂缓实现。

---

## 3. Tool Contract（工具契约）

每个 Tool 统一定义以下内容：

```text
Tool Contract
│
├── 1. name（名称）
├── 2. description（描述）
├── 3. input_schema（输入 Schema）
├── 4. output_schema（输出 Schema）
├── 5. implementation（实现）
├── 6. data_source（数据源）
├── 7. permission（权限）
├── 8. error_contract（错误契约）
└── 9. tests（测试）
```

其中直接影响 LLM Tool Calling 的核心信息是：

```text
name
+
description
+
input_schema
```

模型根据这三部分判断是否调用 Tool，以及如何生成调用参数。

---

## 4. name（名称）

Tool 名称统一遵循：

- 使用英文。
- 使用动词开头。
- 名称能够直接体现业务作用。
- 一个 Tool 对应一个清晰业务对象或原子能力。

完整规划中的 9 个名称固定为：

```text
get_student_profile
get_student_grading_history
get_class_profile
list_class_students
list_class_homeworks
get_homework_analysis
get_question_analysis
search_teaching_materials
search_question_bank
```

其中 `search_teaching_materials` 本阶段暂缓实现。

---

## 5. description（描述）

Tool Description 不只说明“这个 Tool 是什么”，还需要说明：

```text
什么时候调用
返回什么
什么时候不应该调用
应该改用哪个 Tool
```

`get_student_profile` 的 Description：

```text
查询指定学生在某学科上的长期学习画像，包括整体表现、
知识点掌握度、薄弱知识点、重复错误和不同难度表现。

用于回答学生长期学习状态、薄弱点、学习趋势等问题。

如果需要查询某一道题、某次作业或具体历史错误记录，
应使用 get_student_grading_history，而不是本工具。
```

两个列表 Tool 的 Description 必须显式区分“发现对象”和“分析对象”：

```text
list_class_students
= 查询这个班级有哪些学生
≠ 分析这些学生学得怎么样

list_class_homeworks
= 查询这个时间范围有哪些作业
≠ 分析某次作业表现如何
```

Description 是 Tool Selection（工具选择）的核心依据之一，需要明确各 Tool 之间的边界。

---

## 6. input_schema（输入 Schema）

Tool 输入使用结构化 Schema 定义，推荐使用 Pydantic。

`get_student_profile` 示例：

```python
from pydantic import BaseModel, Field
from typing import Literal


class GetStudentProfileInput(BaseModel):
    student_id: str = Field(
        description="学生唯一 ID"
    )

    subject: Literal["math", "english"] = Field(
        description="需要查询的学科"
    )

    sections: list[
        Literal[
            "overview",
            "knowledge_points",
            "weak_points",
            "recurring_errors",
            "difficulty_performance"
        ]
    ] | None = Field(
        default=None,
        description="需要返回的画像模块；为空时返回完整画像"
    )
```

对应 Tool Calling 参数：

```json
{
  "student_id": "stu_001",
  "subject": "math",
  "sections": [
    "weak_points",
    "recurring_errors"
  ]
}
```

新增列表 Tool 的输入保持简单：

```text
list_class_students
└── class_id（班级ID） 必填

list_class_homeworks
├── class_id（班级ID） 必填
├── subject（学科） 可选
├── start_time（开始时间） 可选
├── end_time（结束时间） 可选
└── limit（返回数量） 可选
```

Input Schema 负责约束：

- 必填参数。
- 可选参数。
- 参数类型。
- 枚举值。
- 参数语义。

---

## 7. output_schema（输出 Schema）

虽然 Tool 框架不一定强制要求每个 Tool 暴露独立 Output Schema，但业务层需要明确返回结构。

```text
GetStudentProfileOutput
│
├── student_id（学生ID）
├── subject（学科）
├── overview（整体表现）
├── knowledge_points（知识点画像）
├── weak_points（薄弱知识点）
├── recurring_errors（重复错误）
└── difficulty_performance（不同难度表现）
```

该结构直接复用 03 中已经定义的 Student Profile（学生画像）。

列表 Tool 返回业务事实摘要：

```text
list_class_students
→ ClassStudent[]

list_class_homeworks
→ HomeworkSummary[]
```

其他 Tool 同样直接复用 03–05 联合设计中已经确定的数据结构，避免重复定义。

---

## 8. implementation（实现）

DeerFlow 中自定义 Tool 使用 LangChain Tool 机制实现，可以使用 `@tool` 或 `BaseTool`。

```python
from langchain_core.tools import tool


@tool(
    "get_student_profile",
    args_schema=GetStudentProfileInput
)
def get_student_profile(
    student_id: str,
    subject: str,
    sections: list[str] | None = None,
) -> dict:
    """查询学生长期学习画像。"""

    profile = profile_service.get_student_profile(
        student_id=student_id,
        subject=subject,
    )

    return filter_sections(profile, sections)
```

Tool 层只负责：

```text
接收 Agent 参数
↓
调用业务 Service
↓
返回结构化结果
```

不在 Tool 内直接堆积 SQL、Redis 操作和复杂画像算法。

统一采用：

```text
Tool
↓
Service
↓
Repository
↓
Redis / MySQL / RAG
```

其中 RAG 属于后续 `search_teaching_materials` 的规划数据源，不进入当前阶段实现。

```text
get_student_profile Tool
        ↓
StudentProfileService
        ↓
├── RedisProfileRepository
└── MySQLGradingRepository

list_class_students Tool
        ↓
ClassQueryService
        ↓
MySQL class_student / student

list_class_homeworks Tool
        ↓
ClassQueryService
        ↓
MySQL homework
```

---

## 9. data_source（数据源）

完整规划中 9 个 Tool 的数据来源如下：

| Tool | 数据来源 |
|---|---|
| `get_student_profile` | Redis → Miss 后基于 MySQL 重算 |
| `get_student_grading_history` | MySQL |
| `get_class_profile` | Redis → Miss 后基于 MySQL 重算 |
| `list_class_students` | MySQL `class_student + student` |
| `list_class_homeworks` | MySQL `homework` |
| `get_homework_analysis` | MySQL 即时聚合 |
| `get_question_analysis` | MySQL 即时聚合 |
| `search_teaching_materials` | 后续：RAG / 教材知识库（本阶段暂缓） |
| `search_question_bank` | MySQL Question Database（题库） |

---

## 10. permission（权限）

教师身份和权限不能依赖 LLM 参数声明。

禁止采用：

```text
LLM 参数
teacher_id = teacher_001
student_id = stu_001
```

并直接相信 `teacher_id`。

权限信息必须来自后端 Runtime Context（运行时上下文）：

```text
当前登录教师身份
        ↓
Runtime / Backend Context
        ↓
Tool
        ↓
权限校验
        ↓
确认教师是否有权访问 Student / Class / Homework
```

LLM 只负责提供业务查询参数：

```text
student_id
class_id
homework_id
question_id
subject
```

用户身份、角色和权限由系统提供并校验。

---

## 11. error_contract（错误契约）

所有 Tool 使用统一返回结构。

正常结果：

```json
{
  "success": true,
  "data": {
    "...": "..."
  }
}
```

失败结果：

```json
{
  "success": false,
  "error": {
    "code": "STUDENT_NOT_FOUND",
    "message": "Student not found"
  }
}
```

错误类型至少覆盖：

```text
INVALID_ARGUMENT（参数错误）
PERMISSION_DENIED（无权限）
STUDENT_NOT_FOUND（学生不存在）
CLASS_NOT_FOUND（班级不存在）
HOMEWORK_NOT_FOUND（作业不存在）
QUESTION_NOT_FOUND（题目不存在）
PROFILE_REBUILD_FAILED（画像重算失败）
DATA_SOURCE_ERROR（数据源异常）
```

业务 Tool 不使用 `None`、自由文本错误和不统一 Exception 作为 Agent 的最终可见返回格式。

---

## 12. tests（测试）

每个当前实现的 Tool 至少覆盖以下测试：

```text
正常查询
参数错误
数据不存在
无权限
Redis Miss（仅画像 Tool）
MySQL 异常
返回 Schema 校验
```

列表 Tool 额外验证：

```text
空班级成员列表
时间范围内无作业
时间范围过滤正确性
班级权限隔离
```

除 Tool 单元测试外，还需要进行 Agent 层 Tool Selection 评测。

```text
用户问题：
“三班这次作业哪几道题问题最大？”

期望 Tool：
get_homework_analysis

不期望：
get_class_profile

用户问题：
“三班这周有哪些数学作业？”

期望 Tool：
list_class_homeworks

不期望：
get_homework_analysis
```

核心评测指标：

```text
Tool Selection Accuracy（工具选择准确率）
Argument Generation Accuracy（参数生成准确率）
Tool Execution Success Rate（工具执行成功率）
```

当前实现的 4 个 Skill 还需要增加流程级评测：

```text
Skill Routing Accuracy（Skill 选择准确率）
Required Tool Coverage（必需 Tool 覆盖率）
Tool Sequence Correctness（Tool 调用顺序正确率）
Evidence Grounding Rate（事实证据支撑率）
Task Completion Rate（任务完成率）
```

---

## 13. 9 个 Tool 的完整职责

### 13.1 `get_student_profile`

作用：获取 Student Profile（学生画像），回答学生长期学习状态、薄弱知识点、重复错误和学习趋势。

```text
输入
student_id（学生ID）        必填
subject（学科）             必填
sections（返回模块）        可选

输出
StudentProfile（学生画像）

数据来源
Redis → Miss 后基于 MySQL 重算
```

---

### 13.2 `get_student_grading_history`

作用：查询学生真实历史批改事实，为 Student Profile（学生画像）中的结论提供证据。

```text
输入
student_id（学生ID）                  必填
subject（学科）                       可选
knowledge_point_key（知识点标识）     可选
error_code（错误类型）                可选
homework_id（作业ID）                 可选
start_time（开始时间）                可选
end_time（结束时间）                  可选
limit（返回数量）                     可选

输出
GradingResult[]

数据来源
MySQL
```

定位：

```text
Student Profile（学生画像）
= 结论

Grading History（批改历史）
= 证据
```

---

### 13.3 `get_class_profile`

作用：获取 Class Profile（班级画像），回答班级长期整体表现、薄弱知识点、常见错误和重点关注学生。

```text
输入
class_id（班级ID）          必填
subject（学科）             必填
sections（返回模块）        可选

输出
ClassProfile（班级画像）

数据来源
Redis → Miss 后基于 MySQL 重算
```

---

### 13.4 `list_class_students`

作用：查询一个班级的完整学生成员列表，用于后续批量学生任务。

```text
输入
class_id（班级ID）          必填

输出
ClassStudent[]
├── student_id
└── name

数据来源
MySQL class_student + student
```

---

### 13.5 `list_class_homeworks`

作用：按班级、学科和时间范围查询作业列表，用于发现后续需要分析的 homework_id。

```text
输入
class_id（班级ID）          必填
subject（学科）             可选
start_time（开始时间）      可选
end_time（结束时间）        可选
limit（返回数量）           可选

输出
HomeworkSummary[]
├── homework_id
├── name
├── subject
└── published_at

数据来源
MySQL homework
```

---

### 13.6 `get_homework_analysis`

作用：分析某个班级的一次具体作业。

```text
输入
homework_id（作业ID）       必填
class_id（班级ID）          必填
sections（返回模块）        可选

输出
HomeworkAnalysis（作业分析）

数据来源
MySQL → 即时聚合
```

主要返回：

```text
completion（完成情况）
performance（成绩表现）
knowledge_points（知识点表现）
questions（题目表现）
attention_students（重点关注学生）
```

---

### 13.7 `get_question_analysis`

作用：下钻分析某个班级在某次作业中的一道具体题。

```text
输入
homework_id（作业ID）       必填
class_id（班级ID）          必填
question_id（题目ID）       必填

输出
QuestionAnalysis（题目分析）

数据来源
MySQL → 即时聚合
```

主要返回：

```text
attempt_count（作答人数）
avg_score_rate（平均得分率）
error_rate（错误率）
knowledge_points（涉及知识点）
common_errors（常见错误）
representative_errors（典型错误证据）
```

---

### 13.8 `search_teaching_materials`【本阶段暂缓】

> 本阶段暂不实现。当前阶段不建设 RAG / Teaching Knowledge Base，仅保留该 Tool 的完整 Contract，待后续知识检索能力建设时启用。

作用：根据教学问题、学科和知识点检索教学材料。

```text
输入
query（查询内容）                       必填
subject（学科）                         可选
knowledge_point_key（知识点标识）       可选
grade（年级）                           可选

输出
TeachingMaterial[]

规划数据来源
教材知识库 / RAG
```

返回结构：

```text
TeachingMaterial
├── title（标题）
├── content（内容）
├── knowledge_point（知识点）
└── source（来源）
```

---

### 13.9 `search_question_bank`

作用：根据知识点、难度和题型检索练习题。

```text
输入
subject（学科）                        必填
knowledge_point_keys（知识点）         必填
difficulty（难度）                    可选
question_type（题型）                 可选
count（数量）                         可选
exclude_question_ids（排除题目）      可选

输出
Question[]

数据来源
MySQL Question Database（题库）
```

返回结构：

```text
Question
├── question_id（题目ID）
├── content（题目内容）
├── knowledge_points（知识点）
├── difficulty（难度）
├── question_type（题型）
└── answer / reference_answer（参考答案）
```

---

## 14. DeerFlow Tool 与 Skill 接入

### 14.1 Tool 注册

当前阶段只注册实际实现的 8 个 Tool。`search_teaching_materials` 的注册配置留到后续 RAG / Teaching Knowledge Base 实现时再加入。

```text
teacher:data
teacher:resource
```

当前阶段示意配置：

```yaml
tool_groups:
  - name: teacher:data
  - name: teacher:resource

tools:
  - name: get_student_profile
    group: teacher:data
    use: teacher_copilot.tools.profile:get_student_profile

  - name: get_student_grading_history
    group: teacher:data
    use: teacher_copilot.tools.profile:get_student_grading_history

  - name: get_class_profile
    group: teacher:data
    use: teacher_copilot.tools.profile:get_class_profile

  - name: list_class_students
    group: teacher:data
    use: teacher_copilot.tools.class_query:list_class_students

  - name: list_class_homeworks
    group: teacher:data
    use: teacher_copilot.tools.class_query:list_class_homeworks

  - name: get_homework_analysis
    group: teacher:data
    use: teacher_copilot.tools.analysis:get_homework_analysis

  - name: get_question_analysis
    group: teacher:data
    use: teacher_copilot.tools.analysis:get_question_analysis

  - name: search_question_bank
    group: teacher:resource
    use: teacher_copilot.tools.resource:search_question_bank
```

后续实现 `search_teaching_materials` 后，再补充：

```yaml
- name: search_teaching_materials
  group: teacher:resource
  use: teacher_copilot.tools.resource:search_teaching_materials
```

### 14.2 Skill 实现

当前阶段实现 4 个 `SKILL.md`；`personalized-intervention` 的设计保留，但不进入当前 Skill 注册与执行范围。

当前阶段逻辑目录：

```text
skills/
├── student-diagnosis/
│   └── SKILL.md
├── class-learning-analysis/
│   └── SKILL.md
├── homework-review/
│   └── SKILL.md
└── differentiated-practice/
    └── SKILL.md
```

后续启用教学资料检索能力后再增加：

```text
skills/
└── personalized-intervention/
    └── SKILL.md
```

每个 `SKILL.md` 至少定义：

```text
name（Skill 名称）
description（何时使用）
task_goal（任务目标）
required_tools（主要 Tool）
workflow（执行步骤）
evidence_rules（事实验证规则）
output_format（输出结构）
fallback（失败 / 数据不足处理）
```

Skill 不直接访问 MySQL、Redis 或 RAG，只通过 Tool 获取数据和资源。

---

## 15. 推荐代码结构

当前阶段：

```text
teacher_copilot/
│
├── tools/
│   ├── schemas/
│   │   ├── student.py
│   │   ├── class_profile.py
│   │   ├── class_query.py
│   │   ├── homework.py
│   │   ├── question.py
│   │   └── resource.py
│   │
│   ├── profile.py
│   ├── class_query.py
│   ├── analysis.py
│   └── resource.py
│
├── services/
│   ├── student_profile_service.py
│   ├── class_profile_service.py
│   ├── class_query_service.py
│   ├── homework_analysis_service.py
│   ├── question_analysis_service.py
│   └── question_bank_service.py
│
├── repositories/
│   ├── mysql/
│   └── redis/
│
└── skills/
    ├── student-diagnosis/
    ├── class-learning-analysis/
    ├── homework-review/
    └── differentiated-practice/
```

后续 RAG / Teaching Knowledge Base 阶段再增加：

```text
services/
└── teaching_material_service.py

repositories/
└── rag/

skills/
└── personalized-intervention/
```

职责边界：

```text
Tool
= Agent 能调用什么

Schema
= 输入参数和返回结果的结构

Service
= 业务逻辑如何执行

Repository
= 数据如何读取和写入

Skill
= 多个 Tool 按什么教学流程组合
```

---

## 16. Tool、Skill 与后续 Multi-Agent 的边界

完整能力规划：

```text
9 个 Tools
  ↓
5 个 Skills
  ↓
Teacher Agent
  ↓
按业务复杂度决定是否 Multi-Agent
```

当前阶段实现：

```text
8 个 Tools
  ↓
4 个 Skills
  ↓
Teacher Lead Agent
```

其中 `search_teaching_materials` 与 `personalized-intervention` 留待后续 RAG / Teaching Knowledge Base 阶段实现。

两个列表 Tool 的定位：

```text
list_class_students
list_class_homeworks
= 业务对象发现能力
= 可以被 Lead Agent / Sub-Agent 作为复杂任务的数据准备步骤
= 不需要单独包装成 Skill
```

Tool 负责原子业务能力；Skill 负责稳定教学任务 SOP；Multi-Agent 只在更大规模、可并行或需要上下文隔离 / 独立审核的真实业务中启用。

Skill 重点定义：

```text
任务目标
调用哪些 Tool
Tool 调用顺序
事实验证规则
分析步骤
输出格式
失败和降级策略
```

最终边界：

```text
Tool = 能力
Skill = 使用能力的方法
Agent = 根据用户目标选择并执行能力
Multi-Agent = 真实业务有并行 / 隔离 / 独立审核收益时的按需协作
```

---

## 17. 参考

- DeerFlow Agent Core：https://hawkli-1994.github.io/deerflow-book/chapters/05-agent-core.html
- DeerFlow Skills & Tools：https://hawkli-1994.github.io/deerflow-book/chapters/06-skills-tools.html
- DeerFlow Custom Skill：https://hawkli-1994.github.io/deerflow-book/chapters/12-custom-skill.html