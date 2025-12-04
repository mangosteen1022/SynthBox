"""服务器相关处理逻辑"""

from PyQt5 import QtWidgets, QtCore
import logging

log = logging.getLogger("SynthBox")


class ServerHandler:
    """
    服务器相关处理类，负责处理服务器的启动、停止等功能
    """
    
    def __init__(self, page):
        self.page = page
        self.init_connections()
    
    def init_connections(self):
        """初始化信号连接"""
        # 顶部工具栏
        self.page.btnServerToggle.clicked.connect(self.toggle_server)
        self.page.btnOpenIndex.clicked.connect(self.open_index_page)
    
    def toggle_server(self):
        """切换服务器状态"""
        if self.page.server_thread and self.page.server_thread.is_running:
            self.page.server_thread.stop()
            self.page.server_thread.quit()
            self.page.server_thread.wait()
            self.page.server_thread = None
            self.page.btnServerToggle.setText("启动API")
            self.page.btnServerToggle.setChecked(False)
            self.page.send_log("正在停止FastAPI服务...")
        else:
            self.page.server_thread = self.page.ServerThread()
            self.page.server_thread.server_started.connect(self.on_server_started)
            self.page.server_thread.server_stopped.connect(self.on_server_stopped)
            self.page.server_thread.server_error.connect(self.on_server_error)
            self.page.server_thread.start()
            self.page.send_log("正在启动FastAPI服务...")
    
    def on_server_started(self):
        """服务启动成功"""
        self.page.send_log("FastAPI服务已启动")
        self.page.btnServerToggle.setText("停止API")
        self.page.btnServerToggle.setChecked(True)
        QtCore.QTimer.singleShot(500, self.page.account_handler.load_accounts)
    
    def on_server_stopped(self):
        """服务停止"""
        self.page.send_log("FastAPI服务已停止")
        self.page.btnServerToggle.setText("启动API")
        self.page.btnServerToggle.setChecked(False)
    
    def on_server_error(self, error):
        """服务错误"""
        self.page.send_log(f"服务错误: {error}")
    
    def open_index_page(self):
        """打开网页"""
        config = self.page.AppConfig()
        webbrowser.open(f"{config.base_url}/index")