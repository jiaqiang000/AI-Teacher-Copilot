# AI Teacher Copilot：GradingResult 统一数据结构设计

## 1. 设计目标

`GradingResult` 是一次 `Submission` 经过完整 Grading Workflow 后，对业务层输出的**唯一最终批改结果**。

```text
Submission
    ↓
完整 Grading Workflow
    ↓
GradingResult
```

它需要同时满足三类需求：

1. 学生当前能看到：分数、对错/表现、错误原因、本题反馈。
2. 后续系统能沉淀：知识点、错误类型、得分等结构化事实，用于学生画像和班级学情分析。
3. 教师侧和 Teacher Agent 能查询：最近错误、薄弱知识点、高错题、典型错误等。

因此 `GradingResult` 不能只保存一段自然语言评语，而必须同时保存**结构化诊断结果 + 展示型文本反馈**。

---

## 2. 核心原则

### 2.1 一个 Submission 对应一个最终 GradingResult

```text
Submission A
    ↓
完整 Workflow
    ↓
GradingResult A
```

Workflow 内部即使发生多个模型调用、Evidence Extraction、Scoring、模型路由或工具调用，对业务层仍然只输出一个最终结果。

### 2.2 数学和英语共用一个顶层结构

不要分别维护两套完全独立的 `MathGradingResult` 和 `EnglishGradingResult`。

统一使用：

```text
GradingResult
├── common fields
├── diagnosis
├── feedback
├── math_detail            可选
└── english_essay_detail   可选
```

### 2.3 知识点由模型自动识别

当前 MVP 不要求教师逐题手动标注知识点。

```text
Question + Student Answer
          ↓
      Grading Model
          ↓
自动识别 Knowledge Points
          ↓
     GradingResult
```

知识点是模型产生的结构化诊断结果。

为了支持后续统计，不能长期依赖完全自由的自然语言名称。当前 Schema 同时保留 `name` 和可标准化的 `key`；知识点标准化、同义词归一和知识体系映射在后续数据沉淀阶段处理。

### 2.4 difficulty 由小模型自动识别

教师不需要填写题目难度。

```text
Question
   ↓
Qwen 小模型
   ↓
difficulty / complexity
   ↓
模型路由
```

最终识别结果进入 `GradingResult`，既可以用于工程统计，也可以用于后续分析模型路由效果。

### 2.5 GradingResult 只保存“当前这次批改”的反馈

`feedback` 表示针对当前 Submission 的即时反馈。

例如：

> 解题思路正确，但移项后符号处理错误。

它不负责保存：

> 你最近三周已经多次出现移项符号错误。

后者属于结合历史数据生成的长期个性化反馈，不属于单次 `GradingResult` 本身。

---

## 3. 顶层结构

推荐的逻辑结构：

```text
GradingResult
│
├── grading_result_id
├── submission_id
│
├── subject
├── question_type
├── difficulty
│
├── score
│   ├── earned
│   ├── max
│   └── rate
│
├── diagnosis
│   ├── knowledge_points[]
│   └── errors[]
│
├── feedback
│   ├── summary
│   ├── strengths[]
│   └── improvements[]
│
├── math_detail                 可选
├── english_essay_detail        可选
│
├── execution_meta
│   ├── route
│   └── models_used[]
│
└── created_at
```

---

## 4. 公共字段

### 4.1 身份与题型

```json
{
  "grading_result_id": "gr_10001",
  "submission_id": "sub_10001",
  "subject": "math",
  "question_type": "calculation",
  "difficulty": "easy"
}
```

字段含义：

| 字段 | 含义 |
|---|---|
| `grading_result_id` | 最终批改结果 ID |
| `submission_id` | 对应哪一次学生提交 |
| `subject` | `math` / `english` |
| `question_type` | 如 `calculation` / `solution` / `essay` |
| `difficulty` | 小模型识别出的题目难度，如 `easy` / `medium` / `hard` |

`student_id`、`question_id`、`homework_id` 不需要在逻辑 Schema 中重复保存，通过 `submission_id` 可以关联获得。是否在数据库层做冗余字段优化，留到数据库设计阶段决定。

---

## 5. Score

统一使用：

```json
{
  "score": {
    "earned": 8,
    "max": 10,
    "rate": 0.8
  }
}
```

其中：

```text
earned = 实际得分
max    = 满分
rate   = earned / max
```

后续学生画像和班级统计优先使用结构化 `score.rate`，而不是从自然语言评语中提取成绩信息。

---

## 6. Diagnosis：结构化诊断

这是 `GradingResult` 最重要的沉淀部分。

```text
diagnosis
├── knowledge_points
└── errors
```

这些字段主要服务于后续：

```text
学生知识画像
班级薄弱知识点
高频错误统计
Teacher Agent 查询
```

### 6.1 KnowledgePoint

