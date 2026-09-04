# AI Teacher Copilot：UI、Figma 与 DeerFlow Frontend 复用映射

## 1. 文档目的

本文件不定义新的业务规则、数据 Schema、Agent 架构或画像算法。

本文件只负责把已经在 `docs/00.md` ～ `docs/08.md` 中确定的产品与技术设计映射到前端实现，统一说明：

```text
页面 Information Architecture（信息架构）
+
Figma 设计
+
页面消费的业务数据
+
TeacherBusinessContext
+
DeerFlow Frontend 可复用能力
+
Teacher Copilot 前端新增能力
```

本文件的目标是让前端实现阶段可以直接回答：

```text
这个功能在哪个页面？
这个页面应该读取什么业务数据？
普通页面应该调用 Business API 还是 Agent Tool？
进入 Teacher Copilot 时当前页面应该传什么 Context？
DeerFlow 哪些前端代码可以直接复用？
哪些部分必须由 Teacher Copilot 自己实现？
```

因此，本文件属于 **UI / Frontend Mapping 文档**，不是新的业务 Source of Truth。

---

## 2. Source of Truth（事实源边界）

当前项目的四层关系固定为：

```text
业务规则 / Schema / Agent Runtime
→ docs/00.md ～ docs/08.md

UI 信息架构 / 交互 / 视觉
→ Figma

Frontend 复用实现
→ DeerFlow 当前 main 代码

本文件
→ 上述三者之间的映射关系
```

发生冲突时：

```text
Figma 与业务文档冲突
→ 业务文档优先
→ 更新 Figma

本文件与业务文档冲突
→ 业务文档优先
→ 更新本文件

DeerFlow Frontend 当前实现与 Figma 有差异
→ 保持已经确定的业务交互目标
→ 优先复用 DeerFlow 现有组件 / primitives
→ 只在教育业务确实需要时增加 Teacher Copilot 领域扩展
```

因此禁止：

```text
因为 Figma 里多了一张 Card
→ 临时给 GradingResult / Profile 新增字段

因为某个 DeerFlow 页面只有 Chat
→ 强行把所有教师业务页面都做成 Chat

因为 UI 需要某个数字
→ 在 Frontend 临时重新计算 ProfileAlgorithmV1 / AnalysisCalculationV1
```

业务规则变化必须先修改对应业务设计文档，再同步到本文件和 Figma。

---

## 3. Figma

当前设计文件：

```text
AI Teacher Copilot — DeerFlow UI
https://www.figma.com/design/0ugwazaOoaDw71Nlrak6tB
```

当前核心 Frame：

```text
Teacher
01 · Teacher Dashboard
02 · Class Detail
03 · Student Profile
04 · Homework Authoring
05 · Homework Analysis
06 · Teacher Copilot Chat

Student
07 · Student Homework
08 · Student Grading
```

当前 `01～06` Teacher Frames 使用统一 Teacher Workspace Sidebar。除工作台、班级、作业、学生、Teacher Copilot 等业务导航外，Sidebar 还包含“最近聊天”区域，用于表现历史 Teacher Copilot 会话入口。

Figma 当前展示的：

```text
八三班最近学情
hw_004 作业讲评
张三数学诊断
```

只是历史会话标题的示例内容，用于表达列表与当前会话状态；实际前端内容由运行时 Teacher Copilot 会话产生。

这里的 Frame Name 只是设计标识：

```text
Frame Name
≠ 最终 Route Name
≠ Backend API Path
≠ 业务对象名称
```

最终 Next.js Route 可以在编码阶段按 DeerFlow 当前路由结构和 Teacher Copilot 页面组织方式确定，但页面职责必须保持与本文件一致。

---

## 4. 页面总览

### 4.1 Teacher 页面

```text
01 · Teacher Dashboard
= 教师工作台首页
= 快速查看班级、近期作业和重点状态

02 · Class Detail
= 一个班级的长期学情与业务入口
= 班级画像 + 学生 / 作业入口

03 · Student Profile
= 一个学生某学科的长期学习画像
= 薄弱点、趋势、重复错误、历史证据

04 · Homework Authoring
= 创建 / 编辑 DRAFT Homework
= 手动输入 / 图片 OCR / Question Bank 添加 Question
= 发布 Homework

05 · Homework Analysis
= 一次具体作业的即时分析
= 完成情况、成绩、知识点、题目表现
= 可下钻 Question Analysis

06 · Teacher Copilot Chat
= 教师侧唯一 Agent Runtime 交互面
= DeerFlow Thread / Run + teacher-copilot
```

