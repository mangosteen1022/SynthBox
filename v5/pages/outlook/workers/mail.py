"""邮件检查相关工作线程"""

import threading
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Callable

from PyQt5.QtCore import QObject, pyqtSignal

from ..config import AppConfig
from ..core import ApiService
from ..core.msal_client import MSALClient
from .base import BaseWorker


class MailCheckTask:
    """邮件检查任务数据"""

    def __init__(self, account_data: dict):
        self.account_id = account_data["id"]
        self.email = account_data["email"]
        self.token_uuid = account_data.get("token_uuid")
        self.sync_strategy = None  # 默认增量同步
        self.start_date = None  # 用于时间范围查询
        self.end_date = None


class MailCheckPoolSignals(QObject):
    """邮件检查池信号"""

    task_started = pyqtSignal(int, str)  # account_id, email
    task_progress = pyqtSignal(int, str)  # account_id, message
    task_success = pyqtSignal(int, dict)  # account_id, result
    task_error = pyqtSignal(int, str)  # account_id, error
    task_finished = pyqtSignal(int)  # account_id
    all_finished = pyqtSignal(int, int)  # success_count, fail_count


class MailCheckExecutor:
    """邮件检查执行器（使用同步管理器）"""

    def __init__(self):
        self.config = AppConfig()
        self.api = ApiService()
        # 延迟导入，避免循环依赖
        from ..services.mail_sync import MailSyncManager

        self.sync_manager = MailSyncManager(self.api)

    def execute(self, task: MailCheckTask, progress_callback: Optional[Callable[[int, str], None]] = None) -> dict:
        """执行邮件检查任务"""
        try:
            # 1. 查询token缓存
            if not task.token_uuid:
                if progress_callback:
                    progress_callback(task.account_id, "正在查询token缓存...")
                try:
                    cache_data = self.api.get_token_cache(task.account_id)
                    task.token_uuid = cache_data.get("uuid")
                    if not task.token_uuid:
                        return {"success": False, "error": "未找到token缓存，请先登录"}
                except Exception as e:
                    return {"success": False, "error": f"查询缓存失败: {str(e)}"}

            # 2. 创建MSAL客户端
            if progress_callback:
                progress_callback(task.account_id, "正在创建邮件客户端...")

            msal_client = MSALClient(
                client_id=self.config.msal_client_id,
                authority=self.config.msal_authority,
                scopes=self.config.msal_scopes,
                token_uuid=task.token_uuid,
                default_port=self.config.msal_port,
            )

            # 3. 使用同步管理器同步邮件
            if task.sync_strategy == "time_range" and task.start_date and task.end_date:
                # 按时间范围查询
                if progress_callback:
                    progress_callback(task.account_id, f"正在查询 {task.start_date} 到 {task.end_date} 的邮件...")

                sync_result = self.sync_manager.sync_folder_by_time_range(
                    account_id=task.account_id,
                    msal_client=msal_client,
                    folder_id=None,
                    start_date=task.start_date,
                    end_date=task.end_date,
                    progress_callback=progress_callback,
                )
            else:
                # 使用同步管理器的策略
                sync_result = self.sync_manager.sync_account_mails(
                    account_id=task.account_id,
                    msal_client=msal_client,
                    strategy=task.sync_strategy,
                    progress_callback=progress_callback,
                )

            if not sync_result.get("success"):
                return {"success": False, "error": sync_result.get("error", "同步失败")}

            # 4. 获取统计信息
            if progress_callback:
                progress_callback(task.account_id, "正在获取邮件统计...")

            stats = self.get_mail_statistics(task.account_id)

            return {
                "success": True,
                "result": {
                    "account_id": task.account_id,
                    "email": task.email,
                    "synced": sync_result.get("synced", 0),
                    "total_fetched": sync_result.get("total_fetched", 0),
                    "stats": stats,
                },
            }

        except Exception as e:
            return {"success": False, "error": f"邮件检查异常: {str(e)}"}

    def get_mail_statistics(self, account_id: int) -> Dict:
        """获取邮件统计信息"""
        try:
            result = self.api.request("GET", f"/mail/statistics/{account_id}")
            return result
        except:
            return {"total": 0, "unread": 0, "today": 0}


