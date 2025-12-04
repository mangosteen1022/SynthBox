"""API服务层 - 处理所有API调用"""

import requests
from typing import Dict, Any, Optional, List

from ..config import AppConfig


class ApiService:
    """API服务层（处理所有API调用）"""

    def __init__(self):
        self.config = AppConfig()

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Any] = None,
        headers: Optional[Dict] = None,
        timeout: int = 30,
    ):
        """统一的API请求方法"""
        url = f"{self.config.base_url}{endpoint}"
        response = requests.request(
            method=method, url=url, params=params, json=json_data, headers=headers or {}, timeout=timeout
        )
        response.raise_for_status()
        return response.json()

    # ==================== 健康检查 ====================
    def health_check(self) -> Dict:
        """健康检查"""
        return self.request("GET", "/health")

    # ==================== 账号管理 ====================
    def create_accounts_batch(self, accounts: List[Dict]) -> Dict:
        """批量创建账号"""
        return self.request("POST", "/accounts/batch", json_data=accounts)

    def update_accounts_batch(self, updates: List[Dict]) -> Dict:
        """批量更新账号"""
        return self.request("PUT", "/accounts/batch", json_data=updates)

    def get_accounts(self, page: int = 1, size: int = 20, **filters) -> Dict:
        """获取账号列表

        filters可包含: status, email_contains, recovery_email_contains,
                      recovery_phone, alias_contains, note_contains,
                      updated_after, updated_before
        """
        params = {"page": page, "size": size, **filters}
        return self.request("GET", "/accounts", params=params)

    def get_account(self, account_id: int) -> Dict:
        """获取单个账号"""
        return self.request("GET", f"/accounts/{account_id}")

    def get_account_history(self, account_id: int, page: int = 1, size: int = 20) -> Dict:
        """获取账号历史版本"""
        params = {"page": page, "size": size}
        return self.request("GET", f"/accounts/{account_id}/history", params=params)

    def update_account_status(self, account_id: int, status: str) -> Dict:
        """更新账号状态"""
        return self.request("PATCH", f"/accounts/{account_id}/status", json_data={"status": status})

    def restore_account_version(
        self, account_id: int, version: int, note: Optional[str] = None, created_by: Optional[str] = None
    ) -> Dict:
        """恢复账号版本"""
        data = {"version": version}
        if note:
            data["note"] = note
        if created_by:
            data["created_by"] = created_by
        return self.request("POST", f"/accounts/{account_id}/restore", json_data=data)

    def delete_account(self, account_id: int) -> Dict:
        """删除账号"""
        return self.request("DELETE", f"/accounts/{account_id}")

    def export_accounts(self, **filters) -> str:
        """导出账号（返回CSV内容）"""
        url = f"{self.config.base_url}/accounts/export"
        response = requests.get(url, params=filters, timeout=30)
        response.raise_for_status()
        return response.text

    # ==================== 别名管理 ====================
    def get_account_aliases(self, account_id: int) -> Dict:
        """获取账号别名"""
        return self.request("GET", f"/accounts/{account_id}/aliases")

    def replace_account_aliases(self, account_id: int, aliases: List[str]) -> Dict:
        """替换账号别名"""
        return self.request("PUT", f"/accounts/{account_id}/aliases", json_data={"aliases": aliases})

    def add_account_aliases(self, account_id: int, aliases: List[str]) -> Dict:
        """添加账号别名"""
        return self.request("POST", f"/accounts/{account_id}/aliases", json_data={"aliases": aliases})

    def delete_account_alias(self, account_id: int, alias: str) -> Dict:
        """删除账号别名"""
        return self.request("DELETE", f"/accounts/{account_id}/aliases/{alias}")

    def get_accounts_by_alias(self, alias: str) -> Dict:
        """通过别名查询账号"""
        return self.request("GET", "/accounts/by-alias", params={"q": alias})

    # ==================== Token缓存管理 ====================
    def get_token_cache(self, account_id: int) -> Dict:
        """获取token缓存"""
        return self.request("GET", f"/accounts/{account_id}/token-caches")

    def save_token_cache(self, account_id: int, uuid: str) -> Dict:
        """保存token缓存"""
        return self.request("PUT", f"/accounts/{account_id}/token-caches", json_data={"uuid": uuid})

    def find_accounts_by_token_uuid(self, uuid: str) -> Dict:
        """通过token UUID查找账号"""
        return self.request("GET", f"/token-caches/{uuid}")

    # ==================== 邮件管理 ====================
    def create_mail_message(self, mail_data: Dict) -> Dict:
        """创建邮件消息"""
        return self.request("POST", "/mail/messages", json_data=mail_data)

    def update_mail_message(self, message_id: int, update_data: Dict) -> Dict:
        """更新邮件消息"""
        return self.request("PATCH", f"/mail/{message_id}", json_data=update_data)

    def delete_mail_message(self, message_id: int) -> Dict:
        """删除邮件消息"""
        return self.request("DELETE", f"/mail/{message_id}")

    def get_mail_detail(self, message_id: int) -> Dict:
        """获取邮件详情"""
        return self.request("GET", f"/mail/{message_id}")

    def get_mail_preview(self, message_id: int) -> Dict:
        """获取邮件预览（用于右侧显示）"""
        return self.request("GET", f"/mail/{message_id}/preview")

    def list_account_mails(
        self, account_id: int, page: int = 1, size: int = 50, q: Optional[str] = None, folder: Optional[str] = None
    ) -> Dict:
        """列出账号邮件"""
        params = {"page": page, "size": size}
        if q:
            params["q"] = q
        if folder:
            params["folder"] = folder
        return self.request("GET", f"mail/accounts/{account_id}/mails", params=params)

    def search_mails(self, search_data: Dict) -> Dict:
        """批量搜索邮件"""
        return self.request("POST", "/mail/search", json_data=search_data)

    # ==================== 附件管理 ====================
    def add_mail_attachment(self, message_id: int, storage_url: str) -> Dict:
        """添加邮件附件"""
        return self.request("POST", f"/mail/{message_id}/attachments", json_data={"storage_url": storage_url})

    def list_mail_attachments(self, message_id: int) -> Dict:
        """列出邮件附件"""
        return self.request("GET", f"/mail/{message_id}/attachments")

    def delete_mail_attachment(self, message_id: int, attachment_id: int) -> Dict:
        """删除邮件附件"""
        return self.request("DELETE", f"/mail/{message_id}/attachments/{attachment_id}")

    # ==================== 统计方法 ====================
    def get_account_stats(self) -> Dict:
        """获取账号统计信息"""
        try:
            data = self.get_accounts(page=1, size=1)
            total = data.get("total", 0)
            logged_in = self.get_accounts(page=1, size=1, status="登录成功").get("total", 0)
            failed = self.get_accounts(page=1, size=1, status="登录失败").get("total", 0)
            not_logged = total - logged_in - failed

            return {"total": total, "logged_in": logged_in, "login_failed": failed, "not_logged": not_logged}
        except Exception as e:
            return {"total": 0, "logged_in": 0, "login_failed": 0, "not_logged": 0, "error": str(e)}

    def get_mail_stats(self, account_id: int) -> Dict:
        """获取邮件统计信息"""
        try:
            data = self.list_account_mails(account_id, page=1, size=1)
            total = data.get("total", 0)
            return {"account_id": account_id, "total_mails": total}
        except Exception as e:
            return {"account_id": account_id, "total_mails": 0, "error": str(e)}
