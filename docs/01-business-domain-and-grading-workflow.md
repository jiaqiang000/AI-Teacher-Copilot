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
Grading Workflow
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
| `Submission` | 一个学生对一道题当前有效的答案，同时保存当前批改状态和执行阶段 |
| `GradingResult` | 当前 Submission 成功完成完整 Workflow 后的最终批改结果 |

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

question_no:
1

subject:
math

question_type:
calculation

content:
解方程 2x + 4 = 8

max_score:
10
```

数学步骤分由批改模型根据正式题目、题目总分和学生实际 OCR 作答动态判断，不要求教师预先维护固定解法或固定步骤评分模板。

`difficulty` 不要求教师维护，由 `Qwen3.5-4B` 在数学批改 Workflow 中自动识别。

#### 英语作文 Question

例如：

```text
question_id: q101

question_no:
1

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
├── question_no（题号）
├── subject（学科）
└── question_type（题型）
```

`question_no（题号）` 表示题目在当前 Homework（作业）中的展示序号。例如：

```text
homework_id = hw_004
question_id = q008
question_no = 8
```

教师和学生看到的是“第 8 题”，系统内部仍然使用 `question_id` 标识具体题目。同一个 Homework 内 `question_no` 不重复。教师创建作业题目时，由前端按顺序默认生成 `1、2、3……`，需要时允许教师调整。

后面的 Workflow 直接依据这些业务属性路由，不再使用 LLM 重复识别学科和题型。

### 3.3 Submission

`Submission` 表示：

> **学生针对一道题当前有效的答案，同时也是这份当前答案的批改状态记录。**

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

第一版逻辑结构固定为：

```text
Submission
├── submission_id
├── student_id
├── question_id
├── homework_id
├── image_url
│
├── status
├── current_stage
├── error_code
├── error_message
│
├── submitted_at
├── started_at
├── finished_at
└── updated_at
```

示例：

```json
{
  "submission_id": "sub_10001",
  "student_id": "stu_001",
  "question_id": "q001",
  "homework_id": "hw_001",
  "image_url": "...",
  "status": "RUNNING",
  "current_stage": "GRADING",
  "error_code": null,
  "error_message": null,
  "submitted_at": "...",
  "started_at": "...",
  "finished_at": null,
  "updated_at": "..."
}
```

这里仍然**没有分数、知识点分析或评语**；这些属于 `GradingResult`。`Submission` 只负责当前答案和当前批改生命周期。

当前参赛项目采用简化的重新提交规则：

```text
同一个 student_id + question_id
只保留一个当前 Submission
```

数据库层增加唯一约束：

```text
UNIQUE(student_id, question_id)
```

业务规则固定为：

```text
不存在 Submission
→ 创建 Submission
→ status = PENDING
→ current_stage = QUEUED

已存在，且 status = PENDING / RUNNING
→ 拒绝再次提交
→ HTTP 409
→ code = SUBMISSION_GRADING_IN_PROGRESS

已存在，且 status = SUCCEEDED / FAILED
→ 复用原 submission_id
→ 替换 image_url
→ 删除旧 OCRResult / GradingResult
→ 清空错误与完成时间
→ status = PENDING
→ current_stage = QUEUED
→ 重新执行完整 Workflow
```

第一版不保存 `Submission A / Submission B / Submission C` 这样的历史版本，也不使用：

```text
Submission.version
submission_version
GradingTask
Idempotency Key
旧任务 / 新任务版本竞争
```

原因是同一学生同一道题在 `PENDING / RUNNING` 时不允许再次提交，因此任意时刻最多只有一个运行中的批改 Workflow。

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
       题目内容 / max_score          作文题目/Rubric
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
             POST /api/questions/{question_id}/submission
                           ↓
                 创建 / 重置 Submission
                           ↓
              HTTP 立即返回 submission_id
                           ↓
         DeerFlow Chat 创建 GradingProgressMessage
                           ↓
          订阅 /api/submissions/{submission_id}/events

=================================================

                  Grading Workflow
                           │
                    后台异步开始执行
                           ↓
          Submission = RUNNING / OCR
                           ↓
                          OCR
                           ↓
               持久化 OCRResult
                           ↓
                    结构化内容解析
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
                  写入当前有效结果
                           ↓
       Submission = SUCCEEDED / COMPLETED
                           ↓
                         MySQL
```

