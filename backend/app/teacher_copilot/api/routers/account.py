"""账号相关业务 API(003 品牌与导航整合)。

当前仅提供角色查询端点(角色分流:教师/学生/未映射),复用 identity.py 的
AccountLink 只读查询,无新增表与权限逻辑。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from app.teacher_copilot.api.identity import get_account_role
from app.teacher_copilot.api.response import ok

logger = logging.getLogger("teacher_copilot.account")
router = APIRouter(prefix="/api/teacher-copilot/account")


@router.get("/role")
async def account_role(request: Request) -> dict[str, Any]:
    """当前用户业务角色(teacher/student/none),供前端角色分流。"""
    data = await get_account_role(request)
    logger.info("account/role -> %s", data.get("role"))
    return ok(data)
