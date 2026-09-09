"""班级周度学情复盘流程(参考文档 06-07 §9)。

流程由 Teacher Lead Agent 按 Skill 编排执行,本模块提供:
- 周度复盘的结构化执行顺序与判断要点(供 SOUL/SKILL 引用)
- Diagnosis Worker 的任务 prompt 模板与结构化结果 StudentDiagnosisResult

关键边界(参考文档 06-07 §9.2):
- 全班第一轮 Screening 由 ProfileAlgorithmV1 / AnalysisCalculationV1 的确定性结果完成,
  不使用 Sub-Agent 判断"谁可能有问题"。
- 教师只要求整体复盘时,Lead Agent 完成 Screening 与周度总结即结束,不委派 Sub-Agent。
- 仅当已明确存在多个需要 Deep Diagnosis 的 student_id,才升级 Diagnosis Workers。
- 不规定固定 Worker 数量或固定批次;分配多少 student_id 属于运行时调度,不是业务规则。

说明:实际并行委派复用 DeerFlow task 工具(Sub-Agent Runtime);
本模块不自行实现 asyncio.gather/WorkerPool(宪法 V 不过度设计)。
"""

from __future__ import annotations


# --- 周度复盘执行要点(供 Agent 编排时遵循) ---
WEEKLY_REVIEW_SOP = """班级周度学情复盘执行步骤:
1. list_class_homeworks(class_id, subject, 本周时间范围) → 发现本周 homework_id 列表
2. 逐份 get_homework_analysis + get_class_profile → 获得:
   - ClassProfile.attention_students(长期关注)
   - 各 HomeworkAnalysis.attention_students(本周即时异常)
   两者均已由 ProfileAlgorithmV1 / AnalysisCalculationV1 基于全班数据确定性计算,
   无需 Sub-Agent 对全班逐个学生做第一轮诊断。
3. Lead Agent 综合长期状态 + 本周多份作业信号,判断本轮真正需要 Deep Diagnosis 的学生
   → weekly_attention_students(周度业务判断)
   - 不得把 HomeworkAnalysis.attention_students 直接等同 weekly_attention_students
   - 不得一开始对全班学生全部委派 diagnosis-worker
   - 不重新计算或覆盖算法层的阈值与字段语义
4. 教师只要求整体复盘时,到此形成班级周度总结,不启动 Diagnosis Worker。
5. 教师要求对持续异常学生分别深诊(或直接指定多个学生)时,才
   task(subagent_type="diagnosis-worker");一个 Worker 可接收一个或多个 student_id,
   但必须逐个执行 student-diagnosis SOP 并分别返回独立的 StudentDiagnosisResult。
6. Fan-in:汇总各 Worker 的 StudentDiagnosisResult,形成班级主要问题与教学重点。
"""


# --- Diagnosis Worker task prompt 模板 ---
DIAGNOSIS_WORKER_PROMPT = """你是学习诊断子智能体。请对分配给你的学生执行深度学习诊断:
学生: {student_ids}
学科: {subject}
要求:
1. 严格逐个处理 student_id:完成一个学生并形成该学生独立的 StudentDiagnosisResult 后,
   再处理下一个学生
2. 对每个学生 get_student_profile(必要时 get_student_grading_history 举证)
3. 识别薄弱知识点、重复错误、趋势与历史证据
4. 严格按 StudentDiagnosisResult 结构返回(结构化,不要整段自然语言)
5. 不得把多个学生的 Profile / History / 诊断结论混在一起

StudentDiagnosisResult 结构:
{{
  "student_id": "...",
  "weak_knowledge_points": [{{"key": "...", "mastery": 0.0}}],
  "recurring_errors": [{{"error_code": "...", "knowledge_point_key": "..."}}],
  "trend": "declining|stable|improving|null",
  "diagnosis_type": "persistent_weak|recent_decline|transient|stable",
  "evidence_summary": "..."
}}"""