这构成当前整个学生批改业务闭环。

其中：

- `subject` 和 `question_type` 由教师创建 `Question` 时确定，批改 Workflow 直接读取，不再让模型重复识别。
- `difficulty` / 题目复杂度不要求教师填写。仅数学题进入 Math Workflow 后，由 `Qwen3.5-4B` 自动判断，并用于后续模型路由。
- 英语作文不进行 difficulty 模型路由，固定使用 `DeepSeek v4 Flash` 完成两阶段 Workflow。
- `knowledge_points` 不要求教师逐题标注，由批改模型根据题目、学生作答和批改过程自动识别，并进入最终 `GradingResult`。
- `OCRResult` 保存 OCR 对学生原图的结构化识别证据，为数学步骤评分、错误追溯和原图错误定位提供依据。
- `Submission.status / current_stage` 是当前批改状态事实源；SSE / Streaming Event 只负责把状态变化实时推送给前端。
- 用户上传后仍在 DeerFlow Chat 中实时看到 OCR、解析、难度判断、批改、结果组装等过程；本次简化只删除独立任务和版本竞争设计，不削减前端过程可视化能力。

---

## 5. Grading Workflow 设计

一个当前 `Submission` 被接受提交后启动一次完整 Grading Workflow。Workflow 内部可以包含 OCR、模型路由、多个模型调用或 Agent 步骤，但批改状态和阶段直接持久化到 `Submission`，不再创建独立批改任务对象。

### 5.1 通用前置流程

```text
Submission
    ↓
status = PENDING
current_stage = QUEUED
    ↓
启动后台异步 Workflow
    ↓
status = RUNNING
current_stage = OCR
    ↓
OCR
    ↓
持久化 OCRResult
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

### 5.2 Submission 驱动的异步批改与实时进度

#### 5.2.1 用户实时等待，不等于后端同步阻塞

学生上传答案后，产品体验仍然是“立即开始批改并实时等待结果”：

```text
上传答案
↓
✓ 图片上传完成
↓
● OCR 识别中
↓
○ 作答解析
↓
○ 难度判断（仅数学）
↓
○ 批改
↓
○ 生成批改结果
↓
展示最终结果
```

但后端不采用一个 HTTP 请求阻塞到 OCR 和多个模型调用全部完成的方式。

当前 MVP 采用：

```text
POST /api/questions/{question_id}/submission
        ↓
创建 / 重置 Submission
        ↓
立即返回 submission_id
        ↓
asyncio.create_task(
    run_grading_workflow(submission_id)
)
        ↓
后台异步执行 Grading Workflow
```

示例响应：

```json
{
  "submission_id": "sub_10001",
  "status": "PENDING",
  "current_stage": "QUEUED"
}
```

前端拿到 `submission_id` 后立即创建聊天框内的批改进度消息，并订阅该 Submission 的实时事件，因此：

> **用户体验上是实时等待；后端执行上是轻量异步 Workflow。**

第一版不引入 Kafka、RabbitMQ、Celery 等复杂任务队列。以后如果需要更高并发或独立 Worker，可以替换任务执行器，但 `Submission + grading.* Event` 的业务契约不变。

#### 5.2.2 Submission 批改状态

整个当前批改生命周期只保留 4 个状态：

```text
PENDING
RUNNING
SUCCEEDED
FAILED
```

状态机：

```text
提交被接受
↓
PENDING
↓
后台 Workflow 正式开始
↓
RUNNING
├── 成功写入当前 GradingResult
│      ↓
│   SUCCEEDED
│
└── 批改流程不可恢复失败
       ↓
    FAILED