建议每个知识点不是简单字符串，而是：

```json
{
  "key": "math.linear_equation.transposition",
  "name": "移项",
  "performance": "incorrect",
  "evidence": "学生将 +4 移到等号右侧后仍写成 +4"
}
```

字段：

| 字段 | 含义 |
|---|---|
| `key` | 可归一化的知识点标识；当前可以由模型输出，后续统一映射 |
| `name` | 面向人的知识点名称 |
| `performance` | 当前这道题上该知识点表现 |
| `evidence` | 为什么判断该知识点表现如此 |

`performance` 建议限制为：

```text
correct
partial
incorrect
```

注意：

> `performance = incorrect` 只说明学生在**当前这道题**上暴露了问题，不代表系统已经认定该知识点是学生的长期薄弱点。

长期薄弱点必须由多次 `GradingResult` 聚合得到。

### 6.2 Error

建议统一结构：

```json
{
  "code": "SIGN_ERROR",
  "type": "符号错误",
  "knowledge_point_key": "math.linear_equation.transposition",
  "description": "移项后没有改变符号",
  "evidence": "+4 移到右侧后仍写为 +4"
}
```

字段：

| 字段 | 含义 |
|---|---|
| `code` | 用于程序统计的标准错误类型 |
| `type` | 面向教师/学生的名称 |
| `knowledge_point_key` | 错误关联到哪个知识点 |
| `description` | 错误原因描述 |
| `evidence` | 从学生作答中找到的证据 |

后续班级统计应该优先统计 `code`，而不是统计自然语言 `description`。

---

## 7. Feedback：当前题即时反馈

```json
{
  "feedback": {
    "summary": "整体解题思路正确，但移项时出现符号错误。",
    "strengths": [
      "能够正确建立一元一次方程"
    ],
    "improvements": [
      "移项时注意正负号变化"
    ]
  }
}
```

这里明确区分：

```text
summary
→ 当前题整体评价

strengths
→ 当前题做得好的地方

improvements
→ 当前题需要改进的地方
```

这些字段主要面向学生展示。

后续真正的长期个性化评语应该使用：

```text
当前 GradingResult
+
Student Profile
+
近期历史记录
```

动态生成，而不是直接把当前 `feedback` 当成长画像。

---

# 8. 数学扩展字段

数学题需要额外表达最终答案和过程分。

```text
math_detail
├── correct
├── final_answer
├── reference_answer
└── process
```

推荐：

```json
{
  "math_detail": {
    "correct": false,
    "final_answer": "x = 3",
    "reference_answer": "x = 2",
    "process": {
      "score": 6,
      "max_score": 8,
      "analysis": "列式正确，移项步骤出现符号错误，后续计算基于错误结果继续。"
    }
  }
}
```

### 为什么保留 process？

赛题要求不仅判断最终答案，还要支持过程分。

因此不能只有：

```text
correct = false
```

还需要知道：

```text
学生过程是否合理
错误发生在哪一步
过程应该得到多少分
```

---

# 9. 英语作文扩展字段

英语作文采用 Rubric 多维评分。

```text
english_essay_detail
├── dimension_scores
├── language_errors
└── evidence
```

推荐：

```json
{
  "english_essay_detail": {
    "dimension_scores": {
      "content": {
        "score": 5,
        "max_score": 5
      },
      "organization": {
        "score": 4,
        "max_score": 5
      },
      "grammar": {
        "score": 3,
        "max_score": 5
      },
      "vocabulary": {
        "score": 4,
        "max_score": 5
      }
    },
    "language_errors": [
      {
        "type": "TENSE_ERROR",
        "original": "I go to Beijing last summer.",
        "suggestion": "I went to Beijing last summer."
      }
    ],
    "evidence": [
      "作文内容完整覆盖题目要求",
      "过去时使用存在多处错误",
      "段落之间连接词使用较少"
    ]
  }
}
```

英语作文的知识点也进入公共 `diagnosis.knowledge_points`，例如：

```json
[
  {
    "key": "english.grammar.past_tense",
    "name": "一般过去时",
    "performance": "incorrect",
    "evidence": "描述去年暑假经历时多次使用一般现在时"
  },
  {
    "key": "english.writing.cohesion",
    "name": "篇章衔接",
    "performance": "partial",
    "evidence": "段落基本完整，但连接词使用较少"
  }
]
```

这样数学和英语都可以进入统一的后续知识画像体系。

---

## 10. Execution Meta：记录模型路由结果

业务结果只有一个 `GradingResult`，但为了后续评测模型路由的成本、延迟和效果，可以保留少量执行元数据。

```json
{
  "execution_meta": {
    "route": "small_model",
    "models_used": [
      "qwen2.5-4b"
    ]
  }
}
```

复杂题可能是：

