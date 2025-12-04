import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton, QMainWindow
from PyQt5.QtCore import QTimer, pyqtSignal, QRect, QPropertyAnimation, QEasingCurve, Qt, QAbstractAnimation
from PyQt5.QtGui import QFont


# --- 1. 单个通知弹窗类 (无变化) ---
class NotificationWidget(QWidget):
    closed = pyqtSignal(QWidget)

    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedSize(300, 80)
        self._setup_ui(title, message)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)
        self._timer.start(3000)

    def _setup_ui(self, title, message):
        self.container = QWidget(self)
        self.container.setGeometry(0, 0, self.width(), self.height())
        self.container.setStyleSheet("""
            background-color: rgba(30, 30, 30, 220);
            border-radius: 10px;
            color: white;
        """)
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(5)
        title_label = QLabel(title, self)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title_label.setFont(title_font)
        title_label.setStyleSheet("background-color: transparent; color: #CCCCCC;")
        message_label = QLabel(message, self)
        message_font = QFont()
        message_font.setPointSize(10)
        message_label.setFont(message_font)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("background-color: transparent; color: #AAAAAA;")
        layout.addWidget(title_label)
        layout.addWidget(message_label)
        layout.addStretch()

    def closeEvent(self, event):
        self.closed.emit(self)
        super().closeEvent(event)


# --- 2. 通知管理器类 (已修正) ---
class NotificationManager:
    def __init__(self):
        self.notifications = []
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        self.screen_width = screen_geometry.width()
        self.screen_height = screen_geometry.height()
        self.padding_right = 15
        self.padding_bottom = 15
        self.spacing = 10
        # [修正] 用于存储动画对象，以便可以停止它们
        self.animations = {}

    def show_notification(self, title, message):
        """
        创建并显示一个新的通知。
        """
        # [修正] 在创建新通知前，先停止所有当前动画并让窗口到达最终位置
        self._stop_all_animations()
        self._snap_windows_to_positions()

        notification = NotificationWidget(title, message)

        # 计算新通知的位置
        notification_height = notification.height()
        pos_x = self.screen_width - notification.width() - self.padding_right

        total_height = 0
        for win in self.notifications:
            total_height += win.height() + self.spacing

        pos_y = self.screen_height - self.padding_bottom - notification_height - total_height

        notification.move(pos_x, pos_y)
        notification.show()

        self.notifications.append(notification)
        notification.closed.connect(self.on_notification_closed)

    def on_notification_closed(self, notification):
        """
        当一个通知关闭时的槽函数。
        """
        try:
            # [修正] 在从列表中移除之前，先清理可能存在的动画对象
            if notification in self.animations:
                self.animations.pop(notification).stop()
            self.notifications.remove(notification)
        except (ValueError, KeyError):
            pass
        # 使用动画重新排列剩余的通知
        self._reposition_notifications_with_animation()

    # [修正] 新增方法：立即将窗口移动到正确位置（无动画）
    def _snap_windows_to_positions(self):
        """
        立即将所有当前通知窗口移动到其正确的堆叠位置，无动画。
        用于修复动画和新窗口创建之间的竞态条件。
        """
        total_height = 0
        for win in self.notifications:
            notification_height = win.height()
            pos_x = self.screen_width - win.width() - self.padding_right
            pos_y = self.screen_height - self.padding_bottom - notification_height - total_height
            win.move(pos_x, pos_y)
            total_height += notification_height + self.spacing

    def _reposition_notifications_with_animation(self):
        """
        当一个通知关闭后，以动画方式重新计算并移动所有剩余的通知。
        """
        self._stop_all_animations()  # 开始新动画前，先停止所有旧的

        total_height = 0
        for win in self.notifications:
            notification_height = win.height()
            pos_x = self.screen_width - win.width() - self.padding_right
            pos_y = self.screen_height - self.padding_bottom - notification_height - total_height

            # 检查窗口是否已经在目标位置
            if win.pos().y() == pos_y:
                total_height += notification_height + self.spacing
                continue

            animation = QPropertyAnimation(win, b"geometry")
            animation.setDuration(300)
            animation.setStartValue(win.geometry())
            animation.setEndValue(QRect(pos_x, pos_y, win.width(), win.height()))
            animation.setEasingCurve(QEasingCurve.OutCubic)

            # [修正] 存储动画引用
            self.animations[win] = animation
            # 动画结束后自动清理
            animation.finished.connect(lambda win=win: self.animations.pop(win, None))

            animation.start(QAbstractAnimation.DeleteWhenStopped)

            total_height += notification_height + self.spacing

    # [修正] 新增方法：停止所有正在进行的动画
    def _stop_all_animations(self):
        """停止并清除所有当前活动的动画。"""
        for anim in list(self.animations.values()):
            anim.stop()
        self.animations.clear()


# --- 3. 示例应用程序 (无变化) ---
class ExampleApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 通知弹窗示例 (已修复)")
        self.setGeometry(100, 100, 400, 200)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        self.notification_manager = NotificationManager()
        self.notification_count = 0
        button = QPushButton("显示一个新通知 (可快速点击测试)")
        button.clicked.connect(self.create_new_notification)
        layout.addWidget(button)

    def create_new_notification(self):
        self.notification_count += 1
        title = f"事件 #{self.notification_count}"
        message = "这是一个新的通知消息。\n它将在3秒后自动消失。"
        self.notification_manager.show_notification(title, message)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = ExampleApp()
    main_window.show()
    sys.exit(app.exec_())