```

含义：

- `PENDING`：Submission 已创建或重置，但批改逻辑尚未正式开始，通常持续时间很短。
- `RUNNING`：正在执行 OCR、解析、模型路由或批改。
- `SUCCEEDED`：当前 Submission 对应的 `GradingResult` 已成功写入。
- `FAILED`：当前批改执行失败，保存错误信息供前端展示和工程排查。

#### 5.2.3 status 与 current_stage 分开

`status` 表示当前 Submission 的整个批改生命周期；`current_stage` 表示 `RUNNING` 时具体执行到哪里。

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

数学正常阶段：

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

#### 5.2.4 Submission 批改字段与数据约束

`Submission` 中与批改生命周期直接相关的逻辑字段固定为：

```text
status
current_stage
error_code
error_message
submitted_at
started_at
finished_at
updated_at
```

数据库约束：

```text
UNIQUE(student_id, question_id)
```

不再建立：

```text
grading_task_id
submission_version
retry_count
```

也不单独建立 `grading_task` 表。

#### 5.2.5 页面刷新后的状态恢复

实时 Streaming 不是状态事实源。

如果学生在批改过程中刷新页面：

```http
GET /api/submissions/{submission_id}
```

前端先读取当前持久化状态，例如：

```json
{
  "submission_id": "sub_10001",
  "status": "RUNNING",
  "current_stage": "GRADING",
  "error_code": null,
  "error_message": null
}
```

前端根据 `subject + current_stage` 重建已完成 / active / pending 步骤，然后重新订阅：

```http
GET /api/submissions/{submission_id}/events
```

因此：

```text
Submission.status / current_stage
= 当前批改真实状态 / 页面恢复依据

SSE / Streaming Event
= 实时增量体验
```

刷新页面不得把进度重新显示为 `QUEUED`，也不得重新启动一次 Workflow。

#### 5.2.6 重复提交与重新提交规则

这是删除提交版本机制后的核心业务约束。

如果当前状态为：

```text
PENDING
或
RUNNING
```

学生再次提交时后端直接拒绝：

```text
HTTP 409 Conflict
```

返回：

```json
{
  "code": "SUBMISSION_GRADING_IN_PROGRESS",
  "message": "该题正在批改中，请等待批改完成后再重新提交。",
  "submission_id": "sub_10001"
}
```

前端不创建新 Submission、不启动新 Workflow，继续显示并订阅当前 `submission_id` 的批改过程。

如果当前状态为：

```text
SUCCEEDED
或
FAILED
```

允许重新提交，但复用同一条 Submission：

```text
submission_id      保持不变
image_url          替换为新图片
status             → PENDING
current_stage      → QUEUED
error_code         → null
error_message      → null
started_at         → null
finished_at        → null
submitted_at       → now
updated_at         → now
```

同时清除当前旧结果：

```text
DELETE current OCRResult
DELETE current GradingResult
```

然后重新启动：

```python
asyncio.create_task(
    run_grading_workflow(submission_id)
)
```

第一版不保存旧答案和旧批改历史。

由于 `PENDING / RUNNING` 时禁止再次提交，同一学生同一道题任意时刻最多只有一个运行中的 Workflow，因此不存在“旧 Workflow 与新 Workflow 同时完成后竞争写结果”的场景，也不需要 `Submission.version / submission_version`。

#### 5.2.7 实时批改进度事件

后台 Workflow 在阶段变化时必须完成两件事：

```text
1. 更新 Submission.status / current_stage
2. 发送 grading.* SSE / Streaming Event
```

第一版事件：

```text
grading.stage.started
grading.stage.completed
grading.stage.failed
grading.completed
```

阶段开始：

```json
{
  "type": "grading.stage.started",
  "submission_id": "sub_10001",
  "stage": "OCR",
  "label": "正在识别手写答案"
}
```

OCR 完成：

```json
{
  "type": "grading.stage.completed",
  "submission_id": "sub_10001",
  "stage": "OCR",
  "label": "手写答案识别完成"
}
```

失败：

```json
{
  "type": "grading.stage.failed",
  "submission_id": "sub_10001",
  "stage": "GRADING",
  "error_code": "GRADING_MODEL_FAILED",
  "message": "批改失败，请重新提交。"
}
```

全部完成：

```json
{
  "type": "grading.completed",
  "submission_id": "sub_10001",
  "stage": "COMPLETED"
}
```

这些事件通过 SSE / Streaming 推送给学生前端，前端按事件更新 `complete / active / pending` 三类步骤状态。

#### 5.2.8 DeerFlow Chat 与 Streaming 复用边界

学生端继续复用 DeerFlow Chat 作为主要交互容器，而不是另外做一个脱离聊天上下文的进度页面。

学生提交后的消息时间线固定为：

```text
Student Image Message
        ↓
