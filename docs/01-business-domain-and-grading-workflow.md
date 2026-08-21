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

## 2. 核心业务对象

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

其中最关键的是 `Question`、`Submission` 和 `GradingResult`。

知识点不作为教师必须维护的前置业务对象。当前 MVP 中，知识点由批改模型自动识别，并作为 `GradingResult` 中的结构化诊断结果沉淀；后续如果引入统一知识点体系，再增加知识点标准化与映射层。

---

## 3. 关键业务对象说明

### 3.1 Homework

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

### 3.2 Question

学生不是随意上传一张来源未知的图片，而是先存在 `Question`，学生选择题目后再提交答案。

#### 数学 Question

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
```

后续还可以增加：

```text
reference_solution
grading_rubric
```

`difficulty` 不要求教师维护，由 Qwen 小模型在批改 Workflow 中自动识别。

#### 英语作文 Question

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

后面的 Workflow 直接依据这些业务属性路由，不再使用 LLM 重复识别学科和题型。

### 3.3 Submission

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

这里**没有分数、没有知识点分析、没有评语**，因为 `Submission` 只代表学生提交行为。

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

## 4. 完整业务主流程

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
                  创建持久化批改任务
                           ↓

=================================================

                  Grading Workflow
                           │
                          OCR
                           ↓
                    结构化内容识别
                           ↓
              读取 Question 业务属性
               subject / question_type
                           ↓
                    按业务属性路由
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

其中：

- `subject` 和 `question_type` 由教师创建 `Question` 时确定，批改 Workflow 直接读取，不再让模型重复识别。
- 图中原先由 Qwen 判断“题型”的步骤，当前设计改为读取 `Question.subject / question_type` 做确定性路由，避免模型判断结果与业务数据冲突。
- `difficulty` / 题目复杂度不要求教师填写。数学题进入 Math Workflow 后，由 Qwen 小模型自动判断，并用于后续模型路由。
- `knowledge_points` 不要求教师逐题标注，由批改模型根据题目、学生作答和批改过程自动识别，并进入最终 `GradingResult`。
- 持久化批改任务用于工程层追踪任务状态、失败重试和异步执行，它不改变业务层的 `Submission → GradingResult` 关系。

---

## 5. Grading Workflow 设计

一次 `Submission` 只进入一次完整批改 Workflow。Workflow 内部可以包含 OCR、模型路由、多个模型调用或 Agent 步骤，但这些都属于内部实现。

### 5.1 通用前置流程

```text
Submission
    ↓
创建持久化批改任务
    ↓
OCR
    ↓
结构化解析
    ↓
读取 Question
├── subject
└── question_type
    ↓
按业务属性路由
├── Math
└── English Essay
```

这里不再让 Qwen 判断学科或题型。

教师创建 `Question` 时已经确定：

```text
subject
question_type
```

因此这一层采用确定性路由。

---

### 5.2 Math Grading Workflow

数学题当前重点支持计算题 / 解答题。

整体流程对应当前数学批改设计：

```text
Math Submission
      ↓
Question
├── 题目内容
├── 标准答案
├── max_score
└── 可选 reference_solution / grading_rubric
      +
OCR 后的学生答案 / 解题过程
      ↓
Qwen3.5-4B 小模型
难度识别 Prompt
      ↓
输出
├── difficulty: easy / medium / hard
└── reason: 一句话说明判断原因
      ↓
模型路由
├── easy
│      ↓
│   Qwen3.5-4B
│
├── medium
│      ↓
│   Qwen3.5-4B
│
└── hard
       ↓
   DeepSeek v4 Flash
      ↓
数学批改结果
├── 对错判断
├── 得分
├── 过程分
├── 错误诊断
└── 知识点识别
      ↓
统一组装 GradingResult
```

这里的核心思想是：

> **先用便宜的小模型做难度判断，再根据题目复杂度进行模型级联。简单和中等题继续走小模型，困难题再调用更强模型。**

这样可以把大部分常规数学题留在低成本路径，只对确实困难的题使用更强模型。

`Qwen3.5-4B` 和 `DeepSeek v4 Flash` 是当前实现方案中的模型选择，后续可以替换；真正需要稳定的是输入输出协议和模型路由规则。

数学 Workflow 最终至少需要产出当前题的：

```text
对错
得分
过程分
错误诊断
知识点
```

这些结果再统一映射到 `GradingResult`，而不是让不同模型分别产生业务层批改结果。

---

### 5.3 English Essay Grading Workflow

英语作文采用 **AutoSCORE 风格的两阶段 Workflow**。

参考思路：

```text
AutoSCORE: Enhancing Automated Scoring with Multi-Agent
Large Language Models via Structured Component Recognition
AAAI 2026
```

核心思想不是让两个 Agent 重复打分，而是把“找评分证据”和“根据证据评分”拆开：

```text
作文原文 + 作文题目 + 评分标准 Rubric
                 ↓
        Agent 1：评分证据提取
                 ↓
             evidence.json
                 ↓
        Agent 2：评分与反馈
                 ↓
      分数 + 扣分原因 + 修改建议
                 ↓
        统一组装 GradingResult
