# AI Teacher Copilot：06–07 Agent Memory、意图路由与 Multi-Agent 设计

## 1. 设计定位

在 Step 1–5 已经确定业务事实、`GradingResult`、学习画像、Teacher Agent Tools（教师智能体工具）与 Skills（技能）之后，Step 6–7 只解决 Teacher Agent（教师智能体）的运行时问题：

```text
Step 6   Agent Memory（智能体记忆）
         = 系统长期记住什么

Step 6.5 Intent Routing（意图识别与任务路由）
         = 当前请求应该怎么执行

Step 7   Multi-Agent（多智能体）
         = 复杂组合任务由哪些 Agent 协作
```

三者共同形成 Teacher Agent Runtime（教师智能体运行时）：

```text
Teacher Request（教师请求）
        ↓
Intent Router（意图路由器）
        ↓
读取当前任务需要的 Memory（记忆）
        ↓
选择执行路径
├── Direct Tool（直接工具）
├── Single Skill（单技能）
└── Composite Task（组合任务）
        ↓
   Multi-Agent（多智能体）
        ↓
Answer（最终回答）
```

核心原则：

> **Memory（记忆）提供跨会话上下文，Intent Router（意图路由器）选择执行路径，Multi-Agent（多智能体）只处理真正需要多个教学任务协作的复杂请求。**

---

# 6. Agent Memory（智能体记忆）

## 6.1 定位与边界

Agent Memory（智能体记忆）只保存：

> **需要跨会话长期保留，但不属于客观业务事实的信息。**

系统边界固定为：

```text
MySQL / Profile（画像）
= 客观业务事实与可重算学习状态

Tool（工具）
= 查询和访问业务数据

Skill（技能）
= 完成复杂教学任务的 SOP（标准流程）

Agent Memory（智能体记忆）
= 教师长期偏好、教学习惯、历史教学决策、跨会话上下文
```

Memory 不能替代 MySQL / Profile，也不能成为学生学习数据的事实源。

---

## 6.2 Memory 保存内容

当前阶段只规划 4 类长期信息：

```text
Teacher Preference（教师偏好）
├── 偏好的回答长度
├── 偏好的分析方式
└── 偏好的输出形式

Teaching Style（教学风格）
├── 偏重基础讲解
├── 偏重启发式提问
└── 偏重错题复盘

Teaching Decision（历史教学决策）
├── 某知识点决定重点讲解
├── 某学生需要持续关注
└── 某班级采用某种练习策略

Conversation Context（跨会话上下文）
├── 上一次分析的班级 / 学生
├── 当前正在处理的作业
└── 上一次教学任务的关键上下文
```

这些信息的共同特点是：

- 需要跨会话保留；
- 会影响后续 Teacher Agent 的回答或教学策略；
- 不是学生分数、掌握度等客观业务事实。

---

## 6.3 不进入 Memory 的内容

以下内容必须由 Tool（工具）从 MySQL / Profile 中读取，不能依赖 Memory：

```text
学生分数
知识点掌握度
薄弱知识点
重复错误统计
作业完成率
题目错误率
历史 GradingResult（批改结果）
Student Profile（学生画像）
Class Profile（班级画像）
```

例如：

```text
教师：
“张三数学现在有哪些薄弱知识点？”

错误：
直接读取 Memory 中旧的学习结论

正确：
get_student_profile（查询学生画像）
↓
获取当前可重算学习状态
```

核心原则：

> **Memory 是上下文，不是业务事实数据库。**

---

## 6.4 Memory 读写流程

运行时流程：

```text
Teacher Request（教师请求）
        ↓
确定当前任务需要哪些 Memory
        ↓
读取相关 Memory
        ↓
作为补充上下文参与 Tool / Skill / Agent 执行
        ↓
生成最终结果
        ↓
判断是否产生值得长期保存的新信息
        ↓
必要时新增 / 更新 / 失效 Memory
```

Memory 读取需要按当前任务裁剪，不把教师全部历史记忆一次性塞入 LLM 上下文。

---

## 6.5 Memory 数据结构

当前阶段先使用简单结构，不提前建设复杂 Memory Framework（记忆框架）：

```text
AgentMemory
│
├── id
├── teacher_id
├── memory_type
├── content
├── status
├── created_at
└── updated_at
```

其中 `memory_type（记忆类型）`：

```text
teacher_preference
teaching_style
teaching_decision
conversation_context
```

`status（状态）` 至少支持：

```text
active（有效）
invalid（失效）
```

当前阶段只要求支持：

```text
Write（写入）
Read（读取）
Update（更新）
Invalidate（失效）
```

