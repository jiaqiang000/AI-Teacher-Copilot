"""图片上传 API(V2,contracts/upload-api.md)。

POST /api/teacher-copilot/uploads —— multipart file → OSS → 公网 URL。
身份:MVP 过渡期 header 占位,正式版由登录态取(见 T011)。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, UploadFile

from app.teacher_copilot.api.response import fail, ok
from app.teacher_copilot.errors import InvalidArgument, TcError
from app.teacher_copilot.services.oss_service import OssService

router = APIRouter(prefix="/api/teacher-copilot")

# 允许类型/大小(参考 V1 上传校验思路;PDF 供未来,当前图片为主)
ALLOWED_SUFFIX = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/uploads")
async def upload_image(
    file: UploadFile,
    x_teacher_id: str = Header(default="teacher_01"),  # TODO: V2 T011 改登录态身份
):
    """上传图片,返回 OSS 公网 URL。"""
    try:
        name = (file.filename or "upload.jpg").lower()
        suffix = Path(name).suffix
        if suffix not in ALLOWED_SUFFIX:
            raise InvalidArgument(f"不支持的文件类型: {suffix}(允许 jpg/png/pdf)")
        data = await file.read()
        if len(data) > MAX_SIZE:
            raise InvalidArgument("文件超过 10MB 限制")
        # 落临时文件 → OSS(避免接口直接暴露本地存储)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        url = await OssService().upload(tmp_path)
        return ok({"url": url})
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))
