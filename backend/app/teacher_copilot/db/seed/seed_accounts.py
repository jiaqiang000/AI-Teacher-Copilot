"""预置 DeerFlow 登录账号(教师/学生双角色,T009)。

- 账号写入 DeerFlow 默认库(backend/.deer-flow/data/deerflow.db,Gateway 初始化
  后存在 users 表);业务 teacher/student 由 demo seed 提供。
- 密码使用 DeerFlow 官方哈希(app.gateway.auth.password.hash_password)。
- 幂等:email 已存在则跳过。

用法:python3 -m app.teacher_copilot.db.seed.seed_accounts
(需先启动过一次 Gateway / 或确认 deerflow.db 已初始化)
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import sqlite3
from pathlib import Path

# 预置账号(email / 业务映射说明)
ACCOUNTS = [
    ("teacher@demo.com", "teacher123", "user", "teacher_01"),   # 教师:王老师
    ("student@demo.com", "student123", "user", "stu_003"),      # 学生:张三
]


def _locate_db() -> Path:
    """定位 DeerFlow 默认库(优先 backend/.deer-flow/data/deerflow.db)。"""
    candidates = [
        Path(".deer-flow/data/deerflow.db"),
        Path("deer-flow-backend-data/deerflow.db"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "未找到 DeerFlow 数据库(backend/.deer-flow/data/deerflow.db);"
        "请先启动一次 Gateway(make dev 或 uvicorn app.gateway.app:app)。"
    )


async def seed_accounts() -> None:
    """幂等创建 DeerFlow 登录账号。"""
    from app.gateway.auth.password import hash_password

    db_path = _locate_db()
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    for email, password, role, biz_id in ACCOUNTS:
        exists = cur.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            print(f"账号已存在,跳过: {email}")
            continue
        import uuid

        cur.execute(
            "INSERT INTO users (id, email, password_hash, system_role, needs_setup, "
            "created_at, token_version) "
            "VALUES (?, ?, ?, ?, 0, ?, 0)",
            (str(uuid.uuid4()), email, hash_password(password), role,
             datetime.utcnow().isoformat()),
        )
        print(f"已创建账号: {email} → {biz_id}")
    con.commit()
    con.close()
    print("账号预置完成")


if __name__ == "__main__":
    asyncio.run(seed_accounts())
