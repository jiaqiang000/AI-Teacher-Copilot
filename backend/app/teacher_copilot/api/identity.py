"""业务身份 FastAPI 依赖(T011):DeerFlow 登录态 → 业务 teacher_id/student_id。

- 认证:复用 gateway 的 get_current_user_from_request(cookie 会话/PAT),
  与 DeerFlow 其余接口同一认证实现,不做第二套。
- 映射:AccountLink 表(user_id → biz_type + biz_id);未映射视为无业务权限。
- 禁止再接收 X-Teacher-Id/X-Student-Id 头(可被伪造)。
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import select
from app.gateway.deps import get_current_user_from_request
from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.db.models.org import AccountLink


async def _resolve_biz_id(request: Request, biz_type: str) -> str:
    """从登录态解析业务 ID;未认证 401,未映射 403。"""
    user = await get_current_user_from_request(request)
    if user is None:  # pragma: no cover - 依赖自身已抛 401
        raise HTTPException(status_code=401, detail="Not authenticated")
    async with get_session() as session:
        link = await session.scalar(
            select(AccountLink).where(
                AccountLink.user_id == str(user.id),
                AccountLink.biz_type == biz_type,
            )
        )
    if link is None:
        raise HTTPException(
            status_code=403,
            detail={"code": "NO_BIZ_MAPPING", "message": "登录用户未映射教师/学生业务身份"},
        )
    return link.biz_id


async def get_teacher_id(request: Request) -> str:
    """教师接口依赖:当前登录用户对应的 teacher_id。"""
    return await _resolve_biz_id(request, "teacher")


async def get_student_id(request: Request) -> str:
    """学生接口依赖:当前登录用户对应的 student_id。"""
    return await _resolve_biz_id(request, "student")


async def get_account_role(request: Request) -> dict:
    """返回当前登录用户的业务角色(003 品牌与导航整合:角色分流用)。

    只读查询 AccountLink;未登录 401;登录但无业务映射返回 role=none
    (前端按未映射处理,不视为错误)。
    """
    user = await get_current_user_from_request(request)
    if user is None:  # pragma: no cover - 依赖自身已抛 401
        raise HTTPException(status_code=401, detail="Not authenticated")
    async with get_session() as session:
        rows = list(await session.execute(
            select(AccountLink.biz_type).where(AccountLink.user_id == str(user.id))
        ))
    role = "teacher" if "teacher" in [r[0] for r in rows] else (
        "student" if "student" in [r[0] for r in rows] else "none"
    )
    return {"role": role}


async def reject_legacy_identity_headers(request: Request) -> None:
    """全局依赖:若请求仍带旧身份头(可被伪造),直接拒绝,强制走登录态。"""
    if request.headers.get("X-Teacher-Id") or request.headers.get("X-Student-Id"):
        raise HTTPException(
            status_code=400,
            detail={"code": "LEGACY_IDENTITY_HEADER", "message": "请移除 X-Teacher-Id/X-Student-Id,身份以登录态为准"},
        )
