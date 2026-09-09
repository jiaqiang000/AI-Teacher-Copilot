"""Tool 层共享小工具(时间参数解析等)。"""

from __future__ import annotations

from datetime import datetime

from app.teacher_copilot.errors import InvalidArgument


def parse_iso_time(value: str, field: str) -> datetime:
    """解析 ISO 时间参数;非法值转为业务错误,不把 ValueError 抛到数据层。"""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise InvalidArgument(
            f"{field} 必须是 ISO 时间格式,例如 2026-09-01T00:00:00"
        ) from None
