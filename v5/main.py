import logging
import multiprocessing
import sys
import inspect
import pkgutil  # 用于发现包内的模块
import importlib  # 用于动态导入模块
import traceback
import faulthandler

from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize, QPropertyAnimation, Qt, QEasingCurve, pyqtSlot, QThread, QPoint
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QStackedWidget,
    QGridLayout,
)

from v4.core.clean_worker import CleanupWorker
from v4.layout.CleanupDialog import CleanupDialog
from v4.layout.Notification import NotificationManager

logging.getLogger("passlib").setLevel(logging.ERROR)


from v4 import pages  # 导入 pages 包
from v4.core.utils import get_icon_path, LayoutState
from v4.core.log import setup_logging

log = setup_logging(app_name="SynthBox")


def global_exception_hook(exctype, value, tb):
    """
    全局异常捕获钩子
    """
    # 打印到控制台
    print("捕获到全局异常:")
    print(f"类型: {exctype}")
    print(f"信息: {value}")
    traceback.print_tb(tb)

    # 记录到日志文件
    error_message = "".join(traceback.format_exception(exctype, value, tb))
    log.error("未捕获的异常:\n" + error_message)

    # 在这里可以添加一个弹窗来提示用户
    from PyQt5.QtWidgets import QMessageBox

    QMessageBox.critical(None, "应用崩溃", "发生了一个致命错误，请查看日志文件 app_errors.log。")

    sys.__excepthook__(exctype, value, tb)


