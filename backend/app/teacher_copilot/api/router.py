"""Teacher Copilot 业务 API 汇总路由器。

子路由按业务域拆分并在此挂载:
- homework:作业与题目(US1)
- 其余子路由随后续用户故事追加
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.teacher_copilot.api.identity import reject_legacy_identity_headers
from app.teacher_copilot.api.routers import account, homework, profile, submissions, uploads

router = APIRouter(dependencies=[Depends(reject_legacy_identity_headers)])
router.include_router(homework.router)
router.include_router(submissions.router)
router.include_router(profile.router)
router.include_router(uploads.router)
router.include_router(account.router)


@router.get("/healthz")
async def healthz() -> dict:
    """健康检查:确认 Teacher Copilot 路由已挂载。"""
    return {"status": "ok", "service": "teacher_copilot"}
