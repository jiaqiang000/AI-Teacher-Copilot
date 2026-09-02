"""题目图片资产服务:保存教师上传的题目原图。

MVP 实现:存本地磁盘目录,返回可访问 URL;参考设计指出 Thread Upload
生命周期不适合业务资产,故本项目单独管理(参考文档 01 §3.3 DeerFlow 落地小节)。
"""

from __future__ import annotations

import shutil
from pathlib import Path


class QuestionAssetService:
    """题目图片资产(MVP:本地文件存储,URL 由静态目录暴露)。"""

    def __init__(self) -> None:
        # 存储根目录:TC_QUESTION_ASSET_DIR 或默认 tc-data/question-assets
        import os

        self._root = Path(os.environ.get("TC_QUESTION_ASSET_DIR", "tc-data/question-assets"))
        self._root.mkdir(parents=True, exist_ok=True)

    async def save(self, src_path: str) -> str:
        """保存图片,返回相对 URL(/tc-assets/question/{filename})。"""
        name = Path(src_path).name
        dest = self._root / name
        shutil.copyfile(src_path, dest)
        return f"/tc-assets/question/{name}"
