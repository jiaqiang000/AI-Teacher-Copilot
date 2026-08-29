# AI Teacher Copilot：GradingResult 统一数据结构设计

## 1. 设计目标

`GradingResult` 是当前有效 `Submission` 经过完整 Grading Workflow 后，对业务层输出的**唯一最终批改结果**。

```text
Submission（当前提交）
    ↓
完整 Grading Workflow
    ↓
GradingResult（当前有效结果）
```

它需要同时满足三类需求：

1. 学生当前能看到：分数、对错/表现、错误原因、本题反馈。
2. 后续系统能沉淀：知识点、错误类型、得分等结构化事实，用于学生画像和班级学情分析。
3. 教师侧和 Teacher Agent 能查询：最近错误、薄弱知识点、高错题、典型错误等。

因此 `GradingResult` 不能只保存一段自然语言评语，而必须同时保存**结构化诊断结果 + 展示型文本反馈**。

> 文档中的逻辑结构图、字段清单和字段说明统一采用 `field_name（中文含义）` 的形式。为了保证 JSON 示例仍然是合法、可直接用于程序实现的 JSON，JSON Key 本身保持英文原字段名不变。

---

## 2. 核心原则

### 2.1 一个当前有效 Submission 对应一个当前有效 GradingResult

```text
Submission（当前提交）
    ↓
完整 Workflow
    ↓
GradingResult（当前有效结果）
```

Workflow 内部即使发生多个模型调用、Evidence Extraction、Scoring、模型路由或工具调用，对业务层仍然只输出一个最终结果。

当前关系固定为：

```text
Submission.status = SUCCEEDED
→ 当前 GradingResult 有效并可以展示

Submission.status = PENDING / RUNNING / FAILED
→ 不存在可展示的当前成功 GradingResult
```

如果学生在 `SUCCEEDED / FAILED` 后重新提交：

```text
删除旧 GradingResult
↓
删除旧 OCRResult
↓
复用同一 Submission
↓
status = PENDING
current_stage = QUEUED
↓
重新执行完整 Workflow
↓
成功后写入新的当前 GradingResult
```

`GradingResult.submission_id` 始终指向当前 Submission。第一版不保存旧批改版本，也不使用 `Submission.version / submission_version / GradingTask` 解决结果竞争；`PENDING / RUNNING` 时禁止再次提交，因此同一道题任意时刻最多只有一个运行中的批改 Workflow。

### 2.2 数学和英语共用一个顶层结构

不要分别维护两套完全独立的 `MathGradingResult` 和 `EnglishGradingResult`。

统一使用：

```text
GradingResult
├── common fields（公共字段）
├── diagnosis（结构化诊断）
├── feedback（当前题即时反馈）
├── math_detail（数学详情）                可选
└── english_essay_detail（英语作文详情）   可选
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

为了支持后续统计，不能长期依赖完全自由的自然语言名称。当前 Schema 同时保留 `name（知识点名称）` 和可标准化的 `key（知识点标识）`；知识点标准化、同义词归一和知识体系映射在后续数据沉淀阶段处理。

### 2.4 difficulty（难度）仅用于数学模型路由

教师不需要填写题目难度。

数学题：

```text
Question
   ↓
Qwen3.5-4B
   ↓
difficulty = easy / medium / hard
   ↓
模型路由
```

识别结果进入 `GradingResult`，既可以用于工程统计，也可以用于后续分析模型路由效果。

英语作文当前固定使用 `DeepSeek v4 Flash` 两阶段批改，不进行 difficulty classification，因此英语作文的 `difficulty` 允许为 `null`。

### 2.5 GradingResult 只保存“当前这次批改”的反馈

`feedback（当前题即时反馈）` 表示针对当前 Submission 的即时反馈。

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
├── grading_result_id（批改结果ID）
├── submission_id（学生提交ID）
│
├── subject（学科）
├── question_type（题型）
├── difficulty（难度；英语可为 null）
│
├── score（得分信息）
│   ├── earned（实际得分）
│   ├── max（满分）
│   └── rate（得分率）
│
├── diagnosis（结构化诊断）
│   ├── knowledge_points[]（知识点列表）
│   └── errors[]（错误列表）
│
├── feedback（当前题即时反馈）
│   ├── summary（总体评价）
│   ├── strengths[]（做得好的地方）
│   └── improvements[]（需要改进的地方）
│
├── math_detail（数学详情）                    可选
├── english_essay_detail（英语作文详情）       可选
│
├── execution_meta（执行元数据）
│   ├── route（模型路由结果）
│   └── models_used[]（实际使用的模型列表）
│
└── created_at（创建时间）
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
| `grading_result_id（批改结果ID）` | 最终批改结果 ID |
| `submission_id（学生提交ID）` | 对应当前哪个学生提交 |
| `subject（学科）` | `math` / `english` |
| `question_type（题型）` | 如 `calculation` / `solution` / `essay` |
| `difficulty（难度）` | 数学题由 `Qwen3.5-4B` 识别为 `easy` / `medium` / `hard`；英语作文当前为 `null` |

`student_id（学生ID）`、`question_id（题目ID）`、`homework_id（作业ID）` 不需要在逻辑 Schema 中重复保存，通过 `submission_id（学生提交ID）` 可以关联获得。是否在数据库层做冗余字段优化，留到数据库设计阶段决定。

---

## 5. Score（得分信息）

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
earned（实际得分） = 实际得分
max（满分）         = 满分
rate（得分率）      = earned / max
```