后续数据量和复杂度真正增加后，再考虑：

```text
Semantic Retrieval（语义检索）
Memory Compression（记忆压缩）
Memory Reflection（记忆反思）
```

不作为当前 MVP 的前置依赖。

---

## 6.6 Memory 与 Skill 的关系

Skill（技能）的 SOP 本身保持稳定，Memory 只作为额外上下文参与执行。

例如：

```text
homework-review（作业讲评分析）
        ↓
按照固定 SOP 查询作业事实
        +
Teacher Preference（教师偏好）
        ↓
事实分析不改变
        ↓
最终输出形式可以适配教师偏好
```

因此：

```text
Skill
= 决定任务怎么完成

Memory
= 补充教师长期上下文
```

Memory 不修改 Tool 返回的事实，也不改变 Skill 中必须执行的事实验证步骤。

---

# 6.5 Intent Routing（意图识别与任务路由）

## 6.5.1 定位

这里不单独建设一个复杂的 Intent Classification（意图分类）系统，而是建设一个轻量 Intent Router（意图路由器）。

它只回答一个问题：

> **当前教师请求应该走 Direct Tool（直接工具）、Single Skill（单技能），还是 Multi-Agent（多智能体）？**

因此不设计十几个甚至几十个意图标签。

---

## 6.5.2 三类执行路径

```text
Teacher Request（教师请求）
        ↓
Intent Router（意图路由器）
        ↓
┌──────────────────────────────┐
│                              │
├── Direct Tool（直接工具）
│   简单、明确的数据查询
│
├── Single Skill（单技能）
│   一个完整教学任务
│
└── Composite Task（组合任务）
    多个教学任务需要协作
            ↓
       Multi-Agent（多智能体）
```

### A. Direct Tool（直接工具）

适合明确、简单的数据查询。

```text
“张三有哪些薄弱知识点？”
→ get_student_profile（查询学生画像）

“这次作业完成率是多少？”
→ get_homework_analysis（查询作业分析）

“第 8 题错误率是多少？”
→ get_question_analysis（查询题目分析）
```

流程：

```text
Teacher Request
↓
Intent Router
↓
Tool
↓
Answer
```

不进入 Skill，也不进入 Multi-Agent。

### B. Single Skill（单技能）

适合一个完整、明确的教学任务。

```text
“分析一下张三长期学习情况。”
→ student-diagnosis（学生学习诊断）

“分析一下八三班整体学情。”
→ class-learning-analysis（班级学情分析）

“帮我分析这次作业应该怎么讲评。”
→ homework-review（作业讲评分析）

“给班里不同水平学生安排练习。”
→ differentiated-practice（分层练习设计）
```

当前阶段可路由到 4 个 Skill：

```text
student-diagnosis（学生学习诊断）
class-learning-analysis（班级学情分析）
homework-review（作业讲评分析）
differentiated-practice（分层练习设计）
```

`personalized-intervention（个性化教学干预）` 当前阶段仍暂缓。

流程：

```text
Teacher Request
↓
Intent Router
↓
Single Skill
↓
Skill SOP
↓
Tools
↓
Answer
```

### C. Composite Task（组合任务）

当一个请求同时包含多个独立教学目标时，才进入 Multi-Agent。

例如：

```text
“分析这次作业，
找出班级主要问题，
然后针对不同水平学生生成分层练习。”
```

可以拆成：

```text
Task 1
homework-review（作业讲评分析）

Task 2
differentiated-practice（分层练习设计）
```

因此：

```text
Intent Router
↓
Composite Task（组合任务）
↓
Teacher Supervisor（教师主管智能体）
↓
Multi-Agent（多智能体）执行
```

---

## 6.5.3 Intent Router 输出

Intent Router 输出保持简单，只保留执行真正需要的信息：

```text
route_type（路由类型）
target（执行目标）
entities（业务实体参数）
```

示例：

```json
{
  "route_type": "single_skill",
  "target": "student-diagnosis",
  "entities": {
    "student_id": "stu_001",
    "subject": "math"
  }
}
```

`route_type（路由类型）` 固定为：

```text
direct_tool
single_skill
multi_agent
```

`target（执行目标）` 可以是：

```text
get_student_profile
homework-review
student-diagnosis
teacher-supervisor
...
```

`entities（业务实体参数）` 根据请求提取：

```text
student_id
class_id
homework_id
question_id
subject
```

---

## 6.5.4 路由原则

优先使用最简单、成本最低且能完整完成任务的执行路径：

