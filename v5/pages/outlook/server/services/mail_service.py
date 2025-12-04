"""邮件业务逻辑服务"""

import sqlite3
import traceback
from typing import Optional, List, Dict, Any

from fastapi import HTTPException

from ..database import begin_tx, commit_tx, rollback_tx
from ..models.mail import MailBodyIn, MailMessageCreate, MailMessageUpdate, MailSearchRequest, MailMessageBatchCreate
from ..utils.normalizers import normalize_list


class MailService:
    """邮件服务"""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def create_message(self, it: MailMessageCreate) -> Dict[str, Any]:
        """创建邮件消息"""
        to_all = normalize_list(it.to) + normalize_list(it.cc) + normalize_list(it.bcc)
        seen, seq = set(), []
        for a in to_all:
            if a not in seen:
                seen.add(a)
                seq.append(a)
        to_joined = ";".join(seq)

        labels_joined = ";".join(normalize_list(it.labels))
        attachments_count = len(it.attachments or [])

        try:
            begin_tx(self.db)

            cur = self.db.execute(
                """
                INSERT INTO mail_message(
                    account_id, msg_uid, msg_id, subject, from_addr, to_joined,
                    folder_id, labels_joined, sent_at, received_at, size_bytes,
                    attachments_count, flags, snippet, created_at, updated_at
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                """,
                (
                    it.account_id,
                    it.msg_uid,
                    it.msg_id,
                    it.subject or "",
                    it.from_addr or "",
                    to_joined,
                    it.folder_id or "",
                    labels_joined,
                    it.sent_at,
                    it.received_at,
                    it.size_bytes,
                    attachments_count,
                    it.flags or 0,
                    it.snippet,
                ),
            )
            mid = cur.lastrowid

            # 插入收件人明细
            if it.to:
                self.db.executemany(
                    "INSERT INTO mail_recipient(message_id, account_id, kind, addr) VALUES (?,?,?,?)",
                    [(mid, it.account_id, "to", a) for a in normalize_list(it.to)],
                )
            if it.cc:
                self.db.executemany(
                    "INSERT INTO mail_recipient(message_id, account_id, kind, addr) VALUES (?,?,?,?)",
                    [(mid, it.account_id, "cc", a) for a in normalize_list(it.cc)],
                )
            if it.bcc:
                self.db.executemany(
                    "INSERT INTO mail_recipient(message_id, account_id, kind, addr) VALUES (?,?,?,?)",
                    [(mid, it.account_id, "bcc", a) for a in normalize_list(it.bcc)],
                )

            # 插入正文
            if it.body and (it.body.headers or it.body.body_plain or it.body.body_html):
                self.db.execute(
                    "INSERT OR REPLACE INTO mail_body(message_id, headers, body_plain, body_html) VALUES (?,?,?,?)",
                    (mid, it.body.headers, it.body.body_plain, it.body.body_html),
                )

            # 插入附件
            if it.attachments:
                self.db.executemany(
                    "INSERT INTO mail_attachment(message_id, account_id, storage_url) VALUES (?,?,?)",
                    [(mid, it.account_id, url) for url in it.attachments],
                )

                real_cnt = self.db.execute(
                    "SELECT COUNT(*) c FROM mail_attachment WHERE message_id=?", (mid,)
                ).fetchone()["c"]

                if real_cnt != attachments_count:
                    self.db.execute(
                        "UPDATE mail_message SET attachments_count=?, updated_at=datetime('now') WHERE id=?",
                        (real_cnt, mid),
                    )

            commit_tx(self.db)

        except Exception as e:
            rollback_tx(self.db)
            raise HTTPException(500, f"insert mail failed: {e}")

        return {"id": mid}

    def update_message(self, message_id: int, body: MailMessageUpdate) -> Dict[str, Any]:
        """更新邮件消息"""
        m = self.db.execute("SELECT * FROM mail_message WHERE id=?", (message_id,)).fetchone()
        if not m:
            raise HTTPException(404, "message not found")

        fields, args = [], []

        if body.folder_id is not None:
            fields.append("folder_id=?")
            args.append(body.folder_id)
        if body.labels is not None:
            fields.append("labels_joined=?")
            args.append(";".join(normalize_list(body.labels)))
        if body.flags is not None:
            fields.append("flags=?")
            args.append(int(body.flags))
        if body.snippet is not None:
            fields.append("snippet=?")
            args.append(body.snippet)
        if body.subject is not None:
            fields.append("subject=?")
            args.append(body.subject)
        if body.from_addr is not None:
            fields.append("from_addr=?")
            args.append(body.from_addr)

        try:
            begin_tx(self.db)

            if fields:
                sql = f"UPDATE mail_message SET {', '.join(fields)}, updated_at=datetime('now') WHERE id=?"
                self.db.execute(sql, args + [message_id])

            # 如果更新收件人
            if body.to is not None or body.cc is not None or body.bcc is not None:
                to_list = normalize_list(body.to) if body.to is not None else None
                cc_list = normalize_list(body.cc) if body.cc is not None else None
                bcc_list = normalize_list(body.bcc) if body.bcc is not None else None

                all_addrs = (to_list or []) + (cc_list or []) + (bcc_list or [])
                seen, seq = set(), []
                for a in all_addrs:
                    if a not in seen:
                        seen.add(a)
                        seq.append(a)
                to_joined = ";".join(seq)

                self.db.execute(
                    "UPDATE mail_message SET to_joined=?, updated_at=datetime('now') WHERE id=?",
                    (to_joined, message_id),
                )

                self.db.execute("DELETE FROM mail_recipient WHERE message_id=?", (message_id,))

                if to_list:
                    self.db.executemany(
                        "INSERT INTO mail_recipient(message_id, account_id, kind, addr) VALUES (?,?,?,?)",
                        [(message_id, m["account_id"], "to", a) for a in to_list],
                    )
                if cc_list:
                    self.db.executemany(
                        "INSERT INTO mail_recipient(message_id, account_id, kind, addr) VALUES (?,?,?,?)",
                        [(message_id, m["account_id"], "cc", a) for a in cc_list],
                    )
                if bcc_list:
                    self.db.executemany(
                        "INSERT INTO mail_recipient(message_id, account_id, kind, addr) VALUES (?,?,?,?)",
                        [(message_id, m["account_id"], "bcc", a) for a in bcc_list],
                    )

            commit_tx(self.db)

        except Exception as e:
            rollback_tx(self.db)
            raise HTTPException(500, f"update mail failed: {e}")

        return {"id": message_id, "updated": True}

    def delete_message(self, message_id: int) -> Dict[str, Any]:
        """删除邮件消息"""
        r = self.db.execute("SELECT id FROM mail_message WHERE id=?", (message_id,)).fetchone()
        if not r:
            raise HTTPException(404, "message not found")

        try:
            begin_tx(self.db)
            self.db.execute("DELETE FROM mail_message WHERE id=?", (message_id,))
            commit_tx(self.db)
        except Exception as e:
            rollback_tx(self.db)
            raise HTTPException(500, f"delete mail failed: {e}")

        return {"id": message_id, "deleted": True}

    def get_detail(self, message_id: int) -> Dict[str, Any]:
        """获取邮件详情"""
        m = self.db.execute("SELECT * FROM mail_message WHERE id=?", (message_id,)).fetchone()
        if not m:
            raise HTTPException(404, "message not found")

        body = self.db.execute(
            "SELECT headers, body_plain, body_html FROM mail_body WHERE message_id=?", (message_id,)
        ).fetchone()

        rec_rows = self.db.execute(
            "SELECT kind, addr FROM mail_recipient WHERE message_id=? ORDER BY kind, id", (message_id,)
        ).fetchall()

        to_list = [r["addr"] for r in rec_rows if r["kind"] == "to"]
        cc_list = [r["addr"] for r in rec_rows if r["kind"] == "cc"]
        bcc_list = [r["addr"] for r in rec_rows if r["kind"] == "bcc"]

        att = self.db.execute(
            "SELECT id, storage_url, created_at FROM mail_attachment WHERE message_id=? ORDER BY id", (message_id,)
        ).fetchall()

        out = dict(m)
        out["recipients"] = {"to": to_list, "cc": cc_list, "bcc": bcc_list}
        out["attachments"] = [dict(x) for x in att]

        if body:
            out["body"] = {"headers": body["headers"], "body_plain": body["body_plain"], "body_html": body["body_html"]}
        else:
            out["body"] = {"headers": None, "body_plain": None, "body_html": None}

        return out

    def get_preview(self, message_id: int) -> Dict[str, Any]:
        """获取邮件预览"""
        m = self.db.execute(
            "SELECT id, account_id, subject, from_addr, received_at FROM mail_message WHERE id=?", (message_id,)
        ).fetchone()

        if not m:
            raise HTTPException(404, "message not found")

        b = self.db.execute(
            "SELECT headers, body_plain, body_html FROM mail_body WHERE message_id=?", (message_id,)
        ).fetchone()

        return {
            "message": dict(m),
            "body_html": b["body_html"] if b else None,
            "body_plain": b["body_plain"] if b else None,
            "headers": b["headers"] if b else None,
        }

    def update_body(self, message_id: int, body_data: MailBodyIn) -> Dict[str, Any]:
        """更新邮件正文"""
        mail = self.db.execute("SELECT id FROM mail_message WHERE id=?", (message_id,)).fetchone()
        if not mail:
            raise HTTPException(404, "message not found")

        try:
            self.db.execute(
                """
                INSERT INTO mail_body (message_id, headers, body_plain, body_html)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    headers = excluded.headers,
                    body_plain = excluded.body_plain,
                    body_html = excluded.body_html
                """,
                (message_id, body_data.headers, body_data.body_plain, body_data.body_html),
            )

            self.db.execute("UPDATE mail_message SET updated_at = datetime('now') WHERE id = ?", (message_id,))

            self.db.commit()
            return {"success": True, "message_id": message_id}

        except Exception as e:
            self.db.rollback()
            raise HTTPException(500, f"更新正文失败: {str(e)}")

    def add_attachment(self, message_id: int, storage_url: str) -> Dict[str, Any]:
        """添加附件"""
        m = self.db.execute("SELECT account_id FROM mail_message WHERE id=?", (message_id,)).fetchone()
        if not m:
            raise HTTPException(404, "message not found")

        try:
            begin_tx(self.db)
            self.db.execute(
                "INSERT INTO mail_attachment(message_id, account_id, storage_url) VALUES (?,?,?)",
                (message_id, m["account_id"], storage_url),
            )
            cnt = self.db.execute(
                "SELECT COUNT(*) c FROM mail_attachment WHERE message_id=?", (message_id,)
            ).fetchone()["c"]
            self.db.execute(
                "UPDATE mail_message SET attachments_count=?, updated_at=datetime('now') WHERE id=?", (cnt, message_id)
            )
            commit_tx(self.db)
        except Exception as e:
            rollback_tx(self.db)
            raise HTTPException(500, f"add attachment failed: {e}")

        return {"message_id": message_id, "attachments_count": cnt}

    def list_attachments(self, message_id: int) -> Dict[str, Any]:
        """列出附件"""
        rows = self.db.execute(
            "SELECT id, storage_url, created_at FROM mail_attachment WHERE message_id=? ORDER BY id", (message_id,)
        ).fetchall()

        return {"items": [dict(r) for r in rows]}

    def delete_attachment(self, message_id: int, attach_id: int) -> Dict[str, Any]:
        """删除附件"""
        r = self.db.execute(
            "SELECT id FROM mail_attachment WHERE id=? AND message_id=?", (attach_id, message_id)
        ).fetchone()

        if not r:
            raise HTTPException(404, "attachment not found")

        try:
            begin_tx(self.db)
            self.db.execute("DELETE FROM mail_attachment WHERE id=?", (attach_id,))
            cnt = self.db.execute(
                "SELECT COUNT(*) c FROM mail_attachment WHERE message_id=?", (message_id,)
            ).fetchone()["c"]
            self.db.execute(
                "UPDATE mail_message SET attachments_count=?, updated_at=datetime('now') WHERE id=?", (cnt, message_id)
            )
            commit_tx(self.db)
        except Exception as e:
            rollback_tx(self.db)
            raise HTTPException(500, f"delete attachment failed: {e}")

        return {"message_id": message_id, "attachments_count": cnt}

    def list_account_mails(
        self, account_id: int, q: Optional[str], folder: Optional[str], page: int, size: int
    ) -> Dict[str, Any]:
        """列出账号邮件"""
        where = ["m.account_id=?"]
        args: List[Any] = [account_id]

        if q:
            where.append(
                "(m.subject_lc LIKE '%'||lower(?)||'%' OR m.from_addr_lc LIKE '%'||lower(?)||'%' OR m.to_joined_lc LIKE '%'||lower(?)||'%')"
            )
            args += [q, q, q]
        if folder:
            where.append("m.folder_lc = lower(?)")
            args.append(folder)

        where_sql = " AND ".join(where)

        total = self.db.execute(f"SELECT COUNT(*) c FROM mail_message m WHERE {where_sql}", args).fetchone()["c"]

        offset = (page - 1) * size
        rows = self.db.execute(
            f"""
            SELECT 
                m.id, m.subject, m.from_addr, m.received_at, m.attachments_count, m.flags,
                m.folder_id,
                COALESCE(f.well_known_name, f.display_name, m.folder_id) as folder_name
            FROM mail_message m
            LEFT JOIN mail_folder f ON f.id = m.folder_id AND f.account_id = m.account_id
            WHERE {where_sql}
            ORDER BY m.received_at DESC, m.id DESC
            LIMIT ? OFFSET ?
            """,
            args + [size, offset],
        ).fetchall()

        return {
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size,
            "items": [dict(r) for r in rows],
        }

    def search_mails(self, req: MailSearchRequest) -> Dict[str, Any]:
        """批量搜索邮件"""
        if not req.account_ids:
            return {"total": 0, "page": req.page, "size": req.size, "pages": 0, "items": []}

    def batch_create_messages(self, batch_data: MailMessageBatchCreate) -> Dict[str, Any]:
        """
        批量创建邮件消息

        Args:
            batch_data: 批量邮件数据

        Returns:
            批量创建结果统计
        """
        mails = batch_data.mails
        ignore_duplicates = batch_data.ignore_duplicates

        total = len(mails)
        saved = 0
        duplicates = 0
        errors = 0
        error_details = []

        if not mails:
            return {"total": 0, "saved": 0, "duplicates": 0, "errors": 0, "error_details": []}

        try:
            begin_tx(self.db)

            for idx, mail in enumerate(mails):
                try:
                    # 准备数据
                    to_all = normalize_list(mail.to) + normalize_list(mail.cc) + normalize_list(mail.bcc)
                    seen, seq = set(), []
                    for a in to_all:
                        if a not in seen:
                            seen.add(a)
                            seq.append(a)
                    to_joined = ";".join(seq)

                    labels_joined = ";".join(normalize_list(mail.labels))
                    attachments_count = len(mail.attachments or [])

                    # 检查是否重复
                    if mail.msg_uid:
                        existing = self.db.execute(
                            "SELECT id FROM mail_message WHERE account_id = ? AND msg_uid = ?",
                            (mail.account_id, mail.msg_uid),
                        ).fetchone()

                        if existing:
                            duplicates += 1
                            if ignore_duplicates:
                                continue  # 跳过重复邮件
                            else:
                                error_details.append(
                                    {"index": idx, "msg_uid": mail.msg_uid, "error": "Duplicate message"}
                                )
                                errors += 1
                                continue

                    # 插入邮件主记录
                    cur = self.db.execute(
                        """
                        INSERT INTO mail_message(
                            account_id, msg_uid, msg_id, subject, from_addr, to_joined,
                            folder_id, labels_joined, sent_at, received_at, size_bytes,
                            attachments_count, flags, snippet, created_at, updated_at
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                        """,
                        (
                            mail.account_id,
                            mail.msg_uid,
                            mail.msg_id,
                            mail.subject or "",
                            mail.from_addr or "",
                            to_joined,
                            mail.folder_id or "",
                            labels_joined,
                            mail.sent_at,
                            mail.received_at,
                            mail.size_bytes,
                            attachments_count,
                            mail.flags or 0,
                            mail.snippet,
                        ),
                    )
                    mid = cur.lastrowid

                    # 插入收件人明细
                    if mail.to:
                        self.db.executemany(
                            "INSERT INTO mail_recipient(message_id, account_id, kind, addr) VALUES (?,?,?,?)",
                            [(mid, mail.account_id, "to", a) for a in normalize_list(mail.to)],
                        )
                    if mail.cc:
                        self.db.executemany(
                            "INSERT INTO mail_recipient(message_id, account_id, kind, addr) VALUES (?,?,?,?)",
                            [(mid, mail.account_id, "cc", a) for a in normalize_list(mail.cc)],
                        )
                    if mail.bcc:
                        self.db.executemany(
                            "INSERT INTO mail_recipient(message_id, account_id, kind, addr) VALUES (?,?,?,?)",
                            [(mid, mail.account_id, "bcc", a) for a in normalize_list(mail.bcc)],
                        )

                    # 插入正文
                    if mail.body and (mail.body.headers or mail.body.body_plain or mail.body.body_html):
                        self.db.execute(
                            "INSERT OR REPLACE INTO mail_body(message_id, headers, body_plain, body_html) VALUES (?,?,?,?)",
                            (mid, mail.body.headers, mail.body.body_plain, mail.body.body_html),
                        )

                    # 插入附件
                    if mail.attachments:
                        self.db.executemany(
                            "INSERT INTO mail_attachment(message_id, account_id, storage_url) VALUES (?,?,?)",
                            [(mid, mail.account_id, url) for url in mail.attachments],
                        )

                    saved += 1

                except sqlite3.IntegrityError as e:
                    # 处理唯一约束冲突（重复邮件）
                    if "UNIQUE constraint" in str(e) or "unique" in str(e).lower():
                        duplicates += 1
                        if not ignore_duplicates:
                            error_details.append(
                                {"index": idx, "msg_uid": mail.msg_uid, "error": f"Duplicate: {str(e)}"}
                            )
                            errors += 1
                    else:
                        errors += 1
                        error_details.append({"index": idx, "msg_uid": mail.msg_uid, "error": str(e)})

                except Exception as e:
                    errors += 1
                    error_details.append({"index": idx, "msg_uid": getattr(mail, "msg_uid", None), "error": str(e)})

            commit_tx(self.db)

        except Exception as e:
            rollback_tx(self.db)
            traceback.print_exc()
            raise HTTPException(500, f"批量插入邮件失败: {e}")

        return {
            "total": total,
            "saved": saved,
            "duplicates": duplicates,
            "errors": errors,
            "error_details": error_details[:10] if error_details else [],  # 只返回前10个错误
        }

    def batch_create_messages_optimized(self, batch_data: MailMessageBatchCreate) -> Dict[str, Any]:
        """
        批量创建邮件消息（优化版本 - 使用更少的SQL语句）

        适合大批量数据导入，性能更好
        """
        mails = batch_data.mails
        ignore_duplicates = batch_data.ignore_duplicates

        total = len(mails)
        saved = 0
        duplicates = 0
        errors = 0
        error_details = []

        if not mails:
            return {"total": 0, "saved": 0, "duplicates": 0, "errors": 0, "error_details": []}

        try:
            begin_tx(self.db)

            # 预处理所有邮件数据
            mail_records = []
            recipient_records = []
            body_records = []
            attachment_records = []

            # 如果忽略重复，先批量查询已存在的 msg_uid
            existing_uids = set()
            if ignore_duplicates:
                account_id = mails[0].account_id
                msg_uids = [m.msg_uid for m in mails if m.msg_uid]

                if msg_uids:
                    # 分批查询（避免 SQL 参数过多）
                    batch_size = 500
                    for i in range(0, len(msg_uids), batch_size):
                        batch_uids = msg_uids[i : i + batch_size]
                        placeholders = ",".join("?" * len(batch_uids))
                        query = f"SELECT msg_uid FROM mail_message WHERE account_id = ? AND msg_uid IN ({placeholders})"

                        rows = self.db.execute(query, [account_id] + batch_uids).fetchall()
                        existing_uids.update(row["msg_uid"] for row in rows)

            # 准备所有数据
            for idx, mail in enumerate(mails):
                try:
                    # 跳过重复邮件
                    if mail.msg_uid in existing_uids:
                        duplicates += 1
                        continue

                    # 准备主记录数据
                    to_all = normalize_list(mail.to) + normalize_list(mail.cc) + normalize_list(mail.bcc)
                    seen, seq = set(), []
                    for a in to_all:
                        if a not in seen:
                            seen.add(a)
                            seq.append(a)
                    to_joined = ";".join(seq)

                    labels_joined = ";".join(normalize_list(mail.labels))
                    attachments_count = len(mail.attachments or [])

                    mail_records.append(
                        (
                            mail.account_id,
                            mail.msg_uid,
                            mail.msg_id,
                            mail.subject or "",
                            mail.from_addr or "",
                            to_joined,
                            mail.folder_id or "",
                            labels_joined,
                            mail.sent_at,
                            mail.received_at,
                            mail.size_bytes,
                            attachments_count,
                            mail.flags or 0,
                            mail.snippet,
                        )
                    )

                    # 记录索引以便后续关联
                    mail_index = len(mail_records) - 1

                    # 准备收件人数据（临时存储，等插入后获取 message_id）
                    recipient_data = []
                    if mail.to:
                        recipient_data.extend([("to", a) for a in normalize_list(mail.to)])
                    if mail.cc:
                        recipient_data.extend([("cc", a) for a in normalize_list(mail.cc)])
                    if mail.bcc:
                        recipient_data.extend([("bcc", a) for a in normalize_list(mail.bcc)])

                    if recipient_data:
                        recipient_records.append((mail_index, mail.account_id, recipient_data))

                    # 准备正文数据
                    if mail.body and (mail.body.headers or mail.body.body_plain or mail.body.body_html):
                        body_records.append((mail_index, mail.body.headers, mail.body.body_plain, mail.body.body_html))

                    # 准备附件数据
                    if mail.attachments:
                        attachment_records.append((mail_index, mail.account_id, mail.attachments))

                except Exception as e:
                    errors += 1
                    error_details.append({"index": idx, "msg_uid": getattr(mail, "msg_uid", None), "error": str(e)})

            # 批量插入邮件主记录
            if mail_records:
                if ignore_duplicates:
                    # 使用 INSERT OR IGNORE
                    self.db.executemany(
                        """
                        INSERT OR IGNORE INTO mail_message(
                            account_id, msg_uid, msg_id, subject, from_addr, to_joined,
                            folder_id, labels_joined, sent_at, received_at, size_bytes,
                            attachments_count, flags, snippet, created_at, updated_at
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                        """,
                        mail_records,
                    )
                else:
                    # 普通插入
                    self.db.executemany(
                        """
                        INSERT INTO mail_message(
                            account_id, msg_uid, msg_id, subject, from_addr, to_joined,
                            folder_id, labels_joined, sent_at, received_at, size_bytes,
                            attachments_count, flags, snippet, created_at, updated_at
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                        """,
                        mail_records,
                    )

                saved = len(mail_records)

                # 获取刚插入的邮件 ID（按 msg_uid 查询）
                message_id_map = {}
                account_id = mails[0].account_id

                for idx, record in enumerate(mail_records):
                    msg_uid = record[1]  # msg_uid 是第二个字段
                    if msg_uid:
                        row = self.db.execute(
                            "SELECT id FROM mail_message WHERE account_id = ? AND msg_uid = ?", (account_id, msg_uid)
                        ).fetchone()
                        if row:
                            message_id_map[idx] = row["id"]

                # 批量插入收件人
                all_recipients = []
                for mail_index, account_id, recipient_data in recipient_records:
                    if mail_index in message_id_map:
                        message_id = message_id_map[mail_index]
                        for kind, addr in recipient_data:
                            all_recipients.append((message_id, account_id, kind, addr))

                if all_recipients:
                    self.db.executemany(
                        "INSERT INTO mail_recipient(message_id, account_id, kind, addr) VALUES (?,?,?,?)",
                        all_recipients,
                    )

                # 批量插入正文
                all_bodies = []
                for mail_index, headers, body_plain, body_html in body_records:
                    if mail_index in message_id_map:
                        message_id = message_id_map[mail_index]
                        all_bodies.append((message_id, headers, body_plain, body_html))

                if all_bodies:
                    self.db.executemany(
                        "INSERT OR REPLACE INTO mail_body(message_id, headers, body_plain, body_html) VALUES (?,?,?,?)",
                        all_bodies,
                    )

                # 批量插入附件
                all_attachments = []
                for mail_index, account_id, attachments in attachment_records:
                    if mail_index in message_id_map:
                        message_id = message_id_map[mail_index]
                        for url in attachments:
                            all_attachments.append((message_id, account_id, url))

                if all_attachments:
                    self.db.executemany(
                        "INSERT INTO mail_attachment(message_id, account_id, storage_url) VALUES (?,?,?)",
                        all_attachments,
                    )

            commit_tx(self.db)

        except Exception as e:
            rollback_tx(self.db)
            traceback.print_exc()
            raise HTTPException(500, f"批量插入邮件失败: {e}")

        return {
            "total": total,
            "saved": saved,
            "duplicates": duplicates,
            "errors": errors,
            "error_details": error_details[:10] if error_details else [],
        }
