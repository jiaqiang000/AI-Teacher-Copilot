"""英语作文批改:AutoSCORE 风格两阶段(证据提取 → 评分+诊断)。

依据参考文档 01 §5.4:两阶段均 DeepSeek v4 Flash;
EnglishEssayRubricV1 固定四维(Content/Organization/Grammar/Vocabulary,各 0-5,总分 20)。
Agent 1 只提取证据不打分;Agent 2 依据 Rubric 与证据正式评分并做结构化诊断。
"""

from __future__ import annotations

from app.teacher_copilot.models.clients.llm import LlmClient

# 系统内置英语作文评分标准 V1(固定,教师不可自定义)
ENGLISH_ESSAY_RUBRIC_V1 = {
    "content": {"name": "内容", "max_score": 5},
    "organization": {"name": "组织结构与衔接", "max_score": 5},
    "grammar": {"name": "语法与句式", "max_score": 5},
    "vocabulary": {"name": "词汇", "max_score": 5},
    "total": 20,
}

_EVIDENCE_SYSTEM = (
    "你是英语作文评分证据提取助手。依据 EnglishEssayRubricV1,从学生作文中提取"
    "支持 Content / Organization / Grammar / Vocabulary 四个维度判断的客观证据。"
    "你不直接打分,也不做最终 Taxonomy 分类。严格输出 JSON:"
    '{"evidence":{"content":["..."],"organization":["..."],"grammar":["..."],"vocabulary":["..."]}}'
)

_SCORE_SYSTEM = (
    "你是英语作文正式评分教师。依据 EnglishEssayRubricV1(各维度 0-5 整数,总分 20)与"
    "Agent 1 提供的 evidence 正式评分。说明扣分原因,给出修改建议,"
    "从给定 Taxonomy 的 level=2 小类中选择 knowledge_point_key / error_code,"
    "无匹配用对应大类 OTHER 并保留 raw_name / raw_type 语义。严格输出 JSON:"
    '{"dimension_scores":{"content":{"score":5,"max_score":5},'
    '"organization":{"score":4,"max_score":5},"grammar":{"score":3,"max_score":5},'
    '"vocabulary":{"score":4,"max_score":5}},'
    '"feedback":{"summary":"...","strengths":["..."],"improvements":["..."]},'
    '"language_errors":[{"error_code":"TENSE_ERROR","original":"...","suggestion":"..."}],'
    '"diagnosis":{"knowledge_points":[{"key":"...","raw_name":"...",'
    '"performance":"partial","evidence":"..."}],'
    '"errors":[{"code":"...","raw_type":"...","knowledge_point_key":"...",'
    '"description":"...","evidence":"..."}]}}'
)


async def run_english_grading(
    *, llm: LlmClient, question: dict, essay_text: str,
    kp_taxonomy: list[str], err_taxonomy: list[str],
) -> dict:
    """执行英语两阶段批改:返回 {english_essay_detail, diagnosis} 原始输出。"""
    evidence_prompt = (
        f"EnglishEssayRubricV1:{ENGLISH_ESSAY_RUBRIC_V1}\n\n"
        f"作文题目:{question['content']}\n\n学生作文:\n{essay_text}"
    )
    evidence_resp = await llm.generate_json(prompt=evidence_prompt, system=_EVIDENCE_SYSTEM)
    evidence = evidence_resp.get("evidence", {})

    score_prompt = (
        f"EnglishEssayRubricV1:{ENGLISH_ESSAY_RUBRIC_V1}\n\n"
        f"作文题目:{question['content']}\n\n学生作文:\n{essay_text}\n\n"
        f"评分证据 evidence:\n{evidence}\n\n"
        f"Knowledge Point Taxonomy:{kp_taxonomy}\nError Type Taxonomy:{err_taxonomy}"
    )
    score_resp = await llm.generate_json(prompt=score_prompt, system=_SCORE_SYSTEM)
    # 统一结构:模型可能把 dimension_scores/feedback/language_errors 放在顶层
    # (score_resp 顶层),而 detail 只放 evidence;在此归一(参考文档 02 §9)。
    det = score_resp.get("english_essay_detail") or {}
    det["dimension_scores"] = score_resp.get("dimension_scores") or det.get("dimension_scores") or {}
    det["language_errors"] = score_resp.get("language_errors") or det.get("language_errors", [])
    det["evidence"] = evidence
    score_resp["english_essay_detail"] = det
    # feedback 顶层保留(Assembler 会读取 score_resp["feedback"])
    return score_resp