后续学生画像和班级统计优先使用结构化 `score.rate（得分率）`，而不是从自然语言评语中提取成绩信息。

---

## 6. Diagnosis（结构化诊断）

这是 `GradingResult` 最重要的沉淀部分。

```text
diagnosis（结构化诊断）
├── knowledge_points（知识点列表）
└── errors（错误列表）
```

这些字段主要服务于后续：

```text
学生知识画像
班级薄弱知识点
高频错误统计
Teacher Agent 查询
```

### 6.1 KnowledgePoint（知识点）

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
| `key（知识点标识）` | 可归一化的知识点标识；当前可以由模型输出，后续统一映射 |
| `name（知识点名称）` | 面向人的知识点名称 |
| `performance（当前表现）` | 当前这道题上该知识点表现 |
| `evidence（判断证据）` | 为什么判断该知识点表现如此 |

`performance（当前表现）` 建议限制为：

```text
correct（正确）
partial（部分正确）
incorrect（错误）
```

注意：

> `performance = incorrect` 只说明学生在**当前这道题**上暴露了问题，不代表系统已经认定该知识点是学生的长期薄弱点。

长期薄弱点必须由多次 `GradingResult` 聚合得到。

### 6.2 Error（错误）

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
| `code（错误编码）` | 用于程序统计的标准错误类型 |
| `type（错误类型）` | 面向教师/学生的名称 |
| `knowledge_point_key（关联知识点标识）` | 错误关联到哪个知识点 |
| `description（错误描述）` | 错误原因描述 |
| `evidence（错误证据）` | 从学生作答中找到的证据 |

后续班级统计应该优先统计 `code（错误编码）`，而不是统计自然语言 `description（错误描述）`。

数学步骤上的原图定位信息不重复塞进公共 `diagnosis.errors[]`。真正需要定位的 OCR Block 由 `math_detail.steps[].error_block_ids` 保存，再通过对应 `OCRResult.layout_details` 回查 `bbox2d`。

---

## 7. Feedback（当前题即时反馈）

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
summary（总体评价）
→ 当前题整体评价

strengths（做得好的地方）
→ 当前题做得好的地方

improvements（需要改进的地方）
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

动态生成，而不是直接把当前 `feedback（当前题即时反馈）` 当成长画像。

---

# 8. 数学扩展字段

数学题需要额外保存模型从学生实际作答中识别出的关键步骤、步骤得分和 OCR Block 证据。

```text
math_detail（数学详情）
├── correct（最终答案是否正确）
├── final_answer（模型从学生作答中识别出的最终答案）
└── steps[]（关键解题步骤）
    ├── step_index（步骤序号）
    ├── description（步骤说明）
    ├── evidence_block_ids[]（该步骤对应的 OCR Block）
    ├── error_block_ids[]（该步骤中需要在原图标记的错误 Block）
    ├── status（步骤状态）
    ├── earned_score（步骤实际得分）
    ├── max_score（步骤满分）
    └── feedback（步骤反馈）
```

推荐：

