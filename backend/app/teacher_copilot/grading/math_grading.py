"""数学批改:按学生实际解法动态识别步骤并给步骤分。

依据参考文档 01 §5.3(步骤分 Prompt 规则、Taxonomy 标准 level=2 候选注入、
步骤状态 correct/partial/incorrect/consequential_error、OCR Block 证据)。
模型统一使用 DeepSeek anthropic v1/messages(用户实际接入)。
"""

from __future__ import annotations

from app.teacher_copilot.models.clients.llm import LlmClient

# 数学批改 System Prompt(参考文档 01 §5.3.5 精简为可执行版本)
_MATH_SYSTEM = (
    "你是一名数学教师,负责批改学生的数学解题过程并给出步骤分。"
    "你会收到 Question(正式题目)、Max Score、OCR Student Submission(带 Block 编号)、"
    "Knowledge Point Taxonomy、Error Type Taxonomy。"
    "要求:理解学生实际解法并识别关键步骤;不得因解法与常见解法不同扣分;"
    "每步标记 correct/partial/incorrect/consequential_error;"
    "所有步骤 max_score 之和必须等于 Max Score;"
    "knowledge_point.key 与 error.code 必须从给定 Taxonomy 的 level=2 小类中选择,"
    "无匹配时用对应大类下的 OTHER,并输出 raw_name / raw_type 保留本次语义;"
    "evidence_block_ids 与 error_block_ids 必须引用真实存在的 Block 编号。"
    "严格输出 JSON:"
    '{"steps":[{"step_index":1,"description":"...","evidence_block_ids":[2],'
    '"error_block_ids":[],"status":"correct","earned_score":3,"max_score":3,'
    '"feedback":"..."}],"score":{"earned":6,"max":10},'
    '"correct":true,"final_answer":"x=3",'
    '"diagnosis":{"knowledge_points":[{"key":"...","raw_name":"...",'
    '"performance":"correct","evidence":"..."}],'
    '"errors":[{"code":"...","raw_type":"...","knowledge_point_key":"...",'
    '"description":"...","evidence":"..."}]}}'
)


def _build_math_prompt(question: dict, ocr_blocks: list[dict], kp_taxonomy: list[str], err_taxonomy: list[str]) -> str:
    """构造数学批改用户 Prompt(Block 按 index 升序转为稳定文本)。"""
    # 保序拼装:保持学生原始书写顺序(参考文档 01 §5.3.3)
    blocks_text = "\n\n".join(
        f"[Block {b['index']} | {b['label']}]\n{b['content']}" for b in ocr_blocks
    )
    return (
        f"Question:\n{question['content']}\n\n"
        f"Max Score:\n{question['max_score']}\n\n"
        f"Knowledge Point Taxonomy:\n{kp_taxonomy}\n\n"
        f"Error Type Taxonomy:\n{err_taxonomy}\n\n"
        f"OCR Student Submission:\n{blocks_text}\n\n"
        "请批改学生完整解题过程并给出步骤分,同时按照给定 Taxonomy 输出结构化知识点和错误诊断。"
    )


async def run_math_grading(
    *, llm: LlmClient, question: dict, ocr_blocks: list[dict],
    kp_taxonomy: list[str], err_taxonomy: list[str],
) -> dict:
    """执行数学批改,返回 {math_detail, diagnosis} 原始模型输出(由 Assembler 校验)。"""
    prompt = _build_math_prompt(question, ocr_blocks, kp_taxonomy, err_taxonomy)
    return await llm.generate_json(prompt=prompt, system=_MATH_SYSTEM)