GradingProgressMessage
        ↓
GradingResultMessage
```

前端复用：

```text
DeerFlow Chat 页面 / Message Timeline
+
ChainOfThought 类步骤 UI primitives
+
已有 Streaming / SSE 基础设施
```

前端新增一层很薄的批改适配：

```text
GradingProgressAdapter / useGradingStream
= 订阅 grading.* Event
= 读取 / 恢复 Submission.status + current_stage
= 转换为 complete / active / pending

GradingProgressMessage
= 位于 DeerFlow Chat 消息时间线中
= 内部复用 ChainOfThought 类步骤组件展示批改阶段

GradingResultMessage
= grading.completed 后
= 在同一聊天上下文中展示最终 GradingResult
```

示例 UI：

```text
学生：
[上传的答案图片]

AI Teacher：
正在批改你的答案

✓ 图片上传完成
✓ OCR 识别完成
● 正在解析学生作答
○ 正在判断题目难度
○ 正在批改
○ 正在生成批改结果
```

后续随着事件到达更新为：

```text
✓ 图片上传完成
✓ OCR 识别完成
✓ 作答解析完成
✓ 难度判断完成
● 正在批改
○ 正在生成批改结果
```

最终：

```text
✓ 批改完成

GradingResultMessage
→ 得分
→ 错误原因
→ 反馈
→ 数学原图错误定位（如有）
```

明确不复用：

```text
MessageGroup 的 AIMessage / reasoning / tool_calls 转换逻辑
```

原因是 `OCR / PARSING / DIFFICULTY_CLASSIFICATION / GRADING` 是明确的业务 Workflow 阶段，不是 Agent Tool Call。前端复用 DeerFlow 的聊天容器、步骤组件和流式基础能力，但保持自己的 `grading.*` 业务事件协议。

如果批改 Workflow 接入 DeerFlow / LangGraph，可以通过 custom stream event 推送 `grading.*`；如果批改 Workflow 不依赖 DeerFlow，也继续使用同一事件协议，由自己的 SSE endpoint 推送，前端适配层不变。

---

### 5.3 Math Grading Workflow

数学题当前重点支持计算题 / 解答题。当前实现把 OCR 的结构化识别结果作为数学批改的证据层：代码负责保持学生原始书写顺序并构造稳定输入，真正的数学理解、解法识别和步骤评分由批改模型完成。

#### 5.3.1 整体流程

```text
Math Submission
        ↓
GLM-OCR
        ↓
OCRResult 持久化
├── md_results
└── layout_details
        ↓
读取 layoutDetails[0]
        ↓
按照 index 升序排列
        ↓
拼装 OCR Student Submission
        ↓
Qwen3.5-4B
难度识别 Prompt
        ↓
difficulty = easy / medium / hard
        ↓
模型路由
├── easy / medium → Qwen3.5-4B
└── hard          → DeepSeek v4 Flash
        ↓
数学批改 Prompt
        ↓
理解学生实际采用的解法
        ↓
动态识别关键解题步骤
        ↓
逐步骤评分
├── evidence_block_ids
├── error_block_ids
├── status
├── earned_score
└── max_score
        ↓
统一组装 GradingResult
        ↓
error_block_ids 回查 OCRResult.layout_details
        ↓
bbox2d
        ↓
