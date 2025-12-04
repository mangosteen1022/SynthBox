from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal
import logging

from v5.core.protocols import ManagedWorker
from v5.core.config import config_manager

log = logging.getLogger("SynthBox")


class BasePage(QWidget):
    log_message_sent = pyqtSignal(str)
    notification_sent = pyqtSignal(str, str)

    # --- 用于自动发现和配置的类属性 ---
    page_id_name: str = None
    display_text: str = "未命名页面"
    icon_path: str = ""
    order: int = 999
    add_to_sidebar_menu: bool = True
    is_fixed_bottom: bool = False
    THEME_QSS = r""""""

    def __init__(self, parent=None):
        super().__init__(parent)
        app = QtWidgets.QApplication.instance()
        if app and not getattr(app, "_sb_theme_applied", False):
            app.setStyleSheet(self.THEME_QSS)
            app._sb_theme_applied = True
        if self.page_id_name is None and type(self) is not BasePage:
            raise NotImplementedError(f"{type(self).__name__} 必须定义 page_id_name 类属性。")

        self.workers: dict[str, ManagedWorker] = {}

    def send_log(self, message):
        self.log_message_sent.emit(f"[{self.display_text}] {message}")

    def send_notification(self, title, message):
        if config_manager.get("notification"):
            self.notification_sent.emit(title, message)
        else:
            self.send_log("已禁用通知，改为使用日志输出。")
            self.send_log(" ".join([title, message]))
