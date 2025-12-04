from PyQt5 import QtWidgets, QtCore, QtGui
from v5.core.config import config_manager


class CopyTableWidget(QtWidgets.QTableWidget):
    """
    一个实现了最终版、健壮的、可配置的自动复制逻辑的QTableWidget。
    使用 selectionChanged 信号作为统一入口。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # --- 基础设置 ---
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)

        # --- 关键修改：使用 selectionChanged 作为唯一信号源 ---
        self.selectionModel().selectionChanged.connect(self.on_selection_changed)

        # --- 防抖定时器 ---
        self.copy_timer = QtCore.QTimer(self)
        self.copy_timer.setSingleShot(True)  # 设置为单次触发
        self.copy_timer.setInterval(200)  # 设置延时，单位毫秒
        self.copy_timer.timeout.connect(self.trigger_auto_copy)  # 定时器超时后执行复制

    def keyPressEvent(self, event):
        """
        重写键盘按下事件，来手动接管 Ctrl+C。
        """
        if event.matches(QtGui.QKeySequence.Copy):
            self.copy_selection("手动复制 (Ctrl+C)")
        else:
            super().keyPressEvent(event)

    def _get_cell_text(self, row, col):
        """
        智能获取指定单元格的文本内容。
        如果单元格中是控件，则视为空。
        """
        widget = self.cellWidget(row, col)
        if widget:
            return ""

        item = self.item(row, col)
        return item.text() if item else ""

    @QtCore.pyqtSlot("QItemSelection", "QItemSelection")
    def on_selection_changed(self, selected, deselected):
        """
        当选中区变化时触发，启动或重置防抖定时器。
        """
        if not config_manager.get("table_auto_copy", 0):
            return

        # 只要选择有变动，就（重新）启动计时器
        # 如果用户仍在快速选择，计时器会不断被重置，不会触发
        # 只有当用户停止操作150ms后，才会真正执行复制
        self.copy_timer.start()

    def trigger_auto_copy(self):
        """
        由定时器触发，执行最终的检查和复制操作。
        """
        # 再次检查功能是否开启
        if not config_manager.get("table_auto_copy", 0):
            return

        # 如果选中的单元格总数大于1，则执行复制
        if len(self.selectedItems()) > 1:
            self.copy_selection("自动复制")

    def copy_selection_with_feedback(self):
        self.copy_selection("手动复制 (Ctrl+C)")

    def copy_selection(self, copy_type=""):
        """
        将当前选中的内容复制到剪贴板。
        这个新版本能正确处理任何选择形状（包括Ctrl+A）。
        """
        selected_items = self.selectedItems()
        if not selected_items:
            return

        is_single_cell = len(selected_items) == 1

        # 2. 健壮的复制算法
        selected_cells = {(item.row(), item.column()) for item in selected_items}
        min_row = min(row for row, col in selected_cells)
        max_row = max(row for row, col in selected_cells)
        min_col = min(col for row, col in selected_cells)
        max_col = max(col for row, col in selected_cells)

        clipboard_string = ""
        for row in range(min_row, max_row + 1):
            row_data = [
                self._get_cell_text(row, col) if (row, col) in selected_cells else ""
                for col in range(min_col, max_col + 1)
            ]
            clipboard_string += "\t".join(row_data)
            if row < max_row:
                clipboard_string += "\n"
        # 3. 根据配置和是否为单格，决定最终是否在末尾添加换行符
        final_clipboard_text = clipboard_string
        if config_manager.get("table_copy_line_wrap", 0) and not is_single_cell:
            final_clipboard_text += "\n"

        QtWidgets.QApplication.clipboard().setText(final_clipboard_text)
