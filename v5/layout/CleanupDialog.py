import os
import sys
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QApplication, QWidget
from PyQt5.QtGui import QMovie
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve
from v5.core.utils import get_icon_path


class CleanupDialog(QDialog):
    """
    一个经过美化的“清理中”等待对话框。
    - 支持淡入淡出动画。
    - 支持Windows下的亚克力/毛玻璃背景效果。
    - 带有柔和的阴影和圆角。
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 窗口基础设置 ---
        self.setWindowTitle("正在关闭")
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setFixedSize(240, 160)  # 尺寸微调

        # --- 布局和控件 ---
        # 我们在一个"内容"QWidget中放置所有东西，以便于管理背景和圆角
        self.container = QWidget(self)
        self.container.setObjectName("container")

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. 旋转等待图标
        self.spinner_label = QLabel(self)
        layout.addWidget(self.spinner_label, alignment=Qt.AlignCenter)

        gif_path = get_icon_path("spinner.gif")
        if os.path.exists(gif_path):
            self.movie = QMovie(gif_path)
            self.movie.setScaledSize(QSize(70, 70))
            self.spinner_label.setMovie(self.movie)
            self.movie.start()
        else:
            self.spinner_label.setText("⏳")

        # 2. 提示文字
        self.message_label = QLabel("正在清理后台任务...", self)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setObjectName("messageLabel")
        layout.addWidget(self.message_label)

        # 将内容容器设置为主布局
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)

        # --- 应用样式和动画 ---
        self.apply_stylesheet()
        self.fade_animation = None

    def apply_stylesheet(self):
        """应用QSS样式表"""
        style = """
            #container {background-color: rgba(245, 247, 250, 0.95); /* 半透明的浅灰色背景 */border-radius: 6px;border: 1px solid rgba(0, 0, 0, 0.08);}
            #messageLabel {color: #404040;font-weight: bold;}
        """
        self.setStyleSheet(style)

    def _run_fade_animation(self, start, end, on_finished=None):
        """执行淡入淡出动画的辅助函数"""
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(200)  # 动画持续200毫秒
        self.fade_animation.setStartValue(start)
        self.fade_animation.setEndValue(end)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        if on_finished:
            self.fade_animation.finished.connect(on_finished)
        self.fade_animation.start()

    def showEvent(self, event):
        """重写showEvent，在窗口显示时启动淡入动画"""
        super().showEvent(event)
        # 启动淡入动画，从完全透明到完全不透明
        self._run_fade_animation(0.0, 1.0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = CleanupDialog()
    dialog.show()
    sys.exit(app.exec_())
