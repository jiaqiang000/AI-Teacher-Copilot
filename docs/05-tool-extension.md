# AI Teacher Copilot：05 Teacher Agent Tool 扩展设计

## 1. Tool 与 Skill 的职责边界

Teacher Agent 当前定义的 7 个核心业务能力全部实现为 Tool，不实现为 Skill。

```text
Teacher Agent
│
├── Skills（如何完成教学任务）
│
└── Tools（实际查询和操作数据）
    ├── get_student_profile
    ├── get_student_grading_history
    ├── get_class_profile
    ├── get_homework_analysis
    ├── get_question_analysis
    ├── search_teaching_materials
    └── search_question_bank
```

职责划分：

```text
Tool
= 原子业务能力
= 明确输入 → 查询 / 计算 / 检索 → 返回结构化结果

Skill
= 教学任务 SOP
= 规定如何组合多个 Tool、如何分析结果、如何生成最终输出
```

7 个 Tool 均属于明确的数据查询、数据分析或资源检索能力，因此统一保留为 Tool。

Skill 在后续阶段独立设计，用于组合这些 Tool 完成复杂教学任务。

---

## 2. Tool 与 Skill 的组合关系

后续可设计以下 Skill：

```text
student-diagnosis
（学生学习诊断）

class-learning-analysis
（班级学情分析）

homework-review
（作业讲评分析）

differentiated-practice
（分层练习设计）

personalized-intervention
（个性化教学干预）
```

例如：

```text
student-diagnosis Skill
        │
        ├── get_student_profile
        ├── get_student_grading_history
        └── search_teaching_materials
```

对应 Skill 的流程可以定义为：

```text
1. 查询 Student Profile（学生画像）
2. 找出 weak_points（薄弱知识点）
3. 对重要薄弱点查询 grading history（批改历史）
4. 使用历史事实验证画像结论
5. 必要时检索教学材料
6. 按固定结构输出学生诊断
```

Tool 不负责决定后续流程，也不在内部继续调用其他业务 Tool 完成完整教学任务。

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

当前 7 个名称保持不变：

```text
get_student_profile
get_student_grading_history
get_class_profile
get_homework_analysis
get_question_analysis
search_teaching_materials
search_question_bank
```

---

## 5. description（描述）

Tool Description 不只说明“这个 Tool 是什么”，还需要说明：

```text
什么时候调用
返回什么
什么时候不应该调用
应该改用哪个 Tool
```

例如 `get_student_profile`：

```text
查询指定学生在某学科上的长期学习画像，包括整体表现、
知识点掌握度、薄弱知识点、重复错误和不同难度表现。

用于回答学生长期学习状态、薄弱点、学习趋势等问题。

如果需要查询某一道题、某次作业或具体历史错误记录，
应使用 get_student_grading_history，而不是本工具。
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

Input Schema 负责约束：

- 必填参数。
- 可选参数。
- 参数类型。
- 枚举值。
- 参数语义。

---

## 7. output_schema（输出 Schema）

虽然 Tool 框架不一定强制要求每个 Tool 暴露独立 Output Schema，但业务层需要明确返回结构。

例如：

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

该结构直接复用 03 中已经定义的：

```text
Student Profile（学生画像）
```

对应关系：

```text
03
定义 Student Profile Schema
        ↓
05
get_student_profile
        ↓
Student Profile 作为返回结构
```

其他 Tool 同样直接复用 03–05 联合设计中已经确定的数据结构，避免重复定义。

---

## 8. implementation（实现）

DeerFlow 中自定义 Tool 使用 LangChain Tool 机制实现，可以使用 `@tool` 或 `BaseTool`。

示例：

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

例如：

```text
get_student_profile Tool
        ↓
StudentProfileService
        ↓
