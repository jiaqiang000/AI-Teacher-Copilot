# AI Teacher Copilot：业务边界、作业创建与批改工作流设计

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
Question ←──── QuestionBankItem
   │               ↑
   │               │
   │          Question Bank
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
| `Homework` | 一次作业，先以草稿存在，发布后学生可见 |
| `Question` | 已经属于某个 Homework、真正布置给学生的一道题 |
| `QuestionBankItem` | 系统题库中的可复用题目资源，不直接属于某个 Homework |
| `Submission` | 一个学生对一道题当前有效的答案，同时保存当前批改状态和执行阶段 |
| `GradingResult` | 当前 Submission 成功完成完整 Workflow 后的最终批改结果 |

其中最关键的是 `Question`、`Submission` 和 `GradingResult`。`QuestionBankItem` 只作为可复用题目来源；题库题被加入 Homework 时会复制成新的 `Question`，不会让已发布作业实时引用题库记录。

Knowledge Point（知识点）和 Error Type（错误类型）不要求教师逐题手工维护。当前 MVP 已维护轻量的两级标准 Taxonomy：系统根据 `Question.subject` 读取当前学科允许的标准分类，并在正式批改时把标准 `level = 2` 候选提供给 Grading Model。模型从候选中选择 `knowledge_point_key / error_code`，同时生成 `raw_name / raw_type` 保留本次实际诊断语义；无法精确匹配现有小类时使用对应大类下的 `OTHER`。后端只通过 `TaxonomyValidator` 做确定性合法性校验，不增加独立标准化 Agent、Embedding Mapping 或第二次 LLM 映射。

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
status: DRAFT
published_at: null
```

`Homework.status` 当前只保留两个状态：

```text
DRAFT（草稿）
= 教师正在创建作业
= 可以添加、修改、删除、排序 Question

PUBLISHED（已发布）
= 学生可见
= 当前 MVP 不再允许修改已发布 Question
```

发布时：

```text
status = PUBLISHED
published_at = 当前时间
```

当前 MVP 不增加定时发布、撤回、Homework 版本或审批流程。

一个 Homework 包含多道实际作业题：

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

`Question` 表示已经进入某个 Homework 的实际作业题，第一版逻辑结构固定为：

```text
Question
├── question_id（题目ID）
├── homework_id（作业ID）
├── question_no（题号）
│
├── subject（学科）
├── question_type（题型）
├── difficulty（难度）
│
├── content（题目文本）
├── image_url（题目原图，可选）
├── max_score（满分）
│
└── source_question_bank_item_id（来源题库题ID，可选）
```

字段职责：

```text
subject
= 继承所属 Homework.subject

question_type
= 数学当前为 calculation / solution
= 英语当前为 essay

difficulty
= 数学 Question 的稳定题目属性
= easy / medium / hard
= 在 Question 创建 / 加入 Homework 时确定
= 英语作文当前为 null

content
= 学生真正看到和批改 Workflow 使用的正式题目文本

image_url
= 教师通过图片创建题目时可保留的题目原图
= 手动输入纯文本题目时可为空

source_question_bank_item_id
= 从题库复制时记录来源 QuestionBankItem ID
= 教师自行创建时为 null
= 只用于来源追踪，不表示实时引用关系
```

#### 数学 Question

例如：

```text
question_id: q001
homework_id: hw_001
question_no: 1
subject: math
question_type: calculation
difficulty: easy
content: 解方程 2x + 4 = 8
image_url: null
max_score: 10
source_question_bank_item_id: null
```

数学步骤分由批改模型根据正式题目、题目总分和学生实际 OCR 作答动态判断，不要求教师预先维护固定解法或固定步骤评分模板。

#### 英语作文 Question

例如：

```text
question_id: q101
homework_id: hw_101
question_no: 1
subject: english
question_type: essay
difficulty: null
content: Write an article about your summer vacation.
image_url: null
max_score: 20
source_question_bank_item_id: null
```

英语作文统一使用系统内置 `EnglishEssayRubricV1（英语作文评分标准 V1）`。Rubric 是系统级批改规则，不属于 `Question` 字段，也不随每一道 Question 单独保存。当前 MVP 中英语作文 `max_score` 固定为 `20`，教师不可修改评分维度、维度权重或总分。

`question_no（题号）` 表示题目在当前 Homework（作业）中的展示序号。例如：

```text
homework_id = hw_004
question_id = q008
question_no = 8
```

教师和学生看到的是“第 8 题”，系统内部仍然使用 `question_id` 标识具体题目。同一个 Homework 内 `question_no` 不重复。教师创建作业题目时，由前端按顺序默认生成 `1、2、3……`，需要时允许教师调整。

后面的 Grading Workflow 直接依据这些业务属性路由，不再使用 LLM 重复识别学科、题型或题目难度。

#### 3.2.1 Question 创建来源

当前 MVP 的 Question 只有两类来源：

```text
方式 A：教师自行创建
├── 手动输入题目文本
└── 上传题目图片

