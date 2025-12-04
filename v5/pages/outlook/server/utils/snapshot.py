"""账号版本快照管理"""

import json
import sqlite3
from typing import Dict, List, Optional

from fastapi import HTTPException


def fetch_current_state(db: sqlite3.Connection, account_id: int) -> dict:
    """获取账号当前状态（用于比较变化）"""
    from .normalizers import (
        norm_email,
        norm_name,
        norm_birthday,
        norm_email_list,
        norm_phone_digits_list,
        norm_alias_list,
    )

    a = db.execute(
        "SELECT id,email,password,status,username,birthday,version FROM account WHERE id=?", (account_id,)
    ).fetchone()

    if not a:
        raise HTTPException(404, "account not found")

    rec_emails = [
        r["email"]
        for r in db.execute("SELECT email FROM account_recovery_email WHERE account_id=? ORDER BY email", (account_id,))
    ]

    rec_phones = [
        r["phone"]
        for r in db.execute("SELECT phone FROM account_recovery_phone WHERE account_id=? ORDER BY phone", (account_id,))
    ]

    aliases = [
        r["alias"]
        for r in db.execute("SELECT alias FROM account_alias WHERE account_id=? ORDER BY alias", (account_id,))
    ]

    return {
        "id": a["id"],
        "email": a["email"],
        "email_norm": norm_email(a["email"]),
        "password": a["password"],
        "status": a["status"],
        "username": a["username"],
        "username_norm": norm_name(a["username"]),
        "birthday": a["birthday"],
        "birthday_norm": norm_birthday(a["birthday"]),
        "version": a["version"],
        "rec_emails": rec_emails,
        "rec_emails_norm": norm_email_list(rec_emails),
        "rec_phones": rec_phones,
        "rec_phones_norm": norm_phone_digits_list(rec_phones),
        "aliases": aliases,
        "aliases_norm": norm_alias_list(aliases),
    }


def insert_version_snapshot(db: sqlite3.Connection, account_id: int, note: Optional[str], who: Optional[str]):
    """插入版本快照到 account_version 表"""
    a = db.execute(
        "SELECT id, email, password, status, username, birthday, version FROM account WHERE id=?", (account_id,)
    ).fetchone()

    if not a:
        raise HTTPException(404, f"account {account_id} not found when snapshot")

    rec_emails = [
        r["email"]
        for r in db.execute("SELECT email FROM account_recovery_email WHERE account_id=? ORDER BY email", (account_id,))
    ]

    rec_phones = [
        r["phone"]
        for r in db.execute("SELECT phone FROM account_recovery_phone WHERE account_id=? ORDER BY phone", (account_id,))
    ]

    aliases = [
        r["alias"]
        for r in db.execute("SELECT alias FROM account_alias WHERE account_id=? ORDER BY alias", (account_id,))
    ]

    db.execute(
        """
        INSERT INTO account_version(
            account_id, version, email, password, status, username, birthday,
            recovery_emails_json, recovery_phones_json, aliases_json, note, created_by
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            a["id"],
            a["version"],
            a["email"],
            a["password"],
            a["status"],
            a["username"],
            a["birthday"],
            json.dumps(rec_emails, ensure_ascii=False),
            json.dumps(rec_phones, ensure_ascii=False),
            json.dumps(aliases, ensure_ascii=False),
            note,
            who,
        ),
    )


def get_recovery_maps(db: sqlite3.Connection, ids: List[int]):
    """获取辅助信息映射（批量查询优化）"""
    emails_map = {i: [] for i in ids}
    phones_map = {i: [] for i in ids}

    if not ids:
        return emails_map, phones_map

    qmarks = ",".join(["?"] * len(ids))

    for row in db.execute(f"SELECT account_id, email FROM account_recovery_email WHERE account_id IN ({qmarks})", ids):
        emails_map.setdefault(row["account_id"], []).append(row["email"])

    for row in db.execute(f"SELECT account_id, phone FROM account_recovery_phone WHERE account_id IN ({qmarks})", ids):
        phones_map.setdefault(row["account_id"], []).append(row["phone"])

    return emails_map, phones_map
