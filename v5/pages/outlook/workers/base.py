"""基础工作线程"""

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from ..core import ApiService


class BaseWorker(QThread):
    """工作线程基类"""

    success = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    finished_work = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.api = ApiService()
        self._is_running = False

    def stop(self):
        """停止线程"""
        self._is_running = False
        self.quit()


class ApiWorker(BaseWorker):
    """API请求工作线程"""

    def __init__(self, method: str, endpoint: str, params=None, json_data=None):
        super().__init__()
        self.method = method
        self.endpoint = endpoint
        self.params = params
        self.json_data = json_data

    def run(self):
        """执行API请求"""
        self._is_running = True
        try:
            result = self.api.request(self.method, self.endpoint, params=self.params, json_data=self.json_data)
            if self._is_running:
                self.success.emit(result)
        except requests.exceptions.RequestException as e:
            if self._is_running:
                self.error.emit(f"请求失败: {str(e)}")
        except Exception as e:
            if self._is_running:
                self.error.emit(f"错误: {str(e)}")
        finally:
            self._is_running = False
            self.finished_work.emit()
