from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                             QLineEdit, QToolButton, QPlainTextEdit, QFrame,
                             QHBoxLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer


class DoubleClickLineEdit(QLineEdit):
    doubleClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)


class ExpandableInput(QWidget):
    textChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._is_expanded = False
        self.MIN_POPUP_WIDTH = 300

        self.line_edit = DoubleClickLineEdit(self)
        self.toggle_button = QToolButton(self)
        self.toggle_button.setArrowType(Qt.DownArrow)
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.setStyleSheet("QToolButton { border: 1px; padding: 1px; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.toggle_button)

        self.popup_editor = QPlainTextEdit()
        self.popup_editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.popup_editor.setStyleSheet("QPlainTextEdit { border: 1px solid #A9A9A9; }")

        self.popup_container = QFrame()
        self.popup_container.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.popup_container.setFrameShape(QFrame.NoFrame)

        popup_layout = QVBoxLayout(self.popup_container)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.addWidget(self.popup_editor)

        # --- 3. 连接信号与槽 ---
        self.toggle_button.clicked.connect(self._toggle_popup)
        self.line_edit.doubleClicked.connect(self._toggle_popup)

        app = QApplication.instance()
        app.focusChanged.connect(self._on_focus_changed)

        self.line_edit.textChanged.connect(self.textChanged)
        self.popup_editor.textChanged.connect(self._on_popup_text_changed)

    def _toggle_popup(self):
        if self._is_expanded:
            QTimer.singleShot(0, self._hide_popup)
        else:
            QTimer.singleShot(0, self._show_popup)

    def _show_popup(self):
        if self._is_expanded:
            return

        self._is_expanded = True
        self.toggle_button.setArrowType(Qt.UpArrow)
        self.popup_editor.setPlainText(self.line_edit.text())
        current_width = self.width()
        popup_width = max(current_width, self.MIN_POPUP_WIDTH)

        screen_rect = QApplication.primaryScreen().availableGeometry()
        global_pos = self.mapToGlobal(self.rect().bottomLeft())
        popup_x = global_pos.x()
        popup_y = global_pos.y()
        if popup_x + popup_width > screen_rect.right():
            popup_x = screen_rect.right() - popup_width
        if popup_x < screen_rect.left():
            popup_x = screen_rect.left()
        self.popup_container.setGeometry(
            popup_x,
            popup_y,
            popup_width,
            170
        )
        self.popup_container.show()
        self.popup_editor.setFocus()

    def _hide_popup(self):
        if not self._is_expanded:
            return

        self._is_expanded = False
        self.toggle_button.setArrowType(Qt.DownArrow)

        self.line_edit.setText(self.popup_editor.toPlainText())
        self.popup_container.hide()

    def _on_focus_changed(self, old_widget, new_widget):
        if not self._is_expanded:
            return

        is_focus_still_inside = False
        if new_widget is self or \
                new_widget is self.line_edit or \
                new_widget is self.toggle_button or \
                new_widget is self.popup_editor or \
                new_widget is self.popup_container:  # 把容器也加入判断
            is_focus_still_inside = True

        if not is_focus_still_inside:
            self._hide_popup()

    def _on_popup_text_changed(self):
        self.textChanged.emit(self.popup_editor.toPlainText())

    def text(self):
        if self._is_expanded:
            return self.popup_editor.toPlainText()
        else:
            return self.line_edit.text()

    def setText(self, text):
        self.line_edit.setText(text)
        self.popup_editor.setPlainText(text)