```json
{
  "execution_meta": {
    "route": "strong_model",
    "models_used": [
      "qwen2.5-4b",
      "deepseek-v3"
    ]
  }
}
```

这里记录内部执行事实，但不会产生多个业务层 GradingResult。

---

# 11. 数学完整示例

```json
{
  "grading_result_id": "gr_10001",
  "submission_id": "sub_10001",
  "subject": "math",
  "question_type": "solution",
  "difficulty": "easy",

  "score": {
    "earned": 8,
    "max": 10,
    "rate": 0.8
  },

  "diagnosis": {
    "knowledge_points": [
      {
        "key": "math.linear_equation",
        "name": "一元一次方程",
        "performance": "partial",
        "evidence": "能够正确建立方程"
      },
      {
        "key": "math.linear_equation.transposition",
        "name": "移项",
        "performance": "incorrect",
        "evidence": "移项后符号没有改变"
      }
    ],
    "errors": [
      {
        "code": "SIGN_ERROR",
        "type": "符号错误",
        "knowledge_point_key": "math.linear_equation.transposition",
        "description": "移项后没有改变符号",
        "evidence": "+4 移到右侧后仍写为 +4"
      }
    ]
  },

  "feedback": {
    "summary": "解题整体思路正确，但移项时出现符号错误。",
    "strengths": [
      "能够正确建立方程"
    ],
    "improvements": [
      "重点检查移项后的正负号变化"
    ]
  },

  "math_detail": {
    "correct": false,
    "final_answer": "x = 3",
    "reference_answer": "x = 2",
    "process": {
      "score": 6,
      "max_score": 8,
      "analysis": "列式正确，移项步骤发生符号错误。"
    }
  },

  "english_essay_detail": null,

  "execution_meta": {
    "route": "small_model",
    "models_used": [
      "qwen2.5-4b"
    ]
  },

  "created_at": "2026-08-21T17:30:00+08:00"
}
```

---

# 12. 英语作文完整示例

```json
{
  "grading_result_id": "gr_20001",
  "submission_id": "sub_20001",
  "subject": "english",
  "question_type": "essay",
  "difficulty": "medium",

  "score": {
    "earned": 16,
    "max": 20,
    "rate": 0.8
  },

  "diagnosis": {
    "knowledge_points": [
      {
        "key": "english.grammar.past_tense",
        "name": "一般过去时",
        "performance": "incorrect",
        "evidence": "描述过去经历时多次错误使用一般现在时"
      },
      {
        "key": "english.writing.cohesion",
        "name": "篇章衔接",
        "performance": "partial",
        "evidence": "段落完整，但连接词较少"
      }
    ],
    "errors": [
      {
        "code": "TENSE_ERROR",
        "type": "时态错误",
        "knowledge_point_key": "english.grammar.past_tense",
        "description": "描述过去经历时使用一般现在时",
        "evidence": "I go to Beijing last summer."
      }
    ]
  },

  "feedback": {
    "summary": "内容完整、表达清楚，但过去时使用和篇章衔接仍需加强。",
    "strengths": [
      "完整覆盖了题目要求",
      "主要内容表达清晰"
    ],
    "improvements": [
      "描述过去经历时统一使用一般过去时",
      "适当增加连接词增强段落衔接"
    ]
  },

  "math_detail": null,

  "english_essay_detail": {
    "dimension_scores": {
      "content": {
        "score": 5,
        "max_score": 5
      },
      "organization": {
        "score": 4,
        "max_score": 5
      },
      "grammar": {
        "score": 3,
        "max_score": 5
      },
      "vocabulary": {
        "score": 4,
        "max_score": 5
      }
    },
    "language_errors": [
      {
        "type": "TENSE_ERROR",
        "original": "I go to Beijing last summer.",
        "suggestion": "I went to Beijing last summer."
      }
    ],
    "evidence": [
      "内容覆盖完整",
      "过去时使用存在错误",
      "段落之间连接词不足"
    ]
  },

  "execution_meta": {
    "route": "strong_model",
    "models_used": [
      "qwen2.5-4b",
      "deepseek-v3"
    ]
  },

  "created_at": "2026-08-21T17:35:00+08:00"
}
```

---

# 13. 哪些字段用于后续沉淀

后续学生画像和班级学情分析不应该直接依赖所有字段。

优先沉淀和聚合：

```text
score.rate

diagnosis.knowledge_points[].key
diagnosis.knowledge_points[].performance

diagnosis.errors[].code

subject
question_type
difficulty
```

主要用于展示或追溯，不直接作为长期画像核心统计值：

```text
feedback.summary
feedback.strengths
feedback.improvements

diagnosis.*.evidence
math_detail.process.analysis
english_essay_detail.evidence
```

也就是说：

> **长期画像尽量建立在结构化、可统计的信号上；自然语言文本主要用于解释和展示。**
