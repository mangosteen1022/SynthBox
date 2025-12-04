from PyQt5.QtWidgets import QVBoxLayout, QLabel, QPlainTextEdit
from PyQt5.QtCore import Qt
from v5.pages.base.page import BasePage
import logging

log = logging.getLogger("SynthBox")


class FullLogPage(BasePage):
    page_id_name = "full_log"
    display_text = "完整日志"
    icon_path = "log.png"  # 即使不显示在侧边栏，也可能被其他地方引用
    add_to_sidebar_menu = False
    is_fixed_bottom = False

    def __init__(self, parent=None):
        super().__init__(parent)
        # self.setupUi(self)
        self.setObjectName(self.page_id_name + "Page")
        self.setStyleSheet("background: #B0B0B0;")
        layout = QVBoxLayout(self)

        self.log_title = QLabel(self.display_text, alignment=Qt.AlignCenter)
        font = self.log_title.font()
        font.setPointSize(16)
        self.log_title.setFont(font)
        layout.addWidget(self.log_title)

        self.full_log_display = QPlainTextEdit()
        self.full_log_display.setReadOnly(True)
        self.full_log_display.setMaximumBlockCount(5000)
        layout.addWidget(self.full_log_display)
        self.setLayout(layout)

    def set_logs(self, log_list):
        self.full_log_display.setPlainText("\n".join(log_list))

    def append_log_entry(self, message):
        print(...)
        self.full_log_display.append(message)


# ... 为 ProfilePage.py 创建类似的文件 ...
