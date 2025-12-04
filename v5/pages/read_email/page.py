from PyQt5 import QtCore
from v5.pages.base.page import BasePage
from .ui import Ui_Form
from v5.core.config import config_manager
from v5.core.read_email import ReadEmail, GetMailContent
import logging

from v5.core.utils import get_icon_path

log = logging.getLogger("SynthBox")


class ReadEmailPage(BasePage, Ui_Form):
    page_id_name = "read_email"
    display_text = "邮件读取"
    icon_path = "email.png"
    order = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.read_email = None

        self._initial_styles()
        self._initial_data()
        self._connect_signals()

    def _initial_styles(self):
        drop_down_icon = get_icon_path("chevron_down.png").replace("\\", "/")
        style = """
            QPushButton {padding: 3px 6px;border: 1px solid #c0c0c0;border-radius: 2.5px;background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,stop:0 #fAfAfA, stop:1 #E1E1E1);min-height: 20px;}
            QPushButton:hover {background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,stop:0 #E8E8E8, stop:1 #D0D0D0);}
            QPushButton:pressed {background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,stop:0 #D0D0D0, stop:1 #E8E8E8);}
            QPushButton:disabled {background-color: #f0f0f0;color: #a0a0a0;}
            QLineEdit, QSpinBox, QComboBox {padding: 3px;border: 1px solid #cccccc;border-radius: 3px;min-height: 20px;}
            QComboBox {border: 1px solid #34495E;border-radius: 5px;padding: 3px 8px;background-color: #2C3E50;color: #ECF0F1;font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;font-size: 16px;}
            QComboBox:hover {border: 1px solid #3498DB;}
            QComboBox::drop-down {subcontrol-origin: padding;subcontrol-position: top right;width: 25px;border-left-width: 1px;border-left-color: #34495E;border-left-style: solid;border-top-right-radius: 1px;border-bottom-right-radius: 1px;}
            QComboBox::drop-down:hover {background-color: #34495E;}
            QComboBox::down-arrow {image: url(%s);width: 25px;height: 40px;}
            QComboBox QAbstractItemView {background-color: #2C3E50;border: 1px solid #3498DB;border-radius: 5px;color: #ECF0F1;selection-background-color: #3498DB;selection-color: #FFFFFF;outline: 0px;}
            QComboBox QAbstractItemView::item {min-height: 40px;padding-left: 10px;font-size: 16px;}
            QComboBox QAbstractItemView::item:hover {background-color: #34495E;color: #FFFFFF;}
        """
        style = style % drop_down_icon
        self.setStyleSheet(style)

    def _initial_data(self):
        subjects = ReadEmail.get_all_subjects()
        if subjects:
            self.comboBox.addItems(subjects)
        self.comboBox.setEditable(True)

    def _connect_signals(self):
        self.pushButton.clicked.connect(self.read_email_content)

    def read_email_content(self):
        if not self.read_email:
            username = config_manager.get("read_email_user")
            password = config_manager.get("read_email_pass")
            if not username or not password:
                self.send_log("请在设置页填写邮箱账号和密码！")
                return
            self.read_email = ReadEmail(username=username, password=password)
        subject = self.comboBox.currentText()
        _to = self.lineEdit.text()
        if not subject or not _to:
            self.send_log("请填写完整的信息！")
            return
        self.pushButton.setEnabled(False)
        self.gmc_worker_thread = QtCore.QThread()
        self.gmc_worker = GetMailContent(self.read_email, subject, _to)
        self.gmc_worker.moveToThread(self.gmc_worker_thread)
        self.gmc_worker_thread.started.connect(self.gmc_worker.run)
        self.gmc_worker.finished.connect(lambda s: self.textBrowser.setText(s))
        self.gmc_worker.finished.connect(lambda s: self.pushButton.setEnabled(True))
        self.gmc_worker.finished.connect(self.gmc_worker_thread.quit)
        self.gmc_worker.finished.connect(self.gmc_worker.deleteLater)
        self.gmc_worker_thread.finished.connect(self.gmc_worker_thread.deleteLater)
        self.gmc_worker_thread.start()
