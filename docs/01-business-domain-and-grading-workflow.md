# AI Teacher Copilot：业务边界与批改工作流设计

## 1. MVP 业务边界

整个系统先限定成两个角色、两个学科：

```text
角色
├── Teacher
└── Student

学科
├── Math
└── English
```

当前 MVP：

```text
数学
→ 计算题 / 解答题

英语
→ 英语作文
```

并且：

> **一张学生上传图片 = 一道数学题，或者一篇英语作文。**

暂时不支持整页试卷自动切题。

---

## 2. 完整业务主流程

```text
                        Teacher
                           │
                     创建 Class
                           ↓
                    创建 Homework
                           ↓
                    添加 Question
                           │
              ┌────────────┴────────────┐
              ↓                         ↓
           Math题目                 English作文
              │                         │
         题目/标准答案              作文题目/Rubric
              │                         │
              └────────────┬────────────┘
                           ↓
                       发布作业

=================================================

                        Student
                           │
                     查看 Homework
                           ↓
                    选择 Question
                           ↓
                     上传单题图片
                           ↓
                       Submission
                           ↓

=================================================

                  Grading Workflow
                           │
                          OCR
                           ↓
                    结构化内容识别
                           ↓
                  学科 / 题型路由
                      ↙         ↘
                   Math        English
                    ↓             ↓
                数学批改       作文批改
                    ↓             ↓
                    └──────┬──────┘
                           ↓
                  最终 GradingResult
                           ↓
                         MySQL
```

这构成当前整个学生批改业务闭环。

---

## 3. 核心对象

```text
Teacher
   │
   ↓
Class
   │
   ↓
Homework
   │
   ↓
Question
   │
   ↓
Submission ← Student
   │
   ↓
GradingResult
   │
   ↓
KnowledgePoint
```

核心对象职责如下：

| 对象 | 含义 |
|---|---|
| `Teacher` | 教师 |
| `Student` | 学生 |
| `Class` | 班级 |
| `Homework` | 一次作业 |
| `Question` | 作业中的一道题 |
| `Submission` | 一个学生对一道题的一次提交 |
| `GradingResult` | 这次提交经过完整 Workflow 后的最终批改结果 |
| `KnowledgePoint` | 题目及批改结果对应的知识点 |

其中最关键的是 `Question`、`Submission` 和 `GradingResult`。

---

## 4. Homework

例如：

```text
Homework
────────────────────
id: hw_001
name: 八年级数学周末作业
class_id: class_03
teacher_id: teacher_01
subject: math
published_at: ...
```

包含：

```text
Homework hw_001

├── Question q001
├── Question q002
├── Question q003
└── Question q004
```

英语也一样：

```text
Homework
英语 Unit 3 Writing

└── Question q101
    Write an article about...
```

---

## 5. Question

不要让学生随便上传一张完全不知道来源的图片。应该先存在 `Question`，学生再提交答案。

### 5.1 数学 Question

例如：

```text
question_id: q001

subject:
math

question_type:
calculation

content:
解方程 2x + 4 = 8

standard_answer:
x = 2

max_score:
10

knowledge_points:
- 一元一次方程
- 移项
```

后续还可以增加：

```text
reference_solution
grading_rubric
difficulty
```

### 5.2 英语作文 Question

例如：

```text
question_id: q101

subject:
english

question_type:
essay

content:
Write an article about your summer vacation.

max_score:
20

rubric:
├── Content: 5
├── Organization: 5
├── Grammar: 5
└── Vocabulary: 5
```

因此从一开始，`Question` 必须包含：

```text
Question
├── subject
└── question_type
```

后面的 Router 才能稳定工作。

---

## 6. Submission

`Submission` 只表示：

> 学生提交了什么。

例如小明做 q001：

```text
Student
小明
   ↓
Question q001
   ↓
上传 answer_001.jpg
   ↓
Submission sub_10001
```

Submission 大概表达：

```json
{
  "submission_id": "sub_10001",
  "student_id": "stu_001",
  "question_id": "q001",
  "homework_id": "hw_001",
  "image_url": "...",
  "submitted_at": "..."
}
```

