"""提交图片资产服务(参考文档 01 §3.4,与 QuestionAssetService 同模式)。

MVP 本地文件存储;真实业务学生上传图片后存对象存储取公网 URL
(待办:阿里云 OSS,见 tasks.md Notes / ocr.py 注释)。
"""

from __future__ import annotations

import shutil
from pathlib import Path


class SubmissionAssetService:
    """学生提交图片资产(MVP:本地存储,URL 由静态目录暴露)。"""

    def __init__(self) -> None:
        import os

        self._root = Path(os.environ.get("TC_SUBMISSION_ASSET_DIR", "tc-data/submission-assets"))
        self._root.mkdir(parents=True, exist_ok=True)

    async def save(self, src_path: str) -> str:
        """保存图片,返回相对 URL(/tc-assets/submission/{filename})。"""
        name = Path(src_path).name
        dest = self._root / name
        shutil.copyfile(src_path, dest)
        return f"/tc-assets/submission/{name}"
