"""统一业务返回结构。

参考 docs/05-tool-skill.md §11:正常 {"success": true, "data": ...};
失败 {"success": false, "error": {"code", "message"}}。APP 层直接包一层,
Tool 层复用同一结构。
"""

from __future__ import annotations

from typing import Any

from app.teacher_copilot.errors import TcError


def ok(data: Any) -> dict:
    """构造成功响应体。"""
    return {"success": True, "data": data}


def fail(error: TcError) -> dict:
    """构造失败响应体(统一错误码)。"""
    return {"success": False, "error": error.to_dict()}
