"""分层/个性化练习流程(参考文档 06-07 §10-11,US6)。

- 分层练习:get_class_profile → list_class_students → 按需 get_student_profile →
  划分 基础/巩固/提升 三组 → 各组 search_question_bank → PracticeResult
- 全班个性化:list_class_students → 按批次 practice-worker → 每人
  get_student_profile → search_question_bank → PracticeResult

本模块提供批处理组织与 Worker prompt 模板;并行执行复用 DeerFlow task。
"""

from __future__ import annotations

# 三组默认层(参考文档 05 §2.5)
GROUPS = {
    "基础组": {"difficulty": "easy", "target": "补基础知识点"},
    "巩固组": {"difficulty": "medium", "target": "当前核心知识点"},
    "提升组": {"difficulty": "hard", "target": "综合应用"},
}


def assign_group(profile: dict) -> str:
    """按学生画像划分层次:基础组(整体低/多薄弱)/巩固组(中)/提升组(高)。

    简化规则(参考文档 05 §2.5 默认三档):
    - 有 ≥2 个 weak_point 或 avg_score_rate < 0.6 → 基础组
    - avg_score_rate >= 0.85 且 weak_point 少 → 提升组
    - 其余 → 巩固组
    """
    overview = profile.get("overview", {})
    weak_count = len(profile.get("weak_points", []))
    avg_rate = overview.get("avg_score_rate") or 0.0
    if weak_count >= 2 or avg_rate < 0.6:
        return "基础组"
    if avg_rate >= 0.85 and weak_count <= 1:
        return "提升组"
    return "巩固组"


def batch_students(student_ids: list[str], batch_size: int = 8) -> list[list[str]]:
    """全班个性化练习按批次切分(30-40 人班级默认每批 8 人)。"""
    return [student_ids[i : i + batch_size] for i in range(0, len(student_ids), batch_size)]


PRACTICE_WORKER_PROMPT = """你是分层与个性化练习设计子智能体,为分配的学生生成针对性练习。
学生: {student_ids}
学科: {subject}
要求:
1. 对每个学生 get_student_profile → 选择薄弱知识点
2. search_question_bank(知识点/难度/题型)→ 选题(只选题库 QuestionBankItem)
3. 按 PracticeResult 结构返回

PracticeResult 结构:
{{
  "target_students": ["..."],
  "knowledge_points": ["..."],
  "difficulty": "easy|medium|hard",
  "question_type": "calculation|solution",
  "selected_questions": [{{"question_bank_item_id": "...", "content": "..."}}]
}}"""


def build_group_configs(class_profile: dict) -> list[dict]:
    """按班级画像生成各组配置(三组,每组知识点从班级薄弱点选取)。"""
    weak_keys = [w["knowledge_point_key"] for w in class_profile.get("weak_points", [])]
    if not weak_keys:
        weak_keys = [kp["knowledge_point_key"] for kp in class_profile.get("knowledge_points", [])[:2]]
    configs = []
    for group, meta in GROUPS.items():
        configs.append({
            "group_name": group,
            "difficulty": meta["difficulty"],
            "target": meta["target"],
            "knowledge_points": weak_keys,
        })
    return configs
