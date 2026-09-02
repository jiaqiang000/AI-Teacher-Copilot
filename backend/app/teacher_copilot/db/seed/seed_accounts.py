"""预置 DeerFlow 登录账号 + 业务身份映射(双角色,T009/T011)。

- 账号写入 DeerFlow 默认库(backend/.deer-flow/data/deerflow.db,Gateway 初始化
  后存在 users 表);密码统一为 xxx123456(与体验指引一致)。
- 业务身份映射写入 AccountLink(业务库 tc-data/teacher_copilot.db):
  DeerFlow user_id → teacher_01 / stu_003,供 identity.py 解析登录态身份。
- 幂等:email 已存在则只补密码与映射,不重复建号。

用法:python3 -m app.teacher_copilot.db.seed.seed_accounts
(需先启动过一次 Gateway / 或确认 deerflow.db 已初始化)
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import sqlite3
import uuid
from pathlib import Path

# 预置账号(email / 密码 / 角色 / 业务类型 / 业务 ID / 说明)
ACCOUNTS = [
    ("teacher@demo.com", "teacher123456", "user", "teacher", "teacher_01", "教师:王老师(演示账号)"),
    ("student@demo.com", "student123456", "user", "student", "stu_003", "学生:张三(演示账号)"),
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


def _ensure_account_link_table(con: sqlite3.Connection) -> None:
    """account_link 表由 ORM create_all 在 Gateway 启动时创建;脚本兜底自建。"""
    con.execute(
        "CREATE TABLE IF NOT EXISTS account_link ("
        " user_id VARCHAR(64) PRIMARY KEY,"
        " biz_type VARCHAR(16) NOT NULL,"
        " biz_id VARCHAR(64) NOT NULL,"
        " UNIQUE (biz_type, biz_id))"
    )


async def seed_accounts() -> None:
    """幂等创建 DeerFlow 登录账号并写入业务映射。"""
    from app.gateway.auth.password import hash_password

    db_path = _locate_db()
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    # 业务库(AccountLink)
    tc_db = Path("tc-data/teacher_copilot.db")
    tc_con = sqlite3.connect(str(tc_db))
    _ensure_account_link_table(tc_con)
    tc_cur = tc_con.cursor()

    for email, password, role, biz_type, biz_id, desc in ACCOUNTS:
        row = cur.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            user_id = row[0]
            cur.execute("UPDATE users SET password_hash = ? WHERE email = ?",
                        (hash_password(password), email))
            print(f"账号已存在,补同步密码: {email}({desc})")
        else:
            user_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO users (id, email, password_hash, system_role, needs_setup, "
                "created_at, token_version) VALUES (?, ?, ?, ?, 0, ?, 0)",
                (user_id, email, hash_password(password), role, datetime.utcnow().isoformat()),
            )
            print(f"已创建账号: {email}({desc})")

        # 幂等写业务映射
        tc_cur.execute(
            "INSERT OR IGNORE INTO account_link (user_id, biz_type, biz_id) VALUES (?, ?, ?)",
            (user_id, biz_type, biz_id),
        )
        print(f"  业务映射: {email} → {biz_type}:{biz_id}")

    con.commit()
    con.close()
    tc_con.commit()
    tc_con.close()
    print("账号与映射预置完成")


if __name__ == "__main__":
    asyncio.run(seed_accounts())