`01～06` Teacher 页面共享同一 Teacher Workspace Sidebar。Sidebar 一侧承载教师业务导航，另一部分提供“最近聊天”入口，帮助教师快速回到此前的 Teacher Copilot 会话；“最近聊天”不是新增的独立业务页面。

### 4.2 Student 页面

```text
07 · Student Homework
= 查看已发布 Homework
= 查看 Question 列表
= 查看每道题当前 Submission 状态
= 选择一道 Question 进入作答 / 批改

08 · Student Grading
= 上传当前 Question 的单题答案图片
= 实时展示 Submission 批改阶段
= 展示最终 GradingResult
= 数学支持 OCR Block 级错误定位
= 英语作文支持固定四维 Rubric 结果
```

---

## 5. 非独立页面的 UI

以下能力需要 UI，但当前 MVP 不建设成独立产品页面。

### 5.1 Question Bank

```text
Question Bank
→ 04 · Homework Authoring 内 Drawer / Dialog
```

用途：

```text
筛选 QuestionBankItem
→ 选择
→ Copy
→ 当前 Homework 中生成新的 Question
```

Question Bank 当前只要求 Seed Data + MySQL 条件查询，不建设独立教师题库管理后台。

### 5.2 Question Analysis

```text
Question Analysis
→ 05 · Homework Analysis 内 Drawer / Detail Panel
```

用途：

```text
HomeworkAnalysis.questions[]
→ 发现高错题
→ 打开某一 Question
→ 读取 QuestionAnalysis
→ 展示 common_errors / representative_errors / knowledge_points
```

因此 Question Analysis 是 Homework Analysis 的下钻，不新增顶级导航页面。

### 5.3 Question Add / Edit

```text
Question Add / Edit
→ 04 · Homework Authoring 内 Modal / Drawer / Inline Editor
```

支持：

```text
手动输入
上传题目图片
Question Bank 选择
content 修正
difficulty 确认
max_score
question_no / 排序
```

这些是 Homework Authoring 的编辑能力，不建设独立 Question Management 页面。

### 5.4 DeerFlow HITL Clarification

```text
ask_clarification
→ 06 · Teacher Copilot Chat 内 Human Input Card
```

Figma 中如果出现 Clarification Card，它只是 DeerFlow Human Input UI / Card 的产品视觉表现。

实现仍然复用：

```text
ask_clarification
→ ClarificationMiddleware
→ Human Input Request / Interrupt
→ DeerFlow Human Input UI
→ Resume Thread / Run
```

不新增 `TeacherClarificationModal / TeacherHITLService / TeacherInterruptProtocol`。

### 5.5 Math / English Result

```text
Math Result
English Essay Result
→ 都属于 08 · Student Grading 的 Result Variant
```

不是：

```text
Math Grading Page
+
English Grading Page
```

也不是两套 `GradingResult` Contract。

统一由：

```text
GradingResult
├── common fields
├── math_detail              可选
└── english_essay_detail     可选
```

决定当前结果展示 Variant。

---

## 6. 明确不建设的产品页面

当前 MVP 不建设以下独立页面。

### 6.1 Question Bank Management

原因：

```text
当前 Question Bank
= 系统预置 / Seed Data
= MySQL 条件查询
= Homework Authoring 的候选题来源
```

没有教师题库审核、版本、去重、RAG、自动生成等管理业务，因此不需要独立管理页。

### 6.2 Agent Management

Teacher Agent 固定为 DeerFlow Custom Agent：

```text
teacher-copilot
```

当前教师用户不负责创建、配置、切换 Agent，因此不建设 Agent Management 页面。

### 6.3 Sub-Agent Management

Diagnosis Worker / Practice Worker / Reviewer 是 DeerFlow Runtime 内按需 `task` 启动的执行能力：