这里**没有分数、没有知识点分析、没有评语**。

因为 `Submission` 只代表学生提交行为。

如果学生修改答案后重新提交：

```text
第一次图片
→ Submission A
→ GradingResult A

重新修改后上传
→ Submission B
→ GradingResult B
```

这是两个独立提交。

---

## 7. Grading Workflow

`Submission` 进入批改 Workflow：

```text
Submission
    ↓
OCR
    ↓
结构化解析
    ↓
Qwen 小模型识别题型 / 难度
    ↓

如果 Math
    ↓
Math Grading Workflow
    ├── 简单 → 小模型
    └── 困难 → 强模型

如果 English Essay
    ↓
AutoSCORE 风格 Workflow
    ├── Evidence Extraction
    └── Scoring
```

其中：

```text
Qwen
DeepSeek
Agent1
Agent2
Rubric
模型路由
```

全部属于 **Grading Workflow 内部实现**，业务层不需要感知内部进行了多少模型调用或 Agent 步骤。

---

## 8. Workflow 最终只输出一个 GradingResult

业务关系固定为：

```text
Submission
     ↓
【完整 Grading Workflow】
     ↓
GradingResult
```

> **一次 Submission 运行一次完整批改 Workflow，最终只产生一个 GradingResult。**

不存在业务层面的“第一次批改结果”“第二次复核结果”。即使 Workflow 内部存在模型路由、证据提取、评分、验证等多个步骤，对外仍然只有一个最终批改结果。

---

## 9. GradingResult 兼容数学与英语

不要为数学和英语维护两套完全独立的数据体系，统一使用公共 `GradingResult`。

公共字段：

```text
GradingResult
│
├── grading_result_id
├── submission_id
│
├── subject
├── question_type
│
├── score
├── max_score
├── score_rate
│
├── knowledge_points
├── error_types
├── error_reason
│
├── feedback
│
├── difficulty
├── grading_model
└── created_at
```

不同题型可以增加自己的详细结果。

### 9.1 数学扩展信息

例如：

```json
{
  "subject": "math",

  "score": 8,
  "max_score": 10,
  "correct": false,

  "knowledge_points": [
    "一元一次方程",
    "移项"
  ],

  "error_types": [
    "符号错误"
  ],

  "error_reason": "移项时符号处理错误",

  "process": {
    "process_score": 6,
    "final_answer_score": 2
  },

  "feedback": "解题思路正确，但移项时需要注意符号变化。"
}
```

### 9.2 英语作文扩展信息

```json
{
  "subject": "english",

  "score": 16,
  "max_score": 20,

  "knowledge_points": [
    "一般过去时",
    "连接词"
  ],

  "error_types": [
    "时态错误",
    "连接词使用不足"
  ],

  "dimension_scores": {
    "content": 5,
    "organization": 4,
    "grammar": 3,
    "vocabulary": 4
  },

  "feedback": "内容完整，但过去时使用存在多处错误，段落之间可以增加连接词。"
}
```

这样后续学生画像可以同时覆盖：

```text
Student
│
├── Math
│   ├── 一元一次方程
│   ├── 因式分解
│   └── 函数
│
└── English
    ├── Grammar
    ├── Vocabulary
    ├── Organization
    └── Writing
```

---

## 10. 当前业务事实链

当前核心业务关系固定为：

```text
Teacher
   ↓
Class
   ↓
Homework
   ↓
Question
   ↓
Student Submission
   ↓
Grading Workflow
   ↓
GradingResult
   ↓
MySQL
```

其中：

- `Teacher / Student / Class / Homework / Question` 定义业务上下文。
- `Submission` 表示学生的一次真实提交。
- `Grading Workflow` 负责 OCR、模型路由以及数学或英语作文的具体批改过程。
- `GradingResult` 是整个 Workflow 对外输出的唯一最终批改结果。
- `MySQL` 保存业务事实，为后续学生画像、班级学情分析和 Teacher Agent 提供可信数据基础。
