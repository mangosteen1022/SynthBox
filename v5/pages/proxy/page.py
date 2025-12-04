import subprocess
import time

from PyQt5.QtGui import QIcon, QColor, QBrush, QFont
from PyQt5.QtWidgets import QMessageBox, QApplication, QTableWidgetItem, QPushButton, QWidget, QHBoxLayout, QStyle
from PyQt5.QtCore import Qt, QTimer
import logging

from v5.core.gen_auth_key import validate_short_license_key

log = logging.getLogger("SynthBox")

from v5.pages.base.page import BasePage
from .ui import Ui_Form
from .proxy import *
from .cert_installer import cert_installer, check_cert_is_installed
from v5.core.utils import get_icon_path, capture_error, LayoutState
from v5.core.config import config_manager


class ProxyPage(BasePage, Ui_Form):
    page_id_name = "proxy"
    display_text = "代理工具"
    icon_path = "proxy.png"
    order = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.collapsible_medium_widgets = [
            self.groupBox_2,  # 流量统计
            self.groupBox_7,  # 程序代理
            self.groupBox_5,  # 端口设置
            self.groupBox_6,  # 注意事项
        ]
        self.collapsible_compact_widgets = [
            self.groupBox_2,  # 流量统计
            self.groupBox_7,  # 程序代理
            self.groupBox_5,  # 端口设置
            self.groupBox_6,  # 注意事项
            self.groupBox_4,  # 代理设置
        ]

        self.mitm_pending_delete = []
        self.ip_worker_thread = None
        self.signals_bridge = MitmproxySignals()
        self.clipboard = QApplication.clipboard()
        # self.additional_workers = {"kernel"} # 子页面额外工作对象  所有页面固定名称
        self.network_traffic = {"up": 0, "up_save": 0, "down": 0, "down_save": 0}
        self.mitm_delete_timer = QTimer(self)
        self.network_traffic_update_timer = QTimer(self)
        self._connect_signals()
        self._initial_styles()
        self._initial_data()
        self._lock = threading.Lock()
        self.check_secret_key = None

    def set_compact_layout(self, state: LayoutState):
        if state == LayoutState.COMPACT:
            for _ in self.collapsible_compact_widgets:
                _.setVisible(False)
        elif state == LayoutState.MEDIUM:
            for _ in self.collapsible_medium_widgets:
                _.setVisible(False)
        else:
            for _ in self.collapsible_compact_widgets:
                _.setVisible(True)

    def _connect_signals(self):
        self.pushButton_apply_config.clicked.connect(self.service_control_apply_configuration)
        self.pushButton_stop_all.clicked.connect(
            lambda _: self.service_control_batch_control_proxies(TabStatus.Running.show)
        )
        self.pushButton_start_all.clicked.connect(
            lambda _: self.service_control_batch_control_proxies(TabStatus.Stopped.show)
        )
        self.pushButton_proxy_generate.clicked.connect(self.proxy_config_dynamic_proxy)
        self.pushButton_network_refresh.clicked.connect(self.refresh_local_ips_clicked)
        self.pushButton_clear_traffic.clicked.connect(self.clear_traffic_stats_clicked)
        self.pushButton_clear_cache.clicked.connect(self.clear_cache_stats_clicked)
        self.tableWidget_proxy_log.itemDoubleClicked.connect(self.proxy_log_item_double_clicked)
        self.pushButton_install_cert.clicked.connect(self._install_cert)
        # mitm 连接槽函数
        self.signals_bridge.notification.connect(self.send_notification)
        self.signals_bridge.notification.connect(lambda _, y: self.clipboard.setText(y))
        self.signals_bridge.notification.connect(lambda x, y: self.send_log(">".join([x, y])))
        self.signals_bridge.log_message.connect(self.send_log)
        self.signals_bridge.instance_ip.connect(self.upload_table_instance_ip)
        self.signals_bridge.status_changed.connect(self.upload_table_status_changed)
        self.signals_bridge.traffic_update.connect(self.receive_traffic_update)
        self.mitm_delete_timer.timeout.connect(self.upload_table_by_delete_item)
        self.network_traffic_update_timer.timeout.connect(self.upload_table_traffic_update)
        self.checkBox_auto_select_port.clicked.connect(lambda x: self.spinBox_socks5_port.setDisabled(x))

    def _initial_styles(self):
        self.setStyleSheet(
            """
            QGroupBox {font-weight: bold;border: 1px solid #cccccc;border-radius: 4px;margin-top: 4px;padding: 6px 2px 2px 2px;}
            QGroupBox::title {subcontrol-origin: margin;subcontrol-position: top left;padding: 0 5px;left: 10px;color: #333;}
            QPushButton {padding: 3px 6px;border: 1px solid #c0c0c0;border-radius: 2.5px;background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #fAfAfA, stop:1 #E1E1E1);min-height: 20px;}
            QPushButton:hover {background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #E8E8E8, stop:1 #D0D0D0);}
            QPushButton:pressed {background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #D0D0D0, stop:1 #E8E8E8);}
            QPushButton:disabled {background-color: #f0f0f0;color: #a0a0a0;}
            QTableWidget {border: 1px solid #cccccc;gridline-color: #e0e0e0;alternate-background-color: #f8f8fa;selection-background-color: #cceeff;selection-color: #000000;}
            QTableWidget::item {padding: 4px;}
            QHeaderView::section {background-color: #f0f0f0;padding: 5px;border: 1px solid #d8d8d8;border-left: none;border-top: none;font-weight: bold;color: #333;}
            QLineEdit, QSpinBox, QComboBox {padding: 3px;border: 1px solid #cccccc;border-radius: 3px;min-height: 20px;}
            QTabWidget::pane {border: 1px solid #cccccc;border-top: none;}
            QTabBar::tab {background: #e1e1e1;border: 1px solid #c0c0c0;border-bottom: none;border-top-left-radius: 4px;border-top-right-radius: 4px;padding: 6px 12px;margin-right: 1px;color: #333;}
            QTabBar::tab:selected {background: #ffffff;font-weight: bold;border-bottom: 1px solid #ffffff;}
            QTabBar::tab:!selected:hover {background: #efefef;}
            QCheckBox::indicator {width: 16px;height: 16px;}
            """
        )
        self.pushButton_network_refresh.setMinimumSize(25, 25)
        self.pushButton_network_refresh.setMaximumSize(25, 25)
        icon = get_icon_path("refresh.png")
        self.pushButton_network_refresh.setIcon(QIcon(icon))
        self.pushButton_network_refresh.setStyleSheet(
            "QPushButton { padding: -1px; border: none; background: transparent; }"
        )
        self.pushButton_network_refresh.setStyleSheet(
            "QPushButton:hover {background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,stop:0 #E8E8E8, stop:1 #D0D0D0);}"
        )
        self.pushButton_install_cert.setStyleSheet("QPushButton {padding: -1px; border: none;}")

    def _initial_data(self):
        self.comboBox_proxy_scheme.addItems(["SOCKS5", "HTTPS", "HTTP"])
        self.refresh_local_ips_clicked()
        self.check_cert_is_installed()
        self.lineEdit_username.setPlaceholderText("用户名(可选)")
        self.lineEdit_password.setPlaceholderText("密码(可选)")
        self.lineEdit_proxy.setPlaceholderText("填入其他代理(可选)")
        self.lineEdit_state_city.setPlaceholderText("州 城市(starry平台代理指定城市必须同时指定州)")
        self.lineEdit_username.setText(config_manager.get("proxy_platform_user"))
        self.lineEdit_password.setText(config_manager.get("proxy_platform_pass"))
        self.comboBox_proxy_platform.addItems([i.value for i in ProxyPlatform])
        if config_manager.get("proxy_platform_select"):
            self.comboBox_proxy_platform.setCurrentIndex(config_manager.get("proxy_platform_select"))
        self.comboBox_select_country.addItems(["US", "CA"])
        self.add_network_flow_entry("0 B", "0 B", "0 B")
        self.mitm_delete_timer.start(1000)
        self.network_traffic_update_timer.start(1000)
        self.checkBox_auto_select_port.setChecked(True)
        self.spinBox_socks5_port.setDisabled(True)
        self.label_precautions.setText(
            """
        * 代理配置后，点应用配置启动,复制[代理:端口]使用,协议HTTP,不生成代理则默认直连
        * 自定义端口5000-60000,自动端口30000-40000
        * 启动前需管理员权限安装证书
        * 一代理尽量一浏览器(多浏览器需版本不同),否则指纹伪装失效
        * 尽量代理浏览器，同代理同版本浏览器需重启代理,否则指纹伪装失效
        * 如果其他设备连接代理,则其他设备也需安装证书,可为其他设备充当vpn(建议直连使用)
        """.replace(
                "        ", ""
            )
        )

    def check_cert_is_installed(self):
        if check_cert_is_installed():
            self.pushButton_install_cert.setText("✅证书已安装")

    @QtCore.pyqtSlot()
    @capture_error(is_traceback=True)
    def _install_cert(self):
        if cert_installer():
            self.send_log("✅ 检测到 mitmproxy 证书已经安装")
            self.pushButton_install_cert.setText("✅证书已安装")
        else:
            self.send_log("✅ 检测到 mitmproxy 证书安装失败，请安装证书")
            self.pushButton_install_cert.setText("❌证书安装失败")

    @QtCore.pyqtSlot(int, str)
    @capture_error(is_traceback=True)
    def upload_table_instance_ip(self, port, instance_ip):
        """更新表中实例ip"""
        for row in range(self.tableWidget_proxy_log.rowCount()):
            host_port_item = self.tableWidget_proxy_log.item(row, 0)
            row_id = host_port_item.text().split(":")[1]
            if str(port) == row_id:
                self.tableWidget_proxy_log.item(row, 1).setText(instance_ip)
                return

    @QtCore.pyqtSlot(int, str)
    @capture_error(is_traceback=True)
    def upload_table_status_changed(self, port, status):
        """更新表中代理任务状态"""
        self.send_log(f"端口:{port}更新状态:[{status}]")
        for row in range(self.tableWidget_proxy_log.rowCount()):
            host_port_item = self.tableWidget_proxy_log.item(row, 0)
            row_id = host_port_item.text().split(":")[1]
            if str(port) == row_id:
                self.table_on_status_changed(row_id, status)

    @QtCore.pyqtSlot()
    @capture_error(is_traceback=True)
    def upload_table_traffic_update(self):
        """更新统计表中流量使用状态"""
        # 默认接收的单位都为B
        table = self.tableWidget_network_flow
        all_up = self.network_traffic["up"]
        all_up_save = self.network_traffic["up_save"]
        all_down = self.network_traffic["down"]
        all_down_save = self.network_traffic["down_save"]
        item_0 = f"{traffic_conversion(all_up)}({traffic_conversion(all_up_save)})"
        item_1 = f"{traffic_conversion(all_down)}({traffic_conversion(all_down_save)})"
        item_2 = f"{traffic_conversion(all_up + all_down)}({traffic_conversion(all_up_save + all_down_save)})"
        table.item(0, 0).setText(item_0)
        table.item(0, 1).setText(item_1)
        table.item(0, 2).setText(item_2)

    @QtCore.pyqtSlot(int, dict)
    @capture_error(is_traceback=True)
    def receive_traffic_update(self, port, traffic):
        with self._lock:
            self.network_traffic["up"] += traffic["up"][0]
            self.network_traffic["up_save"] += traffic["up"][1]
            self.network_traffic["down"] += traffic["down"][0]
            self.network_traffic["down_save"] += traffic["down"][1]

    @QtCore.pyqtSlot()
    @capture_error(is_traceback=True)
    def upload_table_by_delete_item(self):
        table = self.tableWidget_proxy_log
        if self.mitm_pending_delete:
            for row in range(table.rowCount()):
                try:
                    host_port_item = table.item(row, 0)
                    if not host_port_item:
                        continue
                    row_id = host_port_item.text().split(":")[1]
                    if row_id in self.mitm_pending_delete:
                        task = self.workers.get(row_id)
                        if task and not task.get("worker"):
                            table.removeRow(row)
                            if row_id in self.mitm_pending_delete:
                                self.mitm_pending_delete.remove(row_id)
                            if row_id in self.workers:
                                self.workers.pop(row_id)
                except (Exception,) as e:
                    log.exception(str(e))
            self.label_proxy_count.setText(f"活动代理数:{table.rowCount()}")

    @capture_error(is_traceback=True)
    def _service_control_find_available_port(self, port: int = None) -> (int, int):
        """mitm占用30000-40000"""
        listen_port = port
        used_port = [int(i) for i in self.workers]
        if listen_port:
            if listen_port not in used_port and not check_port_using(listen_port):
                return listen_port
            return None
        for listen_port in range(30000, 40000):
            if listen_port not in used_port and not check_port_using(listen_port):
                return listen_port
        return None

    @QtCore.pyqtSlot()
    @capture_error(is_traceback=True)
    def service_control_apply_configuration(self):
        """应用配置"""
        if not self.check_secret_key or (int(time.time()) >= (self.check_secret_key + 180)):
            password = config_manager.get("auth_password")
            if not password:
                self.send_log("请在设置页面进行秘钥认证!")
                return
            msg = validate_short_license_key(password)
            if msg["msg"] != "许可证有效":
                self.send_log(msg["msg"])
                return
            self.check_secret_key = int(time.time())

        # 更新日志条目以反映新配置的应用
        # 将端口作为唯一id
        listen_port = None
        listen_host = self.comboBox_localhost.currentText()
        if not self.checkBox_auto_select_port.isChecked():
            listen_port = self.spinBox_socks5_port.value()
            if not (5000 <= listen_port <= 60000):
                self.send_log("当前端口不可用,SOCKS5|HTTP/S范围[5000-60000]")
                return
        listen_port = self._service_control_find_available_port(listen_port)
        if not listen_port:
            self.send_log("当前端口被占用或不可用")
            return
        if not self.proxy_config_dynamic_proxy(True):  # 如何没有填写用户名密码,则跳过,如何填了,但是生成失败,则返回错误
            self.send_log("已填写[用户名,密码],但是代理生成失败,请检查州跟城市是否正确")
            return
        proxy = self.lineEdit_proxy.text().strip()
        proxy_scheme = self.comboBox_proxy_scheme.currentText().lower()
        if not proxy:
            self.send_log("未填写用户名,密码,并且当前代理为空,启用直连模式")
            proxy_host, proxy_port, proxy_user, proxy_pass = None, None, None, None
        else:
            proxy_host, proxy_port, proxy_user, proxy_pass = format_proxy(proxy)
            if not proxy_host or not proxy_port:
                self.send_log("代理格式不正确!")
                return
            self.send_log(f"代理:{proxy_host}:{proxy_port} auth:[{proxy_user}:{proxy_pass}]")
        # self.workers[str(listen_port)] = {"worker": None, "config": , "status": TabStatus.Starting.show}
        self.table_on_status_changed(
            str(listen_port),
            TabStatus.Starting.show,
            config={
                "scheme": proxy_scheme,
                "proxy_host": proxy_host,
                "proxy_port": proxy_port,
                "listen_host": listen_host,
                "listen_port": listen_port,
                "proxy_user": proxy_user,
                "proxy_pass": proxy_pass,
            },
        )

    @QtCore.pyqtSlot(str)
    @capture_error(is_traceback=True)
    def service_control_batch_control_proxies(self, status_control):
        """启动所有代理实例"""

        if status_control == TabStatus.Stopped.show:  # 批量启动完全停止的
            on_change = TabStatus.Starting.show
        else:  # TabStatus.Running.show 批量停止完全启动的
            on_change = TabStatus.Stopping.show
        for row in range(self.tableWidget_proxy_log.rowCount()):
            host_port_item = self.tableWidget_proxy_log.item(row, 0)
            status = self.tableWidget_proxy_log.item(row, 2).text()
            row_id = host_port_item.text().split(":")[1]
            if self.workers.get(row_id) and status == status_control:
                self.table_on_status_changed(row_id, on_change)

    @capture_error(is_traceback=True)
    def service_force_close(self, port_or_row_id: str):
        if port := self._service_control_find_available_port(int(port_or_row_id)):

            def find_pid_by_port():
                """查找占用指定端口的进程ID"""
                command = f"netstat -ano | findstr :{port}"
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                lines = result.stdout.splitlines()

                if not lines:
                    return None
                for line in lines:
                    parts = line.split()
                    if len(parts) > 4:
                        pid = parts[-1]
                        return pid
                return None

            def kill_process(pid):
                """终止指定进程ID的进程"""
                if str(pid) == "0":
                    return
                try:
                    command = f"taskkill /F /PID {pid}"
                    result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"成功终止进程ID {pid}")
                    else:
                        print(f"终止进程ID {pid} 失败: {result.stderr}")
                except Exception as e:
                    print(f"终止进程ID {pid} 时出错: {e}")

            if _pid := find_pid_by_port():
                kill_process(_pid)

    @capture_error(is_traceback=True)
    def table_on_status_changed(self, port_or_row_id: str, status: str, config: dict = None):

        if status == TabStatus.Starting.show:
            if not config:
                config = self.workers[port_or_row_id]["config"]
            listen_host_port = f"{config["listen_host"]}:{port_or_row_id}"
            self.service_force_close(port_or_row_id)
            worker = MitmproxyWorker(config, signals=self.signals_bridge)
            self.workers[port_or_row_id] = {"worker": worker, "config": config}
            row = self._find_row_by_row_id(port_or_row_id)
            if row is None:  # 创建新行
                self.table_add_proxy_log_entry(listen_host_port, "检测中", TabStatus.Starting.show)
                row = self._find_row_by_row_id(port_or_row_id)
            self.update_action_buttons_for_row(row, TabStatus.Starting.show, port_or_row_id)
            item = self.tableWidget_proxy_log.item(row, 2)
            item.setForeground(QColor(TabStatus.Starting.color))
            item.setFont(QFont("Arial", weight=QFont.Bold))
            self.tableWidget_proxy_log.item(row, 2).setText(status)
            self.clipboard.setText(listen_host_port)
            self.send_log("配置已应用，代理启动/更新。")
            self.workers[str(port_or_row_id)]["worker"].start()
            self.set_row_disable_status(row, False)

        elif status == TabStatus.Running.show:
            row = self._find_row_by_row_id(port_or_row_id)
            if row is None:  # 创建新行
                return
            item = self.tableWidget_proxy_log.item(row, 2)
            item.setForeground(QColor(TabStatus.Running.color))
            item.setFont(QFont("Arial", weight=QFont.Bold))
            self.tableWidget_proxy_log.item(row, 2).setText(status)
            self.update_action_buttons_for_row(row, TabStatus.Running.show, port_or_row_id)
            self.set_row_disable_status(row, True)

        elif status == TabStatus.Stopping.show:
            row = self._find_row_by_row_id(port_or_row_id)
            if row is None:  # 创建新行
                return
            item = self.tableWidget_proxy_log.item(row, 2)
            item.setForeground(QColor(TabStatus.Stopping.color))
            item.setFont(QFont("Arial", weight=QFont.Bold))
            self.workers[port_or_row_id]["worker"].stop()
            self.tableWidget_proxy_log.item(row, 2).setText(status)
            self.update_action_buttons_for_row(row, TabStatus.Stopping.show, port_or_row_id)
            self.set_row_disable_status(row, False)

        elif status == TabStatus.Stopped.show:
            row = self._find_row_by_row_id(port_or_row_id)
            if row is None:  # 创建新行
                return
            item = self.tableWidget_proxy_log.item(row, 2)
            item.setForeground(QColor(TabStatus.Stopped.color))
            item.setFont(QFont("Arial", weight=QFont.Bold))
            self.service_force_close(port_or_row_id)
            self.workers[port_or_row_id]["worker"] = None
            if self.workers[port_or_row_id].get("del_flag"):  # 如果获取到删除标志,则更新删除状态
                self.table_on_status_changed(port_or_row_id, TabStatus.Delete.show)
                return
            self.tableWidget_proxy_log.item(row, 2).setText(status)
            self.update_action_buttons_for_row(row, TabStatus.Stopped.show, port_or_row_id)
            self.set_row_disable_status(row, True)

        elif status == TabStatus.Error.show:
            row = self._find_row_by_row_id(port_or_row_id)
            if row is None:  # 创建新行
                return
            item = self.tableWidget_proxy_log.item(row, 2)
            item.setForeground(QColor(TabStatus.Error.color))
            item.setFont(QFont("Arial", weight=QFont.Bold))
            self.workers[port_or_row_id]["worker"] = None
            self.tableWidget_proxy_log.item(row, 2).setText(status)
            self.update_action_buttons_for_row(row, TabStatus.Error.show, port_or_row_id)

        elif status == TabStatus.Delete.show:
            row = self._find_row_by_row_id(port_or_row_id)
            if row is None:  # 创建新行
                return
            self.set_row_disable_status(row, False)
            if self.workers[port_or_row_id]["worker"]:
                self.workers[port_or_row_id]["del_flag"] = True
                self.table_on_status_changed(port_or_row_id, TabStatus.Stopping.show)
            else:
                row = self._find_row_by_row_id(port_or_row_id)
                if row is None:  # 创建新行
                    return
                item = self.tableWidget_proxy_log.item(row, 2)
                item.setForeground(QColor(TabStatus.Delete.color))
                item.setFont(QFont("Arial", weight=QFont.Bold))
                self.service_force_close(port_or_row_id)
                self.workers[port_or_row_id]["worker"] = None
                self.tableWidget_proxy_log.item(row, 2).setText("删除中")
                self.update_action_buttons_for_row(row, TabStatus.Delete.show, port_or_row_id)
                self.mitm_pending_delete.append(port_or_row_id)

    @QtCore.pyqtSlot(bool)
    @capture_error(is_traceback=True)
    def proxy_config_dynamic_proxy(self, _):
        """动态生成代理"""
        platform = self.comboBox_proxy_platform.currentText()
        username = self.lineEdit_username.text()
        password = self.lineEdit_password.text()
        if not username or not password:
            if _ is False:  # 动态生成按钮触发
                self.send_log("<动态生成>用户名或密码不能为空")
                self.lineEdit_proxy.setText("")  # 清空代理,如果用户填入自定义代理,并点击动态生成按钮,则清空代理
                # 如果输入了自定义代理,由应用配置按钮触发,忽略返回值,则使用自定义代理,不清空代理
            return True  # 动态生成忽略返回值,针对应用配置按钮触发,没有username,password就默认直连,不是错误
        state_city = self.lineEdit_state_city.text()
        state, city = split_state_city(state_city)
        country = self.comboBox_select_country.currentText()
        proxy = generate_proxy(platform, username, password, country=country, state=state, city=city, timeout=20)
        if not proxy:
            if _ is False:  # 动态生成按钮触发
                self.send_log("<动态生成>未正确生成代理,starry平台代理指定城市必须同时指定州")
            # 如果填写了自定义代理,但是有用户名和密码,则在错误时清空代理
            self.lineEdit_proxy.setText("")
            return False  # 动态生成忽略返回值,针对应用配置按钮触发,有username,password但是生成错误,则返回错误
        self.send_log(f"[生成代理]:{proxy}")
        self.lineEdit_proxy.setText(proxy)
        return True  # 动态生成忽略返回值,,针对应用配置按钮触发,有username,password,生成成功则返回正确

    @QtCore.pyqtSlot()
    @capture_error(is_traceback=True)
    def refresh_local_ips_clicked(self):
        """刷新本地ip跟网络ip"""
        self.send_log("正在刷新本地IP列表...")
        self.comboBox_localhost.clear()
        socket_hostname = get_socket_hostname()
        self.comboBox_localhost.addItems(socket_hostname)
        self.send_log(f"获取本地IP成功: {socket_hostname}")

        self.pushButton_network_refresh.setEnabled(False)
        self.label_local_network.setText("网络 IP: 正在获取...")
        self.ip_worker_thread = QtCore.QThread()
        self.ip_worker = NetworkIpWorker()
        self.ip_worker.moveToThread(self.ip_worker_thread)
        self.ip_worker_thread.started.connect(self.ip_worker.run)
        self.ip_worker.finished.connect(lambda s: self.label_local_network.setText(f"网络 IP: {s}"))
        self.ip_worker.finished.connect(lambda s: self.pushButton_network_refresh.setEnabled(True))
        self.ip_worker.finished.connect(self.ip_worker_thread.quit)
        self.ip_worker.finished.connect(self.ip_worker.deleteLater)
        self.ip_worker_thread.finished.connect(self.ip_worker_thread.deleteLater)
        self.ip_worker_thread.start()

    @QtCore.pyqtSlot()
    @capture_error(is_traceback=True)
    def clear_traffic_stats_clicked(self):
        """清理流量统计表"""
        self.network_traffic = {"up": 0, "up_save": 0, "down": 0, "down_save": 0}
        self.send_log("流量统计已清理。")

    @QtCore.pyqtSlot()
    @capture_error(is_traceback=True)
    def clear_cache_stats_clicked(self):
        self.send_log("正在清理过期缓存...")
        self.pushButton_clear_cache.setEnabled(False)
        self.clear_cache_thread = QtCore.QThread()
        self.clear_cache = ClearCache()
        self.clear_cache.moveToThread(self.clear_cache_thread)
        self.clear_cache_thread.started.connect(self.clear_cache.run)
        self.clear_cache.finished.connect(lambda s: self.pushButton_clear_cache.setText(f"清理缓存"))
        self.clear_cache.finished.connect(lambda s: self.pushButton_clear_cache.setEnabled(True))
        self.clear_cache.finished.connect(lambda s: self.send_log(f"清理过期缓存:{s}个"))
        self.clear_cache.finished.connect(self.clear_cache_thread.quit)
        self.clear_cache.finished.connect(self.clear_cache.deleteLater)
        self.clear_cache_thread.finished.connect(self.clear_cache_thread.deleteLater)
        self.clear_cache_thread.start()

    @QtCore.pyqtSlot(QTableWidgetItem)
    @capture_error(is_traceback=True)
    def proxy_log_item_double_clicked(self, item: QTableWidgetItem):
        """表格操作"""
        if not item:
            return
        row = item.row()
        local_port_info = self.tableWidget_proxy_log.item(row, 0).text()
        log_message = f"双击了代理日志第 {row + 1} 行: {local_port_info}"
        self.send_log(log_message)

    @capture_error(is_traceback=True)
    def table_add_proxy_log_entry(self, host_port: str, instance_ip: str, status: str):
        """添加代理实例表"""
        table = self.tableWidget_proxy_log
        row_position = table.rowCount()
        table.insertRow(row_position)
        table.setItem(row_position, 0, QTableWidgetItem(host_port))
        table.setItem(row_position, 1, QTableWidgetItem(instance_ip))
        status_item = QTableWidgetItem(status)
        table.setItem(row_position, 2, status_item)
        self.label_proxy_count.setText(f"活动代理数:{table.rowCount()}")
        table.scrollToBottom()

    @staticmethod
    @capture_error(is_traceback=True)
    def _create_proxy_log_button(row_id):
        btn = QPushButton()
        btn.setStyleSheet("QPushButton { padding: -1px; border: none; background: transparent;}")
        btn.setProperty("row_id", row_id)
        return btn

    @capture_error(is_traceback=True)
    def update_action_buttons_for_row(self, row: int, status: str, row_id: str | int):
        """根据状态更新或创建给定行的操作按钮"""
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(2, 2, 2, 2)
        action_layout.setSpacing(10)

        start_stop_button = self._create_proxy_log_button(row_id)

        if status in [TabStatus.Starting.show, TabStatus.Running.show]:
            start_stop_button.setToolTip("停止此代理实例")
            start_stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        else:
            start_stop_button.setToolTip("启动此代理实例")
            start_stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

        start_stop_button.clicked.connect(self.handle_start_stop_single_proxy)
        action_layout.addWidget(start_stop_button)

        delete_button = self._create_proxy_log_button(row_id)
        delete_button.setToolTip("删除此代理配置")
        delete_button.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))  # Example icon
        delete_button.clicked.connect(self.handle_delete_single_proxy)
        action_layout.addWidget(delete_button)

        action_layout.addStretch()
        self.tableWidget_proxy_log.setCellWidget(row, 3, action_widget)

    @QtCore.pyqtSlot()
    @capture_error(is_traceback=True)
    def handle_start_stop_single_proxy(self):
        button = self.sender()
        if not button:
            return
        row_id = button.property("row_id")
        row = self._find_row_by_row_id(row_id)
        status_item = self.tableWidget_proxy_log.item(row, 2)
        if status_item.text() == TabStatus.Running.show:
            self.table_on_status_changed(row_id, TabStatus.Stopping.show)
        else:
            self.table_on_status_changed(row_id, TabStatus.Starting.show)

    @capture_error(is_traceback=True)
    def _find_row_by_row_id(self, row_id):
        for row in range(self.tableWidget_proxy_log.rowCount()):
            host_port_item = self.tableWidget_proxy_log.item(row, 0)
            _row_id = host_port_item.text().split(":")[1]
            if row_id == _row_id:
                return row
        return None

    @capture_error(is_traceback=True)
    def set_row_disable_status(self, row_index: int, enabled: bool = True):
        table = self.tableWidget_proxy_log
        if not (0 <= row_index < table.rowCount()):
            return
        if enabled:  # 启用逻辑
            background_brush = QBrush()
            flags_modifier = lambda flags: flags | Qt.ItemIsEnabled
        else:  # 禁用逻辑
            background_brush = QBrush(QColor(240, 240, 240))
            flags_modifier = lambda flags: flags & ~Qt.ItemIsEnabled
        for col_index in range(table.columnCount()):
            widget = table.cellWidget(row_index, col_index)
            if widget:
                widget.setEnabled(enabled)
            item = table.item(row_index, col_index)
            if item:
                item.setFlags(flags_modifier(item.flags()))
                item.setBackground(background_brush)

    @QtCore.pyqtSlot()
    @capture_error(is_traceback=True)
    def handle_delete_single_proxy(self):
        button = self.sender()
        if not button:
            return
        row_id = button.property("row_id")
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"您确定要删除代理 '{row_id}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            if row_id:
                self.table_on_status_changed(row_id, TabStatus.Delete.show)
        else:
            self.send_log(f"取消删除代理: {row_id}")

    @capture_error(is_traceback=True)
    def add_network_flow_entry(self, upload: str, download: str, total: str):
        """向流量统计表格添加一行。"""
        table = self.tableWidget_network_flow
        row_position = table.rowCount()
        table.insertRow(row_position)
        table.setItem(row_position, 0, QTableWidgetItem(upload))
        table.setItem(row_position, 1, QTableWidgetItem(download))
        table.setItem(row_position, 2, QTableWidgetItem(total))
        table.scrollToBottom()