方式 B：从 Question Bank 选择
└── QuestionBankItem → Copy → Question
```

核心边界：

```text
QuestionBankItem
= 可复用题库资源

Question
= 某个 Homework 中真正布置出去的题
```

题库题加入 Homework 时必须复制成新的 Question：

```text
QuestionBankItem qb_001
        ↓ Copy
Question q008
```

复制后的 `Question` 自己保存实际作业题内容和难度。以后 `qb_001` 被修改，不会修改已经存在或已经发布的 `q008`。

#### 3.2.2 difficulty（难度）确定规则

`difficulty` 是题目的属性，不是学生答案的属性，因此数学题只在进入 Homework 时确定一次。

教师自行创建数学题：

```text
教师输入题目文本
或
教师上传题目图片 → OCR 得到题目文本
        ↓
Qwen3.5-4B
        ↓
difficulty = easy / medium / hard
        ↓
前端展示预判结果
        ↓
教师确认 / 可修改
        ↓
保存 Question.difficulty
```

这里 AI 只负责预判；教师在发布前可以修改，最终写入 `Question.difficulty` 的值才是后续业务使用的稳定值。

从题库加入数学题：

```text
QuestionBankItem.difficulty
        ↓ Copy
Question.difficulty
```

这种路径不重新调用 difficulty classifier。

英语作文当前：

```text
Question.difficulty = null
```

学生 Grading Workflow **不得重新识别 difficulty**，只读取已经保存的 `Question.difficulty` 做模型路由。

### 3.3 Teacher Homework Authoring Workflow（教师作业创建与发布）

当前系统正式补齐教师端作业创建入口：

```text
Teacher
↓
创建 Homework
↓
status = DRAFT
↓
添加 Question
├── 手动输入题目
├── 上传题目图片
└── 从 Question Bank 选择
↓
教师预览 / 修改 / 确认
↓
调整 question_no / 顺序
↓
发布 Homework
↓
status = PUBLISHED
↓
学生可见
```

#### UI / Figma 对应与职责边界

对应 Figma：

```text
04 · Homework Authoring
```

该页面负责组织以下教师操作：

```text
Homework 基础信息
Question 列表 / 排序
添加 Question
├── 手动输入
├── 上传题目图片
└── 从 Question Bank 选择

Question 预览 / 修改
数学 difficulty 预判结果确认
发布 Homework
```

职责边界固定为：

```text
Figma
= 定义这些操作如何组织和展示

本节
= 定义 DRAFT / PUBLISHED
+ Question 创建来源
+ difficulty
+ max_score
+ 发布校验等业务规则
```

Question Bank 在当前 MVP 中作为 Homework Authoring 内的选择 Drawer / Dialog 使用，不建设独立的教师题库管理页面。

#### 路径 A：手动输入题目

```text
创建 Homework
↓
DRAFT
↓
教师输入题目文本
↓
subject 继承 Homework.subject
↓
确定 question_type
├── 数学：教师选择 calculation / solution
└── 英语：当前固定 essay
↓
确定 max_score
├── 数学：教师填写 max_score
└── 英语作文：系统固定 max_score = 20
↓
数学 → Qwen3.5-4B 预判 difficulty
英语 → difficulty = null
↓
前端预览
↓
教师确认 / 可修改
↓
保存 Question
```

英语作文创建时前端不提供 Rubric 编辑入口，也不提供总分编辑入口。

#### 路径 B：上传题目图片

```text
教师上传题目图片
↓
保存题目图片
↓
复用 OCR Service
↓
提取题目 content
↓
确定 max_score
├── 数学：教师填写 max_score
└── 英语作文：系统固定 max_score = 20
↓
数学 → Qwen3.5-4B 预判 difficulty
英语 → difficulty = null
↓
前端展示 content / difficulty
↓
教师修正并确认
↓
保存 Question
```

这里复用 OCR 能力，但**不创建 `OCRResult`**。`OCRResult` 仍然只表示学生 `Submission` 的 OCR 批改证据。

教师题目 OCR 最终只沉淀：

```text
Question.content
= OCR 后经教师确认的正式题目文本

