"""Redis 客户端:画像缓存(可重算派生数据)。

Redis 仅存 Student/Class Profile 快照;MySQL 仍是唯一业务事实源。
key 惯例:student_profile:{student_id}:{subject} / class_profile:{class_id}:{subject}
"""

from __future__ import annotations

import json

from app.teacher_copilot.config.settings import get_config


class RedisProfileClient:
    """画像缓存客户端(redis_enabled=False 时作为无操作缓存,本地开发可单机运行)。"""

    def __init__(self) -> None:
        cfg = get_config()
        self._enabled = cfg.redis_enabled
        self._redis = None
        if self._enabled:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(cfg.redis_url, decode_responses=True)

    def _key(self, kind: str, obj_id: str, subject: str) -> str:
        return f"{kind}_profile:{obj_id}:{subject}"

    async def get(self, kind: str, obj_id: str, subject: str) -> dict | None:
        """读取画像快照;未启用 Redis 时直接 Miss(走 MySQL 重算)。"""
        if not self._enabled or self._redis is None:
            return None
        raw = await self._redis.get(self._key(kind, obj_id, subject))
        return json.loads(raw) if raw else None

    async def set(self, kind: str, obj_id: str, subject: str, profile: dict) -> None:
        """写入画像快照。"""
        if not self._enabled or self._redis is None:
            return
        await self._redis.set(self._key(kind, obj_id, subject), json.dumps(profile, ensure_ascii=False))

    async def delete(self, kind: str, obj_id: str, subject: str) -> None:
        """失效画像快照(新结果写入/旧结果删除时调用,FR-024)。"""
        if not self._enabled or self._redis is None:
            return
        await self._redis.delete(self._key(kind, obj_id, subject))
