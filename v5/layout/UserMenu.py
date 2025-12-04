from PyQt5.QtWidgets import QMenu, QAction
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QPoint


class UserMenu(QMenu):
    """
    一个自定义的用户菜单，可以根据登录状态显示不同选项。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 模拟一个简单的登录状态
        self.is_logged_in = False
        self.username = "SynthBox User"

        # 应用我们自定义的样式
        self.apply_stylesheet()

    def show_menu(self, position: QPoint):
        """
        根据登录状态动态构建并显示菜单。

        Args:
            position: 菜单应该出现的位置（全局坐标）。
        """
        # 每次显示前都清空旧的菜单项，以确保内容是最新的
        self.clear()

        if self.is_logged_in:
            # --- 登录后的菜单 ---
            user_info_action = QAction(QIcon("assets/icons/user.svg"), self.username, self)
            user_info_action.setEnabled(False)  # 让它看起来像个标题，不可点击

            settings_action = QAction(QIcon("assets/icons/settings.svg"), "设置", self)
            logout_action = QAction(QIcon("assets/icons/logout.svg"), "注销", self)

            # 连接信号
            logout_action.triggered.connect(self.logout)
            # settings_action.triggered.connect(...)

            self.addAction(user_info_action)
            self.addSeparator()  # 添加分隔线
            self.addAction(settings_action)
            self.addAction(logout_action)
        else:
            # --- 登录前的菜单 ---
            login_action = QAction(QIcon("assets/icons/login.svg"), "登录", self)
            register_action = QAction(QIcon("assets.png"), "注册", self)

            # 连接信号
            login_action.triggered.connect(self.login)
            # register_action.triggered.connect(...)

            self.addAction(login_action)
            self.addAction(register_action)

        # 在指定位置显示菜单
        self.exec_(position)

    def login(self):
        """模拟登录成功的逻辑"""
        print("用户已登录！")
        self.is_logged_in = True
        # 您可以在这里更新主窗口的用户按钮文本或图标
        # self.parent().menu_user_button.setText("欢迎, SynthBox User")

    def logout(self):
        """模拟注销的逻辑"""
        print("用户已注销。")
        self.is_logged_in = False
        # self.parent().menu_user_button.setText("登录/注册")

    def apply_stylesheet(self):
        """应用现代化的QSS样式"""
        self.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 5px;
                /* 添加阴影效果 */
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }
            QMenu::item {
                padding: 10px 20px 10px 15px; /* 上下内边距、右内边距、左内边距 */
                border-radius: 5px;
                background-color: transparent;
                color: #333;
                margin: 2px 4px;
            }
            QMenu::item:disabled {
                color: #999; /* 不可点击项的颜色 */
                font-weight: bold;
            }
            QMenu::item:selected {
                background-color: #f5f7fa; /* 悬停/选中时的颜色 */
                color: #409eff;
            }
            QMenu::icon {
                padding-left: 10px;
            }
            QMenu::separator {
                height: 1px;
                background: #e8e8e8;
                margin: 5px 10px;
            }
        """)