Question.image_url
= 教师上传的题目原图，可选保留
```

#### DeerFlow 复用落地：题目图片上传

教师端上传题目图片时，当前优先复用 DeerFlow 已确认可用的前端文件选择、上传交互和文件校验 primitives；业务资产存储方式在实现阶段继续核对 DeerFlow 现有能力。

```text
直接复用：
- DeerFlow 文件选择 / Upload UI primitives
- frontend/src/core/uploads/file-validation.ts 等文件大小、类型校验逻辑
- 可复用的上传进度与错误展示交互

本项目新增：
- QuestionAssetService
- Question 业务图片上传 API
- 正式业务资产存储
- Question.image_url

当前暂未直接采用：
- /api/threads/{thread_id}/uploads/... 作为 Question.image_url
```

原因是当前代码阅读下 DeerFlow Thread Upload 更偏向聊天线程的 user-data 生命周期，而 `Question.image_url` 属于 Homework 的业务资产。具体实现时仍需继续检查 DeerFlow Upload 的存储与生命周期能力，满足业务资产要求时优先复用。

#### 路径 C：从 Question Bank 添加

```text
教师打开题库
↓
按知识点 / 难度 / 题型 / 年级筛选
↓
选择 QuestionBankItem
↓
复制到 Question
├── subject
├── question_type
├── difficulty
├── content
└── image_url
↓
确定 max_score
├── 数学：教师设置 max_score
└── 英语作文：系统固定 max_score = 20
↓
生成新的 question_id / question_no
↓
source_question_bank_item_id = 原题库题ID
```

`reference_answer` 仍属于题库资源，不在本次 Question 数据模型中新增第二套答案字段；学生批改流程继续以正式题目、学生作答和既有批改 Contract 为准。`QuestionBankItem` 同样不保存英语 Rubric 配置；英语作文题被复制到 Homework 后直接使用系统内置 `EnglishEssayRubricV1`。

#### 发布前最小校验

当前 MVP 发布 Homework 前至少检查：

```text
Homework.status = DRAFT
至少存在 1 道 Question
question_no 在当前 Homework 内唯一
Question.content 非空
Question.max_score > 0
数学 Question.difficulty 非空
英语作文 Question.max_score = 20
Question.subject 与 Homework.subject 一致
```

校验通过后：

```text
Homework.status = PUBLISHED
Homework.published_at = 当前时间
```

当前 MVP 发布后不再修改 Question，避免学生已经开始作答后题目内容发生变化。

### 3.4 Submission

`Submission` 表示：

> **学生针对一道题当前有效的答案，同时也是这份当前答案的批改状态记录。**

学生侧 UI 对应：

```text
07 · Student Homework
→ 查看当前 Homework
→ 查看 Question 列表与当前作答 / 批改状态
→ 选择 Question

08 · Student Grading
→ 针对选中的 Question 上传当前答案
→ 展示当前 Submission 批改过程与最终结果
```

`07 / 08` 只是同一 `Submission` 业务模型在不同交互阶段的页面表现，不增加新的业务对象或 `GradingTask`。

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

#### Submission 图片资产与 DeerFlow Upload 边界

`Submission.image_url` 是当前学生答案的正式业务资产引用。当前暂不直接将 DeerFlow Thread Upload 临时文件地址作为 Source of Truth；实现阶段继续检查其存储与生命周期能力，满足业务资产要求时优先复用。

```text
Student Frontend
↓
复用 DeerFlow 文件选择 / validation primitives
↓
SubmissionAssetService【本项目】
↓
业务图片存储
↓
Submission.image_url
```

当前设计保证聊天 Thread 的 user-data 清理不能导致当前 Submission 原图丢失；最终存储实现仍以编码阶段对 DeerFlow Upload 能力的进一步检查结果为准。

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
                      status=DRAFT
                           ↓
                     添加 Question
             ┌─────────────┼─────────────┐
             ↓             ↓             ↓
          手动输入       上传题目图片     从题库选择
             │             │             │
             │            OCR       QuestionBankItem
             │             │             │
             └──────┬──────┘          Copy
                    ↓                   │
             正式题目 content           │
                    ↓                   │
        数学自建题 difficulty 预判       │
                    ↓                   │
              教师预览 / 修改 / 确认 ←──┘
                    ↓
                 Question
                    ↓
             调整 question_no
                    ↓
                 发布作业
                    ↓
              status=PUBLISHED

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
        subject / question_type / difficulty
                           ↓
                    按业务属性路由
                      ↙         ↘
                   Math        English
                    ↓             ↓
              按 difficulty      作文批改
                模型路由          +
                    ↓       EnglishEssayRubricV1
                    ↓             ↓
                  标准 Taxonomy 校验
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

这构成当前教师创建作业、学生提交和自动批改的完整 MVP 闭环。

其中：

- `subject` 和 `question_type` 在创建 `Question` 时确定，批改 Workflow 直接读取，不再让模型重复识别。
- `difficulty` 是数学 Question 的题目属性：教师自行创建数学题时由 `Qwen3.5-4B` 预判并经教师确认；从题库添加时直接复制 `QuestionBankItem.difficulty`；学生批改 Workflow 只读取它，不再次识别。
- 英语作文当前 `difficulty = null`，不进行 difficulty 模型路由，固定使用 `DeepSeek v4 Flash` 完成两阶段 Workflow；评分统一读取系统内置 `EnglishEssayRubricV1`，不从 Question 读取自定义 Rubric。
- `knowledge_points / errors` 不要求教师逐题标注。系统根据 `Question.subject` 提供当前学科标准 Taxonomy；Grading Model 从标准 `level = 2` 小类中选择 `knowledge_point_key / error_code`，同时生成 `raw_name / raw_type`，最终结果在写入 `GradingResult` 前通过 `TaxonomyValidator` 校验。
- `OCRResult` 只保存 OCR 对学生 Submission 原图的结构化识别证据；教师上传题目图片时虽然复用 OCR Service，但不创建 `OCRResult`。
- `Submission.status / current_stage` 是当前批改状态事实源；SSE / Streaming Event 只负责把状态变化实时推送给前端。
- 用户上传后仍在 DeerFlow Chat 中实时看到 OCR、解析、批改、结果组装等过程；difficulty classification 已从学生批改过程前移到 Question 创建阶段。

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
├── question_type
└── difficulty
    ↓
按业务属性路由
├── Math
└── English Essay
```

