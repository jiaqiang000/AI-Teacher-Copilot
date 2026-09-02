"""班级周度学情复盘流程(参考文档 06-07 §9,US6)。

流程由 Teacher Lead Agent 按 Skill 编排执行,本模块提供:
- 周度复盘的结构化执行顺序与判断要点(供 SOUL/SKILL 引用)
- Diagnosis Worker 的任务 prompt 模板与结构化结果 StudentDiagnosisResult
- fan-out 批次组织建议(先筛选重点学生再并行,避免全班 30 人全部委派)

说明:实际并行委派复用 DeerFlow task 工具(Sub-Agent Runtime);
本模块不自行实现 asyncio.gather/WorkerPool(宪法 V 不过度设计)。
"""

from __future__ import annotations


# --- 周度复盘执行要点(供 Agent 编排时遵循) ---
WEEKLY_REVIEW_SOP = """班级周度学情复盘执行步骤:
1. list_class_homeworks(class_id, subject, 本周时间范围) → 发现本周 homework_id 列表
2. 逐份 get_homework_analysis + get_class_profile → 获得:
   - ClassProfile.attention_students(长期重点)
   - 各 HomeworkAnalysis.attention_students(本周即时异常)
3. 综合长期 + 本周多份作业异常一致性/严重程度 → weekly_attention_students(周度重点学生)
   - 不得把 HomeworkAnalysis.attention_students 直接等同 weekly_attention_students
   - 不得一开始对全班 30 人全部委派 diagnosis-worker
4. 对重点学生按批次(如每批 4 人)并行 task(subagent_type="diagnosis-worker")
5. Fan-in:汇总各 Worker 的 StudentDiagnosisResult,形成班级主要问题与教学重点
"""


# --- Diagnosis Worker task prompt 模板 ---
DIAGNOSIS_WORKER_PROMPT = """你是学习诊断子智能体。请对分配给你的学生执行深入学习诊断:
学生: {student_ids}
学科: {subject}
要求:
1. 对每个学生 get_student_profile(必要时 get_student_grading_history 举证)
2. 识别薄弱知识点、重复错误、趋势与历史证据
3. 严格按 StudentDiagnosisResult 结构返回(结构化,不要整段自然语言)

StudentDiagnosisResult 结构:
{{
  "student_id": "...",
  "weak_knowledge_points": [{{"key": "...", "mastery": 0.0}}],
  "recurring_errors": [{{"error_code": "...", "knowledge_point_key": "..."}}],
  "trend": "declining|stable|improving|null",
  "diagnosis_type": "persistent_weak|recent_decline|transient|stable",
  "evidence_summary": "..."
}}"""


# --- 批次组织建议 ---
def batch_students(student_ids: list[str], batch_size: int = 4) -> list[list[str]]:
    """把重点学生按批次切分(默认每批 4 人,避免一人一 Agent 的过度开销)。"""
    return [student_ids[i : i + batch_size] for i in range(0, len(student_ids), batch_size)]
