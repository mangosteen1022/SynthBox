"""数据库连接和初始化"""

import os
import sqlite3
from pathlib import Path
from typing import Generator

from .config import DB_PATH, SCHEMA_SQL


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    """检查表是否存在"""
    r = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?;", (name,)).fetchone()
    return r is not None


def init_database(conn: sqlite3.Connection):
    """初始化数据库（执行schema.sql）"""
    if not table_exists(conn, "account"):
        with open(SCHEMA_SQL, "r", encoding="utf-8") as f:
            conn.executescript(f.read())


def create_connection() -> sqlite3.Connection:
    """创建数据库连接"""
    init_file = not os.path.exists(DB_PATH)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # SQLite性能优化配置
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA mmap_size=268435456;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA encoding='UTF-8';")

    # 初始化表结构
    if init_file or not table_exists(conn, "account"):
        init_database(conn)

    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI依赖：获取数据库连接"""
    conn = create_connection()
    try:
        yield conn
    finally:
        conn.close()


def begin_tx(db: sqlite3.Connection):
    """开始事务"""
    db.execute("BEGIN IMMEDIATE")


def commit_tx(db: sqlite3.Connection):
    """提交事务"""
    db.commit()


def rollback_tx(db: sqlite3.Connection):
    """回滚事务"""
    try:
        db.rollback()
    except Exception:
        pass