```text
Sub-Agent
= Runtime implementation
≠ 教师需要管理的业务对象
```

因此不建设 Worker 列表、Worker 配置、手动启动等管理页面。

### 6.4 Memory Management

Teacher Memory 当前直接复用 DeerFlow Memory Runtime，只保存教师偏好、教学风格和 Teaching Decision Context。

当前业务没有“教师手工管理 Memory 条目”的需求，因此不建设 Memory Management 页面。

### 6.5 Skill Management

当前 4 个实施 Skill 是工程配置与 `SKILL.md`：

```text
student-diagnosis
class-learning-analysis
homework-review
differentiated-practice
```

教师不负责在产品中编辑 `SKILL.md` 或配置 allowed-tools，因此不建设 Skill Management 页面。

### 6.6 Rubric Management

英语作文固定使用：

```text
EnglishEssayRubricV1
Content 5
Organization 5
Grammar 5
Vocabulary 5
Total 20
```

教师不可自定义维度、权重或总分，因此不建设 Rubric 配置页面。

### 6.7 Taxonomy Management

Knowledge Point / Error Type 是系统标准参考字典。当前 MVP 不提供教师维护 Taxonomy 的产品能力，因此不建设 Taxonomy Management 页面。

### 6.8 Eval Dashboard

当前评测采用：

```text
DeerFlow RunEventStore
+
Langfuse
+
Eval Runner / Behavior Checker
```

当前项目没有建设第二套产品内 Eval Dashboard 的必要，评测结果通过现有开发 / 观测工具查看。

---

## 7. 页面 → 数据结构映射

页面只消费业务层已经定义的数据，不在 Frontend 新建第二套统计逻辑。

| 页面 | 主要业务数据 | 说明 |
|---|---|---|
| `01 · Teacher Dashboard` | `Teacher / Class / Homework summary` | 教师工作台摘要；不是新的 Profile Source of Truth |
| `02 · Class Detail` | `Class + ClassProfile + ClassStudent[] + HomeworkSummary[]` | 长期班级画像与学生 / 作业入口 |
| `03 · Student Profile` | `Student + StudentProfile + GradingResult[] history` | 长期画像为结论；Grading History 用于证据下钻 |
| `04 · Homework Authoring` | `Homework + Question[] + QuestionBankItem[]` | DRAFT 编辑、题库 Copy、difficulty 确认、发布 |
| `05 · Homework Analysis` | `HomeworkAnalysis + QuestionAnalysis` | HomeworkAnalysis 为主；QuestionAnalysis 为题目下钻 |
| `06 · Teacher Copilot Chat` | `DeerFlow Thread / Run + Teacher Tool / Skill Results` | Agent 最终回答必须基于 Tool 获取的正式业务事实 |
| `07 · Student Homework` | `Homework + Question[] + Submission summary` | 展示题目列表和每题当前作答 / 批改状态 |
| `08 · Student Grading` | `Submission + OCRResult + GradingResult` | Submission 管状态；OCRResult 只在错误定位等证据展示时需要；GradingResult 管最终结果 |

### 7.1 Class Detail

`02 · Class Detail` 中长期学情数据来自：

```text
ClassProfile
├── overview
├── knowledge_points
├── weak_points
├── common_errors
└── attention_students
```

Frontend 不重新计算 `avg_mastery / weak_point / attention_students`。

### 7.2 Student Profile

`03 · Student Profile` 中：

```text
StudentProfile
= 长期学习状态

Grading History
= 真实历史批改证据
```

页面可以把两者做视觉组合，但不能根据某一条 Grading History 在前端自行修改长期 weak_point / recurring_error 判断。

### 7.3 Homework Analysis

`05 · Homework Analysis`：

```text
HomeworkAnalysis
= 当前一次 Homework 的即时确定性分析

QuestionAnalysis
= 一道具体 Question 的下钻分析
```

Frontend 不重新计算：

```text
completion_rate
avg_score_rate
score_distribution
avg_performance
error_rate
attention_students
```

### 7.4 Student Grading

`08 · Student Grading` 的职责分开：

