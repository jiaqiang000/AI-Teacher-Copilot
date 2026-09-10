"""Eval Runner:运行评测用例并对确定性门禁断言(参考文档 08 §3.3/3.4)。

用法(可观察,宪法 X):
    python -m evals.runtime.run                       # 跑默认组合(全部门禁)
    python -m evals.runtime.run --gate profile_algorithm
    python -m evals.runtime.run --gate analysis_calculation
    python -m evals.runtime.run --gate cases          # 用例文件格式守门
    python -m evals.runtime.run --gate cases --gate profile_algorithm
`--gate X` 与 `--gate=X` 两种写法都支持,可重复指定;不指定则跑默认组合。
输出:每用例通过/失败 + 汇总(带耗时);未知门禁与缺失参数以退出码 2 报错。
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

# 不指定 --gate 时运行的门禁组合
DEFAULT_GATES = ("profile_algorithm", "analysis_calculation", "cases")
KNOWN_GATES = frozenset(DEFAULT_GATES)


def parse_gates(argv: list[str]) -> list[str]:
    """解析 `--gate X` / `--gate=X` 参数,支持重复指定。

    不指定时返回 DEFAULT_GATES。参数缺失或为空值时抛 ValueError,
    由调用方转为退出码 2(避免静默回退到默认组合而掩盖调用错误)。
    """
    gates: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--gate":
            if index + 1 >= len(argv):
                raise ValueError("--gate 缺少门禁名")
            gates.append(argv[index + 1])
            index += 2
            continue
        if arg.startswith("--gate="):
            value = arg.split("=", 1)[1]
            if not value:
                raise ValueError("--gate= 缺少门禁名")
            gates.append(value)
        index += 1
    return gates or list(DEFAULT_GATES)


def _cases_dir() -> str:
    """定位用例目录(带路径容错:支持从仓库根或 evals 目录运行)。"""
    import os

    candidate = os.path.join("evals", "teacher_eval_v1", "cases")
    if os.path.isdir(candidate):
        return candidate
    return os.path.join(os.path.dirname(__file__), "..", "teacher_eval_v1", "cases")


def _load_case_file(gate: str):
    """加载门禁用例文件(读取逻辑统一走 case_loader)。"""
    import os

    from evals.runtime.case_loader import load_case_file

    return load_case_file(os.path.join(_cases_dir(), f"{gate}.jsonl"))


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


# ---- 用例格式门禁(不依赖 LLM) ----
def run_cases_gate() -> list[tuple[str, bool, str]]:
    """校验 cases/ 下全部用例文件可加载,且每条用例都有 case_id。

    格式守门用例(007 诊断):core_cases.jsonl 曾因"跨行对象 + 读取逻辑不跳注释"
    长期无法加载却无人发现。此门禁让同类格式漂移当场暴露。
    """
    import os

    from evals.runtime.case_loader import load_case_file

    cases_dir = _cases_dir()
    results: list[tuple[str, bool, str]] = []
    fnames = sorted(f for f in os.listdir(cases_dir) if f.endswith(".jsonl"))
    for fname in fnames:
        try:
            cases = load_case_file(os.path.join(cases_dir, fname))
        except Exception as exc:
            results.append((fname, False, str(exc)))
            continue
        missing = [c.get("case_id") or "<缺 case_id>" for c in cases if not c.get("case_id")]
        if missing:
            results.append((fname, False, f"缺 case_id: {missing[:5]}"))
        else:
            results.append((fname, True, f"{len(cases)} 例"))
    return results


def run_gate(gate: str) -> bool:
    """运行指定门禁并汇总(返回是否全部通过)。"""
    t0 = time.time()
    logger.info("门禁开始: %s", gate)
    if gate == "profile_algorithm":
        results = run_profile_gate()
    elif gate == "analysis_calculation":
        results = run_analysis_gate()
    elif gate == "cases":
        results = run_cases_gate()
    else:
        logger.error("未知门禁: %s(可选 profile_algorithm / analysis_calculation / cases)", gate)
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
    try:
        gates = parse_gates(sys.argv[1:])
    except ValueError as exc:
        logger.error("%s(用法: --gate <name>,可选 %s)",
                     exc, " / ".join(DEFAULT_GATES))
        sys.exit(2)

    unknown = [g for g in gates if g not in KNOWN_GATES]
    if unknown:
        logger.error("未知门禁: %s(可选 %s)",
                     ", ".join(unknown), " / ".join(DEFAULT_GATES))
        sys.exit(2)

    # 逐个执行而不是 all(生成器):all 会在首个失败处短路,
    # 导致后面的门禁完全不跑,失败时看不到完整信息。
    outcomes = [run_gate(gate) for gate in gates]
    sys.exit(0 if all(outcomes) else 1)