前端在原始作业图片对应区域绘制红色矩形框
```

核心原则：

> **学生可能采用不同的正确解法。模型必须根据学生实际书写过程理解其解法并给步骤分，而不是要求学生匹配固定解题路径。**

#### 5.3.2 OCRResult 持久化

GLM-OCR 会返回 `mdResults`、`layoutDetails` 等结构。数学主流程需要持久化 OCR 的核心结果，使系统可以区分“学生原图”“OCR 看到了什么”“模型如何批改”。

逻辑结构：

```text
OCRResult
├── ocr_result_id
├── submission_id
├── model
├── status
├── md_results
├── layout_details
└── created_at
```

当前一个 Submission 最多只保留一个当前 OCRResult。重新提交被接受后，旧 OCRResult 会在新 Workflow 启动前清除。

其中：

```text
md_results
= GLM-OCR 返回的整体 Markdown 识别结果

layout_details
= GLM-OCR 返回的结构化 Block JSON
```

`layout_details` 直接以 JSON 持久化，不把每个 Block 拆成独立数据库表。当前数学步骤评分重点使用每个 Block 的：

```text
index
label
content
bbox2d
width
height
```

例如：

```json
{
  "index": 5,
  "label": "formula",
  "bbox2d": [280, 374, 810, 572],
  "content": "$$ ... $$",
  "width": 875,
  "height": 1077
}
```

这些字段分别承担：

```text
index
→ 保持原始阅读 / 书写顺序

label
→ 区分 text / formula 等内容类型

content
→ 进入批改模型的 OCR 内容

bbox2d + width + height
→ 批改完成后定位回原始图片
```

OCRResult 是一次批改的核心证据数据，需要持久化；运行时拼装出来的 `OCR Student Submission` 只是模型输入，不单独建立业务实体或数据库表。

#### 5.3.3 OCR Block → OCR Student Submission

当前业务是一张图片对应一道题，因此 MVP 直接读取：

```text
layoutDetails[0]
```

按 `index ASC` 排序，然后把每个 Block 转成固定文本：

```text
[Block {index} | {label}]
{content}
```

例如 OCR Block：

```json
{
  "index": 5,
  "label": "formula",
  "content": "$$ I = ... $$"
}
```

转换为：

```text
[Block 5 | formula]
$$ I = ... $$
```

最终模型看到的学生作答类似：

```text
[Block 2 | text]
Answer: Let

[Block 3 | formula]
$$
I = ...
$$

[Block 4 | text]
Then, by ...

[Block 5 | formula]
$$
...
$$

[Block 6 | text]
Thus,

[Block 7 | formula]
$$
2I = ...
$$
```

代码层只负责：

```text
OCR Block
↓
保持原始顺序
↓
拼装稳定的模型输入
```

代码不判断“哪几个 Block 是第几步”，也不在这一层做数学正确性判断。

批改时 `Question` 使用数据库中的正式题目。OCR 图片中如果同时识别到了题干，不增加复杂的题干切割逻辑，而是在 Prompt 中明确：`Question` 是正式题目，模型应根据上下文区分 OCR 中的题目文字和学生实际作答。

#### 5.3.4 数学模型路由

输入 difficulty classifier 的题目来自正式 `Question.content`。

```text
Question.content
      ↓
Qwen3.5-4B
      ↓
difficulty
├── easy
├── medium
└── hard
```

正式数学批改：

```text
easy / medium
→ Qwen3.5-4B

hard
→ DeepSeek v4 Flash
```

两个正式批改模型使用相同的数学批改 Prompt 规则和输出 Contract，只替换模型。

#### 5.3.5 数学步骤评分 Prompt

System Prompt：

```text
你是一名数学教师，负责批改学生的数学解题过程并给出步骤分。

你会收到：
1. Question：正式数学题目
2. Max Score：本题总分
3. OCR Student Submission：OCR 按学生原始书写顺序识别得到的内容

OCR Student Submission 中每段内容都带有 Block 编号以及 text / formula 类型。

请完成以下任务：

1. 理解题目以及学生实际采用的解题方法。

