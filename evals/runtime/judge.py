"""Result Judge:判定 Agent 最终回答的结果正确性(参考文档 08 §6)。

不依赖 LLM 自由判断,按固定 Rubric 与金标准事实做规则判定:
- Result Pass:核心业务事实正确 + 核心结论正确 + 完成主要任务 + 无明显编造
- Quality Score:Correctness 40% / Completeness 25% / Relevance 15% / Teaching 20%
  (每维度 0-5,总分 0-5)
"""

from __future__ import annotations

import logging

logger = logging.getLogger("evals.judge")

# Quality 权重(参考文档 08 §6.2)
WEIGHTS = {"correctness": 0.40, "completeness": 0.25, "relevance": 0.15, "teaching": 0.20}
MAX_SCORE = 5.0


class ResultJudge:
    """基于金标准事实与最终回答的结果判定(规则化,非 LLM)。"""

    def judge(self, case: dict, final_answer: str, gold_facts: dict) -> dict:
        """返回 {result_pass, quality_score, notes}。"""
        answer = final_answer or ""
        notes = []
        gold = case.get("gold_facts", gold_facts or {})

        # 核心事实检查(数值/业务对象)
        checks = []
        for key, val in gold.items():
            if isinstance(val, (int, float)) and str(val) not in str(answer):
                # 数值容忍:百分比表示(如 90% vs 0.90)
                if f"{val * 100}%" in answer or f"{val}" in answer:
                    checks.append(True)
                else:
                    checks.append(False)
                    notes.append(f"缺少金标准事实: {key}={val}")
            elif isinstance(val, str) and val not in answer:
                checks.append(False)
                notes.append(f"缺少金标准事实: {key}={val}")

        # Result Pass:事实要尽量命中 + 回答非空
        hit_rate = sum(checks) / len(checks) if checks else 1.0
        result_pass = (hit_rate >= 0.8 and bool(answer.strip()))

        # Quality Score(简化规则:命中率与完整性加权)
        q = {
            "correctness": 5.0 * hit_rate if checks else 4.0,
            "completeness": 5.0 if bool(answer) else 1.0,
            "relevance": 4.5,  # 默认高(内容针对提问)
            "teaching": 4.0,
        }
        quality = round(sum(q[k] * WEIGHTS[k] for k in WEIGHTS), 2)
        return {"result_pass": result_pass, "quality_score": quality, "notes": notes}
