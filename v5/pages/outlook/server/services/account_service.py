"""账号业务逻辑服务"""

import sqlite3
import json
import csv
import io
from typing import List, Optional, Dict, Any

from fastapi import HTTPException

from ..database import begin_tx, commit_tx, rollback_tx
from ..models.account import AccountCreate, AccountUpdate
from ..utils.normalizers import (
    normalize_list,
    normalize_aliases,
    norm_email,
    norm_name,
    norm_birthday,
    norm_email_list,
    norm_phone_digits_list,
    norm_alias_list,
)
from ..utils.snapshot import fetch_current_state, insert_version_snapshot, get_recovery_maps


class AccountService:
    """账号服务"""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def batch_create(self, items: List[AccountCreate]) -> Dict[str, Any]:
        """批量创建账号"""
        result = {"success": [], "errors": []}

        for idx, it in enumerate(items):
            try:
                begin_tx(self.db)

                # 插入主表
                cur = self.db.execute(
                    "INSERT INTO account(email, password, status, username, birthday) VALUES (?,?,?,?,?)",
                    (
                        it.email.strip(),
                        it.password,
                        it.status,
                        (it.username or "").strip() or None,
                        norm_birthday(it.birthday) or None,
                    ),
                )
                acc_id = cur.lastrowid

                # 插入辅助邮箱
                rem = normalize_list(it.recovery_emails)
                if rem:
                    self.db.executemany(
                        "INSERT OR IGNORE INTO account_recovery_email(account_id, email) VALUES (?,?)",
                        [(acc_id, e) for e in rem],
                    )

                # 插入辅助电话
                rpm = normalize_list(it.recovery_phones)
                if rpm:
                    self.db.executemany(
                        "INSERT OR IGNORE INTO account_recovery_phone(account_id, phone) VALUES (?,?)",
                        [(acc_id, p) for p in rpm],
                    )

                # 插入别名
                als = normalize_aliases(it.aliases)
                if als:
                    self.db.executemany(
                        "INSERT OR IGNORE INTO account_alias(account_id, alias) VALUES (?,?)",
                        [(acc_id, a) for a in als],
                    )

                # 插入版本快照
                insert_version_snapshot(self.db, acc_id, it.note or "初始导入", it.created_by)

                commit_tx(self.db)
                result["success"].append({"id": acc_id, "email": it.email})

            except Exception as e:
                rollback_tx(self.db)
                result["errors"].append({"index": idx, "error": str(e)})

        return result

    def batch_update(self, items: List[AccountUpdate]) -> Dict[str, Any]:
        """批量更新账号"""
        result = {"success": [], "errors": []}

        for idx, it in enumerate(items):
            try:
                # 定位账号
                row = None
                if it.id is not None:
                    row = self.db.execute("SELECT * FROM account WHERE id=?", (it.id,)).fetchone()
                elif it.lookup_email:
                    row = self.db.execute(
                        "SELECT * FROM account WHERE email = ? COLLATE NOCASE", (it.lookup_email.strip(),)
                    ).fetchone()
                else:
                    raise HTTPException(422, "id 或 lookup_email 至少提供一个")

                if not row:
                    raise HTTPException(404, "account not found")

                acc_id = row["id"]
                cur = fetch_current_state(self.db, acc_id)

                # 准备新值
                new_email = it.email.strip() if it.email else cur["email"]
                new_password = it.password if it.password is not None else cur["password"]
                new_status = it.status if it.status is not None else cur["status"]
                new_username = norm_name(it.username if it.username is not None else cur["username"])
                new_birthday = norm_birthday(it.birthday if it.birthday is not None else cur["birthday"])

                # 多值字段
                if it.recovery_emails is not None:
                    rec_emails_raw = normalize_list(it.recovery_emails)
                    rec_emails_norm = norm_email_list(rec_emails_raw)
                else:
                    rec_emails_raw = cur["rec_emails"]
                    rec_emails_norm = cur["rec_emails_norm"]

                if it.recovery_phones is not None:
                    rec_phones_raw = normalize_list(it.recovery_phones)
                    rec_phones_norm = norm_phone_digits_list(rec_phones_raw)
                else:
                    rec_phones_raw = cur["rec_phones"]
                    rec_phones_norm = cur["rec_phones_norm"]

                if it.aliases is not None:
                    aliases_raw = normalize_aliases(it.aliases)
                    aliases_norm = norm_alias_list(aliases_raw)
                else:
                    aliases_raw = cur["aliases"]
                    aliases_norm = cur["aliases_norm"]

                # 无变化判断
                no_change = (
                    norm_email(new_email) == cur["email_norm"]
                    and new_password == cur["password"]
                    and new_status == cur["status"]
                    and norm_name(new_username) == cur["username_norm"]
                    and norm_birthday(new_birthday) == cur["birthday_norm"]
                    and rec_emails_norm == cur["rec_emails_norm"]
                    and rec_phones_norm == cur["rec_phones_norm"]
                    and aliases_norm == cur["aliases_norm"]
                )

                if no_change:
                    result["success"].append(
                        {"id": acc_id, "version": cur["version"], "email": cur["email"], "no_change": True}
                    )
                    continue

                # 更新
                begin_tx(self.db)

                self.db.execute(
                    """
                    UPDATE account SET
                      email=?, password=?, status=?, username=?, birthday=?,
                      version=version+1, updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (new_email, new_password, new_status, new_username or None, new_birthday or None, acc_id),
                )

                # 子表重建
                if it.recovery_emails is not None:
                    self.db.execute("DELETE FROM account_recovery_email WHERE account_id=?", (acc_id,))
                    if rec_emails_raw:
                        self.db.executemany(
                            "INSERT OR IGNORE INTO account_recovery_email(account_id, email) VALUES (?,?)",
                            [(acc_id, e) for e in rec_emails_raw],
                        )

                if it.recovery_phones is not None:
                    self.db.execute("DELETE FROM account_recovery_phone WHERE account_id=?", (acc_id,))
                    if rec_phones_raw:
                        self.db.executemany(
                            "INSERT OR IGNORE INTO account_recovery_phone(account_id, phone) VALUES (?,?)",
                            [(acc_id, p) for p in rec_phones_raw],
                        )

                if it.aliases is not None:
                    self.db.execute("DELETE FROM account_alias WHERE account_id=?", (acc_id,))
                    if aliases_raw:
                        self.db.executemany(
                            "INSERT OR IGNORE INTO account_alias(account_id, alias) VALUES (?,?)",
                            [(acc_id, a) for a in aliases_raw],
                        )

                insert_version_snapshot(self.db, acc_id, it.note or "更新", it.created_by)
                commit_tx(self.db)

                v = self.db.execute("SELECT version FROM account WHERE id=?", (acc_id,)).fetchone()["version"]
                result["success"].append({"id": acc_id, "version": v, "email": new_email, "no_change": False})

            except HTTPException as he:
                result["errors"].append({"index": idx, "error": he.detail})
            except Exception as e:
                rollback_tx(self.db)
                result["errors"].append({"index": idx, "error": str(e)})

        return result

    def list_accounts(self, page: int, size: int, **filters) -> Dict[str, Any]:
        """获取账号列表"""
        where, args = ["1=1"], []

        if filters.get("status"):
            where.append("a.status=?")
            args.append(filters["status"])

        if filters.get("email_contains"):
            where.append("a.email LIKE ?")
            args.append(f"%{filters['email_contains']}%")

        if filters.get("updated_after"):
            where.append("a.updated_at >= ?")
            args.append(filters["updated_after"])

        if filters.get("updated_before"):
            where.append("a.updated_at <= ?")
            args.append(filters["updated_before"])

        if filters.get("recovery_email_contains"):
            where.append("EXISTS (SELECT 1 FROM account_recovery_email e WHERE e.account_id=a.id AND e.email LIKE ?)")
            args.append(f"%{filters['recovery_email_contains']}%")

        if filters.get("recovery_phone"):
            where.append("EXISTS (SELECT 1 FROM account_recovery_phone p WHERE p.account_id=a.id AND p.phone = ?)")
            args.append(filters["recovery_phone"])

        if filters.get("alias_contains"):
            where.append("EXISTS (SELECT 1 FROM account_alias aa WHERE aa.account_id=a.id AND aa.alias LIKE ?)")
            args.append(f"%{filters['alias_contains'].lower()}%")

        if filters.get("note_contains"):
            where.append("EXISTS (SELECT 1 FROM account_version v WHERE v.account_id=a.id AND v.note LIKE ?)")
            args.append(f"%{filters['note_contains']}%")

        where_sql = " AND ".join(where)

        # 获取总数
        total = self.db.execute(f"SELECT COUNT(*) c FROM account a WHERE {where_sql}", args).fetchone()["c"]

        # 获取数据
        offset = (page - 1) * size
        rows = self.db.execute(
            f"""
            SELECT a.* FROM account a
            WHERE {where_sql}
            ORDER BY a.updated_at DESC, a.id ASC
            LIMIT ? OFFSET ?
            """,
            args + [size, offset],
        ).fetchall()

        # 批量查询辅助信息
        ids = [r["id"] for r in rows]
        e_map, p_map = get_recovery_maps(self.db, ids)

        # 查询别名
        als_map: Dict[int, List[str]] = {i: [] for i in ids}
        if ids:
            qmarks = ",".join(["?"] * len(ids))
            for row in self.db.execute(
                f"SELECT account_id, alias FROM account_alias WHERE account_id IN ({qmarks}) ORDER BY alias", ids
            ):
                als_map.setdefault(row["account_id"], []).append(row["alias"])

        # 组装结果
        items = []
        for r in rows:
            d = dict(r)
            d["recovery_emails"] = e_map.get(r["id"], [])
            d["recovery_phones"] = p_map.get(r["id"], [])
            d["aliases"] = als_map.get(r["id"], [])
            items.append(d)

        return {"total": total, "page": page, "size": size, "pages": (total + size - 1) // size, "items": items}

    def get_account(self, account_id: int) -> Dict[str, Any]:
        """获取单个账号"""
        r = self.db.execute("SELECT * FROM account WHERE id=?", (account_id,)).fetchone()
        if not r:
            raise HTTPException(404, "account not found")

        emails = [
            x["email"]
            for x in self.db.execute("SELECT email FROM account_recovery_email WHERE account_id=?", (account_id,))
        ]
        phones = [
            x["phone"]
            for x in self.db.execute("SELECT phone FROM account_recovery_phone WHERE account_id=?", (account_id,))
        ]
        aliases = [
            x["alias"]
            for x in self.db.execute("SELECT alias FROM account_alias WHERE account_id=? ORDER BY alias", (account_id,))
        ]

        d = dict(r)
        d["recovery_emails"] = emails
        d["recovery_phones"] = phones
        d["aliases"] = aliases
        return d

    def get_history(self, account_id: int, page: int, size: int) -> Dict[str, Any]:
        """获取账号历史版本"""
        total = self.db.execute("SELECT COUNT(*) c FROM account_version WHERE account_id=?", (account_id,)).fetchone()[
            "c"
        ]

        offset = (page - 1) * size
        rows = self.db.execute(
            """
            SELECT version, email, password, status, username, birthday,
                   recovery_emails_json, recovery_phones_json, aliases_json,
                   note, created_by, created_at
            FROM account_version
            WHERE account_id=?
            ORDER BY version DESC
            LIMIT ? OFFSET ?
            """,
            (account_id, size, offset),
        ).fetchall()

        items = []
        for r in rows:
            items.append(
                {
                    "version": r["version"],
                    "email": r["email"],
                    "password": r["password"],
                    "status": r["status"],
                    "username": r["username"],
                    "birthday": r["birthday"],
                    "recovery_emails": json.loads(r["recovery_emails_json"] or "[]"),
                    "recovery_phones": json.loads(r["recovery_phones_json"] or "[]"),
                    "aliases": json.loads(r["aliases_json"] or "[]"),
                    "note": r["note"],
                    "created_by": r["created_by"],
                    "created_at": r["created_at"],
                }
            )

        return {"total": total, "page": page, "size": size, "pages": (total + size - 1) // size, "items": items}

    def update_status(self, account_id: int, status: str) -> Dict[str, Any]:
        """更新账号状态"""
        r = self.db.execute("SELECT id FROM account WHERE id=?", (account_id,)).fetchone()
        if not r:
            raise HTTPException(404, "account not found")

        self.db.execute(
            "UPDATE account SET status=?, updated_at=datetime('now') WHERE id=?",
            (status, account_id),
        )

        return {"id": account_id, "status": status}

    def restore_version(
        self, account_id: int, version: int, note: Optional[str], created_by: Optional[str]
    ) -> Dict[str, Any]:
        """恢复账号版本"""
        # 获取历史版本
        t = self.db.execute(
            """
            SELECT email, password, status, username, birthday,
                   recovery_emails_json, recovery_phones_json, aliases_json
            FROM account_version
            WHERE account_id=? AND version=?
            """,
            (account_id, version),
        ).fetchone()

        if not t:
            raise HTTPException(404, "history version not found")

        cur = fetch_current_state(self.db, account_id)

        tgt_emails = json.loads(t["recovery_emails_json"] or "[]")
        tgt_phones = json.loads(t["recovery_phones_json"] or "[]")
        tgt_aliases = json.loads(t["aliases_json"] or "[]")

        # 无变化判断
        no_change = (
            norm_email(t["email"]) == cur["email_norm"]
            and t["password"] == cur["password"]
            and t["status"] == cur["status"]
            and norm_name(t["username"]) == cur["username_norm"]
            and norm_birthday(t["birthday"]) == cur["birthday_norm"]
            and norm_email_list(tgt_emails) == cur["rec_emails_norm"]
            and norm_phone_digits_list(tgt_phones) == cur["rec_phones_norm"]
            and norm_alias_list(tgt_aliases) == cur["aliases_norm"]
        )

        if no_change:
            return {"id": account_id, "version": cur["version"], "no_change": True}

        try:
            begin_tx(self.db)

            # 覆盖主表
            self.db.execute(
                """
                UPDATE account SET
                  email=?, password=?, status=?, username=?, birthday=?,
                  version=version+1, updated_at=datetime('now')
                WHERE id=?
                """,
                (
                    t["email"],
                    t["password"],
                    t["status"],
                    norm_name(t["username"]) or None,
                    norm_birthday(t["birthday"]) or None,
                    account_id,
                ),
            )

            # 重建子表
            self.db.execute("DELETE FROM account_recovery_email WHERE account_id=?", (account_id,))
            if tgt_emails:
                self.db.executemany(
                    "INSERT OR IGNORE INTO account_recovery_email(account_id, email) VALUES (?,?)",
                    [(account_id, e) for e in tgt_emails],
                )

            self.db.execute("DELETE FROM account_recovery_phone WHERE account_id=?", (account_id,))
            if tgt_phones:
                self.db.executemany(
                    "INSERT OR IGNORE INTO account_recovery_phone(account_id, phone) VALUES (?,?)",
                    [(account_id, p) for p in tgt_phones],
                )

            self.db.execute("DELETE FROM account_alias WHERE account_id=?", (account_id,))
            if tgt_aliases:
                self.db.executemany(
                    "INSERT OR IGNORE INTO account_alias(account_id, alias) VALUES (?,?)",
                    [(account_id, a) for a in tgt_aliases],
                )

            insert_version_snapshot(self.db, account_id, note or f"恢复自版本 {version}", created_by)
            commit_tx(self.db)

        except Exception as e:
            rollback_tx(self.db)
            raise HTTPException(500, f"restore failed: {e}")

        new_ver = self.db.execute("SELECT version FROM account WHERE id=?", (account_id,)).fetchone()["version"]
        return {"id": account_id, "version": new_ver, "no_change": False}

    def delete_account(self, account_id: int) -> Dict[str, Any]:
        """删除账号"""
        r = self.db.execute("SELECT id FROM account WHERE id=?", (account_id,)).fetchone()
        if not r:
            raise HTTPException(404, "account not found")

        try:
            begin_tx(self.db)
            self.db.execute("DELETE FROM account WHERE id=?", (account_id,))
            commit_tx(self.db)
        except Exception as e:
            rollback_tx(self.db)
            raise HTTPException(500, f"delete failed: {e}")

        return {"id": account_id, "deleted": True}

    def export_to_csv(self, **filters) -> str:
        """导出为CSV"""
        # 使用list_accounts获取所有数据（不分页）
        where, args = ["1=1"], []

        # 应用过滤条件（同list_accounts）
        if filters.get("status"):
            where.append("a.status=?")
            args.append(filters["status"])
        if filters.get("email_contains"):
            where.append("a.email LIKE ?")
            args.append(f"%{filters['email_contains']}%")
        # ... 其他过滤条件省略（同list_accounts）

        where_sql = " AND ".join(where)

        rows = self.db.execute(
            f"SELECT a.* FROM account a WHERE {where_sql} ORDER BY a.updated_at DESC, a.id ASC", args
        ).fetchall()

        ids = [r["id"] for r in rows]
        e_map, p_map = get_recovery_maps(self.db, ids)

        # 查询别名
        als_map: Dict[int, List[str]] = {i: [] for i in ids}
        if ids:
            qmarks = ",".join(["?"] * len(ids))
            for row in self.db.execute(
                f"SELECT account_id, alias FROM account_alias WHERE account_id IN ({qmarks}) ORDER BY alias", ids
            ):
                als_map.setdefault(row["account_id"], []).append(row["alias"])

        # 生成CSV
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "id",
                "email",
                "username",
                "birthday",
                "password",
                "status",
                "version",
                "created_at",
                "updated_at",
                "recovery_emails",
                "recovery_phones",
                "aliases",
            ]
        )

        for r in rows:
            rec_e = ";".join(e_map.get(r["id"], []))
            rec_p = ";".join(p_map.get(r["id"], []))
            als = ";".join(als_map.get(r["id"], []))
            w.writerow(
                [
                    r["id"],
                    r["email"],
                    r["username"] or "",
                    r["birthday"] or "",
                    r["password"],
                    r["status"],
                    r["version"],
                    r["created_at"],
                    r["updated_at"],
                    rec_e,
                    rec_p,
                    als,
                ]
            )

        csv_text = buf.getvalue()
        return "\ufeff" + csv_text  # BOM for Excel

    # ==================== 别名管理 ====================
    def get_aliases(self, account_id: int) -> Dict[str, Any]:
        """获取别名"""
        r = self.db.execute("SELECT id FROM account WHERE id=?", (account_id,)).fetchone()
        if not r:
            raise HTTPException(404, "account not found")

        rows = self.db.execute(
            "SELECT alias FROM account_alias WHERE account_id=? ORDER BY alias_lc, alias", (account_id,)
        ).fetchall()

        return {"account_id": account_id, "aliases": [x["alias"] for x in rows]}

    def replace_aliases(self, account_id: int, aliases: List[str]) -> Dict[str, Any]:
        """替换别名"""
        r = self.db.execute("SELECT id FROM account WHERE id=?", (account_id,)).fetchone()
        if not r:
            raise HTTPException(404, "account not found")

        new_aliases = normalize_aliases(aliases)

        try:
            begin_tx(self.db)
            self.db.execute("DELETE FROM account_alias WHERE account_id=?", (account_id,))
            if new_aliases:
                self.db.executemany(
                    "INSERT OR IGNORE INTO account_alias(account_id, alias) VALUES (?,?)",
                    [(account_id, a) for a in new_aliases],
                )
            self.db.execute(
                "UPDATE account SET version=version+1, updated_at=datetime('now') WHERE id=?", (account_id,)
            )
            insert_version_snapshot(self.db, account_id, "替换别名", "api")
            commit_tx(self.db)
        except Exception as e:
            rollback_tx(self.db)
            raise HTTPException(500, f"replace aliases failed: {e}")

        rows = self.db.execute(
            "SELECT alias FROM account_alias WHERE account_id=? ORDER BY alias", (account_id,)
        ).fetchall()

        return {"account_id": account_id, "aliases": [x["alias"] for x in rows]}

    def add_aliases(self, account_id: int, aliases: List[str]) -> Dict[str, Any]:
        """添加别名"""
        r = self.db.execute("SELECT id FROM account WHERE id=?", (account_id,)).fetchone()
        if not r:
            raise HTTPException(404, "account not found")

        add_list = normalize_aliases(aliases)

        try:
            begin_tx(self.db)
            if add_list:
                self.db.executemany(
                    "INSERT OR IGNORE INTO account_alias(account_id, alias) VALUES (?,?)",
                    [(account_id, a) for a in add_list],
                )
            self.db.execute(
                "UPDATE account SET version=version+1, updated_at=datetime('now') WHERE id=?", (account_id,)
            )
            insert_version_snapshot(self.db, account_id, "新增别名", "api")
            commit_tx(self.db)
        except Exception as e:
            rollback_tx(self.db)
            raise HTTPException(500, f"add aliases failed: {e}")

        rows = self.db.execute(
            "SELECT alias FROM account_alias WHERE account_id=? ORDER BY alias", (account_id,)
        ).fetchall()

        return {"account_id": account_id, "aliases": [x["alias"] for x in rows]}

    def delete_alias(self, account_id: int, alias: str) -> Dict[str, Any]:
        """删除别名"""
        r = self.db.execute("SELECT id FROM account WHERE id=?", (account_id,)).fetchone()
        if not r:
            raise HTTPException(404, "account not found")

        try:
            begin_tx(self.db)
            self.db.execute(
                "DELETE FROM account_alias WHERE account_id=? AND alias = ? COLLATE NOCASE", (account_id, alias)
            )
            self.db.execute(
                "UPDATE account SET version=version+1, updated_at=datetime('now') WHERE id=?", (account_id,)
            )
            insert_version_snapshot(self.db, account_id, f"删除别名: {alias}", "api")
            commit_tx(self.db)
        except Exception as e:
            rollback_tx(self.db)
            raise HTTPException(500, f"delete alias failed: {e}")

        rows = self.db.execute(
            "SELECT alias FROM account_alias WHERE account_id=? ORDER BY alias", (account_id,)
        ).fetchall()

        return {"account_id": account_id, "aliases": [x["alias"] for x in rows]}

    def get_accounts_by_alias(self, alias: str) -> Dict[str, Any]:
        """通过别名查询账号"""
        rows = self.db.execute(
            """
            SELECT a.*
            FROM account a
            JOIN account_alias aa ON aa.account_id = a.id
            WHERE aa.alias = ? COLLATE NOCASE
            """,
            (alias,),
        ).fetchall()

        items = []
        for a in rows:
            acc = dict(a)
            als = [
                r["alias"]
                for r in self.db.execute(
                    "SELECT alias FROM account_alias WHERE account_id=? ORDER BY alias", (a["id"],)
                )
            ]
            acc["aliases"] = als
            items.append(acc)

        return {"items": items}
