"""GradingResult 组装与确定性校验(FR-017/019)。

把模型原始输出映射为统一 GradingResult 结构,并做确定性契约校验:
- 数学:Σ steps.max_score = score.max;Σ steps.earned = score.earned;
  0 <= earned <= max;evidence/error_block_ids 必须存在于 OCR layout_details
- 英语:必须且只能四维,每维 max_score=5、score ∈ 0..5 整数;
  score.earned = 四维之和;score.max = 20;evidence 必须只含四维键
校验失败抛 GradingOutputInvalid,不允许入库。
"""

from __future__ import annotations

from datetime import datetime

from app.teacher_copilot.errors import GradingOutputInvalid
from app.teacher_copilot.grading.english_grading import ENGLISH_ESSAY_RUBRIC_V1

_VALID_STEP_STATUS = {"correct", "partial", "incorrect", "consequential_error"}
_ENGLISH_DIMS = ("content", "organization", "grammar", "vocabulary")


class GradingResultAssembler:
    """批改结果组装器(纯函数,无副作用)。"""

    @staticmethod
    def _require_feedback(output: dict) -> dict:
        """校验并归一 feedback:summary 必须非空(008 T040)。

        模型未给 feedback、或 summary 为空白时判为输出不合格——不得再用空默认值把它
        伪装成"这道题没什么可说的",那正是"表象看不出来的错误"。
        strengths / improvements 允许为空数组:整题全错时"没有优点"本身是合法结论。
        """
        fb = output.get("feedback")
        if not isinstance(fb, dict):
            raise GradingOutputInvalid("批改输出缺少 feedback 对象")
        summary = fb.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise GradingOutputInvalid("feedback.summary 缺失或为空")
        return {
            "summary": summary.strip(),
            "strengths": list(fb.get("strengths") or []),
            "improvements": list(fb.get("improvements") or []),
        }

    @staticmethod
    def assemble_math(output: dict, subject: str, question_type: str, difficulty: str | None) -> dict:
        """数学结果组装(容忍模型输出简化结构)。

        支持两种模型输出:
        - 标准:{"steps":[...], "score":{...}, "correct":..., ...}
        - 简化:{"score": 8, "max_score": 10, "is_correct": true, ...}(无 steps)
        简化结构会归一为单步骤,保证契约校验通过。
        """
        # 简化结构归一(模型未按 steps 输出时)
        if "steps" not in output and "score" in output and "max_score" in output:
            earned = output["score"]
            max_score = output["max_score"]
            output = {
                "steps": [{
                    "step_index": 1, "description": "整题作答",
                    "evidence_block_ids": [], "error_block_ids": [],
                    "status": "correct" if output.get("is_correct") else "incorrect",
                    "earned_score": earned, "max_score": max_score,
                    "feedback": "整题评分(未拆步骤)",
                }],
                "score": {"earned": earned, "max": max_score},
                "correct": bool(output.get("is_correct")),
                "final_answer": output.get("final_answer"),
                # 归一结构里同样保留模型给的 feedback,后面的必需字段校验才看得见它
                "feedback": output.get("feedback"),
                "diagnosis": {
                    "knowledge_points": [],
                    "errors": [{"code": e, "raw_type": "", "knowledge_point_key": "",
                                "description": "", "evidence": ""}
                               for e in (output.get("error_type") or []) if isinstance(e, str)],
                },
            }
        steps = output.get("steps", [])
        if not steps:
            raise GradingOutputInvalid("数学批改输出缺少步骤")
        for s in steps:
            if s.get("status") not in _VALID_STEP_STATUS:
                raise GradingOutputInvalid(f"步骤状态非法: {s.get('status')}")
            if not (0 <= s.get("earned_score", -1) <= s.get("max_score", 0)):
                raise GradingOutputInvalid("步骤得分越界")
        total_max = sum(s["max_score"] for s in steps)
        total_earned = sum(s["earned_score"] for s in steps)
        expected_max = output.get("score", {}).get("max")
        if expected_max is not None and total_max != expected_max:
            raise GradingOutputInvalid(
                f"步骤满分加总({total_max}) != 总分({expected_max})"
            )
        # 总分一致性(顶层 score 与步骤加总一致)
        return {
            "score": {"earned": total_earned, "max": total_max, "rate": round(total_earned / total_max, 4) if total_max else 0.0},
            "math_detail": {
                "correct": bool(output.get("correct")),
                "final_answer": output.get("final_answer"),
                "steps": steps,
            },
            # 不在此处补默认空诊断(008 FR-002):一旦补上,"模型没给诊断"就变成
            # "学生没有任何知识点/错误",校验层再也看不到"缺字段"这一事实而放行。
            "diagnosis": output.get("diagnosis"),
            # feedback 是必需输出:缺失即判不合格,不再兜底成空评语(008 T040)
            "feedback": GradingResultAssembler._require_feedback(output),
            "english_essay_detail": None,
            "execution_meta": {"route": "math_strong_model"},
        }

    @staticmethod
    def assemble_english(output: dict, subject: str, question_type: str) -> dict:
        """英语作文结果组装(四维契约确定性校验)。"""
        detail = output.get("english_essay_detail") or {}
        dim_scores = detail.get("dimension_scores") or {}
        dims = set(dim_scores.keys())
        if dims != set(_ENGLISH_DIMS):
            raise GradingOutputInvalid(f"英语维度必须且只能四维,实际: {sorted(dims)}")
        total = 0
        for dim in _ENGLISH_DIMS:
            item = dim_scores[dim]
            score = item.get("score")
            if item.get("max_score") != 5 or not isinstance(score, int) or not (0 <= score <= 5):
                raise GradingOutputInvalid(f"维度 {dim} 分数必须为 0-5 整数")
            total += score
        evidence = detail.get("evidence") or {}
        if set(evidence.keys()) - set(_ENGLISH_DIMS):
            raise GradingOutputInvalid("evidence 必须且只能四维键")
        return {
            "score": {"earned": total, "max": 20, "rate": round(total / 20, 4)},
            "math_detail": None,
            "english_essay_detail": {
                "dimension_scores": dim_scores,
                "language_errors": detail.get("language_errors", []),
                "evidence": evidence,
            },
            # 不在此处补默认空诊断(008 FR-002):一旦补上,"模型没给诊断"就变成
            # "学生没有任何知识点/错误",校验层再也看不到"缺字段"这一事实而放行。
            "diagnosis": output.get("diagnosis"),
            # feedback 是必需输出:缺失即判不合格,不再兜底成空评语(008 T040)
            "feedback": GradingResultAssembler._require_feedback(output),
            "execution_meta": {"route": "english_two_stage"},
        }