```text
Submission.status / current_stage
= 实时批改状态和刷新恢复 Source of Truth

SSE / StreamBridge
= 实时增量体验

GradingResult
= 当前成功批改最终业务结果

OCRResult.layout_details
= 数学原图错误 Block 坐标证据
```

Figma 不保存也不定义任何实际 bbox 坐标。

---

## 8. 页面 → TeacherBusinessContext

只有教师业务页面向 Teacher Copilot 发起 AI 请求时，才需要构造 `TeacherBusinessContext`。

当前结构：

```text
TeacherBusinessContext
├── teacher_id
├── class_refs[]
│   ├── class_id
│   └── class_name
│
├── current_class_id        可选
├── current_student_id      可选
├── current_subject         可选
├── current_homework_id     可选
├── current_question_id     可选
│
└── current_question_refs[] 可选
    ├── question_id
    └── question_no
```

页面映射：

| 页面 | Context |
|---|---|
| `01 · Teacher Dashboard` | `teacher_id + class_refs` |
| `02 · Class Detail` | `current_class_id + current_subject`（页面已经选定学科时） |
| `03 · Student Profile` | `current_class_id + current_student_id + current_subject` |
| `04 · Homework Authoring` | `current_class_id + current_homework_id + current_subject + current_question_refs`（已有 Question 时） |
| `05 · Homework Analysis` | `current_class_id + current_homework_id + current_subject + current_question_refs`；打开具体题目时增加 `current_question_id` |
| `06 · Teacher Copilot Chat` | 从业务页进入时继承来源页面 Context；直接打开 Chat 时 Context 可以为空 |

Context 原则：

```text
Context First
= 页面已经知道的对象直接传

Minimal Context
= 只传 ID / subject / refs 等轻量对象引用

Never Snapshot Business Facts
= 不把完整 StudentProfile / ClassProfile / HomeworkAnalysis 塞进 Context
```

真正事实仍通过 Tool 获取。

同时：

```text
TeacherBusinessContext
≠ 权限事实
```

即使前端传入了 `current_student_id / current_class_id`，Teacher Tool 仍然必须使用 Runtime 中的可信身份调用 `TeacherPermissionService` 做权限校验。

---

## 9. 页面 → DeerFlow Frontend 复用

实现阶段默认以 DeerFlow 当前 `main` 为复用来源。

### 9.1 Workspace Shell

教师业务页面整体壳层优先复用：

```text
frontend/src/app/workspace/workspace-content.tsx
frontend/src/components/workspace/workspace-sidebar.tsx
```

优先保留 DeerFlow 的：

```text
Workspace Layout
Sidebar / SidebarInset
Workspace Header
基础导航交互
Recent Chat / Thread History UI
Settings / Toaster 等已有 Workspace 基础设施
```

Teacher Workspace Sidebar 中的“最近聊天”优先复用 DeerFlow 已有的 Thread History / Recent Chat 前端能力。当前 DeerFlow `main` 中的 `RecentChatList` 可以作为实现阶段的直接复用参考；最终具体复用方式仍以编码时 DeerFlow current main 为准。

Teacher Copilot 在其中增加教育业务导航和页面内容，不重新创建一套完全独立 App Shell。

### 9.2 Teacher Copilot Chat

`06 · Teacher Copilot Chat` 优先复用：

```text
frontend/src/components/workspace/chats/chat-page.tsx
```

以及已有：

```text
MessageList
InputBox
Thread
Streaming
Thread Title / Chat lifecycle
Sidecar / Artifact 等当前确有需要的已有能力
```

Teacher Copilot 不重新实现第二套 Chat / Thread / Streaming Runtime。

### 9.3 HITL

复用：

```text
ask_clarification
Clarification Middleware
DeerFlow Human Input UI / Card
Interrupt / Resume
```

Figma Clarification Card 只定义产品视觉和信息组织，不改变该执行链。

### 9.4 Student Grading

`08 · Student Grading` 继续使用 DeerFlow Chat / Message Timeline 作为主要过程容器，并复用：

```text
frontend/src/components/ai-elements/chain-of-thought.tsx
├── ChainOfThought
├── ChainOfThoughtContent
└── ChainOfThoughtStep
```

Teacher Copilot 新增领域消息：

```text
GradingProgressMessage
GradingResultMessage
```