# 设置全局异常钩子
sys.excepthook = global_exception_hook


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SynthBox")
        self.setWindowIcon(QIcon(get_icon_path("Globe.ico")))
        self.setGeometry(100, 100, 1000, 800)
        self.setMinimumSize(650, 300)
        self.all_log_messages = []
        self.button_full_texts = {}
        self.pages = {}
        self.menu_buttons = {}
        # 页面容器
        self.content_area = QStackedWidget()

        # 主布局容器
        self.main_widget = QWidget()
        self.main_layout = QGridLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 侧边栏
        self.sidebar = QWidget()

        self.sidebar_initial_width = 180
        self.sidebar_collapsed_width = 50
        self.sidebar_is_collapsed = False
        self.sidebar.setFixedWidth(self.sidebar_initial_width)
        self.sidebar.setStyleSheet("background: #f0f0f0; border-right: 1px solid #d0d0d0;")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setAlignment(Qt.AlignTop)
        self.sidebar_layout.setContentsMargins(5, 5, 5, 5)
        self.sidebar_layout.setSpacing(10)

        # 内容区响应式逻辑的初始化
        self.MEDIUM_BREAKPOINT = QSize(800, 750)
        self.COMPACT_BREAKPOINT = QSize(500, 350)
        self.current_state = None  # 内容区布局状态标志
        self.check_content_layout(self.size())
        self.content_area.currentChanged.connect(lambda: self.check_content_layout(self.size()))

        # 折叠按钮
        self.toggle_btn = QPushButton()
        self._setup_button_icon(self.toggle_btn, "menu.png", "↔", "折叠/展开侧边栏", QSize(24, 24))
        self.toggle_btn.setFixedSize(40, 40)
        self.toggle_btn.setStyleSheet(
            "QPushButton { border: none; padding: 5px; } QPushButton:hover { background-color: #e0e0e0; }"
        )
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        self.sidebar_layout.addWidget(self.toggle_btn, 0, Qt.AlignLeft)

        # --- 自动发现并配置页面 ---
        self._discover_and_setup_pages()  # 这是核心改动

        # --- 菜单按钮区域 ---
        self.menu_area = QWidget()
        self.menu_area.setFixedHeight(40)
        self.menu_area.setStyleSheet("background: #e9e9e9; border-top: 0px solid #c0c0c0;")
        self.menu_area_layout = QHBoxLayout(self.menu_area)
        self.menu_area_layout.setContentsMargins(10, 0, 10, 0)
        self.menu_notify_label = QLabel("📢通知:双十一折扣将达到25% 哦 !")
        self.menu_area_layout.addWidget(self.menu_notify_label, 1)
        self.menu_area_layout.addStretch(1)
        self.menu_user_button = QPushButton()
        self._setup_button_icon(self.menu_user_button, "user.png", "👷‍♂️", "账号", QSize(24, 24))
        self.menu_user_button.setFixedSize(40, 40)
        self.menu_user_button.setStyleSheet(
            "QPushButton {border-radius: 40px;padding: -1px; border: none; background: transparent;};"
        )

        self.menu_area_layout.addWidget(self.menu_user_button)

        # --- log_panel 区域 ---
        self.log_panel = QWidget()
        self.log_panel.setFixedHeight(40)
        self.log_panel.setStyleSheet("background: #e9e9e9; border-top: 0px solid #c0c0c0;")
        self.log_panel_layout = QHBoxLayout(self.log_panel)
        self.log_panel_layout.setContentsMargins(10, 0, 10, 0)

        self.current_log_status_label = QLabel("日志: 无")
        self.log_panel_layout.addWidget(self.current_log_status_label, 1)
        self.log_panel_layout.addStretch(1)

        self.view_full_log_button = QPushButton()
        self._setup_button_icon(self.view_full_log_button, "log_view.png", "查日志", "打开或关闭详细日志页面")
        self.view_full_log_button.clicked.connect(self.toggle_full_log_page)
        self.log_panel_layout.addWidget(self.view_full_log_button)

        # --- 主布局 ---
        self.main_layout.addWidget(self.sidebar, 0, 0, 3, 1)
        self.main_layout.addWidget(self.menu_area, 0, 1, 1, 1)
        self.main_layout.addWidget(self.content_area, 1, 1, 1, 1)
        self.main_layout.addWidget(self.log_panel, 2, 1, 1, 1)
        self.main_layout.setColumnStretch(0, 0)
        self.main_layout.setColumnStretch(1, 1)
        self.main_layout.setRowStretch(0, 1)
        self.setCentralWidget(self.main_widget)

        self.sidebar_is_collapsed = False

        # 设置默认显示的页面
        default_page_id_to_show = None
        # 查找排序后的第一个 add_to_sidebar_menu=True 且 is_fixed_bottom=False 的页面
        # 注意：这里的 PageClass.order 和 PageClass.page_id_name 需要从实例化的对象或者类本身获取
        # 我们在 _discover_and_setup_pages 中填充 self.menu_buttons，可以基于它来决定默认页

        # 先找到所有顶部菜单的page_id并排序
        temp_pages_for_sort = []
        for page_id, btn in self.menu_buttons.items():
            page_class = type(self.pages[page_id])  # 获取按钮对应页面的类
            if page_class.add_to_sidebar_menu and not page_class.is_fixed_bottom:
                temp_pages_for_sort.append(page_class)

        temp_pages_for_sort.sort(key=lambda cls: cls.order)
        if temp_pages_for_sort:
            default_page_id_to_show = temp_pages_for_sort[0].page_id_name

        if default_page_id_to_show and default_page_id_to_show in self.menu_buttons:
            self.switch_page(default_page_id_to_show, self.menu_buttons[default_page_id_to_show])
        elif default_page_id_to_show and default_page_id_to_show in self.pages:
            self.switch_page(default_page_id_to_show)
        self.notification = NotificationManager()

    def closeEvent(self, event):
        """重写 closeEvent，在关闭前执行带等待提示的清理流程。"""
        # 1. 从所有子页面中聚合需要清理的任务
        all_workers_to_clean = {}
        for _, page in self.pages.items():
            if hasattr(page, "workers") and page.workers:
                for worker_id, worker in page.workers.items():
                    if worker.get("worker"):
                        all_workers_to_clean[worker_id] = worker

        # 2. 如果没有任何需要清理的任务，则直接接受关闭事件
        if not all_workers_to_clean:
            event.accept()
            return

        # 3. 如果有任务需要清理，则先忽略本次关闭事件
        event.ignore()

        # 4. 创建并显示我们的“清理中”对话框
        cleanup_dialog = CleanupDialog(self)

        # 5. 创建并配置清理工作线程
        self.cleanup_thread = QThread()
        self.cleanup_worker = CleanupWorker(all_workers_to_clean)
        self.cleanup_worker.moveToThread(self.cleanup_thread)

        # 6. 连接信号和槽，这是整个流程的核心
        self.cleanup_thread.started.connect(self.cleanup_worker.run)
        self.cleanup_worker.finished.connect(cleanup_dialog.accept)  # 清理完毕，关闭对话框
        self.cleanup_worker.finished.connect(self.cleanup_thread.quit)
        self.cleanup_worker.finished.connect(self.cleanup_worker.deleteLater)
        self.cleanup_thread.finished.connect(self.cleanup_thread.deleteLater)
        # 【关键】当线程结束后，再次调用 self.close()
        self.cleanup_thread.finished.connect(self.close)

        # 7. 启动线程，开始清理
        self.cleanup_thread.start()

        # 8. 显示等待对话框。程序会在这里暂停，直到 dialog.accept() 被调用
        cleanup_dialog.exec_()

    def resizeEvent(self, event):
        """
        【系统二】当用户手动拖动窗口大小时，这个事件被触发。
        """
        super().resizeEvent(event)
        self.check_content_layout(event.size())
        self.set_layout_to_state()

    def check_content_layout(self, size: QSize):
        """
        这是统一的布局决策中心。
        它检查主窗口大小，并命令当前显示的子页面改变布局。
        """
        if size.width() < self.COMPACT_BREAKPOINT.width() or size.height() < self.COMPACT_BREAKPOINT.height():
            self.current_state = LayoutState.COMPACT
        elif size.width() < self.MEDIUM_BREAKPOINT.width() or size.height() < self.MEDIUM_BREAKPOINT.height():
            self.current_state = LayoutState.MEDIUM
        else:
            self.current_state = LayoutState.FULL

    def set_layout_to_state(self):
        current_page = self.content_area.currentWidget()
        if hasattr(current_page, "set_compact_layout"):
            current_page.set_compact_layout(self.current_state)

    def _setup_button_icon(
        self,
        button: QPushButton,
        icon_filename: str,
        fallback_text: str,
        tooltip: str,
        icon_size: QSize = QSize(20, 20),
    ):
        """辅助函数：为按钮设置图标、备用文本和提示，使用 get_icon_path"""
        button.setToolTip(tooltip)
        actual_icon_path = get_icon_path(icon_filename) if icon_filename else ""
        if actual_icon_path:
            icon = QIcon(actual_icon_path)
            if not icon.isNull():
                button.setIcon(icon)
                button.setIconSize(icon_size)
                # button.setText("") # 如果只想显示图标
                return  # 成功设置图标后返回
        button.setText(fallback_text)  # 如果图标加载失败或路径为空，设置备用文本

    def _discover_and_setup_pages(self):
        """自动发现pages包中的BasePage子类并配置"""
        all_page_classes = []
        # pages.__path__ 会给出 pages 包目录的路径列表 (通常只有一个)
        # pages.__name__ 是 "pages"
        for importer, modname, ispkg in pkgutil.walk_packages(pages.__path__, pages.__name__ + "."):
            if not ispkg and modname.endswith(".page"):  # 我们只关心模块文件 (.py)
                try:
                    module = importlib.import_module(modname)  # 动态导入模块，例如 pages.home_page
                    for name, cls_obj in inspect.getmembers(module, inspect.isclass):
                        # 确保类是在此模块中定义的，而不是导入的 (可选，但issubclass通常已足够)
                        if cls_obj.__module__ == modname:
                            # 确保是 BasePage 的子类, 且不是 BasePage 本身
                            # 使用 pages.BasePage (因为 __init__.py 中导入了 BasePage)
                            if issubclass(cls_obj, pages.BasePage) and cls_obj is not pages.BasePage:
                                if not cls_obj.page_id_name:
                                    log.warning(
                                        f"警告: 类 {cls_obj.__name__} 在模块 {modname} 中缺少 page_id_name，将被跳过。"
                                    )
                                    continue
                                all_page_classes.append(cls_obj)
                except ImportError as e:
                    log.info(f"错误: 导入模块 {modname} 失败: {e}")
                except Exception as e:
                    log.info(f"错误: 处理模块 {modname} 时发生意外: {e}")
        # 1. 实例化所有页面，添加到QStackedWidget，并连接日志信号
        for PageClass in all_page_classes:
            page_id = PageClass.page_id_name
            if page_id in self.pages:
                continue  # 避免重复
            try:
                page_instance = PageClass(parent=self)
            except:
                traceback.print_exc()
                continue
            self.pages[page_id] = page_instance
            self.content_area.addWidget(page_instance)
            page_instance.log_message_sent.connect(self.update_log_panel_status)
            page_instance.notification_sent.connect(self.notification_show)

        # 2. 创建侧边栏按钮
        top_menu_classes = sorted(
            [cls for cls in all_page_classes if cls.add_to_sidebar_menu and not cls.is_fixed_bottom],
            key=lambda cls: cls.order,
        )
        bottom_menu_classes = sorted(
            [cls for cls in all_page_classes if cls.is_fixed_bottom], key=lambda cls: cls.order
        )

        for PageClass in top_menu_classes:
            self._add_sidebar_button_from_class(PageClass)

        self.sidebar_layout.addStretch(1)

        for PageClass in bottom_menu_classes:
            self._add_sidebar_button_from_class(PageClass)

        # self.status_label_sidebar = QLabel("状态: 就绪") # 之前已添加，这里可以更新或保持
        # self.sidebar_layout.addWidget(self.status_label_sidebar)

    def _add_sidebar_button_from_class(self, PageClass: type):  # 使用type作为类型提示
        """辅助函数：为指定的页面类创建并添加侧边栏按钮"""
        page_id = PageClass.page_id_name
        display_text = PageClass.display_text
        icon_filename = PageClass.icon_path  # 现在这是文件名，不是完整路径

        btn = QPushButton(display_text)
        self._setup_button_icon(btn, icon_filename, display_text[0] if display_text else "?", display_text)

        btn.setStyleSheet(
            """
            QPushButton { text-align: left; padding: 10px; border: none; background-color: transparent;}
            QPushButton:hover { background-color: #ddeeff; }
            QPushButton:checked { background-color: #cceeff; font-weight: bold; }
        """
        )
        btn.setCheckable(True)
        # lambda中正确捕获循环变量的值
        btn.clicked.connect(lambda checked, p=page_id, b=btn: self.switch_page(p, b))

        self.sidebar_layout.addWidget(btn)  # 这个会按顺序添加到addStretch之前或之后
        self.menu_buttons[page_id] = btn
        self.button_full_texts[btn] = display_text

    @pyqtSlot(str)
    def update_log_panel_status(self, message):
        self.current_log_status_label.setText(f"{message[:100]}")
        self.all_log_messages.append(message)
        full_log_page_instance = self.pages.get("full_log")
        if self.content_area.currentWidget() == full_log_page_instance and isinstance(
            full_log_page_instance, pages.FullLogPage
        ):
            full_log_page_instance.append_log_entry(message)

    @pyqtSlot(str, str)
    def notification_show(self, title, message):
        self.notification.show_notification(title, message)

    def switch_page(self, page_id_to_switch_to, clicked_button: QPushButton = None):
        if page_id_to_switch_to in self.pages:
            current_page_widget = self.content_area.currentWidget()
            if page_id_to_switch_to != "full_log":
                current_page_id = None
                for pid, widget in self.pages.items():
                    if widget == current_page_widget:
                        current_page_id = pid
                        break
                if current_page_id != "full_log" and current_page_id is not None:
                    self.last_active_page_id_before_log = current_page_id

            # self.send_log(f"切换至页面: {page_id_to_switch_to}")
            self.content_area.setCurrentWidget(self.pages[page_id_to_switch_to])

            for btn_widget_iter in self.menu_buttons.values():
                if btn_widget_iter:  # 确保按钮存在
                    btn_widget_iter.setChecked(btn_widget_iter == clicked_button)

            if page_id_to_switch_to == "full_log":
                full_log_page_instance = self.pages.get("full_log")
                if isinstance(full_log_page_instance, pages.FullLogPage):
                    full_log_page_instance.set_logs(self.all_log_messages)
                if clicked_button is None:
                    for btn_iter in self.menu_buttons.values():
                        if btn_iter:
                            btn_iter.setChecked(False)
            self.set_layout_to_state()
        else:
            log.info(f"错误: 页面 {page_id_to_switch_to} 未找到!")

    def toggle_full_log_page(self):
        current_widget_in_stack = self.content_area.currentWidget()
        full_log_page_instance = self.pages.get("full_log")

        if current_widget_in_stack == full_log_page_instance:
            page_to_switch_back_to_id = self.last_active_page_id_before_log
            if page_to_switch_back_to_id == "full_log":
                # 查找第一个可导航的非底部固定按钮作为备用
                top_menu_page_ids_ordered = []
                temp_pages_for_sort = [
                    cls
                    for cls_name, cls in inspect.getmembers(pages, inspect.isclass)
                    if issubclass(cls, pages.BasePage)
                    and cls is not pages.BasePage
                    and cls.add_to_sidebar_menu
                    and not cls.is_fixed_bottom
                ]
                temp_pages_for_sort.sort(key=lambda cls: cls.order)
                if temp_pages_for_sort:
                    page_to_switch_back_to_id = temp_pages_for_sort[0].page_id_name
                else:  # 极端情况，没有其他页面，就回到home
                    page_to_switch_back_to_id = "home"

            button_for_last_active_page = self.menu_buttons.get(page_to_switch_back_to_id)
            self.switch_page(page_to_switch_back_to_id, button_for_last_active_page)
        else:
            current_page_id = None
            for pid, widget in self.pages.items():
                if widget == current_widget_in_stack and pid != "full_log":
                    current_page_id = pid
                    break
            if current_page_id:
                self.last_active_page_id_before_log = current_page_id
            self.switch_page("full_log")

    def send_log(self, message):
        self.update_log_panel_status(f"[MainWindow] {message}")

    def toggle_sidebar(self):
        current_width = self.sidebar.width()
        target_width = self.sidebar_collapsed_width if not self.sidebar_is_collapsed else self.sidebar_initial_width

        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.sidebar_animation.setDuration(250)
        self.sidebar_animation.setStartValue(current_width)
        self.sidebar_animation.setEndValue(target_width)
        self.sidebar_animation.setEasingCurve(QEasingCurve.InOutCubic)

        self.sidebar_animation_max = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.sidebar_animation_max.setDuration(250)
        self.sidebar_animation_max.setStartValue(current_width)
        self.sidebar_animation_max.setEndValue(target_width)
        self.sidebar_animation_max.setEasingCurve(QEasingCurve.InOutCubic)

        self.sidebar_animation.start()
        self.sidebar_animation_max.start()

        if not self.sidebar_is_collapsed:
            for btn, full_text in self.button_full_texts.items():
                btn.setText("")
                btn.setToolTip(full_text)
            self.toggle_btn.setToolTip("展开侧边栏")
        else:
            for btn, full_text in self.button_full_texts.items():
                btn.setText(full_text)
                # 使用按钮自身存储的完整文本作为提示，或特定提示
                btn.setToolTip(full_text if btn != self.menu_buttons.get("settings") else "打开设置页面")
            self.toggle_btn.setToolTip("折叠侧边栏")

        self.sidebar_is_collapsed = not self.sidebar_is_collapsed


if __name__ == "__main__":
    multiprocessing.freeze_support()
    faulthandler.enable(file=open("app_errors.log", "a", encoding="utf-8", buffering=1))
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    except (Exception,) as e:
        log.exception(str(e))
