---
name: student-diagnosis
description: 分析一个学生的长期学习状态、薄弱知识点、重复错误与趋势,并使用历史批改事实提供证据。
allowed-tools:
  - get_student_profile
  - get_student_grading_history
---

# Task Goal

判断学生长期哪里薄弱、为什么薄弱、是否存在重复错误和趋势变化,并给出有历史事实支撑的诊断结论。

# Required Tools

- get_student_profile:读取 ProfileAlgorithmV1 已判定的 weak_points / recurring_errors / trend
- get_student_grading_history:下钻真实历史批改记录作为解释证据

# Workflow

1. get_student_profile → 读取长期薄弱、重复错误、趋势
2. get_student_grading_history → 查找对应历史题目、得分、performance、error 作为证据
3. 按确定性画像语义组织诊断:
   - 长期薄弱 = 对应知识点存在于 profile.weak_points
   - 近期退步 = profile.trend = declining
   - 重复错误 = (error_code, knowledge_point_key) 存在于 profile.recurring_errors
   - 偶发错误 = 历史出现但未进入 weak_points / recurring_errors

# Evidence Rules

- 不得重新计算 mastery / weak_point / trend,这些只来自 ProfileAlgorithmV1
- 单次错误不得升级为长期薄弱或重复错误
- 引用历史证据时给出具体题目、时间与得分

# Output Format

整体状态 / 薄弱知识点 / 重复错误 / 学习趋势 / 历史证据 / 诊断结论

# Fallback

画像数据不足(无批改历史)→ 明确说明证据不足,不下结论;数据源异常 → 报告失败并给出错误码。