class MailCheckThreadPool(QObject):
    """邮件检查线程池管理器"""

    def __init__(self, max_workers: int = 2):
        super().__init__()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.signals = MailCheckPoolSignals()
        self.mail_executor = MailCheckExecutor()

        # 任务追踪
        self.active_tasks = {}  # account_id -> (future, task, submit_time)

        # 计数器
        self.total_count = 0
        self.completed_count = 0
        self.success_count = 0
        self.fail_count = 0
        self._lock = threading.Lock()

    def add_task(self, task: MailCheckTask):
        """添加单个检查任务"""
        self.add_tasks([task])

    def add_tasks(self, tasks: list):
        """批量添加任务（支持去重）"""
        tasks_to_add = []
        with self._lock:
            for task in tasks:
                if task.account_id in self.active_tasks:
                    continue
                tasks_to_add.append(task)

        if not tasks_to_add:
            return

        # 更新计数
        with self._lock:
            if not self.active_tasks:
                self.total_count = len(tasks_to_add)
                self.completed_count = 0
                self.success_count = 0
                self.fail_count = 0
            else:
                self.total_count += len(tasks_to_add)

        # 提交任务
        submit_time = datetime.now()
        for task in tasks_to_add:
            with self._lock:
                self.signals.task_started.emit(task.account_id, task.email)
                future = self.executor.submit(self._run_task, task)
                self.active_tasks[task.account_id] = (future, task, submit_time)

    def _run_task(self, task: MailCheckTask):
        """在线程池中执行任务"""
        try:
            # 执行邮件检查
            result = self.mail_executor.execute(
                task, progress_callback=lambda aid, msg: self.signals.task_progress.emit(aid, msg)
            )

            # 处理结果
            with self._lock:
                self.completed_count += 1

                if result["success"]:
                    self.success_count += 1
                    self.signals.task_success.emit(task.account_id, result["result"])
                else:
                    self.fail_count += 1
                    self.signals.task_error.emit(task.account_id, result["error"])

                self.signals.task_finished.emit(task.account_id)

                if self.completed_count >= self.total_count:
                    self.signals.all_finished.emit(self.success_count, self.fail_count)

        except Exception as e:
            with self._lock:
                self.completed_count += 1
                self.fail_count += 1

                self.signals.task_error.emit(task.account_id, str(e))
                self.signals.task_finished.emit(task.account_id)

                if self.completed_count >= self.total_count:
                    self.signals.all_finished.emit(self.success_count, self.fail_count)
        finally:
            with self._lock:
                self.active_tasks.pop(task.account_id, None)

    def stop_all(self):
        """停止所有任务"""
        with self._lock:
            for future, _, _ in self.active_tasks.values():
                future.cancel()

        self.executor.shutdown(wait=False)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        with self._lock:
            self.active_tasks.clear()
            self.total_count = 0
            self.completed_count = 0
            self.success_count = 0
            self.fail_count = 0


class MailBodyDownloadWorker(BaseWorker):
    """邮件正文下载工作线程"""

    def __init__(self, message_id: int, account_id: int):
        super().__init__()
        self.message_id = message_id
        self.account_id = account_id
        self.config = AppConfig()

    def run(self):
        """执行下载"""
        self._is_running = True
        try:
            # 1. 获取邮件基本信息
            self.progress.emit(f"正在获取邮件 {self.message_id} 的信息...")
            mail_info = self.api.request("GET", f"/mail/{self.message_id}")
            msg_uid = mail_info.get("msg_uid")
            if not msg_uid:
                self.error.emit("邮件信息不完整，缺少 msg_uid")
                return

            # 2. 获取token缓存
            self.progress.emit("正在获取访问令牌...")
            cache_data = self.api.request("GET", f"/accounts/{self.account_id}/token-caches")
            token_uuid = cache_data.get("uuid")
            if not token_uuid:
                self.error.emit("未找到token缓存，请先登录")
                return

            # 3. 创建MSAL客户端
            msal_client = MSALClient(
                client_id=self.config.msal_client_id,
                authority=self.config.msal_authority,
                scopes=self.config.msal_scopes,
                token_uuid=token_uuid,
                default_port=self.config.msal_port,
            )

            # 4. 通过Graph API获取邮件详情
            self.progress.emit("正在从服务器下载邮件正文...")
            token = msal_client.get_access_token()
            if not token:
                self.error.emit("获取访问令牌失败")
                return

            headers = {"Authorization": f"Bearer {token}"}
            endpoint = f"https://graph.microsoft.com/v1.0/me/messages/{msg_uid}"
            params = {"$select": "body,uniqueBody,internetMessageHeaders"}

            resp = requests.get(endpoint, headers=headers, params=params, timeout=30)
            if resp.status_code >= 400:
                self.error.emit(f"下载失败: {resp.status_code} {resp.text[:200]}")
                return

            mail_data = resp.json()

            # 5. 提取正文
            body = mail_data.get("body", {})
            body_html = None
            body_plain = None

            if body.get("contentType") == "html":
                body_html = body.get("content", "")
            else:
                body_plain = body.get("content", "")

            # 提取邮件头
            headers_list = mail_data.get("internetMessageHeaders", [])
            headers_str = "\n".join([f"{h['name']}: {h['value']}" for h in headers_list])

            # 6. 保存到数据库
            self.progress.emit("正在保存邮件正文...")
            body_data = {
                "headers": headers_str,
                "body_html": body_html,
                "body_plain": body_plain,
            }

            result = self.api.request("PUT", f"/mail/{self.message_id}/body", json_data=body_data)

            if self._is_running:
                self.success.emit(self.message_id)

        except Exception as e:
            if self._is_running:
                self.error.emit(f"下载异常: {str(e)}")
        finally:
            self._is_running = False
            self.finished_work.emit()