2. 根据学生实际书写内容识别关键解题步骤。

3. 学生可能采用不同的正确解法。
   应根据学生自己的解题方法判断数学推理是否成立，
   不能因为与常见解法不同而扣分。

4. 判断每个关键步骤是否正确，并根据其重要程度分配步骤分。

5. 每个步骤必须标记为：
   - correct：步骤正确
   - partial：思路或推导部分正确，但存在遗漏或局部错误
   - incorrect：当前步骤本身存在数学错误
   - consequential_error：当前步骤受到前序错误结果影响，但当前数学操作或推理方式本身合理

6. 如果某一步出现错误，不要直接将之后所有步骤判错。
   应继续判断后续步骤本身是否体现正确数学方法，并给予合理过程分。

7. OCR 可能存在少量字符识别错误。
   如果结合上下文能够高置信判断为 OCR 错误，可以按合理含义理解；
   如果无法确定，不要擅自修改学生答案，并在 feedback 中指出 OCR 内容存在歧义。

8. OCR Student Submission 中可能包含题目文字。
   Question 字段中的内容是正式题目，请区分题目和学生实际作答。

9. 所有步骤 max_score 的总和必须等于 Max Score。

10. earned_score 必须等于所有步骤 earned_score 之和，并且不得超过 Max Score。

11. evidence_block_ids 和 error_block_ids 必须引用 OCR Student Submission 中真实存在的 Block 编号。

严格按照指定 JSON 格式输出。
```

User Prompt：

```text
Question:
{question_content}

Max Score:
{max_score}

OCR Student Submission:
{ocr_blocks}

请批改学生完整解题过程并给出步骤分。
```

#### 5.3.6 步骤评分输出 Contract

模型需要对学生自己的解题过程动态识别步骤。每个步骤至少包含：

```text
step_index
说明这是模型识别出的第几个关键步骤

description
说明这一步在做什么

evidence_block_ids
这一解题步骤对应哪些 OCR Block

error_block_ids
真正出现错误、需要在原图标记的 OCR Block；正确步骤为空数组

status
correct / partial / incorrect / consequential_error

earned_score / max_score
该步骤实际得分 / 该步骤满分

feedback
当前步骤的简短判断或错误原因
```

模型总分、总体反馈、错误诊断和步骤结果最终映射到统一 `GradingResult`。最终持久化 Schema 以 `docs/02-grading-result-schema.md` 为唯一字段定义来源，避免在 Workflow 文档里维护第二套业务 Schema。

#### 5.3.7 原始图片错误步骤定位

`error_block_ids` 用于把模型诊断重新定位回学生原图。

例如模型返回：

```json
{
  "error_block_ids": [11],
  "feedback": "最终积分计算存在错误"
}
```

后端根据 `Block 11` 回查当前 `OCRResult.layout_details`：

```json
{
  "index": 11,
  "bbox2d": [223, 964, 684, 1064],
  "width": 875,
  "height": 1077
}
```

返回前端错误区域：

```text
block_id
bbox
image_width
image_height
message
```

前端根据图片当前展示尺寸计算：

```text
scale_x = rendered_width / image_width
scale_y = rendered_height / image_height

left   = x1 * scale_x
top    = y1 * scale_y
width  = (x2 - x1) * scale_x
height = (y2 - y1) * scale_y
```

然后在原图上使用绝对定位绘制红色矩形框，并展示对应步骤 `feedback`。

如果一个错误对应多个 `error_block_ids`，前端分别绘制多个矩形框，不强制合并成一个大框。

当前 MVP 的定位粒度固定为：

> **OCR Block 级错误定位。**

如果整个公式是一个 OCR Block，即使错误只发生在其中一个字符，当前版本也框选整个公式 Block；不增加字符级 OCR 定位或额外视觉模型。

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
OCRResult
OCR Block 拼装
Qwen3.5-4B
DeepSeek v4 Flash
Agent 1
Agent 2
Rubric
evidence.json
模型路由
Prompt
Submission status / current_stage
Progress Event
```

