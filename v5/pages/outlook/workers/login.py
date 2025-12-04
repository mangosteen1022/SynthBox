"""登录相关工作线程"""

import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable

from PyQt5.QtCore import QObject, pyqtSignal

from ..config import AppConfig
from ..core import ApiService
from ..core.msal_client import MSALClient


class LoginTask:
    """登录任务数据"""

    def __init__(self, account_data: dict):
        self.account_id = account_data["id"]
        self.email = account_data["email"]
        self.password = account_data["password"]
        self.recovery_emails = account_data.get("recovery_emails", [])
        self.recovery_phones = account_data.get("recovery_phones", [])


class LoginExecutor:
    """登录执行器（在线程池中运行）"""

    def __init__(self):
        self.config = AppConfig()
        self.api = ApiService()

    def execute(self, task: LoginTask, progress_callback: Optional[Callable[[int, str], None]] = None) -> dict:
        """执行登录任务"""
        try:
            # 1. 查询token缓存
            if progress_callback:
                progress_callback(task.account_id, "正在查询token缓存...")

            token_uuid = None
            try:
                cache_data = self.api.get_token_cache(task.account_id)
                token_uuid = cache_data.get("uuid")
                if token_uuid and progress_callback:
                    progress_callback(task.account_id, f"找到缓存: {token_uuid}")
            except Exception as e:
                if progress_callback:
                    progress_callback(task.account_id, f"查询缓存失败: {str(e)}")

            # 2. 创建MSAL客户端
            if progress_callback:
                progress_callback(task.account_id, "正在创建MSAL客户端...")

            data = {
                "client_id": self.config.msal_client_id,
                "authority": self.config.msal_authority,
                "scopes": self.config.msal_scopes,
                "default_port": self.config.msal_port,
            }
            if token_uuid:
                data["token_uuid"] = token_uuid

            msal_client = MSALClient(**data)

            # 检查是否已登录
            if msal_client.get_access_token():
                if progress_callback:
                    progress_callback(task.account_id, "当前账号已登录")
                return {"success": True, "result": ""}

            # 3. 执行登录
            if progress_callback:
                progress_callback(task.account_id, "正在执行登录...")

            recovery_email = task.recovery_emails[0] if task.recovery_emails else None
            recovery_phone = task.recovery_phones[0] if task.recovery_phones else None

            result = msal_client.acquire_token_by_automation(
                email=task.email, password=task.password, recovery_email=recovery_email, recovery_phone=recovery_phone
            )

            if "error" in result:
                # 登录失败，更新状态
                self.api.update_account_status(task.account_id, "登录失败")
                return {"success": False, "error": result["error"]}
            else:
                self.api.update_account_status(task.account_id, "登录成功")

                # 保存token缓存
                if "cache_path" in result:
                    try:
                        cache_uuid = Path(result["cache_path"]).stem
                        self.api.save_token_cache(task.account_id, cache_uuid)
                        if progress_callback:
                            progress_callback(task.account_id, f"已保存缓存: {cache_uuid}")
                    except Exception as e:
                        if progress_callback:
                            progress_callback(task.account_id, f"保存缓存失败: {str(e)}")

                return {"success": True, "result": result}

        except Exception as e:
            # 异常处理
            try:
                self.api.update_account_status(task.account_id, "登录失败")
            except:
                pass
            return {"success": False, "error": f"登录异常: {str(e)}"}


class LoginPoolSignals(QObject):
    """登录池信号"""

    task_started = pyqtSignal(int, str)  # account_id, email
    task_progress = pyqtSignal(int, str)  # account_id, message
    task_success = pyqtSignal(int)  # account_id
    task_error = pyqtSignal(int, str)  # account_id, error
    task_finished = pyqtSignal(int)  # account_id
    all_finished = pyqtSignal(int, int)  # success_count, fail_count


class LoginThreadPool(QObject):
    """登录线程池管理器"""

    def __init__(self, max_workers: int = 3):
        super().__init__()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.signals = LoginPoolSignals()
        self.login_executor = LoginExecutor()

        # 任务管理
        self.active_tasks = {}  # account_id -> (future, task, submit_time)

        # 计数器和锁
        self.total_count = 0
        self.completed_count = 0
        self.success_count = 0
        self.fail_count = 0
        self._lock = threading.Lock()

    def add_task(self, account_data: dict):
        """添加单个登录任务"""
        self.add_tasks([account_data])

    def add_tasks(self, accounts_data: list):
        """批量添加任务（支持去重）"""
        tasks_to_add = []

        with self._lock:
            for account in accounts_data:
                if account["status"] == "登录成功" or account["id"] in self.active_tasks:
                    continue
                task = LoginTask(account)
                tasks_to_add.append(task)

        # 更新计数
        with self._lock:
            if not self.active_tasks:
                self.total_count = len(tasks_to_add)
                self.completed_count = 0
                self.success_count = 0
                self.fail_count = 0
            else:
                self.total_count += len(tasks_to_add)

        # 提交新任务
        submit_time = datetime.now()
        for task in tasks_to_add:
            with self._lock:
                self.signals.task_started.emit(task.account_id, task.email)
                future = self.executor.submit(self._run_task, task)
                self.active_tasks[task.account_id] = (future, task, submit_time)

    def _run_task(self, task: LoginTask):
        """在线程池中执行任务"""
        try:
            # 执行登录
            result = self.login_executor.execute(
                task, progress_callback=lambda aid, msg: self.signals.task_progress.emit(aid, msg)
            )

            # 更新统计并发送信号
            with self._lock:
                self.completed_count += 1

                if result["success"]:
                    self.success_count += 1
                    self.signals.task_success.emit(task.account_id)
                else:
                    self.fail_count += 1
                    self.signals.task_error.emit(task.account_id, result["error"])

                self.signals.task_finished.emit(task.account_id)

                # 检查是否全部完成
                if self.completed_count >= self.total_count:
                    self.signals.all_finished.emit(self.success_count, self.fail_count)

        except Exception as e:
            # 异常处理
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

    def get_status(self) -> dict:
        """获取当前状态"""
        with self._lock:
            return {
                "total": self.total_count,
                "completed": self.completed_count,
                "running": self.total_count - self.completed_count,
                "success": self.success_count,
                "failed": self.fail_count,
                "max_workers": self.max_workers,
            }

    def stop_all(self):
        """停止所有任务"""
        self.executor.shutdown(wait=False)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        with self._lock:
            self.total_count = 0
            self.completed_count = 0
            self.success_count = 0
            self.fail_count = 0
            self.active_tasks.clear()
