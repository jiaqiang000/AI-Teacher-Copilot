---
name: homework-review
description: 分析某个班级的一次具体作业,定位高错题、共性错误、低表现知识点与即时异常学生,并结合班级长期画像形成讲评优先级与建议。
allowed-tools:
  - get_homework_analysis
  - get_question_analysis
  - get_class_profile
---

# Task Goal

对一次具体作业生成讲评方案:高错题、本次共性错误、本次低表现知识点、长期薄弱知识点、本次即时异常学生、讲评优先级与建议。

# Required Tools

- get_homework_analysis:获取当前作业即时分析(AnalysisCalculationV1)
- get_question_analysis:下钻高错题的常见错误与典型证据
- get_class_profile:判断当前问题是否属于班级长期薄弱

# Workflow

1. get_homework_analysis → 完成情况、成绩表现、低表现知识点、questions[].error_rate、attention_students
2. 从 questions[] 选 error_rate > 0 且最高的 Top 3 高错题
3. 逐题 get_question_analysis → common_errors / representative_errors / knowledge_points
4. get_class_profile → 对照:本次低表现知识点 vs ClassProfile.weak_points;本次异常学生 vs attention_students
5. 区分本次偶发/即时问题 与 长期薄弱问题,生成讲评方案

# Evidence Rules

- 不得重新计算 error_rate / avg_performance / attention_students(AnalysisCalculationV1 专属)
- 不得把一次低表现直接升级为长期 weak_point
- 引用错误证据须给出真实数据(题目、人数、错误码)

# Output Format

作业总体表现 / 高错题 / 本次共性错误 / 本次低表现知识点 / 长期薄弱知识点 / 本次即时异常学生 / 讲评优先级 / 讲评建议

# Fallback

无有效批改数据 → 说明未批改或数据不足;分析失败 → 报告错误码。