├── RedisProfileRepository
└── MySQLGradingRepository
```

---

## 9. data_source（数据源）

7 个 Tool 的数据来源固定如下：

| Tool | 数据来源 |
|---|---|
| `get_student_profile` | Redis → Miss 后基于 MySQL 重算 |
| `get_student_grading_history` | MySQL |
| `get_class_profile` | Redis → Miss 后基于 MySQL 重算 |
| `get_homework_analysis` | MySQL 即时聚合 |
| `get_question_analysis` | MySQL 即时聚合 |
| `search_teaching_materials` | RAG / 教材知识库 |
| `search_question_bank` | Question Database（题库）/ RAG |

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

每个 Tool 至少覆盖以下测试：

```text
正常查询
参数错误
数据不存在
无权限
Redis Miss
MySQL 异常
返回 Schema 校验
```

除 Tool 单元测试外，还需要进行 Agent 层 Tool Selection 评测。

例如：

```text
用户问题：
“三班这次作业哪几道题问题最大？”

期望 Tool：
get_homework_analysis

不期望：
get_class_profile
```

核心评测指标：

```text
Tool Selection Accuracy（工具选择准确率）
Argument Generation Accuracy（参数生成准确率）
Tool Execution Success Rate（工具执行成功率）
```

---

## 13. 7 个 Tool 的最终职责

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

### 13.4 `get_homework_analysis`

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

### 13.5 `get_question_analysis`

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

### 13.6 `search_teaching_materials`

作用：根据教学问题、学科和知识点检索教学材料。

```text
输入
query（查询内容）                       必填
subject（学科）                         可选
knowledge_point_key（知识点标识）       可选
grade（年级）                           可选

输出
TeachingMaterial[]

数据来源
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

### 13.7 `search_question_bank`

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
Question Database（题库）/ RAG
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

## 14. DeerFlow Tool 注册

自定义 Tool 在 DeerFlow 中注册到 Tool 配置，并按业务能力分组。

建议分为：

```text
teacher:data
teacher:resource
```

示意配置：

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

  - name: get_homework_analysis
    group: teacher:data
    use: teacher_copilot.tools.analysis:get_homework_analysis

  - name: get_question_analysis
    group: teacher:data
    use: teacher_copilot.tools.analysis:get_question_analysis

  - name: search_teaching_materials
    group: teacher:resource
    use: teacher_copilot.tools.resource:search_teaching_materials

  - name: search_question_bank
    group: teacher:resource
    use: teacher_copilot.tools.resource:search_question_bank
```

---

## 15. 推荐代码结构

```text
teacher_copilot/
│
├── tools/
│   ├── schemas/
│   │   ├── student.py
│   │   ├── class_profile.py
│   │   ├── homework.py
│   │   ├── question.py
│   │   └── resource.py
│   │
│   ├── profile.py
│   ├── analysis.py
│   └── resource.py
│
├── services/
│   ├── student_profile_service.py
│   ├── class_profile_service.py
│   ├── homework_analysis_service.py
│   ├── question_analysis_service.py
│   ├── teaching_material_service.py
│   └── question_bank_service.py
│
└── repositories/
    ├── mysql/
    ├── redis/
    └── rag/
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

## 16. 与后续 Skill 的边界

05 阶段完成 Tool 的原子业务能力和契约设计。

后续 Skill 不重新实现数据查询逻辑，而是调用这些 Tool 完成教学任务：

```text
Tools
  ↓
Skills
  ↓
Teacher Agent
  ↓
Multi-Agent
```

因此后续 Skill 重点定义：

```text
任务目标
调用哪些 Tool
Tool 调用顺序
事实验证规则
分析步骤
输出格式
失败和降级策略
```

Tool 与 Skill 的最终边界保持：

```text
Tool = 能力
Skill = 使用能力的方法
```

---

## 17. 参考

- DeerFlow Agent Core：https://hawkli-1994.github.io/deerflow-book/chapters/05-agent-core.html
- DeerFlow Skills & Tools：https://hawkli-1994.github.io/deerflow-book/chapters/06-skills-tools.html
- DeerFlow Custom Skill：https://hawkli-1994.github.io/deerflow-book/chapters/12-custom-skill.html
