from PyQt5.QtWidgets import QPushButton, QWidget, QVBoxLayout, QApplication
from PyQt5.QtCore import Qt, QMimeData, QPoint, QByteArray, pyqtSignal
from PyQt5.QtGui import QDrag, QCursor
from v5.core.config import config_manager

CUSTOM_MIME_TYPE = "application/x-my-draggable-button"


class FloatingWindow(QWidget):
    stoped = pyqtSignal(str)

    def __init__(self, button_to_wrap: "DraggableButton", drag_start_pos: QPoint = None):
        if not config_manager.get("floating_button_is_depend"):
            super().__init__(button_to_wrap.window())
        else:
            super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.button = button_to_wrap
        self.worker_key = f"float_{button_to_wrap.objectName()}"
        original_parent = self.button.parentWidget()
        if original_parent:
            stylesheet = original_parent.styleSheet()
            self.setStyleSheet(stylesheet)
        self.button.setParent(self)
        self.button.show()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.button)
        self.setLayout(layout)

        self.setFixedSize(self.button.sizeHint())
        if drag_start_pos:
            self.move(QCursor.pos() - drag_start_pos)
        self.show()

    def stop(self):
        self.stoped.emit(self.worker_key)

    def start(self):
        pass


class DraggableButton(QPushButton):
    floating_window_created = pyqtSignal(FloatingWindow)

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName(text)
        self.drag_start_pos = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData(CUSTOM_MIME_TYPE, QByteArray(self.objectName().encode("utf-8")))
        drag.setMimeData(mime_data)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.pos())
        self.hide()
        drag.exec_(Qt.MoveAction)

        if self.isHidden():
            if self.window() and not self.window().geometry().contains(QCursor.pos()):
                if not config_manager.get("floating_button_is_depend"):
                    FloatingWindow(self, self.drag_start_pos)
                else:
                    initial_pos = QCursor.pos() - self.drag_start_pos
                    floating_win = FloatingWindow(self)
                    floating_win.move(initial_pos)
                    self.floating_window_created.emit(floating_win)
            else:
                # 否则，只是被取消了，在原地恢复显示
                self.show()
