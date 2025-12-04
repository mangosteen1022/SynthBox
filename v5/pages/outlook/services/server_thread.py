"""FastAPI服务线程"""

import os
import sys
import uvicorn
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

from ..config import AppConfig


class ServerThread(QThread):
    """FastAPI服务线程"""

    server_started = pyqtSignal()
    server_stopped = pyqtSignal()
    server_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        config = AppConfig()
        self.host = config.server_host
        self.port = config.server_port
        self.server = None
        self.is_running = False
        self.server_dir = Path(__file__).parent.parent / "server"

    def run(self):
        """启动服务"""
        try:
            original_dir = os.getcwd()
            os.chdir(str(self.server_dir))

            sys.path.insert(0, str(self.server_dir))
            self.is_running = True
            self.server_started.emit()

            # 延迟导入，避免在PyQt5主线程导入FastAPI
            from ..server.app import create_app

            app = create_app()

            config = uvicorn.Config(app=app, host=self.host, port=self.port, log_level="info", access_log=False)
            self.server = uvicorn.Server(config)
            self.server.run()

        except Exception as e:
            self.server_error.emit(f"服务启动失败: {str(e)}")
        finally:
            os.chdir(original_dir)
            self.is_running = False
            self.server_stopped.emit()

    def stop(self):
        """停止服务"""
        if self.server:
            self.server.should_exit = True
            self.is_running = False