这里不再让 Qwen 判断学科、题型或 difficulty。教师创建 `Question` 时已经确定这些业务属性（英语 difficulty 当前为 null），因此这一层采用确定性路由。

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
GRADING
ASSEMBLING_RESULT
COMPLETED
```

数学和英语作文均使用同一通用阶段：

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

数学的模型选择发生在进入 `GRADING` 时，通过读取 `Question.difficulty` 完成，不再单独形成 `DIFFICULTY_CLASSIFICATION` 阶段。

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

学生端继续复用 DeerFlow Chat 作为主要交互容器，但 `Submission` 仍然是教育业务执行对象，不把学生批改强行改造成 DeerFlow Agent Run。

##### 5.2.8.1 Submission 不使用 DeerFlow Run 作为业务状态

```text
Submission
= 教育业务当前答案 + 批改生命周期

DeerFlow Run
= 一次 Agent Graph / Harness 执行生命周期
```

因此明确禁止：

```text
submission_id = deerflow_run_id
Submission.status 直接读取 DeerFlow Run.status
GradingResult 依赖 DeerFlow Run output 才能成为业务事实
```

`Submission.status / current_stage` 始终是批改状态和页面恢复的 Source of Truth。

##### 5.2.8.2 后端 Streaming：当前优先复用 StreamBridge

学生批改事件继续使用已经定义的 `grading.*` 业务协议，后端复用 DeerFlow `StreamBridge` 的 publish / subscribe / end 等流式基础能力：

```text
run_grading_workflow(submission_id)
        ↓
更新 MySQL Submission.status / current_stage
        ↓
emit grading.* Event
        ↓
GradingStreamAdapter【本项目】
        ↓
DeerFlow StreamBridge.publish()【复用】
        ↓
GET /api/submissions/{submission_id}/events【本项目】
        ↓
grading_sse_consumer【本项目薄 Adapter】
        ↓
Browser
```

当前复用边界：

```text
直接复用：
- DeerFlow StreamBridge
- event publish / subscribe / end 基础能力
- SSE 格式化方式可以参考 / 复用公共 helper

本项目新增：
- GradingStreamAdapter
- Submission SSE Endpoint
- grading_sse_consumer

当前暂未直接采用：
- DeerFlow Gateway 针对 Agent Run 的 sse_consumer / RunManager 生命周期
```

当前代码阅读下，DeerFlow 原生 Run SSE 与 `RunRecord / RunManager / Agent Run lifecycle` 绑定较深。实现阶段继续检查 RunManager / Gateway SSE 是否可在保持 Submission 业务状态独立的前提下进一步复用。

##### 5.2.8.3 前端：复用 Chat / ChainOfThought primitives，新增 Grading Adapter

学生提交后的消息时间线固定为：

```text
Student Image Message
        ↓
GradingProgressMessage
        ↓
GradingResultMessage
```

前端直接复用：

```text
DeerFlow Chat 页面 / Message Timeline
+
frontend/src/components/ai-elements/chain-of-thought.tsx
├── ChainOfThought
├── ChainOfThoughtContent
└── ChainOfThoughtStep
```

本项目新增：

```text
frontend/src/core/grading/types.ts

