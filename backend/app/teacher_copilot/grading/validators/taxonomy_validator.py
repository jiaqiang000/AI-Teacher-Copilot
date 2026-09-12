"""Taxonomy 确定性校验(普通后端代码,不是 Agent/LLM)。

依据参考文档 03 §3.2.5:检查 knowledge_point_key / error_code
- 是否存在于当前学科标准 Taxonomy
- 是否为 level=2 可落库小类(不能直接落 level=1 大类)
- 以及 `knowledge_points` / `errors` 两个必需字段是否存在且为数组(008 FR-002)
非法编码视为 Grading Output Contract 校验失败,不允许入库。

空数组视为合法(全对答案可以没有错误);但**字段缺失不等于空数组**——
"模型没给诊断"必须判为不合格,不能当成"学生没有任何问题"放行。
"""

from __future__ import annotations

from sqlalchemy import select

from app.teacher_copilot.db.models.taxonomy import ErrorType, KnowledgePoint
from app.teacher_copilot.errors import GradingOutputInvalid
from app.teacher_copilot.repositories.mysql.base import BaseRepository, wrap_data_error


class TaxonomyValidator(BaseRepository):
    """标准分类校验器。"""

    # 诊断的两个必需字段:模型必须显式给出(008 FR-002)。
    # 刻意不用 .get(..., []) 取默认空值——那样"模型没给诊断"与"学生没有任何
    # 知识点/错误"无法区分,占位输出会被当成合法结果放行。
    _REQUIRED_FIELDS = ("knowledge_points", "errors")

    async def validate_diagnosis(self, subject: str, diagnosis: dict) -> dict:
        """校验并补齐诊断:必需字段存在性 + key/code 存在性 + level=2;标准 name/type 由字典补齐。

        返回清洗后的 diagnosis(结构与传入一致,仅补齐展示字段)。
        """
        try:
            if not isinstance(diagnosis, dict):
                raise GradingOutputInvalid(
                    f"诊断必须是对象,实际为 {type(diagnosis).__name__}"
                )
            for field_name in self._REQUIRED_FIELDS:
                if field_name not in diagnosis:
                    raise GradingOutputInvalid(
                        f"诊断缺少必需字段 {field_name},判定为不合格输出"
                    )
                if not isinstance(diagnosis[field_name], list):
                    raise GradingOutputInvalid(
                        f"诊断字段 {field_name} 必须是数组,实际为 "
                        f"{type(diagnosis[field_name]).__name__}"
                    )
            # 条目自身的标识字段同属"必需字段存在性":缺失时判为输出不合格,
            # 而不是让 KeyError 被下面的兜底包装成数据源错误(会误导排查方向)。
            for kp in diagnosis["knowledge_points"]:
                if not isinstance(kp, dict) or not kp.get("key"):
                    raise GradingOutputInvalid("知识点条目的必需字段 key 缺失或为空")
            for e in diagnosis["errors"]:
                if not isinstance(e, dict) or not e.get("code"):
                    raise GradingOutputInvalid("错误条目的必需字段 code 缺失或为空")

            kp_keys = [kp["key"] for kp in diagnosis["knowledge_points"]]
            err_codes = [e["code"] for e in diagnosis["errors"]]
            kp_meta = await self._load_kp(subject, kp_keys) if kp_keys else {}
            err_meta = await self._load_err(subject, err_codes) if err_codes else {}

            for kp in diagnosis["knowledge_points"]:
                meta = kp_meta.get(kp["key"])
                if meta is None or meta["level"] != 2:
                    raise GradingOutputInvalid(f"知识点 {kp['key']} 不是标准 level=2 小类")
                kp["name"] = meta["name"]  # 展示名由字典补齐,不由模型生成
            for e in diagnosis["errors"]:
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
