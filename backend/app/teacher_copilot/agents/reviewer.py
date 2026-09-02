"""Reviewer 审核流程(参考文档 06-07 §12,US6)。

大型高价值教学方案交付前,Teacher Lead Agent 按需
task(subagent_type="reviewer") 独立审核(不重新生成方案,只检查):
- 重点学生是否有数据依据
- 长期薄弱判断是否有足够历史证据
- 练习知识点是否对应真实薄弱知识点
- 题目难度是否与学生层级匹配
- 结论与 Profile/Analysis 事实是否冲突
- 是否遗漏明显需要关注的学生

普通事实查询/单学生诊断/普通作业分析不触发 Reviewer(参考文档 08 T-L7-002)。
"""

from __future__ import annotations

# --- Reviewer 审核要点(供 Agent 编排遵循) ---
REVIEWER_SOP = """独立审核大型教学方案:
1. 重点学生是否来自真实 attention 依据(长期/本周即时)
2. 薄弱知识点是否来自 ProfileAlgorithmV1 的 weak_points(而非单次推断)
3. 练习知识点是否与真实薄弱点匹配,难度是否与学生层级匹配
4. 结论是否与 get_*_profile / get_*_analysis / get_question_analysis 事实冲突
5. 是否遗漏明显应关注的学生
输出:{"verdict": "pass|warn|fail", "warnings": ["..."], "issues": ["..."]}"""

# --- Reviewer task prompt 模板 ---
REVIEWER_PROMPT = """你是教学方案审核智能体。只做独立检查,不重新生成方案。
方案: {plan_summary}
检查清单:
1. 重点学生依据(是否来自真实 attention/画像)
2. 薄弱判断证据(是否来自 ProfileAlgorithmV1)
3. 练习知识点/难度与层级匹配
4. 与现有 Profile/Analysis 事实冲突
5. 遗漏关注学生
输出:{"verdict": "pass|warn|fail", "warnings": [...], "issues": [...]}"""


def should_review(plan: dict) -> bool:
    """判定大型方案是否需要 Reviewer(按需启动,不默认所有任务审核)。

    参考文档 06-07 §19.4:仅大型、高价值或教师明确要求的任务需要审核。
    """
    # 大型教学方案:包含班级诊断 + 重点学生 + 分层/个性化练习
    scope = plan.get("scope", [])
    has_week_review = "weekly_review" in scope
    has_practice = "differentiated_practice" in scope or "personalized_practice" in scope
    return plan.get("explicit_review", False) or (has_week_review and has_practice)
