"""ProfileAlgorithmV1:学生/班级长期画像(唯一确定性算法,algorithm_version=profile_v1)。

依据 data-model.md §5.1 / 参考文档 03 §4.1:
- performance 映射 correct=1.0/partial=0.5/incorrect=0.0
- 时间窗口: recent=(as_of-14d, as_of];previous=(as_of-28d, as_of-14d];错误窗口 28d
- 权重: 时间(≤14d=1.0/15-28d=0.8/>28d=0.6)× 难度(easy=0.8/medium=1.0/hard=1.2/english=1.0)
- mastery = Σ(p_i×w_i)/Σ(w_i);weak_point 需 attempt_count≥3 且 mastery<0.60
- recurring_error = 同一 (error_code, kp) 28d 内 ≥2 次
- trend: recent−previous 差值 ±0.10,各窗口观察<2 → null
- 输出 round 到 4 位小数;无数据 → null(不写 0)
- Class Profile 从 MySQL 事实直接计算,不以 Redis Student Profile 为事实源
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.teacher_copilot.db.models.grading import GradingResult, Submission
from app.teacher_copilot.db.models.org import ClassRoom
from app.teacher_copilot.errors import ClassNotFound
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error

PERF_MAP = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}

# 时间权重(相对 as_of 的天数)
TIME_WEIGHTS = [(14, 1.0), (28, 0.8)]  # (天数上限, 权重);>28 天 0.6
# 难度权重
DIFF_WEIGHTS = {"easy": 0.8, "medium": 1.0, "hard": 1.2, None: 1.0}

TREND_THRESHOLD = 0.10
WEAK_POINT_MASTERY = 0.60
WEAK_POINT_MIN_ATTEMPTS = 3
RECURRING_DAYS = 28
RECENT_DAYS = 14
CLASS_WEAK_PARTICIPANT = 3


def _time_weight(days_ago: int) -> float:
    """时间权重:≤14d=1.0,15-28d=0.8,>28d=0.6。"""
    if days_ago <= 14:
        return 1.0
    if days_ago <= 28:
        return 0.8
    return 0.6


def _rnd(v: float | None) -> float | None:
    return round(v, 4) if v is not None else None


class ProfileAlgorithmV1(BaseRepository):
    """学生/班级长期画像计算(参考文档 03 §4.1)。"""

    # ---------- 数据层 ----------
    async def _valid_results(self, student_id: str | None = None, class_id: str | None = None,
                             subject: str | None = None) -> list[dict]:
        """读取当前有效成功结果(可限定学生/班级),供画像计算。"""
        try:
            from sqlalchemy.orm import selectinload

            stmt = (
                select(Submission, GradingResult)
                .join(GradingResult, GradingResult.submission_id == Submission.submission_id)
                .options(
                    selectinload(GradingResult._kp_rows),
                    selectinload(GradingResult._error_rows),
                )
            )
            if student_id:
                stmt = stmt.where(Submission.student_id == student_id)
            if subject:
                stmt = stmt.where(Submission.homework_id.in_(
                    select(Submission.homework_id).where(Submission.subject == subject)
                ))
            rows = await self.session.execute(stmt)
            out = []
            for sub, gr in rows:
                # 学科由题目决定;这里通过 homework.subject 关联(简化:用 GradingResult.subject)
                out.append({
                    "student_id": sub.student_id,
                    "subject": gr.subject,
                    "difficulty": gr.difficulty,
                    "score_rate": gr.score_rate,
                    "created_at": gr.created_at,
                    "kps": gr._kp_rows,
                    "errors": gr._error_rows,
                })
            return out
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc

    # ---------- 学生画像 ----------
    async def compute_student(self, student_id: str, subject: str,
                              as_of: datetime | None = None) -> dict:
        """计算学生画像(StudentProfile)。as_of 缺省用当前时间。"""
        as_of = as_of or datetime.utcnow()
        results = [r for r in await self._valid_results(student_id=student_id)
                   if r["subject"] == subject]
        # 整体表现
        overview = self._student_overview(results, as_of)
        # 知识点画像
        kp_stats = self._student_kp(results, as_of, subject)
        weak = self._student_weak(kp_stats)
        recurring = self._student_recurring(results, as_of)
        difficulty = self._student_difficulty(results, as_of, subject)

        # knowledge_points 的 common_error_codes 与 recurring_errors
        for kp in kp_stats:
            kp["common_error_codes"] = self._kp_common_errors(results, kp["knowledge_point_key"])

        return {
            "basic": {
                "student_id": student_id, "subject": subject,
                "generated_at": as_of.isoformat(), "source_data_until": as_of.isoformat(),
                "algorithm_version": "profile_v1",
            },
            "overview": overview,
            "knowledge_points": kp_stats,
            "weak_points": weak,
            "recurring_errors": recurring,
            "difficulty_performance": difficulty,
        }

    def _student_overview(self, results: list[dict], as_of: datetime) -> dict:
        """整体表现:attempt_count/avg_score_rate/recent_score_rate/trend。"""
        recent = [r for r in results if _in_window(r["created_at"], as_of, RECENT_DAYS)]
        prev = [r for r in results if _in_window(r["created_at"], as_of, RECENT_DAYS, 2 * RECENT_DAYS)]
        avg = _rnd(sum(r["score_rate"] for r in results) / len(results)) if results else None
        recent_rate = _rnd(sum(r["score_rate"] for r in recent) / len(recent)) if recent else None
        trend = _trend([r["score_rate"] for r in recent], [r["score_rate"] for r in prev])
        return {
            "attempt_count": len(results),
            "avg_score_rate": avg, "recent_score_rate": recent_rate,
            "trend": trend,
        }

    def _student_kp(self, results: list[dict], as_of: datetime, subject: str) -> list[dict]:
        """知识点画像:mastery/recent/trend/last_practiced。"""
        # 每 kp_key: [(p_i, w_i, created_at)]
        per_kp: dict[str, list] = {}
        for r in results:
            for kp in r["kps"]:
                perf = PERF_MAP.get(kp.performance)
                if perf is None:
                    continue
                days = (as_of - r["created_at"]).days
                diff_w = DIFF_WEIGHTS.get(r["difficulty"], 1.0)
                w = _time_weight(days) * diff_w
                per_kp.setdefault(kp.knowledge_point_key, []).append((perf, w, r["created_at"]))

        out = []
        for kp_key, items in per_kp.items():
            mastery = sum(p * w for p, w, _ in items) / sum(w for _, w, _ in items) if items else None
            recent = [p for p, w, t in items if _in_window(t, as_of, RECENT_DAYS)]
            prev = [p for p, w, t in items if _in_window(t, as_of, RECENT_DAYS, 2 * RECENT_DAYS)]
            out.append({
                "knowledge_point_key": kp_key,
                "attempt_count": len(items),
                "mastery": _rnd(mastery),
                "recent_performance": _rnd(sum(recent) / len(recent)) if recent else None,
                "trend": _trend(recent, prev),
                "last_practiced_at": max(t for _, _, t in items).isoformat(),
                "common_error_codes": [],
            })
        # 按 mastery 排序(低在前,便于展示薄弱)
        out.sort(key=lambda x: x["mastery"] if x["mastery"] is not None else 2)
        return out

    def _student_weak(self, kp_stats: list[dict]) -> list[dict]:
        """薄弱知识点:attempt_count≥3 且 mastery<0.60。"""
        weak = []
        for kp in kp_stats:
            if kp["attempt_count"] >= WEAK_POINT_MIN_ATTEMPTS and kp["mastery"] is not None and kp["mastery"] < WEAK_POINT_MASTERY:
                weak.append({
                    "knowledge_point_key": kp["knowledge_point_key"],
                    "mastery": kp["mastery"], "trend": kp["trend"],
                    "evidence_count": kp["attempt_count"],
                })
        weak.sort(key=lambda x: (x["mastery"], -x["evidence_count"], x["knowledge_point_key"]))
        return weak

    def _student_recurring(self, results: list[dict], as_of: datetime) -> list[dict]:
        """重复错误:同一 (error_code, kp) 28 天内 ≥2 次。"""
        pair_count: dict[tuple, dict] = {}
        for r in results:
            for e in r["errors"]:
                key = (e.error_code, e.knowledge_point_key)
                item = pair_count.setdefault(key, {"error_code": e.error_code,
                                                   "knowledge_point_key": e.knowledge_point_key,
                                                   "occurrence_count": 0,
                                                   "recent_occurrence_count": 0,
                                                   "last_occurred_at": None})
                item["occurrence_count"] += 1
                if _in_window(r["created_at"], as_of, RECURRING_DAYS):
                    item["recent_occurrence_count"] += 1
                if item["last_occurred_at"] is None or r["created_at"] > item["last_occurred_at"]:
                    item["last_occurred_at"] = r["created_at"]
        recur = []
        for item in pair_count.values():
            if item["recent_occurrence_count"] >= 2:
                recur.append({**{k: v for k, v in item.items() if k != "recent_occurrence_count"},
                              "recent_occurrence_count": item["recent_occurrence_count"],
                              "last_occurred_at": item["last_occurred_at"].isoformat() if item["last_occurred_at"] else None})
        recur.sort(key=lambda x: (-x["occurrence_count"], x["error_code"]))
        return recur

    def _kp_common_errors(self, results: list[dict], kp_key: str) -> list[str]:
        """某知识点关联的常见错误:历史 occurrence_count≥2,最多 3 个。"""
        counter: dict[str, int] = {}
        for r in results:
            for e in r["errors"]:
                if e.knowledge_point_key == kp_key:
                    counter[e.error_code] = counter.get(e.error_code, 0) + 1
        codes = [c for c, n in counter.items() if n >= 2]
        codes.sort(key=lambda c: (-counter[c], c))
        return codes[:3]

    def _student_difficulty(self, results: list[dict], as_of: datetime, subject: str) -> dict | None:
        """不同难度表现(仅数学;英语 null)。"""
        if subject != "math":
            return None
        out = {}
        for diff in ("easy", "medium", "hard"):
            items = [r for r in results if r["difficulty"] == diff]
            recent = [r for r in items if _in_window(r["created_at"], as_of, RECENT_DAYS)]
            out[diff] = {
                "attempt_count": len(items),
                "avg_score_rate": _rnd(sum(r["score_rate"] for r in items) / len(items)) if items else None,
                "recent_score_rate": _rnd(sum(r["score_rate"] for r in recent) / len(recent)) if recent else None,
            }
        return out

    # ---------- 班级画像 ----------
    async def compute_class(self, class_id: str, subject: str,
                            as_of: datetime | None = None) -> dict:
        """班级画像(ClassProfile):直接从 MySQL 事实聚合,不以 Student Redis 为源。"""
        as_of = as_of or datetime.utcnow()
        # 班级成员
        from app.teacher_copilot.db.models.org import ClassStudent

        try:
            class_room = await self.session.scalar(
                select(ClassRoom).where(ClassRoom.class_id == class_id)
            )
            student_ids = list(await self.session.scalars(
                select(ClassStudent.student_id).where(ClassStudent.class_id == class_id)
            ))
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc
        if class_room is None:
            raise ClassNotFound(f"班级 {class_id} 不存在")

        # 全班当前有效成功结果(按学生分组)
        all_results = [r for r in await self._valid_results() if r["subject"] == subject]
        by_student: dict[str, list[dict]] = {sid: [] for sid in student_ids}
        for r in all_results:
            if r["student_id"] in by_student:
                by_student[r["student_id"]].append(r)

        # 每学生先算个人画像(内存中同公式,避免重复 SQL)
        student_profiles = {
            sid: self._student_summary(results, as_of, subject)
            for sid, results in by_student.items()
        }

        overview = self._class_overview(student_ids, student_profiles, all_results, as_of)
        kp_stats = self._class_kp(student_profiles, as_of)
        weak = self._class_weak(kp_stats, student_profiles)
        common_errs = self._class_common_errors(by_student)
        attention = self._class_attention(student_ids, student_profiles, weak)

        return {
            "basic": {
                "class_id": class_id, "class_name": class_room.name, "subject": subject,
                "generated_at": as_of.isoformat(), "source_data_until": as_of.isoformat(),
                "algorithm_version": "profile_v1",
            },
            "overview": overview,
            "knowledge_points": kp_stats,
            "weak_points": weak,
            "common_errors": common_errs,
            "attention_students": attention,
        }

    def _student_summary(self, results: list[dict], as_of: datetime, subject: str) -> dict:
        """每学生个人画像摘要(用于班级聚合,与学生画像同一公式)。"""
        overview = self._student_overview(results, as_of)
        kp_stats = self._student_kp(results, as_of, subject)
        weak = self._student_weak(kp_stats)
        recurring = self._student_recurring(results, as_of)
        return {"overview": overview, "kp": kp_stats, "weak": weak, "recurring": recurring,
                "attempt_count": len(results)}

    def _class_overview(self, student_ids, profiles: dict, all_results: list[dict], as_of) -> dict:
        """班级整体:学生数、得分率和趋势,均从当前班级事实计算。"""
        active = [sid for sid in student_ids if profiles[sid]["attempt_count"] > 0]
        rates = [profiles[sid]["overview"]["avg_score_rate"] for sid in active
                 if profiles[sid]["overview"]["avg_score_rate"] is not None]
        recent_rates = [profiles[sid]["overview"]["recent_score_rate"] for sid in active
                        if profiles[sid]["overview"]["recent_score_rate"] is not None]
        class_student_ids = set(student_ids)
        class_results = [
            result for result in all_results
            if result["student_id"] in class_student_ids
        ]
        recent_values = [
            result["score_rate"] for result in class_results
            if _in_window(result["created_at"], as_of, RECENT_DAYS)
        ]
        previous_values = [
            result["score_rate"] for result in class_results
            if _in_window(result["created_at"], as_of, RECENT_DAYS, 2 * RECENT_DAYS)
        ]
        return {
            "student_count": len(student_ids),
            "active_student_count": len(active),
            "avg_score_rate": _rnd(sum(rates) / len(rates)) if rates else None,
            "recent_score_rate": _rnd(sum(recent_rates) / len(recent_rates)) if recent_rates else None,
            "trend": _trend(recent_values, previous_values),
        }

    def _class_kp(self, profiles: dict, as_of) -> list[dict]:
        """班级知识点:participating/attempt/avg_mastery/recent/weak_student 数。"""
        kp_groups: dict[str, dict] = {}
        for sid, prof in profiles.items():
            for kp in prof["kp"]:
                g = kp_groups.setdefault(kp["knowledge_point_key"], {
                    "participating_student_count": 0, "attempt_count": 0,
                    "masteries": [], "recent_performances": [],
                    "weak_student_count": 0,
                })
                g["participating_student_count"] += 1
                g["attempt_count"] += kp["attempt_count"]
                if kp["mastery"] is not None:
                    g["masteries"].append(kp["mastery"])
                if kp["recent_performance"] is not None:
                    g["recent_performances"].append(kp["recent_performance"])
                # weak_student_count:该学生在知识点上满足个人 weak_point(这里简化为 mastery<0.60)
                if kp["mastery"] is not None and kp["mastery"] < WEAK_POINT_MASTERY:
                    g["weak_student_count"] += 1
        out = []
        for kp_key, g in kp_groups.items():
            out.append({
                "knowledge_point_key": kp_key,
                "participating_student_count": g["participating_student_count"],
                "attempt_count": g["attempt_count"],
                "avg_mastery": _rnd(sum(g["masteries"]) / len(g["masteries"])) if g["masteries"] else None,
                "recent_performance": _rnd(sum(g["recent_performances"]) / len(g["recent_performances"])) if g["recent_performances"] else None,
                "weak_student_count": g["weak_student_count"],
                "trend": None,
                "common_error_codes": [],
            })
        out.sort(key=lambda x: x["avg_mastery"] if x["avg_mastery"] is not None else 2)
        return out

    def _class_weak(self, kp_stats: list[dict], profiles: dict) -> list[dict]:
        """班级薄弱知识点:participating≥3 且(avg<0.60 或 weak 占比≥0.30)。"""
        weak = []
        for kp in kp_stats:
            if kp["participating_student_count"] < CLASS_WEAK_PARTICIPANT:
                continue
            if kp["avg_mastery"] is None:
                continue
            if kp["avg_mastery"] < WEAK_POINT_MASTERY or (
                kp["weak_student_count"] / kp["participating_student_count"] >= 0.30
            ):
                weak.append({
                    "knowledge_point_key": kp["knowledge_point_key"],
                    "avg_mastery": kp["avg_mastery"],
                    "weak_student_count": kp["weak_student_count"],
                    "trend": None,
                })
        weak.sort(key=lambda x: x["avg_mastery"] if x["avg_mastery"] is not None else 2)
        return weak

    def _class_common_errors(self, by_student: dict) -> list[dict]:
        """班级常见错误:按 (error_code, kp) 聚合。"""
        pair: dict[tuple, dict] = {}
        for sid, results in by_student.items():
            for r in results:
                for e in r["errors"]:
                    key = (e.error_code, e.knowledge_point_key)
                    item = pair.setdefault(key, {"error_code": e.error_code,
                                                 "knowledge_point_key": e.knowledge_point_key,
                                                 "occurrence_count": 0, "affected_student_count": 0,
                                                 "_students": set()})
                    item["occurrence_count"] += 1
                    item["_students"].add(sid)
        out = []
        for item in pair.values():
            item["affected_student_count"] = len(item["_students"])
            item.pop("_students")
            out.append(item)
        out.sort(key=lambda x: (-x["affected_student_count"], -x["occurrence_count"],
                                x["error_code"], x["knowledge_point_key"]))
        return out[:5]

    def _class_attention(self, student_ids, profiles: dict, class_weak: list[dict]) -> list[dict]:
        """班级重点关注学生:命中任一原因(LOW_RECENT_SCORE/DECLINING_TREND/MULTIPLE_WEAK_POINTS/RECURRING_ERROR)。

        参考文档 03 §4.1.11:最多 Top10,排序 reason 数量 DESC → recent_score ASC。
        """
        weak_keys = {w["knowledge_point_key"] for w in class_weak}
        cands = []
        for sid in student_ids:
            prof = profiles[sid]
            if prof["attempt_count"] == 0:
                continue
            reasons = []
            rec = prof["overview"]["recent_score_rate"]
            if rec is not None and rec < WEAK_POINT_MASTERY:
                reasons.append("LOW_RECENT_SCORE")
            if prof["overview"]["trend"] == "declining":
                reasons.append("DECLINING_TREND")
            weak_count = len([w for w in prof["weak"] if w["knowledge_point_key"] in weak_keys or w["mastery"] < WEAK_POINT_MASTERY])
            if weak_count >= 2:
                reasons.append("MULTIPLE_WEAK_POINTS")
            if prof["recurring"]:
                reasons.append("RECURRING_ERROR")
            if reasons:
                cands.append({
                    "student_id": sid, "weak_point_count": len(prof["weak"]),
                    "recent_score_rate": rec, "trend": prof["overview"]["trend"],
                    "reason_codes": list(set(reasons)),
                })
        cands.sort(key=lambda x: (-len(x["reason_codes"]),
                                  (x["recent_score_rate"] if x["recent_score_rate"] is not None else 10),
                                  -x["weak_point_count"], x["student_id"]))
        return cands[:10]


# ---------- 工具函数 ----------
def _in_window(created_at: datetime, as_of: datetime, days: int,
               offset_days: int | None = None) -> bool:
    """判断 created_at 是否在 as_of 前的 [offset, offset+days] 窗口内。

    默认(offset None):最近 days 天。offset 用于 previous 窗口(如 RECENT_DAYS 偏移)。
    """
    if created_at is None:
        return False
    lower = as_of - timedelta(days=days)
    if offset_days is not None:
        lower = as_of - timedelta(days=offset_days)
        upper = as_of - timedelta(days=offset_days - days)
        return lower < created_at <= upper
    return lower < created_at <= as_of


def _trend(recent_values: list[float], previous_values: list[float]) -> str | None:
    """趋势:各窗口观察<2 → null;±0.10 阈值判断。"""
    if len(recent_values) < 2 or len(previous_values) < 2:
        return None
    delta = sum(recent_values) / len(recent_values) - sum(previous_values) / len(previous_values)
    if delta >= TREND_THRESHOLD:
        return "improving"
    if delta <= -TREND_THRESHOLD:
        return "declining"
    return "stable"
