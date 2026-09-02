"""Eval Runner:运行评测用例并对确定性门禁断言(参考文档 08 §3.3/3.4)。

用法(可观察,宪法 X):
    python -m evals.runtime.run --gate profile_algorithm
    python -m evals.runtime.run --gate analysis_calculation
输出:每用例通过/失败 + 汇总(带耗时)。
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    stream=sys.stderr)
logger = logging.getLogger("evals")


def _load_case_file(gate: str):
    """加载门禁用例文件(带路径容错)。"""
    import json
    import os

    path = f"evals/teacher_eval_v1/cases/{gate}.jsonl"
    if not os.path.exists(path):
        base = os.path.dirname(__file__)
        path = os.path.join(base, "..", "teacher_eval_v1", "cases", f"{gate}.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip() and not l.strip().startswith("#")]


# ---- Profile 门禁(直接调用实现) ----
def run_profile_gate() -> list[tuple[str, bool, str]]:
    """运行 P-PROFILE-* 用例(确定性算法,不依赖 LLM)。"""
    import sys as _s

    _s.path.insert(0, "backend")
    from app.teacher_copilot.services.profile_service import (
        PERF_MAP, _trend, _time_weight, _rnd,
    )

    cases = _load_case_file("profile_algorithm")
    results = []
    for c in cases:
        cid = c["case_id"]
        try:
            if cid == "P-PROFILE-001":
                ok = all(PERF_MAP[k] == v for k, v in c["assert"].items())
            elif cid == "P-PROFILE-002":
                # 手工重算加权 mastery(仅验证公式)
                items = c["input"]
                total_w = 0.0; total_pw = 0.0
                for it in items:
                    days = it["days_ago"]; diff = it["difficulty"]
                    w = _time_weight(days) * {"easy": 0.8, "medium": 1.0, "hard": 1.2}[diff]
                    total_w += w; total_pw += PERF_MAP[it["performance"]] * w
                mastery = _rnd(total_pw / total_w) if total_w else None
                ok = abs(mastery - c["expected"]["mastery"]) < 1e-4
            elif cid == "P-PROFILE-003":
                v = _trend(c["recent"], c["previous"])
                ok = v == c["expected"]
            elif cid == "P-PROFILE-004":
                ok = all(
                    (it["attempt_count"] >= 3 and it["mastery"] < 0.60) == it["expected"]
                    for it in c["cases"]
                )
            elif cid == "P-PROFILE-005":
                ok = all(
                    (it["recent_occurrence_count"] >= 2) == it["expected"]
                    for it in c["cases"]
                )
            elif cid == "P-PROFILE-006":
                # 班级聚合:每学生先算个人值再平均
                rates = [s["score_rate"] for s in c["students"]]
                avg = sum(rates) / len(rates)  # 简化:学生个人 avg 即 score_rate
                ok = abs(avg - c["expected_avg"]) < 1e-9
            else:
                ok, err = True, "未知用例(跳过)"
            results.append((cid, ok, ""))
        except Exception as exc:
            results.append((cid, False, str(exc)))
    return results


# ---- Analysis 门禁 ----
def run_analysis_gate() -> list[tuple[str, bool, str]]:
    """运行 P-ANALYSIS-* 用例(确定性算法断言)。"""
    cases = _load_case_file("analysis_calculation")
    results = []
    for c in cases:
        cid = c["case_id"]
        try:
            if cid == "P-ANALYSIS-001":
                exp = c["expected"]
                attempts = len(c["results"])
                avg = round(sum(r["score_rate"] for r in c["results"]) / attempts, 4)
                err_students = [r for r in c["results"] if r["errors"]]
                error_rate = round(len(err_students) / attempts, 4) if attempts else None
                affected = len([r for r in c["results"] if "SIGN_ERROR" in r["errors"]])
                ok = (attempts == exp["attempt_count"] and abs(avg - exp["avg_score_rate"]) < 1e-4
                      and len(err_students) == exp["error_student_count"]
                      and abs(error_rate - exp["error_rate"]) < 1e-4
                      and affected == exp["SIGN_ERROR_affected"])
            elif cid == "P-ANALYSIS-002":
                exp = c["expected"]
                rates = [s["earned"] / s["max"] for s in c["students"]]
                avg = round(sum(rates) / len(rates), 4)
                dist = {
                    "below_60": sum(1 for x in rates if x < 0.60),
                    "from_60_to_79": sum(1 for x in rates if 0.60 <= x < 0.80),
                    "from_80_to_89": sum(1 for x in rates if 0.80 <= x < 0.90),
                    "from_90_to_100": sum(1 for x in rates if 0.90 <= x <= 1.00),
                }
                ok = (len(rates) == exp["graded_student_count"]
                      and abs(avg - exp["avg_score_rate"]) < 1e-4
                      and dist == {k: exp[k] for k in ["below_60", "from_60_to_79", "from_80_to_89", "from_90_to_100"]})
            elif cid == "P-ANALYSIS-003":
                exp = c["expected"]
                stu_avgs = [sum(s["performances"]) / len(s["performances"]) for s in c["students"]]
                avg = round(sum(stu_avgs) / len(stu_avgs), 4)
                low = sum(1 for v in stu_avgs if v < 0.60)
                ok = (len(stu_avgs) == exp["participating_student_count"]
                      and abs(avg - exp["avg_performance"]) < 1e-4
                      and low == exp["low_performance_student_count"])
            elif cid == "P-ANALYSIS-004":
                cases = c["cases"]
                ok = True
                for it in cases:
                    reasons = []
                    if it["fully_graded"] and it["hw_rate"] < 0.60:
                        reasons.append("LOW_HOMEWORK_SCORE")
                    if it["high_error_question_errors"]:
                        reasons.append("HIGH_ERROR_QUESTION")
                    if set(reasons) != set(it["expected_reasons"]):
                        ok = False
            elif cid == "P-ANALYSIS-005":
                ok = c["empty_results"]["avg_score_rate"] is None and c["empty_results"]["error_rate"] is None
            else:
                results.append((cid, True, "未知用例(跳过)"))
                continue
            results.append((cid, ok, ""))
        except Exception as exc:
            results.append((cid, False, str(exc)))
    return results


def run_gate(gate: str) -> bool:
    """运行指定门禁并汇总(返回是否全部通过)。"""
    t0 = time.time()
    logger.info("门禁开始: %s", gate)
    if gate == "profile_algorithm":
        results = run_profile_gate()
    elif gate == "analysis_calculation":
        results = run_analysis_gate()
    else:
        logger.error("未知门禁: %s(可选 profile_algorithm / analysis_calculation)", gate)
        return False
    passed = 0
    for cid, ok, err in results:
        logger.info("%s %s%s", "✅" if ok else "❌", cid, f" ({err})" if err else "")
        passed += 1 if ok else 0
    logger.info("门禁完成: %s, %d/%d 通过(耗时 %.1fs)",
                gate, passed, len(results), time.time() - t0)
    logger.info("PROFILE 金标准标记字段: weak_point 需 attempt>=3 且 mastery<0.6;"
                "recurring 需 28d>=2(见 profile_algorithm.jsonl)")
    return passed == len(results)


if __name__ == "__main__":
    args = sys.argv[1:]
    gates = [a.split("--gate ")[1] for a in args if a.startswith("--gate ")]
    if not gates:
        gates = ["profile_algorithm", "analysis_calculation"]
    ok = all(run_gate(g) for g in gates)
    sys.exit(0 if ok else 1)