frontend/src/core/grading/lifecycle.ts
└── gradingEventToProgressUpdate()

frontend/src/core/grading/hooks.ts
└── useGradingStream()

GradingProgressMessage
GradingResultMessage
```

`gradingEventToProgressUpdate()` 可以沿用 DeerFlow 已有 task lifecycle reducer 的实现模式，但转换的是：

```text
grading.stage.started
grading.stage.completed
grading.stage.failed
grading.completed
```

而不是：

```text
task_running
AIMessage
ToolMessage
reasoning
tool_calls
```

`GradingProgressMessage` 内部把当前 Submission 的阶段转换为：

```text
complete
active
pending
failed
```

然后通过 DeerFlow ChainOfThought UI primitives 展示。

示例 UI：

```text
学生：
[上传的答案图片]

AI Teacher：
正在批改你的答案

✓ 图片上传完成
✓ OCR 识别完成
● 正在解析学生作答
○ 正在批改
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

对应 Figma：

```text
08 · Student Grading
```

同一个 Student Grading 交互面按 Submission 状态展示不同内容：

```text
未提交
→ 上传答案

PENDING / RUNNING
→ Student Image Message
→ GradingProgressMessage

FAILED
→ 失败信息 + 允许重新提交

SUCCEEDED
→ GradingResultMessage
```

Math / English 不拆成两套路由或两套独立页面：

```text
math_detail
→ 数学结果 Variant

english_essay_detail
→ 英语作文结果 Variant
```

当前不直接套用：

```text
MessageGroup 的 AIMessage / reasoning / tool_calls 转换逻辑
```

原因是 `OCR / PARSING / GRADING` 是确定的业务 Workflow 阶段，不是 Agent Tool Call。实现时继续检查 MessageGroup 的消息转换和扩展机制，能通过 Adapter 复用则优先复用。

##### 5.2.8.4 页面刷新与事件重连边界

页面刷新后仍然执行：

```text
GET /api/submissions/{submission_id}
        ↓
读取持久化 status / current_stage
        ↓
重建 complete / active / pending
        ↓
重新订阅 /events
```

DeerFlow StreamBridge 的 replay / reconnect 能力只用于提升实时体验；即使实时事件无法完整重放，也不能影响页面恢复，因为：

```text
Submission.status / current_stage
= 最终状态事实源

StreamBridge / grading.* Event
= 实时增量体验
```

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
读取 Question.difficulty
        ↓
模型路由
├── easy / medium → Qwen3.5-4B
└── hard          → DeepSeek v4 Flash
        ↓
读取 Math Knowledge Point / Error Type Taxonomy
        ↓
将标准 level=2 候选注入数学批改 Prompt
        ↓
理解学生实际采用的解法
        ↓
动态识别关键解题步骤
        ↓
逐步骤评分 + 结构化诊断
├── evidence_block_ids
├── error_block_ids
├── status
├── earned_score
├── max_score
├── knowledge_point key / raw_name
└── error code / raw_type
        ↓
TaxonomyValidator
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

数学模型路由不再调用 difficulty classifier。进入学生批改 Workflow 前，`Question.difficulty` 已经在作业创建阶段确定。

```text
Question.difficulty
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

两个正式批改模型使用相同的数学批改 Prompt 规则、Taxonomy Contract 和输出 Contract，只替换模型。

如果数学 `Question.difficulty` 缺失，说明发布前业务校验没有通过，不应在学生批改阶段临时重新识别，而应作为 Question 数据异常处理。

#### 5.3.5 数学步骤评分 Prompt

System Prompt：

```text
你是一名数学教师，负责批改学生的数学解题过程并给出步骤分。

你会收到：
1. Question：正式数学题目
2. Max Score：本题总分
3. OCR Student Submission：OCR 按学生原始书写顺序识别得到的内容
4. Knowledge Point Taxonomy：当前数学学科允许使用的标准知识点分类
5. Error Type Taxonomy：当前数学学科允许使用的标准错误分类

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

12. knowledge_point.key 必须从 Knowledge Point Taxonomy 中的 level=2 小类选择，不得自行创造新的 key。

13. error.code 必须从 Error Type Taxonomy 中的 level=2 小类选择，不得自行创造新的 code。

14. 如果没有完全匹配的现有小类，使用最合适的大类下的 OTHER。

15. 每个 KnowledgePoint 都必须输出 raw_name，用自然语言概括本次实际识别出的具体知识点语义。

16. 每个 Error 都必须输出 raw_type，用自然语言概括本次实际发生的具体错误语义。

