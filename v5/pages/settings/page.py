from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtWidgets import QTableWidgetItem

from v5.pages.base.page import BasePage
from .ui import Ui_Form
from v5.core.config import config_manager
import logging

from v5.core.utils import ProxyPlatform
from v5.core.gen_auth_key import validate_short_license_key

log = logging.getLogger("SynthBox")
DEFAULT_PASS_NETLOC = [
    "www.google.com/recaptcha",
    "challenges.cloudflare.com",
    "accounts.google.com/gsi/",
    "fedcm",
    "/gsi/",
    "www.gstatic.com/_/mss/",
    "/.well-known/web-identity",
    "/feedback/js/help/prod/service",
    "cdn-cgi/challenge-platform",
    "blob:",
    "responsive-web/client-web/shared",
    "responsive-web/client-web/icons",
]
DEFAULT_DELIMITER = ["|", "----", ",", "tab"]


class SettingsPage(BasePage, Ui_Form):
    page_id_name = "settings"
    display_text = "设置"
    icon_path = "settings.png"
    add_to_sidebar_menu = False
    is_fixed_bottom = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.lineEdit_app_auth.setPlaceholderText("请输入密码")
        self.lineEdit_read_email_user.setPlaceholderText("读取邮件用户名")
        self.lineEdit_read_email_pass.setPlaceholderText("读取邮件用户名密码")
        self.lineEdit_proxy_platform_pass.setPlaceholderText("代理平台密码")
        self.lineEdit_proxy_platform_user.setPlaceholderText("代理平台用户名")
        self.lineEdit_link_ignore_input.setPlaceholderText("example.com / re:url_pattern(正则表达式必须使用're:'标志)")
        self._init_data()
        self._init_style()
        self._connect_signals()

    def _connect_signals(self):
        self.lineEdit_app_auth.textChanged.connect(self.set_password)
        self.lineEdit_read_email_user.textChanged.connect(self.set_read_email_user)
        self.lineEdit_read_email_pass.textChanged.connect(self.set_read_email_pass)
        self.comboBox_proxy_platform_select.currentIndexChanged.connect(self.set_proxy_platform_select)
        self.lineEdit_proxy_platform_user.textChanged.connect(self.set_proxy_platform_user)
        self.lineEdit_proxy_platform_pass.textChanged.connect(self.set_proxy_platform_pass)
        self.pushButton_link_ignore_add.clicked.connect(self.add_link_ignore)
        self.pushButton_link_ignore_del.clicked.connect(self.del_link_ignore)
        self.pushButton_url_pattern_add.clicked.connect(self.add_url_pattern)
        self.pushButton_url_pattern_del.clicked.connect(self.del_url_pattern)
        self.tableWidget_url_pattern.cellChanged.connect(self.update_url_pattern)
        self.checkBox_notification.stateChanged.connect(self.set_notification)
        self.checkBox_data_gen_is_depend.stateChanged.connect(self.set_data_gen_page_button_is_depend)
        self.checkBox_table_auto_copy.stateChanged.connect(self.set_table_auto_copy)
        self.checkBox_table_copy_line_wrap.stateChanged.connect(self.set_table_copy_line_wrap)
        self.pushButton_delimiter_add.clicked.connect(self.add_delimiter)
        self.pushButton_delimiter_del.clicked.connect(self.del_delimiter)
        self.lineEdit_people_config_thread_number.textChanged.connect(self.people_config_thread)

    def _init_style(self):
        self.setStyleSheet(
            """
            /* --- 全局设置 --- */
            QWidget {font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;font-size: 12px;color: #333;background-color: #f5f7fa;}
            /* --- TabWidget 标签页 --- */
            QTabWidget::pane {border: 1px solid #dcdfe6;border-top: none;background-color: white;}
            QTabBar::tab {padding: 5px 10px;margin-right: 2px;background-color: #e4e7ed;border: 1px solid #dcdfe6;border-bottom: none;border-top-left-radius: 6px;border-top-right-radius: 6px;color: #606266;}
            QTabBar::tab:hover {background-color: #eff2f7;}
            QTabBar::tab:selected {background-color: white;color: #409eff; /* 蓝色强调色 */font-weight: bold;border-color: #dcdfe6;}
            /* --- GroupBox 分组框 --- */
            QGroupBox {font-weight: bold;color: #303133;border: 1px solid #e4e7ed;border-radius: 5px;margin-top: 1em;}
            QGroupBox::title {subcontrol-origin: margin;subcontrol-position: top left;padding: 0 5px;background-color: #f5f7fa;}
            /* --- Label 标签 --- */
            QLabel {color: #606266;padding: 3px 0;}
            /* --- LineEdit & SpinBox 输入框 --- */
            QLineEdit, QSpinBox {padding: 4px;border: 1px solid #dcdfe6;border-radius: 2px;background-color: #fff;}
            QLineEdit:hover, QSpinBox:hover {border-color: #c0c4cc;}
            QLineEdit:focus, QSpinBox:focus {border-color: #409eff;}
            /* --- ComboBox 下拉选择框 --- */
            QComboBox {padding: 8px;border: 1px solid #dcdfe6;border-radius: 4px;}
            QComboBox::drop-down {border: none;}
            QComboBox::down-arrow {image: url(C:/Users/Administrator/Desktop/SynthBox/v2/assets/down_arrow.png); /* 需要一个下箭头图标 */}
            /* --- PushButton 按钮 --- */
            QPushButton {padding: 4px 9px;background-color: #409eff;color: white;border: none;border-radius: 4px;font-weight: bold;}
            QPushButton:hover {background-color: #66b1ff;}
            QPushButton:pressed {background-color: #3a8ee6;}
            QPushButton:disabled {background-color: #a0cfff;color: #e4e7ed;}
            /* --- ListWidget & TableWidget 列表/表格 --- */
            QListWidget, QTableWidget {border: 1px solid #dcdfe6;border-radius: 4px;background-color: #fff;alternate-background-color: #fafcff; /* 斑马条纹 */}
            QHeaderView::section {background-color: #f5f7fa;padding: 6px;border: none;border-bottom: 1px solid #dcdfe6;font-weight: bold;color: #909399;}
            /* --- CheckBox 复选框 --- */
            QCheckBox {spacing: 5px;}
            QCheckBox::indicator {width: 16px;height: 16px;}
            /* --- ScrollBar 滚动条美化 --- */
            QScrollBar:vertical {border: none;background: #f5f7fa;width: 10px;margin: 0px 0px 0px 0px;}
            QScrollBar::handle:vertical {background: #dcdfe6;min-height: 20px;border-radius: 5px;}
            QScrollBar::handle:vertical:hover {background: #c0c4cc;}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height: 0px;}
            QScrollBar:horizontal {border: none;background: #f5f7fa;height: 10px;margin: 0px 0px 0px 0px;}
            QScrollBar::handle:horizontal {background: #dcdfe6;min-width: 20px;border-radius: 5px;}
            QScrollBar::handle:horizontal:hover {background: #c0c4cc;}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {width: 0px;}
            /* --- 默认状态的样式 --- */
            QLabel[status="default"] {background-color: #e9ecef;color: #495057;border: 1px solid #ced4da;}
            /* --- “有效”状态的样式 --- */
            QLabel[status="valid"] {background-color: #e6ffed;color: #28a745; /* 深绿色文字 */border: 1px solid #77dd77;}
            /* --- “无效”状态的样式 --- */
            QLabel[status="invalid"] {background-color: #ffebe6;color: #dc3545;border: 1px solid #ff6961;}
        """
        )

    def add_link_ignore(self):
        _url = self.lineEdit_link_ignore_input.text().strip()
        if _url:
            link_ignore_list = config_manager.get("link_ignore_list")
            if isinstance(link_ignore_list, list):
                link_ignore_list.append(_url)
                config_manager.set("link_ignore_list", link_ignore_list)
            else:
                config_manager.set("link_ignore_list", [_url])
            self.lineEdit_link_ignore_input.clear()
            self.listWidget_link_ignore.addItem(_url)

    def del_link_ignore(self):
        cur_inx = self.listWidget_link_ignore.currentRow()
        if cur_inx > -1:
            link_ignore_list = config_manager.get("link_ignore_list")
            if isinstance(link_ignore_list, list):
                del link_ignore_list[cur_inx]
                config_manager.set("link_ignore_list", link_ignore_list)
            self.listWidget_link_ignore.takeItem(cur_inx)

    def add_url_pattern(self):
        table = self.tableWidget_url_pattern
        row_position = table.rowCount()
        table.insertRow(row_position)
        if config_manager.get("url_pattern_list") is None:
            config_manager.set("url_pattern_list", [["", "", ""]])
        else:
            url_pattern_list = config_manager.get("url_pattern_list")
            url_pattern_list.append(["", "", ""])
            config_manager.set("url_pattern_list", url_pattern_list)
        table.setItem(row_position, 0, QTableWidgetItem(""))
        table.setItem(row_position, 1, QTableWidgetItem(""))
        table.setItem(row_position, 2, QTableWidgetItem(""))

    def update_url_pattern(self, row, col):
        table = self.tableWidget_url_pattern
        item = table.item(row, col)
        if item is None:
            return
        url_pattern_list = config_manager.get("url_pattern_list")
        url_pattern_list[row][col] = item.text()
        config_manager.set("url_pattern_list", url_pattern_list)

    def del_url_pattern(self):
        table = self.tableWidget_url_pattern
        row_position = table.currentRow()
        if row_position > -1:
            url_pattern_list = config_manager.get("url_pattern_list")
            del url_pattern_list[row_position]
            config_manager.set("url_pattern_list", url_pattern_list)
            table.removeRow(row_position)

    def set_password(self, _):
        key = _.strip()
        config_manager.set("auth_password", key)
        msg = validate_short_license_key(key)
        if msg["msg"] == "许可证有效":
            self.label_auth_pass_msg.setText(msg["expiration_iso"])
            self.label_auth_pass_msg.setProperty("status", "valid")
        else:
            self.label_auth_pass_msg.setText(msg["msg"])
            self.label_auth_pass_msg.setProperty("status", "invalid")
        self.style().polish(self.label_auth_pass_msg)

    @staticmethod
    def set_read_email_user(_):
        config_manager.set("read_email_user", _.strip())

    @staticmethod
    def people_config_thread(_):
        config_manager.set("people_config_thread", _.strip())

    @staticmethod
    def set_proxy_platform_select(_):
        config_manager.set("proxy_platform_select", _)

    @staticmethod
    def set_proxy_platform_user(_):
        config_manager.set("proxy_platform_user", _.strip())

    @staticmethod
    def set_proxy_platform_pass(_):
        config_manager.set("proxy_platform_pass", _.strip())

    @staticmethod
    def set_read_email_pass(_):
        config_manager.set("read_email_pass", _.strip())

    @staticmethod
    def set_data_gen_page_button_is_depend(_):
        config_manager.set("floating_button_is_depend", _)

    @staticmethod
    def set_notification(_):
        config_manager.set("notification", _)

    @staticmethod
    def set_table_auto_copy(_):
        config_manager.set("table_auto_copy", _)

    @staticmethod
    def set_table_copy_line_wrap(_):
        config_manager.set("table_copy_line_wrap", _)

    def add_delimiter(self):
        _delimiter = self.lineEdit_delimiter_input.text().strip()
        if _delimiter:
            delimiter_list = config_manager.get("delimiter_list")
            if isinstance(delimiter_list, list):
                delimiter_list.append(_delimiter)
                config_manager.set("delimiter_list", delimiter_list)
            else:
                config_manager.set("delimiter_list", [_delimiter])
            self.lineEdit_delimiter_input.clear()
            self.listWidget_delimiter.addItem(_delimiter)

    def del_delimiter(self):
        cur_inx = self.listWidget_delimiter.currentRow()
        if cur_inx > -1:
            delimiter_list = config_manager.get("delimiter_list")
            if isinstance(delimiter_list, list):
                del delimiter_list[cur_inx]
                config_manager.set("delimiter_list", delimiter_list)
            self.listWidget_delimiter.takeItem(cur_inx)

    def _init_data(self):
        self.lineEdit_people_config_thread_number.setValidator(QRegExpValidator(QRegExp(r"\d{2}")))
        self.lineEdit_app_auth.setText(config_manager.get("app_auth"))
        self.lineEdit_read_email_user.setText(config_manager.get("read_email_user"))
        self.lineEdit_read_email_pass.setText(config_manager.get("read_email_pass"))
        self.lineEdit_proxy_platform_pass.setText(config_manager.get("proxy_platform_pass"))
        self.lineEdit_proxy_platform_user.setText(config_manager.get("proxy_platform_user"))
        self.lineEdit_people_config_thread_number.setText(config_manager.get("people_config_thread"))
        self.comboBox_proxy_platform_select.addItems([i.value for i in ProxyPlatform])
        if config_manager.get("proxy_platform_select"):
            self.comboBox_proxy_platform_select.setCurrentIndex(config_manager.get("proxy_platform_select"))
        if config_manager.get("floating_button_is_depend"):
            self.checkBox_data_gen_is_depend.setChecked(True)

        if config_manager.get("notification"):
            self.checkBox_notification.setChecked(True)

        if config_manager.get("table_auto_copy"):
            self.checkBox_table_auto_copy.setChecked(True)

        if config_manager.get("table_copy_line_wrap"):
            self.checkBox_table_copy_line_wrap.setChecked(True)

        if config_manager.get("link_ignore_list"):
            self.listWidget_link_ignore.addItems(config_manager.get("link_ignore_list"))
        else:
            if config_manager.get("link_ignore_list") is None:
                self.listWidget_link_ignore.addItems(DEFAULT_PASS_NETLOC)
                config_manager.set("link_ignore_list", DEFAULT_PASS_NETLOC)
        if config_manager.get("delimiter_list"):
            self.listWidget_delimiter.addItems(config_manager.get("delimiter_list"))
        else:
            if config_manager.get("delimiter_list") is None:
                self.listWidget_delimiter.addItems(DEFAULT_DELIMITER)
                config_manager.set("delimiter_list", DEFAULT_DELIMITER)

        if key := config_manager.get("auth_password"):
            self.lineEdit_app_auth.setText(key)
            msg = validate_short_license_key(key)
            if msg["msg"] == "许可证有效":
                self.label_auth_pass_msg.setText(msg["expiration_iso"])
                self.label_auth_pass_msg.setProperty("status", "valid")
            else:
                self.label_auth_pass_msg.setText(msg["msg"])
                self.label_auth_pass_msg.setProperty("status", "invalid")
            self.style().polish(self.label_auth_pass_msg)
        else:
            self.label_auth_pass_msg.setText("已过期:1997-01-01T01:01:01+00:00")
            self.label_auth_pass_msg.setProperty("status", "invalid")
            self.style().polish(self.label_auth_pass_msg)

        if config_manager.get("url_pattern_list"):
            for i in config_manager.get("url_pattern_list"):
                self.tableWidget_url_pattern.insertRow(self.tableWidget_url_pattern.rowCount())
                self.tableWidget_url_pattern.setItem(
                    self.tableWidget_url_pattern.rowCount() - 1, 0, QTableWidgetItem(i[0])
                )
                self.tableWidget_url_pattern.setItem(
                    self.tableWidget_url_pattern.rowCount() - 1, 1, QTableWidgetItem(i[1])
                )
                self.tableWidget_url_pattern.setItem(
                    self.tableWidget_url_pattern.rowCount() - 1, 2, QTableWidgetItem(i[2])
                )