```text
能用一个 Tool 完成
→ 不进入 Skill

能用一个 Skill 完成
→ 不进入 Multi-Agent

只有多个独立教学任务需要协作
→ 才进入 Multi-Agent
```

这可以避免为了使用 Agent 而强行增加 Agent 调用，提高执行稳定性并控制成本与延迟。

---

# 7. Teacher Multi-Agent（教师多智能体）

## 7.1 定位

Multi-Agent（多智能体）不是 Teacher Copilot 的默认执行方式。

它只负责：

> **一个教师请求中包含多个相对独立的教学任务，并且后一个任务需要使用前一个任务的分析结果时，组织多个专业 Agent 协作。**

因此整体执行原则是：

```text
简单事实查询
→ Tool

单个复杂教学任务
→ Skill

多个教学任务组合
→ Multi-Agent
```

---

## 7.2 当前阶段 Agent 划分

当前阶段只设计 3 个角色：

```text
Teacher Supervisor
（教师主管智能体）
│
├── Learning Analysis Agent
│   （学习分析智能体）
│
└── Practice Agent
    （练习设计智能体）
```

当前不单独设计 Curriculum Agent（课程智能体）和 Reviewer Agent（审核智能体），避免与现有 Skill 职责重复或为了 Multi-Agent 强行增加角色。

后续 RAG / Teaching Knowledge Base（教学知识库）建设完成后，可以增加：

```text
Teaching Intervention Agent
（教学干预智能体）
```

---

## 7.3 Teacher Supervisor（教师主管智能体）

职责：

```text
接收 Composite Task（组合任务）
↓
拆分子任务
↓
确定任务依赖和执行顺序
↓
调用专业 Agent
↓
传递必要的结构化中间结果
↓
整合最终回答
```

Supervisor（主管智能体）本身尽量不重新执行具体教学分析。

例如：

```text
“分析这次作业并给不同水平学生设计练习。”
```

拆分为：

```text
Task 1：分析作业
Task 2：基于分析结果设计练习
```

执行：

```text
Teacher Supervisor
        ↓
Learning Analysis Agent
        ↓
作业问题分析
        ↓
Practice Agent
        ↓
分层练习设计
        ↓
Teacher Supervisor
        ↓
Final Answer（最终回答）
```

---

## 7.4 Learning Analysis Agent（学习分析智能体）

定位：

> **负责判断学生、班级或作业“发生了什么问题、问题在哪里”。**

可使用 Skills：

```text
student-diagnosis（学生学习诊断）
class-learning-analysis（班级学情分析）
homework-review（作业讲评分析）
```

可使用 Tools：

```text
get_student_profile（查询学生画像）
get_student_grading_history（查询学生批改历史）
get_class_profile（查询班级画像）
get_homework_analysis（查询作业分析）
get_question_analysis（查询题目分析）
```

关系：

```text
Learning Analysis Agent
        ↓
根据任务选择 Skill
        ↓
Skill SOP
        ↓
Tools
        ↓
结构化分析结果
```

Agent 不重新实现 Skill 已经确定的分析 SOP。

---

## 7.5 Practice Agent（练习设计智能体）

定位：

> **根据已经确定的学习问题，决定不同学生下一步应该怎么练。**

核心 Skill：

```text
differentiated-practice（分层练习设计）
```

主要 Tools：

```text
get_class_profile（查询班级画像）
get_student_profile（查询学生画像）
search_question_bank（检索题库）
```

典型流程：

```text
接收学习分析结果
↓
确定训练目标
↓
确定学生分层
↓
确定各层 knowledge_points（知识点）
↓
确定 difficulty（难度）与 question_type（题型）
↓
search_question_bank（检索题库）
↓
生成分层练习方案
```

---

## 7.6 Teaching Intervention Agent（教学干预智能体）【后续】

当前阶段不实现。

原因：

```text
personalized-intervention（个性化教学干预）
        ↓ 依赖
search_teaching_materials（教学资料检索）
        ↓ 依赖
RAG / Teaching Knowledge Base（教学知识库）
```

当前阶段上述能力已暂缓，因此不提前创建一个底层能力尚未成立的 Agent。

后续启用后关系可以是：

```text
Teaching Intervention Agent
        ↓
personalized-intervention
        ↓
search_teaching_materials
+
search_question_bank
```

---

## 7.7 Agent / Skill / Tool 职责边界

三者必须保持清晰：

```text
Agent（智能体）
= 谁负责

Skill（技能）
= 一个教学任务应该怎么完成

Tool（工具）
= 真正查询 / 计算 / 检索数据
```

完整调用关系：

