---
name: class-learning-analysis
description: 分析班级长期整体状态、薄弱知识点、共性错误、学习趋势和重点关注学生。
allowed-tools:
  - get_class_profile
  - get_student_profile
---

# Task Goal

分析班级长期学情:整体表现、薄弱知识点、共性错误、趋势、重点关注学生,并给出教学优先级。

# Required Tools

- get_class_profile:获取班级画像(长期派生事实)
- get_student_profile:必要时下钻重点学生的长期画像与原因

# Workflow

1. get_class_profile → 读取 weak_points / common_errors / attention_students / trend
2. 必要时对重点学生执行 get_student_profile 下钻
3. 输出班级学情诊断与教学优先级

# Evidence Rules

- 不得重新覆盖 ProfileAlgorithmV1 的 weak / attention 判断
- 单次作业情况不属于班级长期画像;需要单次作业时使用 homework-review
- 重点学生说明须给出原因码(如 LOW_RECENT_SCORE / RECURRING_ERROR)

# Output Format

班级整体状态 / 长期薄弱知识点 / 共性错误 / 学习趋势 / 重点关注学生 / 教学优先级

# Fallback

班级无有效数据 → 说明证据不足;数据源异常 → 报告失败并给出错误码。