17. raw_name / raw_type 不替代标准 key / code；标准分类用于统计和检索，raw 字段用于保留本次具体语义。

严格按照指定 JSON 格式输出。
```

User Prompt：

```text
Question:
{question_content}

Max Score:
{max_score}

Knowledge Point Taxonomy:
{knowledge_point_taxonomy}

Error Type Taxonomy:
{error_type_taxonomy}

OCR Student Submission:
{ocr_blocks}

请批改学生完整解题过程并给出步骤分，同时按照给定 Taxonomy 输出结构化知识点和错误诊断。
```

当前比赛规模下可以直接提供当前 `subject` 的标准分类，不要求第一版再建设复杂的动态候选裁剪。后续如果 Taxonomy 明显扩大，可以再按题目范围缩小 Prompt 中的候选集合，业务 Contract 不变。

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

除数学步骤结果外，正式批改模型还需要按照 `docs/02-grading-result-schema.md` 输出 `diagnosis` 所需的结构化诊断信息：

```text
KnowledgePoint
├── key
├── raw_name
├── performance
└── evidence

Error
├── code
├── raw_type
├── knowledge_point_key
├── description
└── evidence
```

标准 `name / type` 不要求模型生成，由后端根据已经通过 Validator 的标准 `key / code` 从 Taxonomy 字典补齐。

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

对应 Figma：

```text
08 · Student Grading 的 Math Result 状态
```

错误框属于 Student Grading 当前结果区的一部分，不创建独立“错误定位页面”。Figma 只定义原图 + 错误框 + 步骤反馈的展示方式；实际坐标仍严格来自：

```text
error_block_ids
→ OCRResult.layout_details
→ bbox2d
```

---

### 5.4 English Essay Grading Workflow

英语作文采用 **AutoSCORE 风格的两阶段 Workflow**，两个阶段均固定使用 `DeepSeek v4 Flash`。

英语作文当前不进行 easy / medium / hard 模型路由。

#### 5.4.1 EnglishEssayRubricV1（英语作文评分标准 V1）

当前 MVP 只使用一套系统内置评分标准：

```text
Content（内容）                    0–5 分
Organization（组织结构与衔接）    0–5 分
Grammar（语法与句式）             0–5 分
Vocabulary（词汇）                0–5 分
Total（总分）                    20 分
```

业务约束固定为：

```text
教师不可新增 / 删除评分维度
教师不可修改各维度满分或权重
教师不可修改英语作文总分
Question / QuestionBankItem 不保存 rubric 字段
英语作文 Question.max_score 固定为 20
每个维度只能输出 0 / 1 / 2 / 3 / 4 / 5 整数分
```

四个维度的分档定义如下。

**Content（内容）**

| 分数 | 判定标准 |
|---:|---|
| 5 | 完整回应题目要求，主题明确，相关细节充分 |
| 4 | 基本完整回应，存在少量遗漏或细节不足 |
| 3 | 基本切题，但有明显内容遗漏，展开较简单 |
| 2 | 只回应部分要求，重要内容缺失或存在明显偏题 |
| 1 | 与题目相关内容很少，仅勉强回应任务 |
| 0 | 基本没有与题目相关的有效内容 |

**Organization（组织结构与衔接）**

| 分数 | 判定标准 |
|---:|---|
| 5 | 结构清楚，顺序合理，段落和衔接自然 |
| 4 | 整体结构清楚，存在少量衔接不自然 |
| 3 | 有基本结构，但存在跳跃、重复或衔接不足 |
| 2 | 结构较弱，内容之间关系不够清楚 |
| 1 | 内容明显零散，阅读顺序较难理解 |
| 0 | 基本无法识别文章结构 |

**Grammar（语法与句式）**

| 分数 | 判定标准 |
|---:|---|
| 5 | 语法基本正确，句式使用恰当，只有极少小错误 |
| 4 | 存在少量语法错误，但基本不影响理解 |
| 3 | 有较明显、重复的语法错误，但主要意思可以理解 |
| 2 | 语法错误较多，部分影响理解 |
| 1 | 大量严重语法错误，明显影响理解 |
| 0 | 基本无法形成可理解的英文句子 |

**Vocabulary（词汇）**

| 分数 | 判定标准 |
|---:|---|
| 5 | 用词准确恰当，有一定丰富度，拼写错误极少 |
| 4 | 用词总体准确，有一定变化，少量用词或拼写错误 |
| 3 | 基础词汇够用但较重复，存在一些用词或拼写问题 |
| 2 | 词汇有限，用词 / 拼写错误较多并影响表达 |
| 1 | 词汇非常有限，难以准确表达意思 |
| 0 | 基本没有足够的有效英文词汇进行评价 |

补充规则：

- 拼写问题归入 `Vocabulary（词汇）`。
- 同一问题原则上只在最相关维度扣分，避免同一个错误同时在 Grammar 和 Vocabulary 重复扣分。
- Rubric 作为系统运行时常量 / 配置提供给两个评分阶段，不从 Question 数据读取。

参考思路：

```text
AutoSCORE: Enhancing Automated Scoring with Multi-Agent
Large Language Models via Structured Component Recognition
AAAI 2026
```

核心思想不是让两个 Agent 重复打分，而是把“找评分证据”和“根据证据评分”拆开：

```text
作文原文 + 作文题目 + EnglishEssayRubricV1
                 ↓