业务阶段：

```text
OCR
PARSING
GRADING
ASSEMBLING_RESULT
```

只是 Grading Workflow stage，不能伪装成：

```text
AIMessage
reasoning
tool_calls
```

### 9.5 Upload

教师题目图片和学生答案图片优先复用 DeerFlow 文件选择 / validation 等通用前端能力，包括：

```text
frontend/src/core/uploads/file-validation.ts
```

但正式业务资产仍分别由 Teacher Copilot 业务能力负责：

```text
QuestionAssetService
→ Question.image_url

SubmissionAssetService
→ Submission.image_url
```

Thread Upload 的临时 user-data 生命周期不能直接成为正式业务资产事实源，除非实现阶段进一步确认其存储生命周期完全满足业务要求。

### 9.6 Sub-Agent Visible Execution

Teacher Copilot Chat 如果需要向教师展示复杂任务正在执行什么，优先复用 DeerFlow 已有：

```text
Sub-Agent execution UI
Background Task UI
Thread Subagent / Task lifecycle display
```

这里只展示执行过程，不建设独立 Sub-Agent 管理页，也不让教师手工管理 Worker 生命周期。

---

## 10. 普通 Business API 与 Agent Tool 的边界

这是前端实现时必须严格遵守的边界。

普通教师业务页面：

```text
Teacher Business Page
        ↓
Business API
        ↓
Service
        ↓
Repository
        ↓
MySQL / Redis
```

Teacher Agent：

```text
Teacher Copilot Chat
        ↓
DeerFlow Tool Runtime
        ↓
Teacher Tool（@tool / BaseTool）
        ↓
同一个 Service
        ↓
Repository
        ↓
MySQL / Redis
```

例如 Student Profile：

```text
03 · Student Profile
→ Student Profile API
→ StudentProfileService

Teacher Agent
→ get_student_profile Tool
→ StudentProfileService
```

例如 Homework Analysis：

```text
05 · Homework Analysis
→ Homework Analysis API
→ HomeworkAnalysisService

Teacher Agent
→ get_homework_analysis Tool
→ HomeworkAnalysisService
```

例如 Question Bank：

```text
04 · Homework Authoring
→ QuestionBank API
→ QuestionBankService

Teacher Agent
→ search_question_bank Tool
→ QuestionBankService
```

核心规则：

```text
UI 不调用 Agent Tool
Tool 不替代 Business API
Business API 不通过 Agent 获取确定性业务事实

Business API 与 Agent Tool
→ 共享 Service / Repository
```

这样可以保证普通页面和 Agent 使用同一套业务语义，又不会把普通 CRUD / 查询页面绑到 LLM Runtime 上。

---

## 11. 每个页面的实现职责

### 11.1 `01 · Teacher Dashboard`

**页面目的**

```text
教师登录后的工作台摘要
快速进入班级、作业、重点学生与 Teacher Copilot
```

**主要业务数据**

```text
Teacher
Class summary
Recent Homework summary
必要的业务摘要数据
```

Dashboard 可以展示摘要，但不在 Frontend 临时计算新的长期画像算法。

**主要操作**

```text
进入 Class Detail
进入 Homework
进入 Student Profile
进入 Teacher Copilot
```

**DeerFlow 直接复用**

```text
Workspace Shell
Sidebar / navigation primitives
基础 Card / Button / Layout primitives（适合时）
```

**Teacher Copilot 新增**

```text
教师教育业务 Dashboard 内容
班级 / 作业 / 重点状态摘要组件
```

**不属于这个页面**

```text
Agent 配置
完整 Student Profile
完整 Homework Analysis
Question Bank 管理
```

### 11.2 `02 · Class Detail`

**页面目的**

```text
查看一个班级长期学习状态
并作为学生 / 作业下钻入口
```

**主要业务数据**

```text
Class
ClassProfile
ClassStudent[]
HomeworkSummary[]
```

**主要操作**

```text
查看长期薄弱知识点
查看常见错误
查看 attention_students
进入 Student Profile
进入 Homework / Homework Analysis
从当前班级上下文进入 Teacher Copilot
```

**DeerFlow 直接复用**

