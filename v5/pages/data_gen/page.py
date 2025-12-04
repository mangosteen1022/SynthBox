import random
import re
import string

from PyQt5 import QtCore
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication, QLabel

from v5.pages import BasePage
import time
from v5.layout.FlowLayout import FlowLayout
from v5.layout.FloatingButton import DraggableButton, FloatingWindow, CUSTOM_MIME_TYPE
from v5.db.database.db_client import db_client
from v5.core.config import config_manager
import logging

log = logging.getLogger("SynthBox")


class DataGenPage(BasePage):
    page_id_name = "smart_tools"
    display_text = "生成工具"
    icon_path = "util.png"
    order = 21

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.flow_layout = FlowLayout(self, margin=10, spacing=10)
        self.pushButton_random_us_phone = DraggableButton("生成美国手机号", self)
        self.pushButton_random_ca_phone = DraggableButton("生成加拿大手机号", self)
        self.pushButton_generate_email = DraggableButton("生成域名邮箱", self)
        self.pushButton_generate_password = DraggableButton("生成密码", self)
        self.pushButton_register_success = DraggableButton("生成注册成功", self)
        self.pushButton_register_fail = DraggableButton("生成注册失败", self)
        self.pushButton_generate_us_name = DraggableButton("生成美国姓名", self)
        self.pushButton_generate_ch_name = DraggableButton("生成瑞士姓名", self)
        self.pushButton_generate_kr_name = DraggableButton("生成韩国姓名", self)
        self.pushButton_generate_jp_name = DraggableButton("生成日本姓名", self)
        self.pushButton_generate_sg_name = DraggableButton("生成新加坡姓名", self)
        self.pushButton_generate_tw_name = DraggableButton("生成台湾姓名", self)
        self.pushButton_generate_hk_name = DraggableButton("生成香港姓名", self)
        self.pushButton_totp_verify = DraggableButton("TOTP 验证", self)
        self.buttons = [
            self.pushButton_random_us_phone,
            self.pushButton_random_ca_phone,
            self.pushButton_generate_email,
            self.pushButton_generate_password,
            self.pushButton_register_success,
            self.pushButton_register_fail,
            self.pushButton_generate_us_name,
            self.pushButton_totp_verify,
            self.pushButton_generate_ch_name,
            self.pushButton_generate_kr_name,
            self.pushButton_generate_jp_name,
            self.pushButton_generate_sg_name,
            self.pushButton_generate_tw_name,
            self.pushButton_generate_hk_name,
        ]
        for btn in self.buttons:
            btn.floating_window_created.connect(self.on_depend_floating_window_created)
            self.flow_layout.addWidget(btn)
        self.clipboard = QApplication.clipboard()
        self.setLayout(self.flow_layout)
        self._connect_signals()
        self._initial_styles()

    def on_depend_floating_window_created(self, floating_window: FloatingWindow):
        button_name = floating_window.button.objectName()
        worker_key = floating_window.worker_key
        floating_window.stoped.connect(self.remove_worker)
        self.workers[worker_key] = {
            "worker": floating_window,
            "config": {"type": "floating_window", "name": button_name},
        }

    @QtCore.pyqtSlot(str)
    def remove_worker(self, worker_key):
        if worker_key in self.workers:
            del self.workers[worker_key]

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(CUSTOM_MIME_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event):
        source_button = event.source()
        if not isinstance(source_button, DraggableButton):
            return
        byte_data = event.mimeData().data(CUSTOM_MIME_TYPE)
        button_name = byte_data.data().decode("utf-8")
        drop_pos = event.pos()
        target_index = 0
        for i in range(self.flow_layout.count()):
            widget = self.flow_layout.itemAt(i).widget()
            if widget and widget != source_button:
                if drop_pos.y() < widget.y() or (
                    drop_pos.y() < widget.y() + widget.height() and drop_pos.x() < widget.x() + widget.width() / 2
                ):
                    break
            target_index += 1

        floating_parent = source_button.parent()
        if isinstance(floating_parent, FloatingWindow):
            worker_key = f"float_{button_name}"
            if worker_key in self.workers:
                del self.workers[worker_key]
            floating_parent.deleteLater()

        source_button.setParent(self)
        self.flow_layout.removeWidget(source_button)  #
        self.flow_layout.insertWidget(target_index, source_button)
        source_button.show()
        event.accept()

    def _connect_signals(self):
        self.pushButton_random_us_phone.clicked.connect(self.random_us_phone)
        self.pushButton_random_ca_phone.clicked.connect(self.random_ca_phone)
        self.pushButton_generate_email.clicked.connect(self.generate_email)
        self.pushButton_generate_password.clicked.connect(self.generate_password)
        self.pushButton_register_success.clicked.connect(self.register_success)
        self.pushButton_register_fail.clicked.connect(self.register_fail)
        self.pushButton_generate_us_name.clicked.connect(self.generate_us_name)
        self.pushButton_generate_ch_name.clicked.connect(self.generate_ch_name)
        self.pushButton_generate_kr_name.clicked.connect(self.generate_kr_name)
        self.pushButton_generate_jp_name.clicked.connect(self.generate_jp_name)
        self.pushButton_generate_sg_name.clicked.connect(self.generate_sg_name)
        self.pushButton_generate_tw_name.clicked.connect(self.generate_tw_name)
        self.pushButton_generate_hk_name.clicked.connect(self.generate_hk_name)

    def _initial_styles(self):
        style = """
            DraggableButton {padding: 3px 6px;border: 1px solid #c0c0c0;border-radius: 2.5px;background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,stop:0 #fAfAfA, stop:1 #E1E1E1);min-height: 20px;}
            DraggableButton:hover {background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,stop:0 #E8E8E8, stop:1 #D0D0D0);}
            DraggableButton:pressed {background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,stop:0 #D0D0D0, stop:1 #E8E8E8);}
            DraggableButton:disabled {background-color: #f0f0f0;color: #a0a0a0;}
        """
        self.setStyleSheet(style)

    def random_us_phone(self):
        db_phone_area = db_client.get_db("phone_area")
        phone_length = db_phone_area["US:PHONE_LENGTH"]
        state = random.choice(db_phone_area["US:STATE"])
        state_length = db_phone_area[f"US:{state}:LENGTH"]
        area = db_phone_area[f"US:{state}:{random.randint(0, state_length - 1)}"]
        area = "".join(re.findall(r"\d+", area))
        phone = f"{area}{(''.join(random.choices(string.digits, k=phone_length - len(area))))}"
        self.clipboard.setText(phone)
        self.send_log(f"美国号码已复制：{phone}")
        self.send_notification("美国号码已复制", phone)

    def random_ca_phone(self):
        db_phone_area = db_client.get_db("phone_area")
        phone_length = db_phone_area["CA:PHONE_LENGTH"]
        area = db_phone_area[f"CA:{random.randint(0, phone_length - 1)}"]
        area = "".join(re.findall(r"\d+", area))
        phone = f"{area}{(''.join(random.choices(string.digits, k=phone_length - len(area))))}"
        self.clipboard.setText(phone)
        self.send_log(f"加拿大号码已复制：{phone}")
        self.send_notification("加拿大号码已复制", phone)

    def generate_email(self):
        db_phone_area = db_client.get_db("phone_area")
        domains = random.choice(db_phone_area["DOMAINS"])
        name = self.generate_name("US").replace(" ", "").lower()
        digits = "".join(random.choices(string.digits, k=4))
        self.clipboard.setText(f"{name}{digits}@{domains}")
        self.send_log(f"已复制：{name}{digits}@{domains}")
        self.send_notification("邮箱已复制", f"{name}{digits}@{domains}")

    def register_success(self):
        _time = time.strftime("%Y年%m月%d日%H:%M:%S", time.localtime())
        msg = f"{_time} 注册成功"
        self.clipboard.setText(msg)
        self.send_log(f"已复制：{msg}")
        self.send_notification("注册成功", msg)

    def register_fail(self):
        _time = time.strftime("%Y年%m月%d日%H:%M:%S", time.localtime())
        msg = f"{_time} 注册失败"
        self.clipboard.setText(msg)
        self.send_log(f"已复制：{msg}")
        self.send_notification("注册失败", msg)

    def generate_password(self):
        lowercase = random.choices(string.ascii_lowercase, k=4)
        uppercase = random.choices(string.ascii_uppercase, k=4)
        digits = random.choices(string.digits, k=4)
        punctuation = random.choices("@!#$", k=4)
        field = lowercase + uppercase + digits + punctuation
        random.shuffle(field)
        password = "".join(field)
        self.clipboard.setText(password)
        self.send_log(f"密码已复制：{password}")
        self.send_notification("密码已复制", password)

    @staticmethod
    def generate_name(country):
        username = db_client.get_db("username")
        first_name_length = username[f"{country}:FIRSTNAME:LENGTH"]
        last_name_length = username[f"{country}:LASTNAME:LENGTH"]
        firstname = username[f"{country}:FIRSTNAME:{random.randint(0, first_name_length - 1)}"]
        lastname = username[f"{country}:LASTNAME:{random.randint(0, last_name_length - 1)}"]
        return " ".join([firstname, lastname])

    def generate_us_name(self):
        name = self.generate_name("US")
        self.clipboard.setText(name)
        self.send_log(f"美国姓名已复制：{name}")
        self.send_notification("美国姓名已复制", name)

    def generate_ch_name(self):
        name = self.generate_name("CH")
        self.clipboard.setText(name)
        self.send_log(f"瑞士姓名已复制：{name}")
        self.send_notification("瑞士姓名已复制", name)

    def generate_kr_name(self):
        name = self.generate_name("KR")
        self.clipboard.setText(name)
        self.send_log(f"韩国姓名已复制：{name}")
        self.send_notification("韩国姓名已复制", name)

    def generate_jp_name(self):
        name = self.generate_name("JP")
        self.clipboard.setText(name)
        self.send_log(f"日本姓名已复制：{name}")
        self.send_notification("日本姓名已复制", name)

    def generate_sg_name(self):
        name = self.generate_name("SG")
        self.clipboard.setText(name)
        self.send_log(f"新加坡姓名已复制：{name}")
        self.send_notification("新加坡姓名已复制", name)

    def generate_tw_name(self):
        name = self.generate_name("TW")
        self.clipboard.setText(name)
        self.send_log(f"台湾姓名已复制：{name}")
        self.send_notification("台湾姓名已复制", name)

    def generate_hk_name(self):
        name = self.generate_name("HK")
        self.clipboard.setText(name)
        self.send_log(f"香港姓名已复制：{name}")
        self.send_notification("香港姓名已复制", name)
