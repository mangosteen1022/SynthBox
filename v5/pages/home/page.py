from PyQt5.QtWidgets import QVBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt5.QtCore import Qt
from v5.pages.base.page import BasePage
import logging

log = logging.getLogger("SynthBox")


class HomePage(BasePage):
    # page_id_name = "home"
    # display_text = "首页"
    # icon_path = "home.png"
    # order = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)  # 使用 self.layout() 或新建

        self.welcome_label = QLabel(f"欢迎使用 {self.display_text}", alignment=Qt.AlignCenter)
        layout.addWidget(self.welcome_label)

        self.input_field = QLineEdit(f"这是{self.display_text}的输入框")
        self.input_field.setObjectName(f"{self.page_id_name}InputField")
        self.input_field.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.input_field)

        self.input_field.editingFinished.connect(lambda: self.send_log(f"输入框内容: {self.input_field.text()}"))

        self.test_log_button = QPushButton(f"测试{self.display_text}日志")
        self.test_log_button.clicked.connect(lambda: self.send_log("测试日志按钮被点击"))
        layout.addWidget(self.test_log_button)
        layout.addStretch()
        self.setLayout(layout)  # 设置布局