```json
{
  "math_detail": {
    "correct": false,
    "final_answer": "x = 3",
    "steps": [
      {
        "step_index": 1,
        "description": "正确建立一元一次方程",
        "evidence_block_ids": [2, 3],
        "error_block_ids": [],
        "status": "correct",
        "earned_score": 3,
        "max_score": 3,
        "feedback": "列式正确。"
      },
      {
        "step_index": 2,
        "description": "进行移项并化简",
        "evidence_block_ids": [4, 5],
        "error_block_ids": [5],
        "status": "incorrect",
        "earned_score": 1,
        "max_score": 4,
        "feedback": "移项后符号处理错误。"
      },
      {
        "step_index": 3,
        "description": "根据前一步结果继续求解",
        "evidence_block_ids": [6, 7],
        "error_block_ids": [],
        "status": "consequential_error",
        "earned_score": 2,
        "max_score": 3,
        "feedback": "结果受前一步错误影响，但当前除法操作本身合理。"
      }
    ]
  }
}
```

### 8.1 Step status（步骤状态）

固定为：

```text
correct
= 当前步骤正确

partial
= 思路或推导部分正确，但存在遗漏或局部错误

incorrect
= 当前步骤本身存在数学错误

consequential_error
= 当前步骤受到前序错误结果影响，但当前数学操作或推理方式本身合理
```

`consequential_error` 用于避免“前一步错了，后续全部判零分”的简单错误传播逻辑。

### 8.2 Block 字段职责

```text
evidence_block_ids
→ 模型判断这一关键步骤时使用的 OCR Block

error_block_ids
→ 这一关键步骤中真正存在错误、需要前端在原图框选的 OCR Block
```

正确步骤通常：

```json
{
  "error_block_ids": []
}
```

`error_block_ids` 不直接保存坐标。坐标仍属于 OCR 证据层：

```text
math_detail.steps[].error_block_ids
        ↓
OCRResult.layout_details[index]
        ↓
bbox2d + width + height
        ↓
前端原图红色矩形框
```

这样避免在 `GradingResult` 里复制 OCR 坐标数据。

### 8.3 数学步骤分约束

数学结果必须满足：

```text
Σ math_detail.steps[].max_score
=
score.max

Σ math_detail.steps[].earned_score
=
score.earned

0 <= step.earned_score <= step.max_score
```

同时：

```text
每个 evidence_block_id
必须存在于当前 OCRResult.layout_details

每个 error_block_id
必须存在于当前 OCRResult.layout_details

同一步骤中的 error_block_ids
应属于该步骤 evidence_block_ids 所覆盖的 OCR 内容
```

因此总分只在顶层 `score` 保存一份；总体评价只在顶层 `feedback` 保存一份；错误类型只在顶层 `diagnosis.errors` 保存一份。

`math_detail` 只承担数学特有的逐步骤过程数据，避免重复字段。

---

# 9. 英语作文扩展字段

英语作文采用 Rubric 多维评分。

```text
english_essay_detail（英语作文详情）
├── dimension_scores（多维评分）
│   ├── content（内容）
│   ├── organization（组织结构）
│   ├── grammar（语法）
│   └── vocabulary（词汇）
├── language_errors（语言错误列表）
└── evidence（评分证据）
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

其中主要字段含义：

```text
dimension_scores（多维评分）
content（内容维度）
organization（组织结构维度）
grammar（语法维度）
vocabulary（词汇维度）
score（该维度得分）
max_score（该维度满分）

language_errors（语言错误列表）
type（错误类型）
original（原句）
suggestion（修改建议）

