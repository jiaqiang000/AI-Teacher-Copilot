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
GradingTask
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
| `Submission` | 一个学生对一道题当前有效的提交 |
| `GradingTask` | 一次提交版本对应的异步批改任务 |
| `GradingResult` | 当前有效提交经过完整 Workflow 后的最终批改结果 |

其中最关键的是 `Question`、`Submission`、`GradingTask` 和 `GradingResult`。

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

`difficulty` 不要求教师维护，由 `Qwen3.5-4B` 在数学批改 Workflow 中自动识别。

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

> 学生针对一道题当前提交了什么。

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
  "version": 1,
  "submitted_at": "..."
}
```

这里**没有分数、没有知识点分析、没有评语**，因为 `Submission` 只代表学生提交行为。

当前参赛项目采用简化的重新提交规则：

```text
同一个 student_id + question_id
只保留一个当前 Submission
```

第一次提交：

```text
image = A
version = 1
```

学生修改答案后重新提交：

```text
UPDATE 原 Submission
image = B
version = 2
```

不额外保留 `Submission A / Submission B / Submission C` 这样的完整业务历史。重新提交后的当前版本直接覆盖旧版本，并以当前版本重新批改。

`version` 必须保留，用于防止旧异步任务晚于新任务完成时覆盖最新结果。每次重新提交：

```text
Submission.version += 1
```

### 3.4 GradingTask

`GradingTask（批改任务）` 是工程层对象，用于承载一次 `Submission.version` 对应的批改执行过程。

它主要解决：

```text
后台异步执行
+
实时批改进度
+
失败状态与重试信息
+
页面刷新后的状态恢复
+
重新提交后的版本保护
```

它不改变业务层的核心关系：

```text
当前有效 Submission
        ↓
完整 Grading Workflow
        ↓
当前有效 GradingResult
```

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
                 创建 / 更新 Submission
                           ↓
                    创建 GradingTask
                           ↓
                HTTP 立即返回 task_id
                           ↓
                前端订阅实时批改进度

=================================================

                  Grading Workflow
                           │
                    后台异步开始执行
                           ↓
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
                  组装 GradingResult
                           ↓
              校验 submission_version
                           ↓
                  写入当前有效结果
                           ↓
                         MySQL
```

这构成当前整个学生批改业务闭环。

其中：

- `subject` 和 `question_type` 由教师创建 `Question` 时确定，批改 Workflow 直接读取，不再让模型重复识别。
- 图中原先由 Qwen 判断“题型”的步骤，当前设计改为读取 `Question.subject / question_type` 做确定性路由，避免模型判断结果与业务数据冲突。
- `difficulty` / 题目复杂度不要求教师填写。仅数学题进入 Math Workflow 后，由 `Qwen3.5-4B` 自动判断，并用于后续模型路由。
- 英语作文不进行 difficulty 模型路由，固定使用 `DeepSeek v4 Flash` 完成两阶段 Workflow。
- `knowledge_points` 不要求教师逐题标注，由批改模型根据题目、学生作答和批改过程自动识别，并进入最终 `GradingResult`。
- `GradingTask` 用于工程层追踪任务状态、异步执行、失败记录、页面恢复和提交版本保护，它不改变业务层的 `Submission → GradingResult` 关系。

---

## 5. Grading Workflow 设计

一次当前有效 `Submission.version` 对应一个 `GradingTask`，并进入一次完整批改 Workflow。Workflow 内部可以包含 OCR、模型路由、多个模型调用或 Agent 步骤，但这些都属于内部实现。

### 5.1 通用前置流程

```text
Submission
    ↓
创建 GradingTask
    ↓
后台异步执行
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

### 5.2 GradingTask 状态机与异步执行

#### 5.2.1 用户实时等待，不等于后端同步阻塞

学生上传答案后，产品体验仍然是“立即开始批改并实时等待结果”：

```text
上传答案
↓
✓ 图片上传完成
↓
✓ OCR 识别完成
↓
● 正在解析 / 判断难度 / 批改
↓
○ 生成批改结果
↓
展示最终结果
```

但后端不采用一个 HTTP 请求阻塞到 OCR 和多个模型调用全部完成的方式。

当前 MVP 采用：

```text
POST Submission
        ↓
创建 / 更新 Submission
        ↓
创建 GradingTask
        ↓
立即返回 task_id
        ↓
后台异步执行 Grading Workflow
```

前端拿到 `task_id` 后立即订阅该任务的实时进度，因此：

> **用户体验上是实时等待；后端执行上是异步任务。**

第一版不引入 Kafka、RabbitMQ、Celery 等复杂任务队列。实现可以使用轻量后台异步任务，例如应用进程内 `asyncio` 后台协程。以后如果需要更高并发或独立 Worker，只替换任务执行器，不改变 `GradingTask` 的业务契约。

#### 5.2.2 GradingTask 状态

整个任务状态只保留 4 个：

```text
PENDING
RUNNING
SUCCEEDED
FAILED
```

状态机：

```text
创建任务
↓
PENDING
↓
后台任务正式开始
↓
RUNNING
├── 成功生成并写入当前有效 GradingResult
│      ↓
│   SUCCEEDED
│
└── 批改流程不可恢复失败
       ↓
    FAILED
