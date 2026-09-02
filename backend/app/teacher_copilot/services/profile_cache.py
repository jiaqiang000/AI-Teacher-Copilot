"""Redis 画像缓存与失效(FR-024,参考文档 03 §3.7)。

- 新 GradingResult 成功写入 / 重新提交删除旧结果 → 失效对应 Student/Class Profile
- 下次读取 Redis Miss → 从 MySQL 当前有效事实重算(惰性)
- 不引入 MQ/定时任务(宪法 V);Redis 未启用时作为无操作缓存
"""

from __future__ import annotations

import logging

from app.teacher_copilot.repositories.redis.client import RedisProfileClient

logger = logging.getLogger("teacher_copilot.profile_cache")


class ProfileCacheService:
    """画像缓存服务:失效 + 读取(封装 RedisProfileClient)。"""

    def __init__(self) -> None:
        self._client = RedisProfileClient()

    async def invalidate_student(self, student_id: str, subject: str) -> None:
        """失效学生画像缓存(新结果写入/旧结果删除时调用)。"""
        await self._client.delete("student", student_id, subject)
        logger.debug("失效学生画像缓存: %s/%s", student_id, subject)

    async def invalidate_class(self, class_id: str, subject: str) -> None:
        """失效班级画像缓存。"""
        await self._client.delete("class", class_id, subject)
        logger.debug("失效班级画像缓存: %s/%s", class_id, subject)

    async def invalidate_all(self, student_id: str, class_id: str, subject: str) -> None:
        """批改结果变化后失效学生+班级对应缓存(参考文档 03 §3.7 缓存失效规则)。"""
        await self.invalidate_student(student_id, subject)
        await self.invalidate_class(class_id, subject)

    async def get_or_rebuild(self, kind: str, obj_id: str, subject: str,
                             rebuild_fn) -> dict:
        """读取缓存;Miss 则调用 rebuild_fn 重算并回填。

        rebuild_fn: async () -> dict(必须是 ProfileAlgorithmV1 计算结果)。
        """
        cached = await self._client.get(kind, obj_id, subject)
        if cached is not None:
            logger.debug("画像命中缓存: %s/%s", kind, obj_id)
            return cached
        profile = await rebuild_fn()
        await self._client.set(kind, obj_id, subject, profile)
        return profile