Agent 1：评分证据提取
Model = DeepSeek v4 Flash
                 ↓
             evidence.json
                 ↓
Agent 2：评分 + 反馈 + 结构化诊断
Model = DeepSeek v4 Flash
                 ↓
        TaxonomyValidator
                 ↓
      分数 + 扣分原因 + 修改建议
      + KnowledgePoint / Error
                 ↓
        统一组装 GradingResult
```

#### 5.4.2 Agent 1：评分证据提取

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
EnglishEssayRubricV1（系统固定英语作文评分标准）
```

职责：

> 根据 `EnglishEssayRubricV1`，从学生作文中分别提取能够支持四个评分维度判断的客观证据。

固定关注：

```text
Content（内容）
Organization（组织结构与衔接）
Grammar（语法与句式）
Vocabulary（词汇）
```

Agent 1 **不直接打分，也不负责最终 Taxonomy 分类**，只生成按四个评分维度组织的结构化评分证据 `evidence.json`。具体持久化结构以 `docs/02-grading-result-schema.md` 为准。

#### 5.4.3 Agent 2：真正评分、反馈与结构化诊断

模型：

```text
DeepSeek v4 Flash
```

输入：

```text
作文题目
+
EnglishEssayRubricV1
+
学生作文原文
+
Agent 1 evidence.json
+
Knowledge Point Taxonomy
+
Error Type Taxonomy
```

职责：

```text
依据 EnglishEssayRubricV1 正式评分
↓
四个维度分别输出 0–5 整数分
↓
说明扣分原因
↓
给出修改建议
↓
从当前英语 Taxonomy 的 level=2 小类中
选择 knowledge_point_key / error_code
↓
同时生成 raw_name / raw_type
```

Agent 2 与数学正式批改使用相同的 Taxonomy Contract：不得自行创造新的 `key / code`；没有精确小类时使用对应大类下的 `OTHER`；每条诊断都保留 `raw_name / raw_type`。标准 `name / type` 由后端字典补齐。

因此英语作文 Workflow 的核心关系是：

```text
DeepSeek v4 Flash
Agent 1：原文 + 题目 + EnglishEssayRubricV1
        ↓
按四维提取证据，不打分、不做最终 Taxonomy 分类
        ↓
evidence
        ↓
DeepSeek v4 Flash
Agent 2：原文 + EnglishEssayRubricV1 + evidence + Taxonomy
        ↓
四维评分 + 反馈 + 标准 key/code + raw 语义
        ↓
TaxonomyValidator
        ↓
GradingResult
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
EnglishEssayRubricV1
evidence.json
模型路由
Prompt
Knowledge Point / Error Type Taxonomy
TaxonomyValidator
Submission status / current_stage
Progress Event
```

这些全部属于 **Grading Workflow / 工程执行层内部实现**。

业务层不需要感知内部进行了多少模型调用，也不把 Agent 1 / Agent 2 的中间结果当成多次业务批改。

知识点、错误类型和错误原因等诊断信息同样由 Workflow 内部识别，不要求教师预先逐题标注；其中标准 `key / code` 必须从当前学科 Taxonomy 的 `level = 2` 小类中选择，`raw_name / raw_type` 保存模型对本次具体情况识别出的原始语义。

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
模型路由
数学步骤识别 / 英语证据提取
正式评分
错误诊断
知识点识别
Taxonomy 校验
```

对外仍然只有一个最终批改结果。

如果学生在 `SUCCEEDED / FAILED` 后重新提交，系统清除旧 `OCRResult / GradingResult`，复用同一 `Submission` 并重新进入一次完整 Workflow；`PENDING / RUNNING` 时不接受新的提交。

---

## 6. GradingResult 边界

`GradingResult` 是完整 Grading Workflow 对外输出的唯一当前有效批改结果，需要同时兼容数学和英语作文，并为后续学生画像、班级学情分析和 Teacher Agent 提供稳定的结构化数据基础。

本文件只定义 `GradingResult` 在业务流程中的位置、来源和职责，不在这里重复展开具体字段设计。

> `GradingResult` 的完整 Schema、公共字段、标准 Taxonomy 诊断字段、数学扩展字段、英语作文扩展字段以及哪些字段用于后续数据沉淀，统一在 `docs/02-grading-result-schema.md` 中定义。

---

## 7. 当前业务事实链

当前核心业务关系固定为：

```text
Teacher
   ↓