```

含义：

- `PENDING`：任务已创建，但批改逻辑尚未正式开始，通常持续时间很短。
- `RUNNING`：正在执行 OCR、解析、模型路由或批改。
- `SUCCEEDED`：当前提交版本对应的 `GradingResult` 已成功写入。
- `FAILED`：任务执行失败，保存错误信息供前端展示和工程排查。

#### 5.2.3 status 与 current_stage 分开

`status` 表示整个任务生命周期状态；`current_stage` 表示任务在 `RUNNING` 时具体执行到哪里。

第一版 `current_stage`：

```text
QUEUED
OCR
PARSING
DIFFICULTY_CLASSIFICATION
GRADING
ASSEMBLING_RESULT
COMPLETED
```

数学任务正常阶段：

```text
QUEUED
↓
OCR
↓
PARSING
↓
DIFFICULTY_CLASSIFICATION
↓
GRADING
↓
ASSEMBLING_RESULT
↓
COMPLETED
```

英语作文正常阶段：

```text
QUEUED
↓
OCR
↓
PARSING
↓
GRADING
↓
ASSEMBLING_RESULT
↓
COMPLETED
```

英语作文**不得进入** `DIFFICULTY_CLASSIFICATION`。

#### 5.2.4 GradingTask 逻辑字段

第一版逻辑结构：

```text
GradingTask
├── grading_task_id
├── submission_id
├── submission_version
├── status
├── current_stage
├── retry_count
├── error_code
├── error_message
├── created_at
├── started_at
└── finished_at
```

这里先固定逻辑字段，不在本文件决定 SQL 类型、索引长度等数据库实现细节。

#### 5.2.5 页面刷新后的状态恢复

实时 Streaming 不是任务事实源。

如果学生在批改过程中刷新页面：

```text
GET /grading-tasks/{task_id}
```

前端应先读取当前持久化状态，例如：

```json
{
  "status": "RUNNING",
  "current_stage": "GRADING"
}
```

然后恢复对应进度 UI，并重新订阅实时事件。

因此：

```text
GradingTask 持久化状态
= 当前任务真实状态 / 页面恢复依据

SSE / Streaming Event
= 实时增量体验
```

二者互补，不互相替代。

#### 5.2.6 重新提交版本保护

每个 `GradingTask` 创建时记录当时的：

```text
submission_version
```

例如：

```text
学生上传 A
Submission.version = 1
Task A.submission_version = 1

随后重新上传 B
Submission.version = 2
Task B.submission_version = 2
```

异步场景下 Task A 可能晚于 Task B 完成。因此任何任务写入最终 `GradingResult` 前，必须检查：

```text
GradingTask.submission_version
==
Submission.version
```

只有相等才允许写入当前结果。

如果：

```text
Task A.submission_version = 1
Submission.version = 2
```

则 Task A 已经过期，其结果不得覆盖当前提交对应的结果。

这个约束是系统 invariant（不变量）：

> **旧提交版本对应的异步任务，无论何时完成，都不能覆盖新提交版本的 GradingResult。**

#### 5.2.7 实时批改进度事件

后台 Workflow 在阶段变化时发送结构化进度事件。

第一版事件：

```text
grading.stage.started
grading.stage.completed
grading.stage.failed
grading.completed
```

例如：

```json
{
  "type": "grading.stage.started",
  "task_id": "gt_001",
  "stage": "OCR",
  "label": "正在识别手写答案"
}
```

OCR 完成：

```json
{
  "type": "grading.stage.completed",
  "task_id": "gt_001",
  "stage": "OCR",
  "label": "手写答案识别完成"
}
```

这些事件通过 SSE / Streaming 推送给学生前端，前端按事件更新 `complete / active / pending` 三类步骤状态。

#### 5.2.8 DeerFlow 前端与 Streaming 复用边界

学生批改页面不直接复用 DeerFlow 聊天消息模型。

当前复用策略：

```text
复用：
DeerFlow ChainOfThought UI primitives
+
已有 Streaming / SSE 基础设施与 custom event 思路