这些全部属于 **Grading Workflow / 工程执行层内部实现**。

业务层不需要感知内部进行了多少模型调用，也不把 Agent 1 / Agent 2 的中间结果当成多次业务批改。

知识点、错误类型、错误原因等诊断信息同样由 Workflow 内部识别，不要求教师预先逐题标注。

---

### 5.6 Workflow 最终只输出一个当前有效 GradingResult

业务关系固定为：

```text
当前 Submission
     ↓
【完整 Grading Workflow】
     ↓
当前 GradingResult
```

> **一个当前 Submission 在一次成功批改后只保留一个当前有效 GradingResult。**

不存在业务层面的“第一次批改结果”“第二次复核结果”。

即使内部存在：

```text
OCR 结构化识别
难度识别
模型路由
数学步骤识别 / 英语证据提取
正式评分
错误诊断
知识点识别
```

对外仍然只有一个最终批改结果。

如果学生在 `SUCCEEDED / FAILED` 后重新提交，系统清除旧 `OCRResult / GradingResult`，复用同一 `Submission` 并重新进入一次完整 Workflow；`PENDING / RUNNING` 时不接受新的提交。

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
Student Submission（当前提交）
├── image_url
├── status
└── current_stage
   ↓
后台异步 Grading Workflow
   ├── OCR → OCRResult
   ├── Math：OCR Block 拼装 → Qwen3.5-4B 难度识别 → 模型路由 → 动态步骤评分
   └── English：DeepSeek v4 Flash Evidence Extraction → DeepSeek v4 Flash Scoring
   ↓
当前有效 GradingResult
   ↓
MySQL
```

数学批改结果还存在一条面向学生的错误定位链：

```text
GradingResult.math_detail.steps[].error_block_ids
        ↓
OCRResult.layout_details[index].bbox2d
        ↓
前端坐标换算
        ↓
学生原始作业图片红色矩形框
        ↓
对应步骤 feedback
```

同时存在一条面向学生前端的实时进度链：

```text
Submission / Grading Workflow
        ↓
grading.* Progress Event
        ↓
SSE / Streaming
        ↓
GradingProgressAdapter / useGradingStream
        ↓
DeerFlow Chat / GradingProgressMessage
        ↓
学生实时看到 complete / active / pending
        ↓
GradingResultMessage
```

其中：

- `Teacher / Student / Class / Homework / Question` 定义业务上下文。
- `Submission` 表示学生对某一道题当前有效的真实答案，同时保存当前批改 `status / current_stage`；同一 `student_id + question_id` 只保留一条。
- `PENDING / RUNNING` 时拒绝重复提交；`SUCCEEDED / FAILED` 后复用同一 Submission 重新提交。
- `OCRResult` 持久化 OCR 的核心结构化识别证据；数学批改使用 `layout_details` 的 Block 顺序、内容和坐标。
- `Grading Workflow` 负责 OCR、结构化解析、确定性题型路由，以及数学或英语作文的具体批改过程。
- 数学题由 `Qwen3.5-4B` 识别 `easy / medium / hard`；easy / medium 使用 `Qwen3.5-4B`，hard 使用 `DeepSeek v4 Flash`。
- 数学步骤由正式批改模型根据学生实际解法动态识别和评分，`error_block_ids` 与 OCR `bbox2d` 共同支持原图 Block 级错误定位。
- 英语作文固定使用 `DeepSeek v4 Flash` 完成“证据提取 → 正式评分”两阶段 Workflow，不进行 difficulty 模型路由。
- `GradingResult` 是当前 Submission 成功完成 Workflow 后对外输出的唯一最终批改结果。
- `MySQL` 保存业务事实和 OCR 证据，为后续学生画像、班级学情分析和 Teacher Agent 提供可信数据基础。
- 学生实时进度继续展示在 DeerFlow Chat 中：复用聊天容器、Message Timeline、ChainOfThought 类步骤 UI 和 Streaming 基础能力；`grading.*` 业务事件不伪装成 `AIMessage / reasoning / tool_calls`。