"""ProfileAlgorithmV1 班级关注学生(attention_students)回归测试(007 T005)。

验证业务数据层不再对班级关注学生做 Top N 截断:命中规则的学生全部返回,
排序规则保持 reason_codes 数量 DESC → recent_score ASC。
纯函数测试,不连接数据库与外部服务。
"""

from __future__ import annotations

from app.teacher_copilot.services.profile_service import ProfileAlgorithmV1


def _profile(recent_score_rate: float | None, trend: str = "stable",
             weak_count: int = 0, recurring: bool = False) -> dict:
    """构造 _class_attention 需要的学生画像结构。"""
    return {
        "attempt_count": 3,
        "overview": {"recent_score_rate": recent_score_rate, "trend": trend},
        "weak": [
            {"knowledge_point_key": f"kp_{i}", "mastery": 0.3} for i in range(weak_count)
        ],
        "recurring": [{"error_code": "SIGN_ERROR"}] if recurring else [],
    }


def test_attention_students_returns_all_matches_without_truncation() -> None:
    """命中数超过 10 时必须返回全部,不做 Top10 截断。"""
    student_ids = [f"stu_{i:03d}" for i in range(15)]
    profiles = {sid: _profile(0.4) for sid in student_ids}  # 全部命中 LOW_RECENT_SCORE

    result = ProfileAlgorithmV1()._class_attention(student_ids, profiles, [])

    assert len(result) == 15
    assert {r["student_id"] for r in result} == set(student_ids)


def test_attention_students_keeps_sort_order() -> None:
    """排序保持 reason_codes 数量 DESC → recent_score ASC。"""
    student_ids = ["stu_001", "stu_002", "stu_003"]
    profiles = {
        "stu_001": _profile(0.4),                  # 1 个 reason
        "stu_002": _profile(0.4, recurring=True),  # 2 个 reason
        "stu_003": _profile(0.9),                  # 不命中任何规则
    }

    result = ProfileAlgorithmV1()._class_attention(student_ids, profiles, [])

    assert [r["student_id"] for r in result] == ["stu_002", "stu_001"]
