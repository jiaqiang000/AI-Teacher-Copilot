"""MySQL 基础仓库:会话管理与异常映射。

业务仓库统一继承 BaseRepository,通过 get_session() 获取异步会话;
DbError 将底层数据源异常映射为 DataSourceError(参考 contracts 错误契约)。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.teacher_copilot.db.engine import get_session
from app.teacher_copilot.errors import DataSourceError


class BaseRepository:
    """仓库基类:提供会话上下文与异常包装。"""

    def __init__(self) -> None:
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        """获取当前仓库会话(需在 async with 中使用)。"""
        if self._session is None:
            raise RuntimeError("请使用 async with repository 上下文")
        return self._session

    async def __aenter__(self) -> "BaseRepository":
        self._session = get_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None


def wrap_data_error(exc: Exception) -> DataSourceError:
    """把数据源底层异常转换为统一业务错误。"""
    return DataSourceError(f"数据源异常: {exc.__class__.__name__}: {exc}")