不复用：
MessageGroup 的 AIMessage / reasoning / tool_calls 转换逻辑
```

原因是 OCR、难度判断、批改等阶段本身就是明确的业务步骤，没有必要伪装成聊天 Tool Call。

学生前端单独实现：

```text
GradingProgress
```

内部复用 DeerFlow 的步骤 UI primitives，用于展示：

```text
✓ 图片上传完成
│
✓ 手写内容识别完成
│
✓ 解题内容解析完成
│
● 正在分析题目难度
│
○ 等待模型批改
│
○ 生成批改结果
```

如果批改 Workflow 接入 DeerFlow / LangGraph，则优先通过自定义 Stream Event 推送 `grading.*` 事件；如果后续批改 Workflow 不依赖 DeerFlow，也保持同一事件协议，由自己的 SSE endpoint 推送即可。

---

### 5.3 Math Grading Workflow

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
Qwen3.5-4B
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

> **先用 `Qwen3.5-4B` 做难度判断，再根据题目复杂度进行模型级联。简单和中等题继续走 `Qwen3.5-4B`，困难题调用 `DeepSeek v4 Flash`。**

这样可以把大部分常规数学题留在低成本路径，只对确实困难的题使用更强模型。

`Qwen3.5-4B` 和 `DeepSeek v4 Flash` 是当前统一模型版本；真正需要稳定的是输入输出协议和模型路由规则。

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

### 5.4 English Essay Grading Workflow

英语作文采用 **AutoSCORE 风格的两阶段 Workflow**，两个阶段均固定使用 `DeepSeek v4 Flash`。

英语作文当前**不经过 `Qwen3.5-4B` difficulty classification，也不进行 easy / medium / hard 模型路由**。

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
Model = DeepSeek v4 Flash
                 ↓
             evidence.json
                 ↓
Agent 2：评分与反馈
Model = DeepSeek v4 Flash
                 ↓
      分数 + 扣分原因 + 修改建议
                 ↓
        统一组装 GradingResult
```

#### Agent 1：评分证据提取

模型：

```text
DeepSeek v4 Flash
```

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

模型：

```text
DeepSeek v4 Flash
```

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
DeepSeek v4 Flash
Agent 1：只找证据，不打分
        ↓
evidence
        ↓
DeepSeek v4 Flash
Agent 2：基于原文 + Rubric + evidence 正式评分
```

这种设计保留了当前图中的 AutoSCORE 思路，同时避免两个 Agent 对同一件事情重复判断。

---

### 5.5 Workflow 内部实现与业务层的边界

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
GradingTask
Progress Event
```

这些全部属于 **Grading Workflow / 工程执行层内部实现**。

业务层不需要感知内部进行了多少模型调用，也不把 Agent 1 / Agent 2 的中间结果当成多次业务批改。

知识点、错误类型、错误原因等诊断信息同样由 Workflow 内部识别，不要求教师预先逐题标注。

---

### 5.6 Workflow 最终只输出一个当前有效 GradingResult

业务关系固定为：

```text
当前有效 Submission.version
     ↓
【完整 Grading Workflow】
     ↓
当前有效 GradingResult
```

> **一个当前有效 Submission 版本运行一次完整批改 Workflow，最终只保留一个当前有效 GradingResult。**

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

如果学生重新提交，新版本会覆盖旧 Submission 内容，并创建新的 `GradingTask`；旧版本任务即使之后完成，也必须因为 `submission_version` 不匹配而失效。

---

## 6. GradingResult 边界

`GradingResult` 是完整 Grading Workflow 对外输出的唯一当前有效批改结果，需要同时兼容数学和英语作文，并为后续学生画像、班级学情分析和 Teacher Agent 提供稳定的结构化数据基础。

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
Student Submission（当前版本）
   ↓
GradingTask
   ↓
后台异步 Grading Workflow
   ├── Math：Qwen3.5-4B 难度识别 → 模型路由 → 数学批改
   └── English：DeepSeek v4 Flash Evidence Extraction → DeepSeek v4 Flash Scoring
   ↓
submission_version 校验
   ↓
当前有效 GradingResult
   ↓
MySQL
```

同时存在一条面向学生前端的实时进度链：

```text
GradingTask / Grading Workflow
        ↓
grading.* Progress Event
        ↓
SSE / Streaming
        ↓
GradingProgress
        ↓
学生实时看到 complete / active / pending
```

其中：

- `Teacher / Student / Class / Homework / Question` 定义业务上下文。
- `Submission` 表示学生对某一道题当前有效的真实提交；重新提交直接更新同一 Submission，并令 `version + 1`。
- `GradingTask` 负责工程层的后台异步执行、状态追踪、错误信息、页面恢复和提交版本保护。
- `Grading Workflow` 负责 OCR、结构化解析、确定性题型路由，以及数学或英语作文的具体批改过程。
- 数学题由 `Qwen3.5-4B` 识别 `easy / medium / hard`；easy / medium 使用 `Qwen3.5-4B`，hard 使用 `DeepSeek v4 Flash`。
- 英语作文固定使用 `DeepSeek v4 Flash` 完成“证据提取 → 正式评分”两阶段 Workflow，不进行 difficulty 模型路由。
- `GradingResult` 是当前有效提交版本对外输出的唯一最终批改结果。
- `MySQL` 保存业务事实，为后续学生画像、班级学情分析和 Teacher Agent 提供可信数据基础。
- 学生实时进度 UI 复用 DeerFlow `ChainOfThought` 类步骤组件和 Streaming 思路，但不复用 `MessageGroup` 的聊天消息转换逻辑。