Class
   ↓
Homework
├── status = DRAFT / PUBLISHED
└── Question ← QuestionBankItem（复制来源）
   ↓
Student Submission（当前提交）
├── image_url
├── status
└── current_stage
   ↓
后台异步 Grading Workflow
   ├── OCR → OCRResult
   ├── Math：OCR Block 拼装 → 读取 Question.difficulty → 模型路由 → Taxonomy Prompt → 动态步骤评分 → TaxonomyValidator
   └── English：EnglishEssayRubricV1 → DeepSeek v4 Flash Evidence Extraction → DeepSeek v4 Flash Scoring + Taxonomy Diagnosis → TaxonomyValidator
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
GradingStreamAdapter
        ↓
DeerFlow StreamBridge
        ↓
Submission SSE Endpoint
        ↓
useGradingStream
        ↓
DeerFlow Chat / GradingProgressMessage
        ↓
学生实时看到 complete / active / pending
        ↓
GradingResultMessage
```

其中：

- `Teacher / Student / Class / Homework / Question` 定义业务上下文；`Homework` 先以 `DRAFT` 创建，发布后进入 `PUBLISHED`。
- `QuestionBankItem` 是可复用题库资源；加入 Homework 时复制为独立 `Question`，已存在 Question 不受题库后续修改影响。
- 教师自行创建数学 Question 时由 `Qwen3.5-4B` 预判 difficulty 并允许教师发布前修正；题库题直接复制已有 difficulty。
- 英语作文 `Question.max_score` 固定为 `20`，`Question / QuestionBankItem` 不保存 Rubric；正式批改统一使用系统内置 `EnglishEssayRubricV1`。
- `Submission` 表示学生对某一道题当前有效的真实答案，同时保存当前批改 `status / current_stage`；同一 `student_id + question_id` 只保留一条。
- `Question.image_url / Submission.image_url` 是 Teacher Copilot 正式业务资产引用；当前优先复用 DeerFlow 已确认的上传 UI / validation 能力，Thread Upload 是否可进一步承担业务资产生命周期在实现阶段继续检查，满足要求时优先复用。
- `PENDING / RUNNING` 时拒绝重复提交；`SUCCEEDED / FAILED` 后复用同一 Submission 重新提交。
- `OCRResult` 持久化学生 Submission 的 OCR 核心结构化识别证据；数学批改使用 `layout_details` 的 Block 顺序、内容和坐标。
- `Grading Workflow` 负责 OCR、结构化解析、确定性题型路由，以及数学或英语作文的具体批改过程。
- 数学批改直接读取 `Question.difficulty`：easy / medium 使用 `Qwen3.5-4B`，hard 使用 `DeepSeek v4 Flash`，学生批改阶段不重新进行 difficulty classification。
- 数学步骤由正式批改模型根据学生实际解法动态识别和评分，`error_block_ids` 与 OCR `bbox2d` 共同支持原图 Block 级错误定位。
- 英语作文固定使用 `DeepSeek v4 Flash` 完成“按 `EnglishEssayRubricV1` 提取四维证据 → 正式四维评分与结构化诊断”两阶段 Workflow，不进行 difficulty 模型路由。
- Knowledge Point / Error Type 使用系统维护的两级 Taxonomy；模型选择标准 `level = 2` `key / code` 并保留 `raw_name / raw_type`，后端 Validator 只负责合法性校验。
- `GradingResult` 是当前 Submission 成功完成 Workflow 后对外输出的唯一最终批改结果。
- `MySQL` 保存业务事实、OCR 证据、Taxonomy 标准参考字典和题库资源，为后续学生画像、班级学情分析和 Teacher Agent 提供可信数据基础。
- 学生实时进度继续展示在 DeerFlow Chat 中：复用聊天容器、Message Timeline、ChainOfThought 类步骤 UI 和 StreamBridge 基础能力；`grading.*` 业务事件不伪装成 `AIMessage / reasoning / tool_calls`，页面刷新恢复仍以 `Submission.status / current_stage` 为准。

页面信息架构、Figma Frame 与 DeerFlow Frontend 组件复用映射统一见：

- `docs/ui-figma-and-deerflow-frontend.md`