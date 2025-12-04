"""邮件管理路由"""

import sqlite3
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Body

from ..database import get_db
from ..models.mail import (
    MailBodyIn,
    MailMessageCreate,
    MailMessageUpdate,
    AttachmentAdd,
    MailSearchRequest,
    MailMessageBatchCreate,
)
from ..services.mail_service import MailService

router = APIRouter()


@router.post("/messages")
def create_mail_message(it: MailMessageCreate, db: sqlite3.Connection = Depends(get_db)):
    """创建邮件消息"""
    service = MailService(db)
    return service.create_message(it)


@router.patch("/{message_id}")
def update_mail_message(message_id: int, body: MailMessageUpdate, db: sqlite3.Connection = Depends(get_db)):
    """更新邮件消息"""
    service = MailService(db)
    return service.update_message(message_id, body)


@router.delete("/{message_id}")
def delete_mail_message(message_id: int, db: sqlite3.Connection = Depends(get_db)):
    """删除邮件消息"""
    service = MailService(db)
    return service.delete_message(message_id)


@router.get("/{message_id}")
def get_mail_detail(message_id: int, db: sqlite3.Connection = Depends(get_db)):
    """获取邮件详情"""
    service = MailService(db)
    return service.get_detail(message_id)


@router.get("/{message_id}/preview")
def get_mail_preview(message_id: int, db: sqlite3.Connection = Depends(get_db)):
    """获取邮件预览（用于右侧显示）"""
    service = MailService(db)
    return service.get_preview(message_id)


@router.put("/{message_id}/body")
def update_mail_body(message_id: int, body_data: MailBodyIn, db: sqlite3.Connection = Depends(get_db)):
    """更新或插入邮件正文"""
    service = MailService(db)
    return service.update_body(message_id, body_data)


@router.post("/{message_id}/attachments")
def add_attachment(message_id: int, data: AttachmentAdd, db: sqlite3.Connection = Depends(get_db)):
    """添加邮件附件"""
    service = MailService(db)
    return service.add_attachment(message_id, data.storage_url)


@router.get("/{message_id}/attachments")
def list_attachments(message_id: int, db: sqlite3.Connection = Depends(get_db)):
    """列出邮件附件"""
    service = MailService(db)
    return service.list_attachments(message_id)


@router.delete("/{message_id}/attachments/{attach_id}")
def delete_attachment(message_id: int, attach_id: int, db: sqlite3.Connection = Depends(get_db)):
    """删除邮件附件"""
    service = MailService(db)
    return service.delete_attachment(message_id, attach_id)


@router.get("/accounts/{account_id}/mails")
def list_account_mails(
    account_id: int,
    db: sqlite3.Connection = Depends(get_db),
    q: Optional[str] = Query(None, description="对 subject/from/to 进行包含匹配"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    folder: Optional[str] = None,
):
    """列出账号邮件"""
    service = MailService(db)
    return service.list_account_mails(account_id, q, folder, page, size)


@router.post("/search")
def search_mails(req: MailSearchRequest, db: sqlite3.Connection = Depends(get_db)):
    """批量搜索邮件"""
    service = MailService(db)
    return service.search_mails(req)


@router.get("/sync-state/{account_id}")
def get_mail_sync_state(account_id: int, db: sqlite3.Connection = Depends(get_db)):
    """获取邮件同步状态"""
    row = db.execute("SELECT * FROM mail_sync_state WHERE account_id = ?", (account_id,)).fetchone()

    if row:
        return dict(row)
    else:
        return {}


@router.put("/sync-state/{account_id}")
def update_mail_sync_state(
    account_id: int, state: Dict[str, Any] = Body(...), db: sqlite3.Connection = Depends(get_db)
):
    """更新邮件同步状态"""
    from ..utils.time_utils import utc_now

    try:
        # 确保时间格式正确
        last_sync_time = state.get("last_sync_time")
        if last_sync_time and not last_sync_time.endswith("Z"):
            from datetime import datetime

            try:
                dt = datetime.fromisoformat(last_sync_time.replace("Z", "+00:00"))
                last_sync_time = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, AttributeError):
                last_sync_time = utc_now()

        db.execute(
            """
            INSERT INTO mail_sync_state (
                account_id, last_sync_time, last_msg_uid,
                delta_link, skip_token, total_synced, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
                last_sync_time = excluded.last_sync_time,
                last_msg_uid = excluded.last_msg_uid,
                delta_link = excluded.delta_link,
                skip_token = excluded.skip_token,
                total_synced = excluded.total_synced,
                updated_at = excluded.updated_at
            """,
            (
                account_id,
                last_sync_time,
                state.get("last_msg_uid"),
                state.get("delta_link"),
                state.get("skip_token"),
                state.get("total_synced", 0),
                utc_now(),
            ),
        )
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"更新同步状态失败: {str(e)}")


