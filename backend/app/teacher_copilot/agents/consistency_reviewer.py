"""Consistency Reviewer 审核流程(参考文档 06-07 §10)。

完整班级周度复盘(WeeklyClassReview)形成后,Teacher Lead Agent 按需
task(subagent_type="consistency-reviewer") 做事实与语义一致性审核:
- 本周 Homework 范围是否完整
- class_findings 是否与 ClassProfile / HomeworkAnalysis 一致
- 长期 weak_point / recurring_error 是否真的来自 Profile
- 是否把一次 Homework 即时异常错误写成长期问题
- students_to_watch / deep_diagnoses 是否有对应的结构化事实依据
- StudentDiagnosisResult 是否与 StudentProfile / GradingHistory 一致
- next_week_teaching_focus 是否对应本周发现的知识点 / 错误

不负责:判断教学法优劣、重新生成整份 WeeklyClassReview、查题库生成练习、发布 Homework。
普通事实查询 / 单学生诊断 / 普通作业分析不触发(参考文档 08 T-L7-002)。

**是否委派由 Lead Agent 按需判断,代码里没有确定性闸门**:此处原本有一个
``should_review(plan)`` 函数,但全仓无人调用,其判据 ``plan["scope"]`` /
``plan["explicit_review"]`` 也没有任何产出方——留着会让人误以为"审核由该闸门把关"
(实际从不执行),已于 008 T045 删除。
"""

from __future__ import annotations

# --- Consistency Reviewer 审核要点(供 Agent 编排遵循) ---
CONSISTENCY_REVIEWER_SOP = """独立审核完整班级周度复盘:
1. 本周 Homework 范围是否完整
2. class_findings 是否与 ClassProfile / HomeworkAnalysis 一致
3. 长期 weak_point / recurring_error 是否真的来自 Profile(而非单次推断)
4. 是否把一次 Homework 即时异常错误写成长期问题
5. students_to_watch / deep_diagnoses 是否有对应结构化事实依据
6. StudentDiagnosisResult 是否与 StudentProfile / GradingHistory 一致
7. next_week_teaching_focus 是否对应本周实际发现的知识点 / 错误
输出:{"status": "PASS|NEEDS_REVISION", "issues": [{"code": "...", "target": "...", "reason": "...", "evidence": "..."}]}"""

# --- Consistency Reviewer task prompt 模板 ---
CONSISTENCY_REVIEWER_PROMPT = """你是班级周度复盘一致性审核子智能体。只做独立检查,
不重新生成整份周度复盘,不判断教学法是否最优。
复盘: {review_summary}
检查清单:
1. 本周 Homework 范围完整性
2. class_findings 与 ClassProfile / HomeworkAnalysis 事实一致性
3. 长期问题与即时问题是否混淆
4. students_to_watch / deep_diagnoses 的事实依据
5. StudentDiagnosisResult 与 Profile / History 一致性
6. next_week_teaching_focus 是否对应实际发现的问题
输出:{"status": "PASS|NEEDS_REVISION", "issues": [{"code": "...", "target": "...", "reason": "...", "evidence": "..."}]}"""
