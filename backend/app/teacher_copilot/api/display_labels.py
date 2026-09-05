"""教师业务页面使用的分类展示名称适配。

知识点和错误类型的中文名称只有一个来源：业务数据库中的标准分类字典。
本模块只处理画像和分析响应中已经确定的字段，不递归改写任意响应对象。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import select

from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.taxonomy import ErrorType, KnowledgePoint
from app.teacher_copilot.repositories.mysql.base import wrap_data_error

logger = logging.getLogger(__name__)

UNKNOWN_KNOWLEDGE_POINT = "未分类知识点"
UNKNOWN_ERROR_TYPE = "未知错误类型"


async def load_taxonomy_names(
    *,
    knowledge_point_keys: Iterable[str],
    error_codes: Iterable[str],
    context: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """批量读取分类名称，返回 ``知识点 key → 名称`` 和 ``错误 code → 名称``。"""
    kp_keys = sorted({value for value in knowledge_point_keys if value})
    err_codes = sorted({value for value in error_codes if value})

    try:
        async with get_session() as session:
            kp_names: dict[str, str] = {}
            if kp_keys:
                rows = await session.execute(
                    select(KnowledgePoint.key, KnowledgePoint.name).where(
                        KnowledgePoint.key.in_(kp_keys)
                    )
                )
                kp_names = {key: name for key, name in rows}

            error_names: dict[str, str] = {}
            if err_codes:
                rows = await session.execute(
                    select(ErrorType.code, ErrorType.name).where(
                        ErrorType.code.in_(err_codes)
                    )
                )
                error_names = {code: name for code, name in rows}
    except Exception as exc:  # pragma: no cover - 由统一 API 错误契约处理
        raise wrap_data_error(exc) from exc

    for key in kp_keys:
        if key not in kp_names:
            logger.warning(
                "教师展示分类缺失 context=%s kind=knowledge_point key=%s",
                context,
                key,
            )
    for code in err_codes:
        if code not in error_names:
            logger.warning(
                "教师展示分类缺失 context=%s kind=error_type code=%s",
                context,
                code,
            )
    return kp_names, error_names


def _attach_knowledge_point_names(
    items: list[dict], names: dict[str, str]
) -> None:
    """给已知业务数组附加标准知识点名称。"""
    for item in items:
        key = item.get("knowledge_point_key")
        item["knowledge_point_name"] = (
            names.get(key, UNKNOWN_KNOWLEDGE_POINT)
            if isinstance(key, str)
            else UNKNOWN_KNOWLEDGE_POINT
        )


def _attach_error_names(
    items: list[dict], kp_names: dict[str, str], error_names: dict[str, str]
) -> None:
    """给已知错误数组附加错误名称及其关联知识点名称。"""
    for item in items:
        code = item.get("error_code")
        key = item.get("knowledge_point_key")
        item["error_name"] = (
            error_names.get(code, UNKNOWN_ERROR_TYPE)
            if isinstance(code, str)
            else UNKNOWN_ERROR_TYPE
        )
        item["knowledge_point_name"] = (
            kp_names.get(key, UNKNOWN_KNOWLEDGE_POINT)
            if isinstance(key, str)
            else UNKNOWN_KNOWLEDGE_POINT
        )


async def annotate_profile(profile: dict, *, context: str) -> dict:
    """为班级或学生画像的已知分类字段附加数据库标准名称。"""
    knowledge_items = list(profile.get("knowledge_points", []))
    weak_items = list(profile.get("weak_points", []))
    common_error_items = list(profile.get("common_errors", []))
    recurring_error_items = list(profile.get("recurring_errors", []))

    kp_keys = [
        item.get("knowledge_point_key")
        for item in knowledge_items + weak_items + common_error_items + recurring_error_items
        if isinstance(item.get("knowledge_point_key"), str)
    ]
    error_codes = [
        item.get("error_code")
        for item in common_error_items + recurring_error_items
        if isinstance(item.get("error_code"), str)
    ]
    kp_names, error_names = await load_taxonomy_names(
        knowledge_point_keys=kp_keys,
        error_codes=error_codes,
        context=context,
    )

    _attach_knowledge_point_names(knowledge_items, kp_names)
    _attach_knowledge_point_names(weak_items, kp_names)
    _attach_error_names(common_error_items, kp_names, error_names)
    _attach_error_names(recurring_error_items, kp_names, error_names)
    return profile


async def annotate_homework_analysis(analysis: dict, *, context: str) -> dict:
    """为作业分析及其中的题目错误附加数据库标准名称。"""
    knowledge_items = list(analysis.get("knowledge_points", []))
    common_error_items = [
        item
        for question in analysis.get("questions", [])
        for item in question.get("common_errors", [])
    ]
    kp_keys = [
        item.get("knowledge_point_key")
        for item in knowledge_items + common_error_items
        if isinstance(item.get("knowledge_point_key"), str)
    ]
    error_codes = [
        item.get("error_code")
        for item in common_error_items
        if isinstance(item.get("error_code"), str)
    ]
    kp_names, error_names = await load_taxonomy_names(
        knowledge_point_keys=kp_keys,
        error_codes=error_codes,
        context=context,
    )

    _attach_knowledge_point_names(knowledge_items, kp_names)
    _attach_error_names(common_error_items, kp_names, error_names)
    return analysis