```

#### Agent 1：评分证据提取

输入：

```text
作文原文
+
作文题目
+
评分标准 Rubric
```

职责：

> 根据 Rubric，从学生作文中提取能够支持后续评分的客观证据。

例如关注：

```text
内容是否覆盖题目要求
结构与组织情况
语法表现
词汇使用
与各评分维度相关的原文证据
```

Agent 1 **不直接打分**，只生成结构化评分证据：

```text
evidence.json
```

#### Agent 2：真正评分与反馈

输入：

```text
作文题目
+
Rubric
+
学生作文原文
+
Agent 1 evidence.json
```

职责：

```text
依据 Rubric 正式评分
↓
给出分数
↓
说明扣分原因
↓
给出修改建议
```

因此英语作文 Workflow 的核心关系是：

```text
Agent 1
只找证据，不打分
        ↓
evidence
        ↓
Agent 2
基于原文 + Rubric + evidence 正式评分
```

这种设计保留了当前图中的 AutoSCORE 思路，同时避免两个 Agent 对同一件事情重复判断。

---

### 5.4 Workflow 内部实现与业务层的边界

当前 Workflow 内部可能出现：

```text
OCR
Qwen3.5-4B
DeepSeek v4 Flash
Agent 1
Agent 2
Rubric
evidence.json
模型路由
Prompt
```

这些全部属于 **Grading Workflow 内部实现**。

业务层不需要感知内部进行了多少模型调用，也不把 Agent 1 / Agent 2 的中间结果当成多次业务批改。

知识点、错误类型、错误原因等诊断信息同样由 Workflow 内部识别，不要求教师预先逐题标注。

---

### 5.5 Workflow 最终只输出一个 GradingResult

业务关系固定为：

```text
Submission
     ↓
【完整 Grading Workflow】
     ↓
GradingResult
```

> **一次 Submission 运行一次完整批改 Workflow，最终只产生一个 GradingResult。**

不存在业务层面的“第一次批改结果”“第二次复核结果”。

即使内部存在：

```text
难度识别
模型路由
证据提取
正式评分
错误诊断
知识点识别
```

对外仍然只有一个最终批改结果。

---

## 6. GradingResult 边界

`GradingResult` 是完整 Grading Workflow 对外输出的唯一最终批改结果，需要同时兼容数学和英语作文，并为后续学生画像、班级学情分析和 Teacher Agent 提供稳定的结构化数据基础。

本文件只定义 `GradingResult` 在业务流程中的位置、来源和职责，不在这里重复展开具体字段设计。

> `GradingResult` 的完整 Schema、公共字段、数学扩展字段、英语作文扩展字段以及哪些字段用于后续数据沉淀，统一在 `docs/02-grading-result-schema.md` 中定义。

---

## 7. 当前业务事实链

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
持久化批改任务
   ↓
Grading Workflow
   ├── Math：难度识别 → 模型路由 → 数学批改
   └── English：Evidence Extraction → Scoring
   ↓
GradingResult
   ↓
MySQL
```

其中：

- `Teacher / Student / Class / Homework / Question` 定义业务上下文。
- `Submission` 表示学生的一次真实提交。
- 持久化批改任务负责工程层的任务状态追踪、异步执行和失败重试。
- `Grading Workflow` 负责 OCR、结构化解析、确定性题型路由，以及数学或英语作文的具体批改过程。
- 数学题由 Qwen 小模型识别 `easy / medium / hard`，再决定走小模型快速路径还是强模型路径。
- 英语作文采用 AutoSCORE 风格的“证据提取 → 正式评分”两阶段 Workflow。
- `GradingResult` 是整个 Workflow 对外输出的唯一最终批改结果。
- `MySQL` 保存业务事实，为后续学生画像、班级学情分析和 Teacher Agent 提供可信数据基础。
