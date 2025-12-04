import csv
import os
import re
import time
import logging

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox

from v4.pages import BasePage
from .ui import Ui_Form
from v4.core.utils import get_icon_path, LayoutState, capture_error
from v4.core.config import config_manager
from v4.core.query_ssn import QuerySSN, format_details, labels, QueryWorker, validate_and_format_zip
from v4.layout.ExportDialog import MultiTableExportDialog
from v4.core.gen_auth_key import validate_short_license_key

log = logging.getLogger("SynthBox")


class PeoplePage(BasePage, Ui_Form):
    page_id_name = "people"
    display_text = "反查工具"
    icon_path = "ssn.png"
    order = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.collapsible_medium_widgets = [
            # self.groupBox_3,  # 查询结果
            # self.groupBox_4,  # 过滤结果
            self.groupBox_remark,  # 资料格式
            self.pushButton_hide_format,
            # self.groupBox,  # 单次查询
            # self.groupBox_2,  # 批量查询
        ]
        self.collapsible_compact_widgets = [
            self.groupBox_4,  # 过滤结果
            self.groupBox_remark,  # 资料格式
            self.pushButton_hide_format,
        ]

        self.active_query_count = 0
        self.names_map = {
            "street": "address",
            "first": "firstname",
            "last": "lastname",
            "mid": "middlename",
            "county": "county_name",
            "state": "st",
            "birth": "birthday",
        }
        self.tab_cols = ["first", "mid", "last", "birth", "street", "city", "county", "state", "zip", "ssn"]
        self.no_filter_tag = "选择列"
        self.combox_filter_items = [self.no_filter_tag] + self.tab_cols
        self._init_data()
        # self._init_style()
        self._connect_signals()
        self.file_path = None
        self.check_secret_key = None
        self.file_details = None
        self._is_updating_combos = False

        self.thread_pool = QtCore.QThreadPool()
        self.query_thread_pool = QtCore.QThreadPool()

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

    def _init_data(self):
        self.comboBox.setEditable(True)
        self.comboBox_delimiter.setEditable(True)
        delimiters = config_manager.get("delimiter_list", [])
        remarks = list(config_manager.get("file_config", {}).keys())
        self.comboBox_delimiter.addItems(delimiters)
        self.comboBox.addItems(remarks)
        self.get_file_config()
        self.lineEdit_name.setPlaceholderText("first [mid] last")
        self.lineEdit_address.line_edit.setPlaceholderText("street [city,county] state zip")
        self.lineEdit_filter_1.setPlaceholderText("过滤值")
        self.lineEdit_filter_2.setPlaceholderText("过滤值")
        self.lineEdit_filter_3.setPlaceholderText("过滤值")
        self.comboBox_filter_1.addItems(self.combox_filter_items)
        self.comboBox_filter_2.addItems(self.combox_filter_items)
        self.comboBox_filter_3.addItems(self.combox_filter_items)

    def _init_style(self): ...

    def _connect_signals(self):
        self.pushButton_hide_format.clicked.connect(self.toggle_remark_visibility)
        self.pushButton_query.clicked.connect(self.query_ssn)
        self.pushButton_clear.clicked.connect(self.clear_up)
        self.pushButton_filter_clear.clicked.connect(self.clear_filter_query_result)
        self.pushButton_filter.clicked.connect(self.filter_query_result)
        self.pushButton_export.clicked.connect(self.export_query_result)
        self.pushButton_up_file.clicked.connect(self.upload_file)
        self.comboBox.currentIndexChanged.connect(self.get_file_config)
        self.pushButton_format_save.clicked.connect(self.save_file_config)
        self.pushButton_format_delete.clicked.connect(self.delete_file_config)
        self.pushButton_batch_query.clicked.connect(self.batch_query)
        self.comboBox_filter_1.currentTextChanged.connect(self._update_filter_combos)
        self.comboBox_filter_2.currentTextChanged.connect(self._update_filter_combos)
        self.comboBox_filter_3.currentTextChanged.connect(self._update_filter_combos)

    def _update_filter_combos(self):
        if self._is_updating_combos:
            return
        self._is_updating_combos = True
        try:
            combos = [self.comboBox_filter_1, self.comboBox_filter_2, self.comboBox_filter_3]
            selections = [combo.currentText() for combo in combos]
            for i, combo_to_update in enumerate(combos):
                current_selection = selections[i]
                other_selections = set(selections)
                other_selections.remove(current_selection)
                columns_to_exclude = {sel for sel in other_selections if sel != self.no_filter_tag}
                available_options = [self.no_filter_tag]
                for option in self.tab_cols:
                    if option not in columns_to_exclude or option == current_selection:
                        available_options.append(option)

                # 重新填充并恢复选中
                combo_to_update.clear()
                combo_to_update.addItems(available_options)
                if current_selection in available_options:
                    combo_to_update.setCurrentText(current_selection)

        finally:
            # 5. 解除锁定，允许下一次更新
            self._is_updating_combos = False

    def toggle_remark_visibility(self):
        """切换 groupBox_remark 的可见性。"""
        if self.groupBox_remark.isVisible():
            self.groupBox_remark.hide()
            self.pushButton_hide_format.setText("显示格式")
        else:
            self.groupBox_remark.show()
            self.pushButton_hide_format.setText("隐藏格式")

    def clear_up(self):
        self.lineEdit_name.clear()
        self.lineEdit_address.line_edit.clear()
        self.lineEdit_address.popup_editor.clear()
        self.tableWidget_query_result.setRowCount(0)

    def clear_filter_query_result(self):
        self.tableWidget_filter_query_result.setRowCount(0)

    def export_query_result(self):
        table_names = ["查询结果", "过滤结果"]
        if self.tableWidget_filter_query_result.rowCount() == 0 and self.tableWidget_query_result.rowCount() == 0:
            QMessageBox.warning(self, "提示", "表格中没有数据可导出")
            return
        settings = MultiTableExportDialog.getMultiExportSettings(self, table_names=table_names)

        if settings:
            selected_table_name = settings["selected_table_name"]
            if selected_table_name == "过滤结果":
                table_widget = self.tableWidget_filter_query_result
            else:
                table_widget = self.tableWidget_query_result
            self.export_table_data(settings, table_widget)

    def export_table_data(self, settings, table_widget):
        """修改此函数，使其接受一个table_widget参数"""
        file_path = settings["file_path"]
        delimiter = settings["delimiter"]
        include_header = settings["include_header"]

        # 检查传入的表格是否有内容
        if table_widget.rowCount() == 0:
            QMessageBox.warning(self, "提示", f"表格 '{settings['selected_table_name']}' 中没有数据可导出。")
            return
        try:
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, delimiter=delimiter)
                if include_header:
                    headers = [table_widget.horizontalHeaderItem(i).text() for i in range(table_widget.columnCount())]
                    writer.writerow(headers)

                for row in range(table_widget.rowCount()):
                    row_data = [
                        table_widget.item(row, col).text() if table_widget.item(row, col) else ""
                        for col in range(table_widget.columnCount())
                    ]
                    writer.writerow(row_data)

            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("成功")
            msg_box.setText(f"数据已成功导出到:\n{file_path}")
            open_button = msg_box.addButton("打开文件", QMessageBox.ActionRole)
            _ = msg_box.addButton("确定", QMessageBox.AcceptRole)
            msg_box.exec_()
            if msg_box.clickedButton() == open_button:
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")

    @staticmethod
    def _translate_sql_like_to_regex(pattern):
        regex_parts = []
        i, n = 0, len(pattern)
        while i < n:
            char = pattern[i]
            if char == "%":
                regex_parts.append(".*")  # % -> .*
            elif char == "_":
                regex_parts.append(".")  # _ -> .
            else:
                regex_parts.append(re.escape(char))
            i += 1
        regex = "".join(regex_parts)
        return re.compile(f"^{regex}$", re.IGNORECASE)

    def filter_query_result(self):
        need_filter_row_data = []
        active_filters = []
        combox_filters = [
            (self.comboBox_filter_1, self.lineEdit_filter_1),
            (self.comboBox_filter_2, self.lineEdit_filter_2),
            (self.comboBox_filter_3, self.lineEdit_filter_3),
        ]
        for combo, line_edit in combox_filters:
            col_name = combo.currentText()
            filter_value = line_edit.text()
            if col_name != self.no_filter_tag and filter_value:
                try:
                    col_index = self.tab_cols.index(col_name)
                    regex_pattern = self._translate_sql_like_to_regex(filter_value)
                    active_filters.append({"col_index": col_index, "pattern": regex_pattern})
                except ValueError:
                    self.send_log(f"错误：列名 '{col_name}' 不存在于 tab_cols 中。")
                    continue  # 如果列名无效，则跳过
        if not active_filters:
            self.send_log("请输入有效的过滤条件（选择列并填写值）。")
            return
        for row in range(self.tableWidget_query_result.rowCount()):
            # 获取整行的数据
            row_data = [
                self.tableWidget_query_result.item(row, col).text()
                for col in range(self.tableWidget_query_result.columnCount())
            ]
            is_match = True
            for _ in active_filters:
                cell_value = row_data[_["col_index"]]
                if not _["pattern"].match(cell_value):
                    is_match = False
                    break  # 只要有一个条件不满足，就无需再检查该行的其他条件
            if is_match:
                need_filter_row_data.append(row_data)
        if need_filter_row_data:
            for row_data in need_filter_row_data:
                row = self.tableWidget_filter_query_result.rowCount()
                self.tableWidget_filter_query_result.insertRow(row)
                for col, item in enumerate(row_data):
                    self.tableWidget_filter_query_result.setItem(row, col, QTableWidgetItem(item))
        else:
            self.send_log("未找到匹配项")

    def upload_file(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择文件", os.getcwd(), "文本文档 (*.txt)")
        if file_name:
            self.send_log(f"已选择文件:{os.path.basename(file_name)}")
            self.label_batch_status.setText(f"文件:{os.path.basename(file_name)}")
            self.file_path = file_name
            self.file_details = None

    def get_file_config(self):
        current_remark = self.comboBox.currentText()
        if not current_remark:
            self.send_log("请填写备注")
            return
        file_config = config_manager.get("file_config")
        config = file_config.get(current_remark)
        if config:
            for line in labels:
                control = self.__getattribute__(f"lineEdit_{line}")
                control.setText(config.get(line))
            delimiter = config.get("delimiter")
            self.comboBox_delimiter.setCurrentText(delimiter)
        else:
            for line in labels:
                control = self.__getattribute__(f"lineEdit_{line}")
                control.setText("")
            self.send_log(f"未找到文件配置:{current_remark}")

    def save_file_config(self):
        current_remark = self.comboBox.currentText()
        current_delimiter = self.comboBox_delimiter.currentText()
        file_config = config_manager.get("file_config", {})
        add_new = False
        if current_remark not in file_config:
            add_new = True
        file_config[current_remark] = {line: self.__getattribute__(f"lineEdit_{line}").text() for line in labels}
        file_config[current_remark]["delimiter"] = current_delimiter
        config_manager.set("file_config", file_config)
        self.send_log(f"已保存文件配置:{current_remark}")
        delimiter_list = config_manager.get("delimiter_list", [])
        if current_delimiter not in delimiter_list:
            delimiter_list.append(current_delimiter)
            config_manager.set("delimiter_list", delimiter_list)
        all_items = [self.comboBox.itemText(i) for i in range(self.comboBox.count())]
        if add_new and current_remark not in all_items:
            self.comboBox.addItem(current_remark)

    def delete_file_config(self):
        current_remark = self.comboBox.currentText()
        file_config = config_manager.get("file_config")
        if current_remark in file_config:
            file_config.pop(current_remark)
            self.comboBox.removeItem(self.comboBox.findText(current_remark))
            self.send_log(f"已删除文件配置:{current_remark}")
        config_manager.set("file_config", file_config)

    @QtCore.pyqtSlot(str, object)
    def query_finished(self, org_addr, addr_list):
        self.active_query_count -= 1
        if self.active_query_count == 0 or self.query_thread_pool.activeThreadCount() == 0:
            self.query_thread_pool.clear()
            self.pushButton_query.setDisabled(False)
        if not addr_list:
            self.send_log(f"地址 {org_addr} 无结果")
            return
        if isinstance(addr_list, str):
            self.send_log(f"地址 {org_addr} {addr_list},请重新查询")
            return
        table = self.tableWidget_query_result
        for addr in addr_list:
            row_position = table.rowCount()
            table.insertRow(row_position)
            for inx, item in enumerate(self.tab_cols):
                field = addr.get(self.names_map.get(item, item), "")
                table.setItem(row_position, inx, QTableWidgetItem(field))
            table.scrollToBottom()

    @QtCore.pyqtSlot(str, object)
    def batch_query_finished(self, org_addr, addr_list):
        active_threads = self.thread_pool.activeThreadCount()
        if active_threads == 0:
            self.pushButton_batch_query.setDisabled(False)
            self.pushButton_batch_query.setText("批量查询")
        if not addr_list:
            self.send_log(f"地址 {org_addr} 无结果")
            return
        if isinstance(addr_list, str):
            self.send_log(f"地址 {org_addr} {addr_list},已重新添加到待查询列表")
            return
        table = self.tableWidget_query_result
        for addr in addr_list:
            row_position = table.rowCount()
            table.insertRow(row_position)
            for inx, item in enumerate(self.tab_cols):
                field = addr.get(self.names_map.get(item, item), "")
                table.setItem(row_position, inx, QTableWidgetItem(field))
            table.scrollToBottom()

    @staticmethod
    def find_used_delimiters(address_string, delimiters):
        found = [d for d in delimiters if d in address_string]
        return len(found)

    def query_ssn(self):
        """查询 SSN。"""
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
        name = self.lineEdit_name.text()
        address = self.lineEdit_address.text()
        if not name or not address:
            self.send_log("请输入数据")
            return
        delimiter_list = config_manager.get("delimiter_list")
        for _ in delimiter_list:
            if _ == "tab":
                delimiter_list.remove(_)
                delimiter_list.append("\t")
                break
        address = [_ for _ in address.split("\n") if _.strip()]
        new_address = []
        for addr in address:
            if self.find_used_delimiters(addr, delimiter_list) == 1:
                new_address.append(addr)
            else:
                self.send_log(f"地址 {addr} 不合法,请使用单个分隔符,请检查地址格式")
        address = new_address
        parse_address = [
            (_, [__.strip() for __ in _.split(delimiter)])
            for _ in address
            for delimiter in delimiter_list
            if delimiter in _
        ]
        used_address = [_[0] for _ in parse_address]
        for addr in address:
            if addr not in used_address:
                self.send_log(f"地址 {addr} 不合法,请检查分割符是否设置(设置页>工具>添加分隔符)")

        if self.find_used_delimiters(name.strip(), [" "] + delimiter_list) > 1:
            self.send_log("请输入正确的姓名,请使用单个分隔符,请检查姓名格式")
            return
        parse_name = [[__.strip() for __ in name.strip().split(_)] for _ in [" "] + delimiter_list if _ in name.strip()]
        if len(parse_name) < 1:
            self.send_log("请输入正确的姓名,请检查分割符是否设置(设置页>工具>添加分隔符)")
            return
        parse_name = parse_name[0]
        first_name = parse_name[0]
        last_name = parse_name[-1]
        self.query_thread_pool.setMaxThreadCount(30)
        for org_addr, addr in parse_address:
            if len(addr) == 3:
                street, state, zip_code = addr
            elif len(addr) == 4:
                street, _, state, zip_code = addr
            elif len(addr) == 5:
                street, _, _, state, zip_code = addr
            else:
                self.send_log(f"地址 {','.join(addr)} 不合法")
                continue
            zip_code = validate_and_format_zip(addr[-1])
            if not zip_code:
                self.send_log(f"地址 {','.join(addr)} zip 不合法")
                continue
            if len(addr[-2]) != 2:
                self.send_log(f"地址 {','.join(addr)} state 不合法")
                continue
            info = [first_name, last_name, street, state, zip_code]
            worker = QuerySSN(org_addr, info)
            worker.signals.finished.connect(self.query_finished)
            self.query_thread_pool.start(worker)
            self.active_query_count += 1
        if self.active_query_count > 0:
            self.pushButton_query.setDisabled(True)
            self.send_log(f"正在查询{self.active_query_count}个地址")

    def batch_query(self):
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
        if self.pushButton_batch_query.text() != "批量查询":
            return
        if not self.file_path:
            self.send_log("请上传文件")
            return
        thread_number = config_manager.get("people_config_thread", 10)
        if thread_number and isinstance(thread_number, str):
            thread_number = int(thread_number)
        if not self.file_details:
            config = {line: self.__getattribute__(f"lineEdit_{line}").text() for line in labels}
            if not any(list(config.values())):
                self.send_log("请填写/选择资料格式(显示格式[隐藏格式]>填写)")
                return
            config["delimiter"] = self.comboBox_delimiter.currentText()
            self.file_details = format_details(self.file_path, config)
            self.send_log(f"已读取文件数量:{self.file_details.qsize()},开始查询")
        else:
            if not self.file_details.qsize():
                self.send_log("文件已全部处理完成,可上传其他文件进行查询")
                self.pushButton_batch_query.setText("批量查询")
                return
            self.send_log(f"剩余文件数量:{self.file_details.qsize()},继续查询")
        self.thread_pool.setMaxThreadCount(thread_number)
        workers = []
        for _ in range(self.file_details.qsize()):
            worker = QueryWorker(self.file_details)
            worker.signals.finished.connect(self.batch_query_finished)
            workers.append(worker)
        for _ in workers:
            self.thread_pool.start(_)
        self.pushButton_batch_query.setText("停止查询")

    def stop_batch_query(self):
        if self.pushButton_batch_query.text() != "停止查询":
            return
        self.thread_pool.clear()
        self.pushButton_batch_query.setDisabled(True)
        active_threads = self.thread_pool.activeThreadCount()
        if active_threads != 0:
            self.send_log(f"等待 {active_threads} 个线程结束")
