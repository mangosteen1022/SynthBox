from PyQt5 import QtWidgets, QtCore


class VariableHeaderView(QtWidgets.QHeaderView):
    """
    一个更智能的表头，能够区分点击区域。
    - 初始为 Stretch。
    - 仅在点击“调整把手”时切换为 Interactive。
    - 双击表头任意位置时，恢复为 Stretch。
    """

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self._is_stretch_mode = True
        self.setMouseTracking(True)
        self.setSectionsClickable(True)

    def mousePressEvent(self, event):
        if self._is_stretch_mode and self._is_on_resize_handle(event.pos()):
            self.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self._is_stretch_mode = False
        super().mousePressEvent(event)


    def mouseDoubleClickEvent(self, event):
        self.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self._is_stretch_mode = True
        super().mouseDoubleClickEvent(event)

    def _is_on_resize_handle(self, pos):
        handle_width = 6  # 定义把手的像素宽度
        for index in range(self.count()):
            section_pos = self.sectionViewportPosition(index)
            section_width = self.sectionSize(index)

            handle_start = section_pos + section_width - (handle_width // 2)
            handle_end = section_pos + section_width + (handle_width // 2)

            if handle_start <= pos.x() < handle_end:
                return True
        return False

    def mouseMoveEvent(self, event):
        """当鼠标在表头上移动时，根据位置改变光标样式"""
        if self._is_on_resize_handle(event.pos()):
            self.setCursor(QtCore.Qt.SplitHCursor)  # 水平分割光标
        else:
            self.setCursor(QtCore.Qt.ArrowCursor)  # 普通箭头光标
        super().mouseMoveEvent(event)

# header = VariableHeaderView(QtCore.Qt.Horizontal, self.tableWidget)
# self.tableWidget.setHorizontalHeader(header)