evidence（评分证据）
```

英语作文的知识点也进入公共 `diagnosis.knowledge_points（知识点列表）`，例如：

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

## 10. Execution Meta（执行元数据）：记录模型路由结果

业务结果只有一个 `GradingResult`，但为了后续评测模型路由的成本、延迟和效果，可以保留少量执行元数据。

```text
execution_meta（执行元数据）
├── route（模型路由结果）
└── models_used[]（实际使用的模型列表）
```

数学 easy / medium：

```json
{
  "execution_meta": {
    "route": "small_model",
    "models_used": [
      "Qwen3.5-4B"
    ]
  }
}
```

数学 hard：

```json
{
  "execution_meta": {
    "route": "strong_model",
    "models_used": [
      "Qwen3.5-4B",
      "DeepSeek v4 Flash"
    ]
  }
}
```

这里 `Qwen3.5-4B` 用于 difficulty classification，`DeepSeek v4 Flash` 用于困难题正式批改。

英语作文：

```json
{
  "execution_meta": {
    "route": "english_two_stage",
    "models_used": [
      "DeepSeek v4 Flash"
    ]
  }
}
```

英语两阶段虽然会调用 `DeepSeek v4 Flash` 两次，但 `models_used[]` 表示使用过的模型集合，不重复记录同一模型。

这里记录内部执行事实，但不会产生多个业务层 GradingResult。

---

# 11. 数学完整示例

> 以下 JSON 保持真实英文 Key，中文含义以本文前面的字段结构和字段表为准。

```json
{
  "grading_result_id": "gr_10001",
  "submission_id": "sub_10001",
  "subject": "math",
  "question_type": "solution",
  "difficulty": "easy",

  "score": {
    "earned": 6,
    "max": 10,
    "rate": 0.6
  },

  "diagnosis": {
    "knowledge_points": [
      {
        "key": "math.linear_equation",
        "name": "一元一次方程",
        "performance": "partial",
        "evidence": "能够正确建立方程，但后续移项出现错误"
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
    "summary": "解题整体思路正确，但移项时出现符号错误，后续结果受到该错误影响。",
    "strengths": [
      "能够正确建立一元一次方程",
      "后续仍能按照已有结果继续进行合理运算"
    ],
    "improvements": [
      "重点检查移项后的正负号变化"
    ]
  },

  "math_detail": {
    "correct": false,
    "final_answer": "x = 3",
    "steps": [
      {
        "step_index": 1,
        "description": "正确建立一元一次方程",
        "evidence_block_ids": [2, 3],
        "error_block_ids": [],
        "status": "correct",
        "earned_score": 3,
        "max_score": 3,
        "feedback": "列式正确。"
      },
      {
        "step_index": 2,
        "description": "进行移项并化简",
        "evidence_block_ids": [4, 5],
        "error_block_ids": [5],
        "status": "incorrect",
        "earned_score": 1,
        "max_score": 4,
        "feedback": "移项后符号处理错误。"
      },
      {
        "step_index": 3,
        "description": "根据前一步结果继续求解",
        "evidence_block_ids": [6, 7],
        "error_block_ids": [],
        "status": "consequential_error",
        "earned_score": 2,
        "max_score": 3,
        "feedback": "结果受到前一步影响，但当前运算方式本身合理。"
      }
    ]
  },

  "english_essay_detail": null,

  "execution_meta": {
    "route": "small_model",
    "models_used": [
      "Qwen3.5-4B"
    ]
  },

  "created_at": "2026-08-21T17:30:00+08:00"
}
```

这个示例中：

```text
score.earned = 3 + 1 + 2 = 6
score.max    = 3 + 4 + 3 = 10
```

`Block 5` 可以通过当前 `OCRResult.layout_details` 找到对应 `bbox2d`，用于学生前端在原始作业图片上绘制红色错误框。

---

# 12. 英语作文完整示例

> 以下 JSON 保持真实英文 Key，中文含义以本文前面的字段结构和字段表为准。

```json
{
  "grading_result_id": "gr_20001",
  "submission_id": "sub_20001",
  "subject": "english",
  "question_type": "essay",
  "difficulty": null,

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
    "route": "english_two_stage",
    "models_used": [
      "DeepSeek v4 Flash"
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
score.rate（得分率）

diagnosis.knowledge_points[].key（知识点标识）
diagnosis.knowledge_points[].performance（当前知识点表现）

diagnosis.errors[].code（错误编码）

subject（学科）
question_type（题型）
difficulty（数学难度；英语当前为空）
```

主要用于展示、过程解释或追溯，不直接作为长期画像核心统计值：

```text
feedback.summary（总体评价）
feedback.strengths（做得好的地方）
feedback.improvements（需要改进的地方）

diagnosis.*.evidence（诊断证据）

math_detail.final_answer（数学最终答案）
math_detail.steps[].description（步骤说明）
math_detail.steps[].evidence_block_ids（步骤 OCR 证据）
math_detail.steps[].error_block_ids（错误定位 Block）
math_detail.steps[].feedback（步骤反馈）

english_essay_detail.evidence（英语作文评分证据）
```

数学步骤中的 `status / earned_score / max_score` 主要用于当前题步骤评分、学生展示和批改追溯；长期画像仍优先使用统一的 `score.rate`、知识点表现和标准错误编码，避免画像过度依赖某一道题的动态步骤划分。

也就是说：

> **长期画像尽量建立在结构化、可统计的稳定信号上；步骤文本、OCR Block 和自然语言反馈主要用于当前批改解释、原图定位与追溯。**