"""FastAPI 依赖注入"""

from fastapi import Depends
import sqlite3

from .database import get_db


def get_database() -> sqlite3.Connection:
    """获取数据库连接（依赖注入）"""
    return Depends(get_db)
