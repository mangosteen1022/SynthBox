"""别名管理路由"""

import sqlite3
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..models.account import AliasesIn
from ..services.account_service import AccountService

router = APIRouter()


@router.get("/accounts/{account_id}/aliases")
def list_aliases(account_id: int, db: sqlite3.Connection = Depends(get_db)):
    """获取账号别名"""
    service = AccountService(db)
    return service.get_aliases(account_id)


@router.put("/accounts/{account_id}/aliases")
def replace_aliases(account_id: int, body: AliasesIn, db: sqlite3.Connection = Depends(get_db)):
    """替换账号别名"""
    service = AccountService(db)
    return service.replace_aliases(account_id, body.aliases)


@router.post("/accounts/{account_id}/aliases")
def add_aliases(account_id: int, body: AliasesIn, db: sqlite3.Connection = Depends(get_db)):
    """添加账号别名"""
    service = AccountService(db)
    return service.add_aliases(account_id, body.aliases)


@router.delete("/accounts/{account_id}/aliases/{alias}")
def delete_alias(account_id: int, alias: str, db: sqlite3.Connection = Depends(get_db)):
    """删除账号别名"""
    service = AccountService(db)
    return service.delete_alias(account_id, alias)


@router.get("/accounts/by-alias")
def get_account_by_alias(q: str, db: sqlite3.Connection = Depends(get_db)):
    """通过别名查询账号"""
    service = AccountService(db)
    return service.get_accounts_by_alias(q)
