"""Teacher Copilot 可独立运行的业务 API 入口(真实运行)。

用途:不启动完整 DeerFlow Gateway 时也能跑通业务 API(数据库/OCR/LLM/
批改/画像/分析)。完整体系下由 DeerFlow Gateway 挂载同一 router(见 gateway/app.py)。

启动:
    source backend/.env
    uvicorn app.teacher_copilot.api.app:app --port 8100
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.teacher_copilot.config.settings import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("teacher_copilot.app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时初始化数据库(业务事实源),关闭时释放。"""
    from app.teacher_copilot.db.engine import create_all, init_db

    cfg = get_config()
    await init_db(cfg.database_url, echo=cfg.database_echo)
    await create_all()
    logger.info("数据库就绪: %s", cfg.database_url)
    yield
    from app.teacher_copilot.db.engine import dispose_db

    await dispose_db()


def build_app() -> FastAPI:
    """构造 FastAPI 应用(挂载业务路由 + 静态资产目录)。"""
    app = FastAPI(title="AI Teacher Copilot Business API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    from app.teacher_copilot.api.router import router

    app.include_router(router)

    # 静态资产(题目/提交图片,MVP 本地存储)
    import os
    from pathlib import Path

    for route, base in [("/tc-assets/question", "tc-data/question-assets"),
                        ("/tc-assets/submission", "tc-data/submission-assets")]:
        p = Path(base)
        if p.exists():
            app.mount(route, StaticFiles(directory=str(p)), name=route)
    return app


app = build_app()
