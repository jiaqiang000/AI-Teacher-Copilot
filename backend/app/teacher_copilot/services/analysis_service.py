"""AnalysisCalculationV1:作业/题目即时聚合(唯一确定性规则)。

依据 data-model.md §5.2 / 参考文档 03 §3.8:
- 仅统计 SUCCEEDED 且当前 GradingResult 仍存在的有效事实(通过 Submission 关联)
- performance 映射 correct=1.0/partial=0.5/incorrect=0.0
- fully graded = 作业内每道题都有该学生当前有效成功结果
- 空值用 null(不用 0);数值 round 到 4 位小数;阈值用未舍入原值
- common_errors 按 (error_code, knowledge_point_key) 精确二元组聚合

本模块只读计算,不改业务事实(宪法 III/VI:与参考设计一致)。
"""

from __future__ import annotations

from sqlalchemy import select

from app.teacher_copilot.db.models.grading import (
    GradingResult,
    GradingResultError,
    GradingResultKnowledgePoint,
    Submission,
)
from app.teacher_copilot.db.models.homework import Question
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error

PERF_MAP = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}


def _rnd(v: float | None) -> float | None:
    """输出精度:4 位小数(阈值判断必须用未舍入值)。"""
    return round(v, 4) if v is not None else None


class AnalysisCalculationV1(BaseRepository):
    """作业/题目确定性即时分析计算器(参考文档 03 §3.8)。"""

    async def _valid_results(self, homework_id: str) -> list[dict]:
        """读取某作业所有当前有效成功结果(join Submission 取 student/question)。"""
        try:
            from sqlalchemy.orm import selectinload

            rows = await self.session.execute(
                select(Submission, GradingResult)
                .join(GradingResult, GradingResult.submission_id == Submission.submission_id)
                .where(Submission.homework_id == homework_id)
                .options(
                    selectinload(GradingResult._kp_rows),
                    selectinload(GradingResult._error_rows),
                )
            )
            out = []
            for sub, gr in rows:
                out.append({
                    "student_id": sub.student_id,
                    "question_id": sub.question_id,
                    "status": sub.status,
                    "score_rate": gr.score_rate,
                    "_earned": gr.score_earned,
                    "_max": gr.score_max,
                    "kps": gr._kp_rows,
                    "errors": gr._error_rows,
                })
            return out
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc

    async def _question_stat(self, question: Question, question_results: list[dict]) -> dict:
        """单题基础统计(参考文档 03 §3.8.2/3.8.8)。"""
        attempts = len(question_results)
        avg = round(sum(r["score_rate"] for r in question_results) / attempts, 4) if attempts else None
        error_students = {r["student_id"] for r in question_results if r["errors"]}
        error_rate = round(len(error_students) / attempts, 4) if attempts else None

        # 常见错误:按 (error_code, knowledge_point_key) 聚合 -> Top3
        err_counter: dict[tuple, dict] = {}
        for r in question_results:
            for e in r["errors"]:
                key = (e.error_code, e.knowledge_point_key)
                item = err_counter.setdefault(key, {
                    "error_code": e.error_code, "knowledge_point_key": e.knowledge_point_key,
                    "occurrence_count": 0, "affected_student_count": 0, "_students": set(),
                })
                item["occurrence_count"] += 1
                item["_students"].add(r["student_id"])
        common = []
        for item in err_counter.values():
            item["affected_student_count"] = len(item["_students"])
            item.pop("_students")
            common.append(item)
        common.sort(key=lambda x: (-x["affected_student_count"], -x["occurrence_count"],
                                   x["error_code"], x["knowledge_point_key"]))
        return {
            "question_id": question.question_id, "question_no": question.question_no,
            "attempt_count": attempts, "avg_score_rate": avg,
            "error_student_count": len(error_students), "error_rate": error_rate,
            "common_errors": common[:3],
        }

    async def compute_homework_analysis(self, homework_id: str, class_id: str) -> dict:
        """计算作业分析(HomeworkAnalysis)。"""
        try:
            questions = list(await self.session.scalars(
                select(Question).where(Question.homework_id == homework_id)
                .order_by(Question.question_no)
            ))
            results = await self._valid_results(homework_id)
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc

        q_stats = []
        for q in questions:
            q_results = [r for r in results if r["question_id"] == q.question_id]
            q_stats.append(await self._question_stat(q, q_results))

        completion = await self._compute_completion(class_id, homework_id, questions, results)
        perf = self._compute_performance(questions, results)
        kp_stats = self._compute_kp(questions, results)
        attention = self._compute_attention(questions, results, q_stats)
        return {
            "homework_id": homework_id, "class_id": class_id,
            "completion": completion, "performance": perf,
            "knowledge_points": kp_stats, "questions": q_stats,
            "attention_students": attention,
        }

    # ---- completion ----
    async def _compute_completion(self, class_id, homework_id, questions, results) -> dict:
        """完成情况:assigned/submitted/completion_rate。"""
        from app.teacher_copilot.db.models.org import ClassStudent

        try:
            assigned = list(await self.session.scalars(
                select(ClassStudent.student_id).where(ClassStudent.class_id == class_id)
            ))
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        submitted = {r["student_id"] for r in results}
        rate = round(len(submitted & set(assigned)) / len(assigned), 4) if assigned else None
        return {
            "assigned_student_count": len(assigned),
            "submitted_student_count": len(submitted),
            "completion_rate": rate,
        }

    # ---- performance ----
    def _compute_performance(self, questions, results) -> dict:
        """成绩表现:fully graded 学生数、平均得分率、成绩分布。"""
        qids = [q.question_id for q in questions]
        if not qids:
            return {"graded_student_count": 0, "avg_score_rate": None, "score_distribution": None}
        # 每学生每题的完成度
        student_done: dict[str, set] = {}
        for r in results:
            student_done.setdefault(r["student_id"], set()).add(r["question_id"])
        fully = [sid for sid, done in student_done.items() if qids and all(qid in done for qid in qids)]
        rates = []
        for sid in fully:
            earned = sum(
                r["_earned"] for r in results if r["student_id"] == sid
            )
            max_score = sum(
                r["_max"] for r in results if r["student_id"] == sid
            )
            rates.append(earned / max_score if max_score else 0)
        avg = round(sum(rates) / len(rates), 4) if rates else None
        dist = {
            "below_60": sum(1 for x in rates if x < 0.60),
            "from_60_to_79": sum(1 for x in rates if 0.60 <= x < 0.80),
            "from_80_to_89": sum(1 for x in rates if 0.80 <= x < 0.90),
            "from_90_to_100": sum(1 for x in rates if 0.90 <= x <= 1.00),
        }
        return {"graded_student_count": len(fully), "avg_score_rate": avg, "score_distribution": dist}

    # ---- knowledge points ----
    def _compute_kp(self, questions, results) -> list[dict]:
        """知识点表现(参考文档 03 §3.8.5):每学生-作业-知识点聚合后平均。"""
        # student_id + kp_key -> [performance数值]
        stu_kp: dict[tuple, list[float]] = {}
        for r in results:
            for kp in r["kps"]:
                perf = PERF_MAP.get(kp.performance)
                if perf is None:
                    continue
                stu_kp.setdefault((r["student_id"], kp.knowledge_point_key), []).append(perf)
        # 每学生-知识点均值 -> 再按知识点聚合
        kp_groups: dict[str, list[float]] = {}
        for (sid, kp_key), vals in stu_kp.items():
            kp_groups.setdefault(kp_key, []).append(sum(vals) / len(vals))
        out = []
        for kp_key, vals in kp_groups.items():
            out.append({
                "knowledge_point_key": kp_key,
                "participating_student_count": len(vals),
                "avg_performance": round(sum(vals) / len(vals), 4),
                "low_performance_student_count": sum(1 for v in vals if v < 0.60),
            })
        out.sort(key=lambda x: x["avg_performance"] if x["avg_performance"] is not None else 2)
        return out

    # ---- attention ----
    def _compute_attention(self, questions, results, q_stats) -> list[dict]:
        """本次即时异常候选(LOW_HOMEWORK_SCORE / HIGH_ERROR_QUESTION)。

        参考文档 03 §3.8.10:仅表示本次作业即时异常,≠ 长期 weak_point。
        """
        qids = [q.question_id for q in questions]
        high_error_qids = {qs["question_id"] for qs in q_stats if qs["error_rate"] is not None and qs["error_rate"] >= 0.50}
        student_done: dict[str, set] = {}
        for r in results:
            student_done.setdefault(r["student_id"], set()).add(r["question_id"])
        fully = [sid for sid, done in student_done.items() if qids and all(qid in done for qid in qids)]

        students = []
        for sid in fully:
            reasons, related = [], []
            # LOW_HOMEWORK_SCORE
            rates = []
            for r in results:
                if r["student_id"] == sid:
                    earned = sum(
                        r["_earned"] for r in results if r["student_id"] == sid
                    )
                    max_score = sum(
                        r["_max"] for r in results if r["student_id"] == sid
                    )
                    rates.append(earned / max_score if max_score else 0)
            hw_rate = round(sum(rates) / len(rates), 4) if rates else None
            if hw_rate is not None and hw_rate < 0.60:
                reasons.append("LOW_HOMEWORK_SCORE")
            # HIGH_ERROR_QUESTION
            for r in results:
                if r["student_id"] == sid and r["question_id"] in high_error_qids and r["errors"]:
                    if "HIGH_ERROR_QUESTION" not in reasons:
                        reasons.append("HIGH_ERROR_QUESTION")
                    if r["question_id"] not in related:
                        related.append(r["question_id"])
            if reasons:
                students.append({
                    "student_id": sid, "homework_score_rate": hw_rate,
                    "reason_codes": reasons, "related_question_ids": related,
                })
        # 排序:reason 数量 DESC → homework_score_rate ASC(null 最后)→ student_id ASC
        students.sort(key=lambda x: (-len(x["reason_codes"]),
                                     (x["homework_score_rate"] if x["homework_score_rate"] is not None else 10),
                                     x["student_id"]))
        return students