@router.get("/statistics/{account_id}")
def get_mail_statistics(account_id: int, db: sqlite3.Connection = Depends(get_db)):
    """获取邮件统计信息"""
    from ..utils.time_utils import utc_now, utc_days_ago
    from datetime import datetime, timezone

    # 总邮件数
    total = db.execute("SELECT COUNT(*) as c FROM mail_message WHERE account_id = ?", (account_id,)).fetchone()["c"]

    # 未读邮件数
    unread = db.execute(
        "SELECT COUNT(*) as c FROM mail_message WHERE account_id = ? AND flags = 1", (account_id,)
    ).fetchone()["c"]

    # 今天的邮件
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_str = today_start.strftime("%Y-%m-%dT%H:%M:%SZ")

    today_count = db.execute(
        "SELECT COUNT(*) as c FROM mail_message WHERE account_id = ? AND received_at >= ?",
        (account_id, today_start_str),
    ).fetchone()["c"]

    # 最近7天的邮件
    seven_days_ago = utc_days_ago(7)
    week_count = db.execute(
        "SELECT COUNT(*) as c FROM mail_message WHERE account_id = ? AND received_at > ?", (account_id, seven_days_ago)
    ).fetchone()["c"]

    # 最新邮件
    latest = db.execute(
        """
        SELECT subject, from_addr, received_at
        FROM mail_message
        WHERE account_id = ?
        ORDER BY received_at DESC
        LIMIT 1
        """,
        (account_id,),
    ).fetchone()

    return {
        "total": total,
        "unread": unread,
        "today": today_count,
        "week": week_count,
        "latest": dict(latest) if latest else None,
    }


@router.post("/accounts/{account_id}/mails/batch")
def batch_create_mails(
    account_id: int,
    batch_data: MailMessageBatchCreate,
    optimized: bool = Query(False, description="是否使用优化版本（适合大批量）"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    批量创建邮件

    Args:
        account_id: 账号ID
        batch_data: 批量邮件数据
        optimized: 是否使用优化版本（推荐500封以上使用）

    Returns:
        批量创建结果统计
    """
    # 验证所有邮件都属于该账号
    for mail in batch_data.mails:
        if mail.account_id != account_id:
            raise HTTPException(400, "邮件账号ID与路径参数不匹配")

    service = MailService(db)

    if optimized:
        return service.batch_create_messages_optimized(batch_data)
    else:
        return service.batch_create_messages(batch_data)


@router.post("/batch")
def batch_create_mails_multi_account(
    batch_data: MailMessageBatchCreate,
    optimized: bool = Query(False, description="是否使用优化版本（适合大批量）"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    批量创建邮件（支持多账号）

    Args:
        batch_data: 批量邮件数据
        optimized: 是否使用优化版本（推荐500封以上使用）

    Returns:
        批量创建结果统计
    """
    service = MailService(db)

    if optimized:
        return service.batch_create_messages_optimized(batch_data)
    else:
        return service.batch_create_messages(batch_data)
