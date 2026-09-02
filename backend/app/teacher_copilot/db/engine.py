"""Teacher Copilot 数据层基础设施。

复用 SQLAlchemy(async)已有依赖(deerflow-harness 已含 sqlalchemy[asyncio]);
业务表使用独立 metadata(与 DeerFlow Harness 自身的模型表分离,避免耦合)。
数据库 URL 默认 SQLite(开发演示零依赖),可切换 MySQL 异步方言(如
mysql+asyncmy://...),参见 config/settings.py。
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# 业务表命名规则:统一 snake_case、主键 *_id 字符串(与参考设计一致)
metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})


class Base(DeclarativeBase):
    """业务 ORM 基类(所有 Teacher Copilot 表继承)。"""
    metadata = metadata


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db(database_url: str, *, echo: bool = False) -> None:
    """初始化全局 async engine(幂等,可重复调用)。"""
    global _engine, _session_factory
    if _engine is not None:
        return
    _engine = create_async_engine(database_url, echo=echo)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


def get_session() -> AsyncSession:
    """获取业务会话(必须在 init_db 之后使用)。"""
    if _session_factory is None:
        raise RuntimeError("init_db() 尚未初始化,请先调用 init_db()")
    return _session_factory()


async def create_all() -> None:
    """按 metadata 自动建表(开发/演示用;正式迁移可改用迁移工具)。"""
    if _engine is None:
        raise RuntimeError("init_db() 尚未初始化")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    """释放全局引擎(用于测试/优雅关停)。"""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
