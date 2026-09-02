"""标准分类字典种子:数学/英语两级 Knowledge Point 与 Error Type。

依据 data-model.md §2.5 与参考文档 03 §3.2.2/3.2.3、08 §3.2 金标准:
- level=1 为大类,level=2 为可落库小类
- 每个大类至少一个 is_other=True 的兜底小类
- 金标准关注:math.linear_equation.transposition、math.function.graph、
  SIGN_ERROR、GRAPH_READING_ERROR
"""

from __future__ import annotations

from sqlalchemy import select

from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.taxonomy import ErrorType, KnowledgePoint

# 数学知识点两级分类:(key, name, parent_key, level, is_other)
MATH_KP: list[tuple[str, str, str | None, int, bool]] = [
    ("math.linear_equation", "一元一次方程", None, 1, False),
    ("math.linear_equation.transposition", "移项", "math.linear_equation", 2, False),
    ("math.linear_equation.combine_like_terms", "合并同类项", "math.linear_equation", 2, False),
    ("math.linear_equation.other", "一元一次方程其他", "math.linear_equation", 2, True),
    ("math.function", "函数", None, 1, False),
    ("math.function.graph", "函数图像", "math.function", 2, False),
    ("math.function.other", "函数其他", "math.function", 2, True),
]

# 数学错误类型两级分类:(code, name, parent_code, level, is_other)
MATH_ERR: list[tuple[str, str, str | None, int, bool]] = [
    ("CALCULATION_ERROR", "计算错误", None, 1, False),
    ("SIGN_ERROR", "符号错误", "CALCULATION_ERROR", 2, False),
    ("ARITHMETIC_ERROR", "算术错误", "CALCULATION_ERROR", 2, False),
    ("CALCULATION_OTHER", "其他计算错误", "CALCULATION_ERROR", 2, True),
    ("REASONING_ERROR", "推理错误", None, 1, False),
    ("INVALID_TRANSFORMATION", "错误变形", "REASONING_ERROR", 2, False),
    ("MISSING_STEP", "关键步骤缺失", "REASONING_ERROR", 2, False),
    ("REASONING_OTHER", "其他推理错误", "REASONING_ERROR", 2, True),
    ("GRAPH_ERROR", "函数图像错误", None, 1, False),
    ("GRAPH_READING_ERROR", "函数图像读取错误", "GRAPH_ERROR", 2, False),
    ("GRAPH_ERROR_OTHER", "其他函数图像错误", "GRAPH_ERROR", 2, True),
]

# 英语知识点两级分类
ENGLISH_KP: list[tuple[str, str, str | None, int, bool]] = [
    ("english.grammar", "语法", None, 1, False),
    ("english.grammar.past_tense", "一般过去时", "english.grammar", 2, False),
    ("english.grammar.subject_verb_agreement", "主谓一致", "english.grammar", 2, False),
    ("english.grammar.other", "语法其他", "english.grammar", 2, True),
    ("english.writing", "写作", None, 1, False),
    ("english.writing.cohesion", "篇章衔接", "english.writing", 2, False),
    ("english.writing.other", "写作其他", "english.writing", 2, True),
]

# 英语错误类型两级分类
ENGLISH_ERR: list[tuple[str, str, str | None, int, bool]] = [
    ("GRAMMAR_ERROR", "语法错误", None, 1, False),
    ("TENSE_ERROR", "时态错误", "GRAMMAR_ERROR", 2, False),
    ("SUBJECT_VERB_ERROR", "主谓一致错误", "GRAMMAR_ERROR", 2, False),
    ("ARTICLE_ERROR", "冠词错误", "GRAMMAR_ERROR", 2, False),
    ("GRAMMAR_OTHER", "其他语法错误", "GRAMMAR_ERROR", 2, True),
    ("LEXICAL_ERROR", "词汇错误", None, 1, False),
    ("WORD_CHOICE_ERROR", "用词不当", "LEXICAL_ERROR", 2, False),
    ("SPELLING_ERROR", "拼写错误", "LEXICAL_ERROR", 2, False),
    ("LEXICAL_OTHER", "其他词汇错误", "LEXICAL_ERROR", 2, True),
    ("ORGANIZATION_ERROR", "结构错误", None, 1, False),
    ("COHESION_ERROR", "衔接不当", "ORGANIZATION_ERROR", 2, False),
    ("ORGANIZATION_OTHER", "其他结构错误", "ORGANIZATION_ERROR", 2, True),
]


async def _insert_kp(rows: list) -> None:
    """幂等写入知识点(按 key 判重)。"""
    async with get_session() as session:
        for key, name, parent_key, level, is_other in rows:
            subject = "math" if key.startswith("math.") else "english"
            exists = await session.scalar(select(KnowledgePoint).where(KnowledgePoint.key == key))
            if exists is None:
                session.add(KnowledgePoint(
                    key=key, name=name, subject=subject,
                    parent_key=parent_key, level=level, is_other=is_other,
                ))
        await session.commit()


async def _insert_err(rows: list) -> None:
    """幂等写入错误类型(按 code 判重)。"""
    # 数学错误码集合:用于确定 subject 归属
    math_codes = {r[0] for r in MATH_ERR}
    async with get_session() as session:
        for code, name, parent_code, level, is_other in rows:
            exists = await session.scalar(select(ErrorType).where(ErrorType.code == code))
            if exists is None:
                session.add(ErrorType(
                    code=code, name=name, subject="math" if code in math_codes else "english",
                    parent_code=parent_code, level=level, is_other=is_other,
                ))
        await session.commit()


async def seed_taxonomy() -> None:
    """写入全部标准分类(幂等,可重复执行)。"""
    await _insert_kp(MATH_KP + ENGLISH_KP)
    await _insert_err(MATH_ERR + ENGLISH_ERR)