```text
Workspace Shell
通用 Layout / Card / list primitives
```

**Teacher Copilot 新增**

```text
ClassProfile 领域展示
学生列表 / 作业列表领域组件
```

**不属于这个页面**

```text
单次 Homework 的完整即时分析
Agent 执行管理
```

### 11.3 `03 · Student Profile`

**页面目的**

```text
查看一个学生某学科的长期学习状态和证据
```

**主要业务数据**

```text
StudentProfile
Grading History
```

**主要操作**

```text
查看 overview
查看 knowledge_points
查看 weak_points
查看 recurring_errors
查看 trend
下钻历史批改证据
从当前学生上下文进入 Teacher Copilot
```

**DeerFlow 直接复用**

```text
Workspace Shell
通用 Layout / Card / list primitives
```

**Teacher Copilot 新增**

```text
StudentProfile 领域展示组件
Grading History 下钻组件
```

**不属于这个页面**

```text
重新计算 mastery
根据单次错误前端判断 weak_point
学生提交作业
```

### 11.4 `04 · Homework Authoring`

**页面目的**

```text
创建 / 编辑 DRAFT Homework
形成实际 Question
发布 Homework
```

**主要业务数据**

```text
Homework
Question[]
QuestionBankItem[]（Drawer 中按需查询）
```

**主要操作**

```text
创建 Homework
手动输入 Question
上传题目图片 → OCR → 修正 content
数学 difficulty 预判 → 教师确认 / 修改
从 Question Bank 选择 → Copy Question
调整 question_no / 排序
发布 Homework
```

**DeerFlow 直接复用**

```text
Workspace Shell
Upload UI primitives
file-validation.ts
通用 Dialog / Drawer / Input / Button primitives（适合时）
```

**Teacher Copilot 新增**

```text
Homework Authoring 业务表单
Question 编辑领域组件
Question Bank Drawer
QuestionAssetService 对应业务 API
发布校验交互
```

**不属于这个页面**

```text
Question Bank Management
Rubric 编辑
学生 Submission OCRResult
```

### 11.5 `05 · Homework Analysis`

**页面目的**

```text
分析一次具体 Homework 的即时表现
并下钻高错 Question
```

**主要业务数据**

```text
HomeworkAnalysis
QuestionAnalysis（按需下钻）
```

**主要操作**

```text
查看 completion
查看 performance / score_distribution
查看 knowledge_points
查看 questions[]
打开 Question Analysis Drawer
查看 attention_students
从当前作业上下文进入 Teacher Copilot
```

**DeerFlow 直接复用**

```text
Workspace Shell
通用 Layout / Card / table / drawer primitives（适合时）
```

**Teacher Copilot 新增**

```text
HomeworkAnalysis 领域可视化
Question Analysis Drawer
```

**不属于这个页面**

```text
重新计算 error_rate
把本次 low_performance 直接标成长 weak_point
```

### 11.6 `06 · Teacher Copilot Chat`

**页面目的**

```text
Teacher Agent 的统一 AI Runtime 交互面
```

**主要业务数据 / Runtime**

```text
DeerFlow Thread / Run
TeacherBusinessContext
Teacher Tool Result
Skill execution
Sub-Agent execution
Memory Context
```

**主要操作**

```text
自然语言提问
Tool / Skill / Multi-Agent 执行
HITL clarification
查看最终回答
```

**DeerFlow 直接复用**

```text
ChatPage
MessageList
InputBox
Thread / Run
Streaming
Human Input UI
Sub-Agent / Background Task UI
```

**Teacher Copilot 新增**

```text
teacher-copilot Custom Agent
TeacherBusinessContextMiddleware
教育业务 Tool / Skill / Worker
必要的教师领域消息展示
```

**不属于这个页面**

```text
Agent Management
Sub-Agent Management
Memory Management
Skill Management
```

### 11.7 `07 · Student Homework`

**页面目的**

```text
学生查看当前已发布 Homework
选择具体 Question
```

**主要业务数据**

```text
Homework
Question[]
Submission summary
```

**主要操作**

```text
查看题目
查看已提交 / 批改中 / 已完成 / 失败状态
选择 Question
进入 Student Grading
```

