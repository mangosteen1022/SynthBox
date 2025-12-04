"""服务器配置"""

import os
from pathlib import Path

# 基础路径
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = Path(os.environ.get("STATIC_DIR", BASE_DIR / "static")).resolve()
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "accounts.db")).resolve()
SCHEMA_SQL = Path(os.environ.get("SCHEMA_PATH", BASE_DIR / "schemas" / "schema.sql")).resolve()

# CORS配置
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# API配置
API_TITLE = "Accounts + Mail API (SQLite)"
API_VERSION = "2.0.0"