```text
Teacher Supervisor（教师主管智能体）
        ↓
Professional Agent（专业智能体）
        ↓
Skill（技能 / SOP）
        ↓
Tool（工具）
        ↓
Service（业务服务）
        ↓
MySQL / Redis
```

例如：

```text
Learning Analysis Agent
        ↓
homework-review（作业讲评分析）
        ↓
get_homework_analysis
get_question_analysis
get_class_profile
        ↓
MySQL / Redis
```

因此不能把 Agent 和 Skill 设计成一一重复的两套能力。

---

## 7.8 Agent 间结果传递

Agent 之间优先传递结构化结果，而不是把整段自然语言回答直接交给下一个 Agent。

例如 Learning Analysis Agent 输出：

```text
LearningAnalysisResult
│
├── weak_knowledge_points
├── common_errors
├── attention_students
├── key_questions
└── evidence_summary
```

Practice Agent 读取这些字段后再执行 `differentiated-practice（分层练习设计）`。

这样可以减少信息丢失，也方便后续评测每个 Agent 的输入输出是否正确。

---

## 7.9 完整 Multi-Agent 示例

教师请求：

```text
“分析八三班这次数学作业，
找到主要问题，
然后给不同水平学生安排练习。”
```

执行流程：

```text
Teacher Request（教师请求）
        ↓
Intent Router（意图路由器）
        ↓
识别为 Composite Task（组合任务）
        ↓
Teacher Supervisor（教师主管智能体）
        ↓
拆分任务
        │
        ├── Task 1：作业分析
        │       ↓
        │ Learning Analysis Agent
        │ （学习分析智能体）
        │       ↓
        │ homework-review
        │ （作业讲评分析）
        │       ↓
        │ 输出高错题 / 薄弱知识点 / 共性错误 / 重点学生
        │
        ↓
Task 2：分层练习设计
        ↓
Practice Agent
（练习设计智能体）
        ↓
differentiated-practice
（分层练习设计）
        ↓
search_question_bank
（检索题库）
        ↓
分层练习方案
        ↓
Teacher Supervisor
        ↓
Final Answer（最终回答）
```

这个场景是当前阶段 Multi-Agent 最核心的业务闭环：

```text
发现问题
↓
分析问题
↓
基于分析结果采取教学行动
```

---

# 8. 06–07 整体运行关系

最终 Teacher Agent Runtime（教师智能体运行时）固定为：

```text
Teacher Request（教师请求）
        ↓
Intent Router（意图路由器）
        ↓
识别任务 + 提取业务实体
        ↓
读取必要 Memory（记忆）
        ↓
选择最简单可完成任务的路径
        │
        ├── Direct Tool（直接工具）
        │
        ├── Single Skill（单技能）
        │
        └── Composite Task（组合任务）
                 ↓
          Teacher Supervisor
                 ↓
       ┌─────────┴─────────┐
       ↓                   ↓
Learning Analysis      Practice Agent
Agent（学习分析）       （练习设计）
       ↓                   ↓
     Skills              Skills
       ↓                   ↓
     Tools               Tools
       └─────────┬─────────┘
                 ↓
          MySQL / Redis
                 ↓
          Final Answer
                 ↓
      必要时更新 Memory
```

一句话概括：

```text
Memory（记忆）
= 记住什么

Intent Routing（意图路由）
= 当前请求走哪条执行路径

Multi-Agent（多智能体）
= 多个教学任务如何由不同 Agent 协作
```

---

# 9. 当前阶段实现范围

当前实现：

```text
Agent Memory
├── 4 类 Memory
└── 基础读 / 写 / 更新 / 失效

Intent Router
├── direct_tool
├── single_skill
└── multi_agent

Multi-Agent
├── Teacher Supervisor
├── Learning Analysis Agent
└── Practice Agent
```

当前暂不实现：

```text
复杂语义 Memory 检索
Memory Reflection（记忆反思）
Teaching Intervention Agent（教学干预智能体）
Curriculum Agent（课程智能体）
Reviewer Agent（审核智能体）
```

原则是：

> **先让 Tool、Skill、Memory、Routing 与 Multi-Agent 的职责边界稳定，再根据真实业务复杂度增加 Agent，而不是提前堆叠 Agent 数量。**

---

## 10. 本阶段产出

```text
Agent Memory Schema（智能体记忆结构）
+
Memory Read / Write Flow（记忆读写流程）
+
Intent Routing Schema（意图路由结构）
+
Tool / Skill / Multi-Agent 路由规则
+
Multi-Agent 架构图
+
Agent 职责与可用 Skill / Tool 边界
+
典型组合任务执行链路
```
