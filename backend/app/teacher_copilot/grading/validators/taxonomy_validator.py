"""Taxonomy 确定性校验(普通后端代码,不是 Agent/LLM)。

依据参考文档 03 §3.2.5:检查 knowledge_point_key / error_code
- 是否存在于当前学科标准 Taxonomy
- 是否为 level=2 可落库小类(不能直接落 level=1 大类)
非法编码视为 Grading Output Contract 校验失败,不允许入库。
"""

from __future__ import annotations

from sqlalchemy import select

from app.teacher_copilot.db.models.taxonomy import ErrorType, KnowledgePoint
from app.teacher_copilot.errors import GradingOutputInvalid
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error


class TaxonomyValidator(BaseRepository):
    """标准分类校验器。"""

    async def validate_diagnosis(self, subject: str, diagnosis: dict) -> dict:
        """校验并补齐诊断:key/code 存在性 + level=2;标准 name/type 由字典补齐。

        返回清洗后的 diagnosis(结构与传入一致,仅补齐展示字段)。
        """
        try:
            kp_keys = [kp["key"] for kp in diagnosis.get("knowledge_points", [])]
            err_codes = [e["code"] for e in diagnosis.get("errors", [])]
            kp_meta = await self._load_kp(subject, kp_keys) if kp_keys else {}
            err_meta = await self._load_err(subject, err_codes) if err_codes else {}

            for kp in diagnosis.get("knowledge_points", []):
                meta = kp_meta.get(kp["key"])
                if meta is None or meta["level"] != 2:
                    raise GradingOutputInvalid(f"知识点 {kp['key']} 不是标准 level=2 小类")
                kp["name"] = meta["name"]  # 展示名由字典补齐,不由模型生成
            for e in diagnosis.get("errors", []):
                meta = err_meta.get(e["code"])
                if meta is None or meta["level"] != 2:
                    raise GradingOutputInvalid(f"错误码 {e['code']} 不是标准 level=2 小类")
                e["type"] = meta["name"]
            return diagnosis
        except GradingOutputInvalid:
            raise
        except Exception as exc:  # pragma: no cover
            raise wrap_data_error(exc) from exc

    async def _load_kp(self, subject: str, keys: list[str]) -> dict:
        rows = await self.session.scalars(
            select(KnowledgePoint).where(
                KnowledgePoint.key.in_(keys), KnowledgePoint.subject == subject
            )
        )
        return {r.key: {"name": r.name, "level": r.level} for r in rows}

    async def _load_err(self, subject: str, codes: list[str]) -> dict:
        rows = await self.session.scalars(
            select(ErrorType).where(ErrorType.code.in_(codes), ErrorType.subject == subject)
        )
        return {r.code: {"name": r.name, "level": r.level} for r in rows}