**DeerFlow 直接复用**

```text
可复用通用 Layout / list / status primitives
```

Student 页面不要求机械复用 Teacher Workspace 的教师业务导航；实现时应保持学生身份和任务流清晰，只复用适合的 DeerFlow 通用前端 primitives。

**Teacher Copilot 新增**

```text
学生 Homework / Question 列表
Submission 状态摘要
学生侧导航与任务入口
```

**不属于这个页面**

```text
完整 GradingResult
Teacher Agent
Teacher Workspace 业务导航
```

### 11.8 `08 · Student Grading`

**页面目的**

```text
完成一个 Question 的答案上传、实时批改和结果查看
```

**主要业务数据**

```text
Question
Submission
OCRResult（数学错误定位按需）
GradingResult
```

**主要操作 / 状态**

```text
未提交
→ 上传答案

PENDING / RUNNING
→ Student Image Message
→ GradingProgressMessage

FAILED
→ 失败信息
→ 允许重新提交

SUCCEEDED
→ GradingResultMessage
```

**DeerFlow 直接复用**

```text
Chat / Message Timeline
ChainOfThought UI primitives
Upload / validation primitives
StreamBridge 基础流式能力
```

**Teacher Copilot 新增**

```text
GradingStreamAdapter
Submission SSE Endpoint
useGradingStream
gradingEventToProgressUpdate
GradingProgressMessage
GradingResultMessage
数学 bbox overlay
英语四维结果组件
SubmissionAssetService 对应业务 API
```

**Math Result Variant**

```text
score
feedback
math_detail.steps[]
error_block_ids
→ OCRResult.layout_details
→ bbox2d
→ 原图 Block 标记
```

**English Essay Result Variant**

```text
score / 20
Content / 5
Organization / 5
Grammar / 5
Vocabulary / 5
feedback
language_errors（如有）
evidence（需要展示时）
```

**不属于这个页面**

```text
把 OCR / PARSING / GRADING 伪装成 Agent reasoning / tool_calls
创建第二套 Math / English GradingResult Contract
字符级错误定位
```

---

## 12. Figma 同步规则

### 12.1 业务规则变化

如果发生：

```text
业务状态变化
Schema 字段变化
Profile / Analysis 规则变化
TeacherBusinessContext 变化
Agent / Tool / Skill 边界变化
```

更新顺序固定为：

```text
对应 docs/00.md ～ docs/08.md
        ↓
本文件
        ↓
Figma
        ↓
Frontend implementation
```

### 12.2 纯视觉变化

如果只是：

```text
间距
字体层级
Card 样式
布局方式
图标
视觉状态表现
```

且没有改变业务语义，则：

```text
更新 Figma
→ Frontend 同步实现
```

不需要因此修改业务 Schema。

### 12.3 DeerFlow 可复用实现发生变化

如果 DeerFlow 新版本出现更适合直接复用的前端能力：

```text
检查 DeerFlow current main
↓
更新本文件中的复用映射
↓
优先减少 Teacher Copilot 自定义代码
```

但：

```text
DeerFlow implementation change
≠ 自动改变 Teacher Copilot 业务规则
```

如果 DeerFlow 的默认行为与本项目业务 Contract 不一致，应通过 Adapter / 轻量领域扩展保持已确定的业务语义，而不是反向修改 Homework / Submission / GradingResult / Profile / Analysis 等事实定义。

---

## 最终前端实现原则

```text
业务规则
→ 以 00–08 为准

页面与交互设计
→ 以 Figma + 本文件为实现参考

通用前端基础能力
→ 优先复用 DeerFlow

教育业务内容
→ Teacher Copilot 领域实现

普通业务页面
→ Business API → Service

Teacher Agent
→ DeerFlow Tool Runtime → Teacher Tool → Same Service

Figma
→ 不成为业务事实源

Frontend
→ 不重新计算业务事实
```

核心目标不是“看起来像 DeerFlow”，而是：

> **在保持 AI Teacher Copilot 已确定业务语义的前提下，最大化复用 DeerFlow 已有 Workspace、Chat、HITL、Streaming、Upload 和 Agent 执行展示能力，只为教育业务真正缺失的部分增加领域实现。**
