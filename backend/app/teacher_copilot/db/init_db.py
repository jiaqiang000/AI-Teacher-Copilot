"""数据库初始化脚本。

用法(在 deer-flow/backend 目录,确保依赖可导入):
    python -m app.teacher_copilot.db.init_db

作用:按 data-model.md 建表;可选 --seed 写入标准分类字典与题库种子。
"""

from __future__ import annotations

import asyncio
import sys

from app.teacher_copilot.config.settings import get_config
from app.teacher_copilot.db.engine import create_all, dispose_db, init_db
from app.teacher_copilot.db.seed.question_bank import seed_question_bank
from app.teacher_copilot.db.seed.taxonomy import seed_taxonomy


async def _run(seed: bool) -> None:
    cfg = get_config()
    await init_db(cfg.database_url, echo=cfg.database_echo)
    # 先导入所有模型,确保 metadata 注册完整
    from app.teacher_copilot.db import models  # noqa: F401

    await create_all()
    if seed:
        await seed_taxonomy()
        await seed_question_bank()
    await dispose_db()
    print(f"数据库初始化完成(url={cfg.database_url}, seed={seed})")


def main() -> None:
    seed = "--seed" in sys.argv[1:]
    asyncio.run(_run(seed))


if __name__ == "__main__":
    main()
