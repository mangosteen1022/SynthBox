"""表格委托组件"""

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt


class StatusDelegate(QtWidgets.QStyledItemDelegate):
    """状态列的自定义委托"""

    def paint(self, painter, option, index):
        """绘制状态"""
        text = str(index.data(Qt.DisplayRole) or "")
        old_pen = painter.pen()

        if text == "登录成功":
            painter.setPen(QtGui.QPen(QColor("green")))
        elif text == "登录失败":
            painter.setPen(QtGui.QPen(QColor("red")))
        else:
            painter.setPen(option.palette.text().color())

        rect = option.rect
        rect.adjust(5, 0, -5, 0)
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        painter.setPen(old_pen)
