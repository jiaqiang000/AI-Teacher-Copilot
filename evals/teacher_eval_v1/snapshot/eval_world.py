"""评测世界数据:teacher_eval_v1(参考文档 08 §3.1/3.2)。

固定评测世界(不随运行时间变化):
- teacher_01 王老师 / class_03 八三班(30 名学生)
- 4 周作业 hw_001~hw_004、题库 Fixture(12 道数学题)
- 金标准批次:张三(stu_003)weak/recurring/declining,李四(stu_011)单次不升级
- Profile as_of 固定(2026-08-30),避免测试机当前日期影响时间窗口

本模块生成/校验评测世界;核心用例(gold facts)在 cases/*.jsonl。
"""

from __future__ import annotations

import json
from datetime import datetime

# 固定 as_of(参考文档 08 §3.1:profile_as_of=2026-08-30T00:00:00+08:00)
PROFILE_AS_OF = datetime(2026, 8, 30, 0, 0, 0).isoformat() + "+08:00"
ALGORITHM_VERSION = "profile_v1"

# 班级金标准(参考文档 08 §3.2 第一批 Gold Facts)
CLASS_GOLD = {
    "class_id": "class_03",
    "student_count": 30,
    "weak_points": ["math.linear_equation.transposition", "math.function.graph"],
    "common_errors": ["SIGN_ERROR", "GRAPH_READING_ERROR"],
    "weekly_attention_students": ["stu_003", "stu_011", "stu_018", "stu_024"],
}

# hw_004 金标准(参考文档 08 §3.2)
HW004_GOLD = {
    "homework_id": "hw_004",
    "assigned_student_count": 30,
    "submitted_student_count": 27,
    "completion_rate": 0.90,
    "top_error_question": {"question_id": "q008", "question_no": 8,
                           "attempt_count": 27, "error_student_count": 18,
                           "error_rate": 0.6667, "common_error": "SIGN_ERROR"},
}

# 学生金标准(张三 vs 李四的边界,单次错误不升级)
STUDENT_GOLD = {
    "stu_003": {
        "weak_point": True, "recurring_error": True, "trend": "declining",
        "transposition_attempt_count_min": 3, "mastery_below": 0.60,
    },
    "stu_011": {
        "weak_point": False, "recurring_error": False, "trend": "stable",
        "note": "单次 SIGN_ERROR 不升级 long-term(参考文档 08)",
    },
}


def load_snapshot(base_dir: str = "evals/teacher_eval_v1") -> dict:
    """加载评测世界数据(snapshot/ 下 JSON;缺失时返回金标准定义)。"""
    import os

    result = {
        "class_gold": CLASS_GOLD,
        "hw004_gold": HW004_GOLD,
        "student_gold": STUDENT_GOLD,
        "profile_as_of": PROFILE_AS_OF,
        "algorithm_version": ALGORITHM_VERSION,
    }
    # 从 snapshot 文件补充(如存在)
    snap_dir = os.path.join(base_dir, "snapshot")
    for fname in ["students.json", "homeworks.json", "questions.json",
                  "question_bank.json", "grading_results.json"]:
        path = os.path.join(snap_dir, fname)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                result[fname.replace(".json", "")] = json.load(fh)
    return result


def load_cases(base_dir: str = "evals/teacher_eval_v1") -> list[dict]:
    """加载全部评测用例(cases/*.jsonl)。

    读取逻辑统一走 evals.runtime.case_loader,避免与门禁侧实现漂移
    (此前两份实现只有一份跳过 `#` 注释行,导致 core_cases.jsonl 无法加载)。
    """
    import os

    from evals.runtime.case_loader import load_case_dir

    return load_case_dir(os.path.join(base_dir, "cases"))
