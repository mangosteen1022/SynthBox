"""改进的邮件同步管理器"""

import re
from typing import Dict, List, Any, Optional, Callable

from ..core import ApiService
from ..core.msal_client import MSALClient
from ..utils import DateTimeHelper


class MailSyncManager:
    """邮件同步管理器"""

    def __init__(self, api_service: ApiService):
        self.api = api_service
        self.dt = DateTimeHelper()

    def sync_account_mails(
        self,
        account_id: int,
        msal_client: MSALClient,
        strategy: str = "auto",
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        同步账号邮件（主入口）

        Args:
            account_id: 账号ID
            msal_client: MSAL客户端实例
            strategy: 同步策略
                - "auto": 自动选择（优先delta > incremental > recent）
                - "full": 完整同步所有邮件
                - "incremental": 增量同步（基于时间）
                - "recent": 同步最近的邮件
            progress_callback: 进度回调函数

        Returns:
            {
                "success": bool,
                "error": str (如果失败),
                "synced": int (同步数量),
                "total_fetched": int (获取总数),
                "sync_state": dict (同步状态)
            }
        """
        try:
            # 1. 获取同步状态
            sync_state = self.get_sync_state(account_id)

            if progress_callback:
                progress_callback(account_id, f"开始同步邮件 (策略: {strategy})")

            # 同步文件夹到数据库
            self._sync_folders_to_db(account_id, msal_client)

            # 2. 根据策略选择同步方式
            if strategy == "auto":
                if sync_state.get("delta_link"):
                    result = self.sync_with_delta(account_id, msal_client, sync_state, progress_callback)
                elif sync_state.get("last_sync_time"):
                    result = self.sync_incremental(account_id, msal_client, sync_state, progress_callback)
                else:
                    result = self.sync_recent(account_id, msal_client, progress_callback)
            elif strategy == "full":
                result = self.sync_full(account_id, msal_client, sync_state, progress_callback)
            elif strategy == "incremental":
                result = self.sync_incremental(account_id, msal_client, sync_state, progress_callback)
            else:  # recent
                result = self.sync_recent(account_id, msal_client, progress_callback)

            # 3. 更新同步状态
            if result.get("success"):
                self.update_sync_state(account_id, result.get("sync_state", {}))

            return result

        except Exception as e:
            return {"success": False, "error": str(e), "synced": 0}

    def _sync_folders_to_db(self, account_id: int, msal_client: MSALClient) -> int:
        """
        同步文件夹到数据库

        Args:
            account_id: 账号ID
            msal_client: MSAL客户端

        Returns:
            同步的文件夹数量
        """
        try:
            response = msal_client.list_mail_folders()
            folders = response.get("value", [])
            if not folders:
                return 0
            result = self.api.request("POST", f"/accounts/{account_id}/folders/sync", json_data=folders)
            return result.get("synced", 0)
        except Exception as e:
            print(f"同步文件夹失败: {e}")
            return 0

    def _get_all_folders(self, msal_client: MSALClient) -> List[Dict[str, Any]]:
        """
        获取所有邮件文件夹（包括子文件夹）

        Returns:
            文件夹列表，每个文件夹包含 id, displayName, totalItemCount, unreadItemCount
        """
        all_folders = []
        try:
            # 获取顶级文件夹
            response = msal_client.list_mail_folders()
            folders = response.get("value", [])

            for folder in folders:
                folder_info = {
                    "id": folder["id"],
                    "name": folder.get("displayName", "Unknown"),
                    "total": folder.get("totalItemCount", 0),
                    "unread": folder.get("unreadItemCount", 0),
                }
                all_folders.append(folder_info)

                # 递归获取子文件夹（如果API支持）
                # 注意: 这里假设 msal_client 有 list_child_folders 方法
                # 如果没有，可以跳过这部分或使用 /mailFolders/{id}/childFolders
                try:
                    child_response = msal_client.list_child_folders(folder["id"])
                    child_folders = child_response.get("value", [])
                    for child in child_folders:
                        child_info = {
                            "id": child["id"],
                            "name": f"{folder.get('displayName', 'Unknown')}/{child.get('displayName', 'Unknown')}",
                            "total": child.get("totalItemCount", 0),
                            "unread": child.get("unreadItemCount", 0),
                        }
                        all_folders.append(child_info)
                except:
                    pass  # 如果不支持子文件夹，忽略

            return all_folders
        except Exception as e:
            print(f"获取文件夹列表失败: {e}")
            return []

    def get_sync_state(self, account_id: int) -> Dict[str, Any]:
        """获取同步状态"""
        try:
            result = self.api.request("GET", f"/mail/sync-state/{account_id}")
            return result
        except Exception as e:
            return {}

    def update_sync_state(self, account_id: int, state: Dict[str, Any]):
        """更新同步状态"""
        try:
            self.api.request("PUT", f"/mail/sync-state/{account_id}", json_data=state)
        except Exception as e:
            print(f"更新同步状态失败: {e}")

    def sync_with_delta(
        self,
        account_id: int,
        msal_client: MSALClient,
        sync_state: Dict,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        使用Delta查询同步所有文件夹（最高效）

        改进：遍历所有文件夹进行 Delta 同步
        """
        if progress_callback:
            progress_callback(account_id, "使用Delta查询获取所有文件夹的变更...")

        all_folders = self._get_all_folders(msal_client)
        if not all_folders:
            if progress_callback:
                progress_callback(account_id, "未找到任何文件夹，跳过同步")
            return {"success": False, "error": "未找到文件夹", "synced": 0}

        total_synced = 0
        folder_delta_links = sync_state.get("folder_delta_links", {})
        new_folder_delta_links = {}

        for folder in all_folders:
            folder_id = folder["id"]
            folder_name = folder["name"]

            # 跳过空文件夹
            if folder["total"] == 0:
                continue

            if progress_callback:
                progress_callback(account_id, f"同步文件夹: {folder_name} (Delta)")

            try:
                delta_link = folder_delta_links.get(folder_id)
                new_mails = []

                # 获取该文件夹的变更
                if delta_link:
                    response = msal_client.get_messages_delta(delta_link, folder_id=folder_id)
                else:
                    # 首次 Delta 查询
                    response = msal_client.get_messages_delta(folder_id=folder_id)

                mails = response.get("value", [])
                new_mails.extend(mails)

                # 处理分页
                batch_count = 1
                while "@odata.nextLink" in response and batch_count < 50:
                    response = msal_client.get_messages_delta(response["@odata.nextLink"])
                    mails = response.get("value", [])
                    new_mails.extend(mails)
                    batch_count += 1

                # 保存邮件
                if new_mails:
                    synced = self.save_mails_to_db(account_id, new_mails, progress_callback)
                    total_synced += synced

                # 保存该文件夹的 delta link
                new_delta_link = response.get("@odata.deltaLink")
                if new_delta_link:
                    new_folder_delta_links[folder_id] = new_delta_link

            except Exception as e:
                print(f"Delta 同步文件夹 {folder_name} 失败: {e}")
                continue

        return {
            "success": True,
            "synced": total_synced,
            "total_fetched": total_synced,
            "sync_state": {
                "folder_delta_links": new_folder_delta_links,
                "last_sync_time": self.dt.now(),
                "total_synced": sync_state.get("total_synced", 0) + total_synced,
            },
        }

    def sync_incremental(
        self,
        account_id: int,
        msal_client: MSALClient,
        sync_state: Dict,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        增量同步所有文件夹（基于时间）

        改进：遍历所有文件夹进行增量同步
        """
        last_sync_time = sync_state.get("last_sync_time")
        if not last_sync_time:
            if progress_callback:
                progress_callback(account_id, "未找到上次同步时间，改为获取最近30天邮件")
            return self.sync_recent(account_id, msal_client, progress_callback)

        if progress_callback:
            progress_callback(account_id, f"获取所有文件夹在 {last_sync_time} 之后的邮件...")

        all_folders = self._get_all_folders(msal_client)
        if not all_folders:
            return {"success": False, "error": "未找到文件夹", "synced": 0}

        total_synced = 0
        total_fetched = 0

        for folder in all_folders:
            folder_id = folder["id"]
            folder_name = folder["name"]

            # 跳过空文件夹
            if folder["total"] == 0:
                continue

            if progress_callback:
                progress_callback(account_id, f"同步文件夹: {folder_name} (增量)")

            result = self._sync_folder_incremental(
                account_id, msal_client, folder_id, folder_name, last_sync_time, progress_callback
            )

            total_synced += result.get("synced", 0)
            total_fetched += result.get("fetched", 0)

        new_sync_time = self.dt.now()

        return {
            "success": True,
            "synced": total_synced,
            "total_fetched": total_fetched,
            "sync_state": {
                "last_sync_time": new_sync_time,
                "total_synced": sync_state.get("total_synced", 0) + total_synced,
            },
        }

    def _sync_folder_incremental(
        self,
        account_id: int,
        msal_client: MSALClient,
        folder_id: str,
        folder_name: str,
        last_sync_time: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """增量同步单个文件夹"""
        try:
            filter_str = f"receivedDateTime gt {last_sync_time}"
            all_mails = []
            skip_token = None
            batch_count = 0

            while batch_count < 20:
                response = msal_client.list_messages(
                    folder_id=folder_id,
                    top=50,
                    filter_str=filter_str,
                    orderby="receivedDateTime desc",
                    skip_token=skip_token,
                    select=[
                        "id",
                        "subject",
                        "from",
                        "toRecipients",
                        "ccRecipients",
                        "receivedDateTime",
                        "sentDateTime",
                        "isRead",
                        "hasAttachments",
                        "bodyPreview",
                        "internetMessageId",
                        "parentFolderId",
                    ],
                )

                mails = response.get("value", [])
                if not mails:
                    break

                all_mails.extend(mails)

                next_link = response.get("@odata.nextLink")
                if next_link:
                    match = re.search(r"\$skiptoken=([^&]+)", next_link)
                    skip_token = match.group(1) if match else None
                else:
                    break

                batch_count += 1

            synced = self.save_mails_to_db(account_id, all_mails, progress_callback)
            return {"synced": synced, "fetched": len(all_mails)}

        except Exception as e:
            print(f"增量同步文件夹 {folder_name} 失败: {e}")
            return {"synced": 0, "fetched": 0}

    def sync_recent(
        self,
        account_id: int,
        msal_client: MSALClient,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        同步所有文件夹最近的邮件（默认30天）

        改进：遍历所有文件夹同步最近邮件
        """
        if progress_callback:
            progress_callback(account_id, f"获取所有文件夹最近 {days} 天的邮件...")

        all_folders = self._get_all_folders(msal_client)
        if not all_folders:
            return {"success": False, "error": "未找到文件夹", "synced": 0}

        total_synced = 0
        total_fetched = 0
        start_date = self.dt.days_ago(days)

        for folder in all_folders:
            folder_id = folder["id"]
            folder_name = folder["name"]

            # 跳过空文件夹
            if folder["total"] == 0:
                continue

            if progress_callback:
                progress_callback(account_id, f"同步文件夹: {folder_name} (最近 {days} 天)")

            result = self._sync_folder_recent(
                account_id, msal_client, folder_id, folder_name, start_date, progress_callback
            )

            total_synced += result.get("synced", 0)
            total_fetched += result.get("fetched", 0)

        return {
            "success": True,
            "synced": total_synced,
            "total_fetched": total_fetched,
            "sync_state": {
                "last_sync_time": self.dt.now(),
                "total_synced": total_synced,
            },
        }

    def _sync_folder_recent(
        self,
        account_id: int,
        msal_client: MSALClient,
        folder_id: str,
        folder_name: str,
        start_date: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        max_mails: int = 500,
    ) -> Dict[str, Any]:
        """同步单个文件夹最近的邮件"""
        try:
            filter_str = f"receivedDateTime gt {start_date}"
            all_mails = []
            skip_token = None
            batch_count = 0

            while len(all_mails) < max_mails and batch_count < 20:
                response = msal_client.list_messages(
                    folder_id=folder_id,
                    top=50,
                    filter_str=filter_str,
                    orderby="receivedDateTime desc",
                    skip_token=skip_token,
                    select=[
                        "id",
                        "subject",
                        "from",
                        "toRecipients",
                        "ccRecipients",
                        "receivedDateTime",
                        "sentDateTime",
                        "isRead",
                        "hasAttachments",
                        "bodyPreview",
                        "internetMessageId",
                        "parentFolderId",
                    ],
                )

                mails = response.get("value", [])
                if not mails:
                    break

                all_mails.extend(mails)

                next_link = response.get("@odata.nextLink")
                if next_link:
                    match = re.search(r"\$skiptoken=([^&]+)", next_link)
                    skip_token = match.group(1) if match else None
                else:
                    break

                batch_count += 1

            synced = self.save_mails_to_db(account_id, all_mails, progress_callback)
            return {"synced": synced, "fetched": len(all_mails)}

        except Exception as e:
            print(f"同步文件夹 {folder_name} 失败: {e}")
            return {"synced": 0, "fetched": 0}

    def sync_full(
        self,
        account_id: int,
        msal_client: MSALClient,
        sync_state: Dict,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        完整同步所有文件夹的所有邮件

        改进：移除硬编码的文件夹名称匹配，同步所有文件夹
        """
        if progress_callback:
            progress_callback(account_id, "开始完整同步所有文件夹...")

        try:
            # 获取所有文件夹
            all_folders = self._get_all_folders(msal_client)

            if not all_folders:
                return {"success": False, "error": "未找到任何文件夹", "synced": 0}

            # 按邮件数量排序，优先同步重要的大文件夹
            all_folders.sort(key=lambda f: f["total"], reverse=True)

            if progress_callback:
                total_mails = sum(f["total"] for f in all_folders)
                progress_callback(account_id, f"找到 {len(all_folders)} 个文件夹，共 {total_mails} 封邮件")

            # 逐个文件夹同步
            all_synced = 0
            all_fetched = 0
            skip_tokens = sync_state.get("skip_tokens", {})

            for folder in all_folders:
                folder_id = folder["id"]
                folder_name = folder["name"]

                # 跳过空文件夹
                if folder["total"] == 0:
                    continue

                if progress_callback:
                    progress_callback(account_id, f"正在同步文件夹: {folder_name} ({folder['total']} 封)")

                folder_result = self._sync_folder_full(
                    account_id,
                    msal_client,
                    folder,
                    skip_tokens.get(folder_id),
                    progress_callback,
                )

                all_synced += folder_result.get("synced", 0)
                all_fetched += folder_result.get("fetched", 0)

                # 保存skip_token用于断点续传
                if folder_result.get("skip_token"):
                    skip_tokens[folder_id] = folder_result["skip_token"]
                elif folder_id in skip_tokens:
                    del skip_tokens[folder_id]

                # 达到单次同步上限
                if all_fetched >= 10000:
                    if progress_callback:
                        progress_callback(account_id, "已达到单次同步上限(10000封)，可以稍后继续")
                    break

            return {
                "success": True,
                "synced": all_synced,
                "total_fetched": all_fetched,
                "sync_state": {
                    "last_sync_time": self.dt.now(),
                    "total_synced": sync_state.get("total_synced", 0) + all_synced,
                    "skip_tokens": skip_tokens,
                    "full_sync_completed": len(skip_tokens) == 0,
                },
            }

        except Exception as e:
            return {"success": False, "error": f"完整同步失败: {str(e)}", "synced": 0}

    def _sync_folder_full(
        self,
        account_id: int,
        msal_client: MSALClient,
        folder: Dict,
        skip_token: Optional[str],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """同步单个文件夹的所有邮件（带断点续传）"""
        folder_id = folder["id"]
        folder_name = folder["name"]

        all_mails = []
        batch_count = 0
        total_saved = 0
        saved_count = 0
        max_batches = 100

        try:
            while batch_count < max_batches:
                response = msal_client.list_messages(
                    folder_id=folder_id,
                    top=50,
                    orderby="receivedDateTime desc",
                    skip_token=skip_token,
                    select=[
                        "id",
                        "subject",
                        "from",
                        "toRecipients",
                        "ccRecipients",
                        "receivedDateTime",
                        "sentDateTime",
                        "isRead",
                        "hasAttachments",
                        "bodyPreview",
                        "internetMessageId",
                        "parentFolderId",
                    ],
                )

                mails = response.get("value", [])
                if not mails:
                    break

                all_mails.extend(mails)

                if progress_callback and batch_count % 5 == 0:
                    progress_callback(account_id, f"{folder_name}: 已获取 {len(all_mails)} 封邮件...")

                next_link = response.get("@odata.nextLink")
                if next_link:
                    match = re.search(r"\$skiptoken=([^&]+)", next_link)
                    skip_token = match.group(1) if match else None
                else:
                    skip_token = None
                    break

                batch_count += 1

                # 每获取500封就保存一次
                if len(all_mails) >= 500:
                    saved_count += self.save_mails_to_db(account_id, all_mails, progress_callback)
                    total_saved += len(all_mails)
                    all_mails = []

            # 保存剩余的邮件
            if all_mails:
                saved_count += self.save_mails_to_db(account_id, all_mails, progress_callback)
                total_saved += len(all_mails)

            return {
                "synced": saved_count,
                "fetched": total_saved,
                "skip_token": skip_token,
            }

        except Exception as e:
            print(f"同步文件夹 {folder_name} 失败: {e}")
            return {"synced": 0, "fetched": 0, "skip_token": skip_token}

    def sync_folder_by_time_range(
        self,
        account_id: int,
        msal_client: MSALClient,
        folder_id: Optional[str],
        start_date: str,
        end_date: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """按时间范围同步文件夹（用于历史邮件）"""
        try:
            filter_str = f"receivedDateTime ge {start_date} and receivedDateTime lt {end_date}"
            all_mails = []
            skip_token = None
            batch_count = 0

            while batch_count < 20:
                response = msal_client.list_messages(
                    folder_id=folder_id,
                    top=50,
                    filter_str=filter_str,
                    orderby="receivedDateTime desc",
                    skip_token=skip_token,
                )

                mails = response.get("value", [])
                if not mails:
                    break

                all_mails.extend(mails)

                if progress_callback:
                    progress_callback(account_id, f"时间范围 {start_date} 到 {end_date}: 已获取 {len(all_mails)} 封")

                next_link = response.get("@odata.nextLink")
                if next_link:
                    match = re.search(r"\$skiptoken=([^&]+)", next_link)
                    skip_token = match.group(1) if match else None
                else:
                    break

                batch_count += 1

                if len(all_mails) >= 1000:
                    break

            # 保存邮件
            saved_count = self.save_mails_to_db(account_id, all_mails, progress_callback)

            return {"success": True, "synced": saved_count, "fetched": len(all_mails)}

        except Exception as e:
            return {"success": False, "error": str(e), "synced": 0}

    def save_mails_to_db(
        self,
        account_id: int,
        mails: List[Dict],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> int:
        """
        批量保存邮件到数据库

        改进：改为真正的批量保存（如果API支持）
        """
        if not mails:
            return 0

        if progress_callback:
            progress_callback(account_id, f"正在保存 {len(mails)} 封邮件到数据库...")

        saved_count = 0

        # 准备批量数据
        mail_data_list = []
        for mail in mails:
            try:
                mail_data = self.prepare_mail_data(account_id, mail)
                mail_data_list.append(mail_data)
            except Exception as e:
                print(f"准备邮件数据失败: {e}")
                continue

        # 尝试批量保存（如果API支持）
        try:
            result = self.api.request(
                "POST", f"/accounts/{account_id}/mails/batch", json_data={"mails": mail_data_list}
            )
            saved_count = result.get("saved", 0)

            if progress_callback:
                progress_callback(account_id, f"成功保存 {saved_count}/{len(mails)} 封邮件")

            return saved_count

        except Exception as batch_error:
            # 如果批量保存失败，降级为逐条保存
            print(f"批量保存失败，降级为逐条保存: {batch_error}")

            for i, mail_data in enumerate(mail_data_list):
                try:
                    result = self.api.create_mail_message(mail_data)
                    if result.get("id"):
                        saved_count += 1
                except Exception as e:
                    # 忽略重复邮件等错误
                    error_msg = str(e)
                    if "UNIQUE constraint" not in error_msg and "duplicate" not in error_msg.lower():
                        print(f"保存邮件失败: {e}")

                # 每50封报告一次进度
                if progress_callback and (i + 1) % 50 == 0:
                    progress_callback(account_id, f"已保存 {saved_count}/{len(mails)} 封邮件...")

            if progress_callback:
                progress_callback(account_id, f"完成保存 {saved_count}/{len(mails)} 封邮件")

            return saved_count

    def prepare_mail_data(self, account_id: int, mail: Dict) -> Dict:
        """准备邮件数据用于保存"""
        to_recipients = [r.get("emailAddress", {}).get("address", "") for r in mail.get("toRecipients", [])]
        cc_recipients = [r.get("emailAddress", {}).get("address", "") for r in mail.get("ccRecipients", [])]

        from_addr = ""
        if mail.get("from"):
            from_addr = mail["from"].get("emailAddress", {}).get("address", "")

        sent_at = mail.get("sentDateTime")
        received_at = mail.get("receivedDateTime")

        mail_data = {
            "account_id": account_id,
            "msg_uid": mail.get("id", ""),
            "msg_id": mail.get("internetMessageId", ""),
            "subject": mail.get("subject", ""),
            "from_addr": from_addr,
            "to": to_recipients,
            "cc": cc_recipients,
            "folder_id": mail.get("parentFolderId", ""),
            "sent_at": sent_at,
            "received_at": received_at,
            "snippet": mail.get("bodyPreview", ""),
            "flags": 0 if mail.get("isRead", False) else 1,
            "attachments_count": len(mail.get("attachments", [])),
        }
        return mail_data
