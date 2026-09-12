"""图片上传 API(V2,contracts/upload-api.md)。

POST /api/teacher-copilot/uploads —— multipart file → OSS → 公网 URL。
身份:仅要求已登录(AuthMiddleware);身份校验在各业务接口(创建题目/提交作答)处完成。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Request

from app.teacher_copilot.api.identity import reject_legacy_identity_headers
from app.teacher_copilot.api.response import fail, ok
from app.teacher_copilot.errors import InvalidArgument, TcError
from app.teacher_copilot.models.clients.ocr import OcrClient
from app.teacher_copilot.services.oss_service import OssService

router = APIRouter(prefix="/api/teacher-copilot")

# 允许类型/大小(参考 V1 上传校验思路;PDF 供未来,当前图片为主)
ALLOWED_SUFFIX = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/uploads")
async def upload_image(
    file: UploadFile,
    request: Request,
):
    """上传图片,返回 OSS 公网 URL(仅要求登录,业务权限交给后续接口)。"""

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


@router.post("/ocr")
async def ocr_recognize(body: dict):
    """题目图 OCR 识别(回填出题文本)。body: {image_url}(公网可下载链接)。

    学生作答批改内部自带 OCR;本端点服务"教师上传题目图 → 回填"场景,
    与 OcrClient 共用智谱 GLM-OCR;未配置密钥时显式失败(OCR_NOT_CONFIGURED),
    不再返回占位识别文本。
    """
    try:
        image_url = body.get("image_url") or ""
        if not image_url:
            raise InvalidArgument("缺少 image_url")
        result = await OcrClient().recognize("", image_url=image_url)
        return ok({
            "text": result.get("md_results", "") or result.get("text", ""),
            "blocks": len(result.get("layout_details") or []),
        })
    except TcError as e:
        raise HTTPException(e.http_status, detail=dict(code=e.code, message=e.message))
