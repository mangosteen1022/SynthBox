import os
from datetime import datetime

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QCheckBox, QDialogButtonBox, QFileDialog,
                             QGroupBox, QRadioButton)
from PyQt5.QtCore import Qt


class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出设置")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(400, 200)
        self.path_label = QLabel("保存路径:")
        self.path_edit = QLineEdit()
        self.browse_button = QPushButton("浏览...")
        self.delimiter_label = QLabel("分隔符:")
        self.delimiter_edit = QLineEdit(",")
        self.header_checkbox = QCheckBox("包含表头")
        self.header_checkbox.setChecked(True)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        # --- Layouts ---
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_button)

        self.main_layout = QVBoxLayout(self)  # Store main_layout for subclass access
        self.main_layout.addWidget(self.path_label)
        self.main_layout.addLayout(path_layout)
        self.main_layout.addWidget(self.delimiter_label)
        self.main_layout.addWidget(self.delimiter_edit)
        self.main_layout.addWidget(self.header_checkbox)
        self.main_layout.addWidget(self.button_box)

        # --- Connections ---
        self.browse_button.clicked.connect(self.browse_file)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.settings = None

    def browse_file(self):
        default_filename = f"exported_data_{datetime.now().strftime('%Y-%m-%d')}.txt"
        default_path = os.path.join(os.getcwd(), default_filename)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", default_path, "文本文件 (*.txt)"
        )
        if save_path:
            self.path_edit.setText(save_path)

    def accept(self):
        if not self.path_edit.text():
            return
        self.settings = {
            "file_path": self.path_edit.text(),
            "delimiter": self.delimiter_edit.text(),
            "include_header": self.header_checkbox.isChecked()
        }
        super().accept()

    @staticmethod
    def getExportSettings(parent=None):
        dialog = ExportDialog(parent)
        result = dialog.exec_()
        return dialog.settings if result == QDialog.Accepted else None


class MultiTableExportDialog(ExportDialog):
    def __init__(self, table_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("表格导出")
        self.table_names = table_names

        self.table_selection_groupbox = QGroupBox("选择要导出的表格")
        group_layout = QVBoxLayout()

        self.radio_buttons = []
        for name in self.table_names:
            radio_button = QRadioButton(name)
            self.radio_buttons.append(radio_button)
            group_layout.addWidget(radio_button)

        if self.radio_buttons:
            self.radio_buttons[0].setChecked(True)

        self.table_selection_groupbox.setLayout(group_layout)

        self.main_layout.insertWidget(self.main_layout.count() - 1, self.table_selection_groupbox)

    def accept(self):
        """重写accept方法，在父类基础上增加获取表格选择的功能"""
        super().accept()

        if self.settings:
            selected_table = None
            for radio_button in self.radio_buttons:
                if radio_button.isChecked():
                    selected_table = radio_button.text()
                    break

            if selected_table is None:
                self.settings = None
                return

            self.settings["selected_table_name"] = selected_table

    @staticmethod
    def getMultiExportSettings(parent=None, table_names=None):
        """一个新的静态方法，用于创建和运行这个增强版对话框"""
        if table_names is None:
            table_names = []
        dialog = MultiTableExportDialog(table_names, parent)
        result = dialog.exec_()
        return dialog.settings if result == QDialog.Accepted else None