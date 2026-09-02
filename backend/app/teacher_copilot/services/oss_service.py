"""OSS 客户端封装(阿里云 OSS,V2,参考 contracts/upload-api.md)。

用途:教师/学生上传图片 → OSS → 返回公网 URL(供 OCR 业务使用)。
配置:TC_OSS_* 环境变量;缺失时抛 UPLOAD_CONFIG_MISSING(不静默降级,宪法 VII)。
【卡点】AK/SK/bucket/endpoint 待用户提供(2026-09-03 已记录)。
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app.teacher_copilot.config.settings import get_config
from app.teacher_copilot.errors import DataSourceError, InvalidArgument

logger = logging.getLogger("teacher_copilot.oss")


class OssService:
    """上传文件到 OSS 并返回公网 URL。"""

    def __init__(self) -> None:
        cfg = get_config()
        self._ak = cfg.oss_access_key_id
        self._sk = cfg.oss_access_key_secret
        self._bucket = cfg.oss_bucket
        self._endpoint = cfg.oss_endpoint

    def _assert_config(self) -> None:
        """配置检查:缺失即报错(不静默降级;宪法 VII)。"""
        missing = [k for k, v in [
            ("TC_OSS_ACCESS_KEY_ID", self._ak),
            ("TC_OSS_ACCESS_KEY_SECRET", self._sk),
            ("TC_OSS_BUCKET", self._bucket),
            ("TC_OSS_ENDPOINT", self._endpoint),
        ] if not v]
        if missing:
            raise DataSourceError(
                f"OSS 配置缺失: {', '.join(missing)}(待用户提供,见卡点清单)",
                code="UPLOAD_CONFIG_MISSING",
            )

    async def upload(self, file_path: str, object_key_prefix: str = "uploads") -> str:
        """上传本地文件,返回公网 URL(https://<bucket>.<endpoint>/<key>)。"""
        self._assert_config()
        import asyncio

        import oss2  # 惰性导入:配置未就绪时不必硬依赖

        path = Path(file_path)
        if not path.exists():
            raise InvalidArgument(f"文件不存在: {file_path}")
        ext = path.suffix or ".jpg"
        key = f"{object_key_prefix}/{uuid.uuid4().hex}{ext}"
        url = await asyncio.to_thread(
            self._upload_sync, str(path), key
        )
        logger.info("OSS 上传完成: %s -> %s", key, url)
        return url

    def _upload_sync(self, file_path: str, key: str) -> str:
        """同步上传(线程内执行)。"""
        import oss2

        auth = oss2.Auth(self._ak, self._sk)
        bucket = oss2.Bucket(auth, self._endpoint, self._bucket)
        bucket.put_object_from_file(key, file_path)
        return f"https://{self._bucket}.{self._endpoint}/{key}"
