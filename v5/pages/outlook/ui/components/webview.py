"""自定义WebView组件"""

from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtCore import QUrl, pyqtSignal, Qt
from PyQt5.QtWidgets import QMenu, QApplication
from PyQt5.QtGui import QDesktopServices


class CustomWebEnginePage(QWebEnginePage):
    """自定义网页，拦截链接点击"""

    link_clicked = pyqtSignal(QUrl)

    def acceptNavigationRequest(self, url, nav_type, isMainFrame):
        """拦截导航请求"""
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked:
            self.link_clicked.emit(url)
            return False  # 阻止导航
        return True


class CustomWebEngineView(QWebEngineView):
    """
    自定义 WebEngineView
    - 屏蔽默认右键菜单
    - 右击链接：显示"复制链接"和"在浏览器中打开"
    - 双击链接：在浏览器中打开
    """

    link_double_clicked = pyqtSignal(QUrl)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_click_url = None

    def contextMenuEvent(self, event):
        """自定义右键菜单"""
        context_data = self.page().contextMenuData()
        link_url = context_data.linkUrl()

        menu = QMenu(self)

        if link_url.isValid():
            # 链接菜单
            action_copy_link = menu.addAction("📋 复制链接地址")
            action_copy_link.triggered.connect(lambda: self.copy_link_to_clipboard(link_url))

            action_open_browser = menu.addAction("🌐 在浏览器中打开")
            action_open_browser.triggered.connect(lambda: self.open_in_browser(link_url))
        else:
            # 文本菜单
            selected_text = context_data.selectedText()

            if selected_text:
                action_copy_text = menu.addAction("📋 复制")
                action_copy_text.triggered.connect(self.copy_selected_text)
            else:
                return

        if not menu.isEmpty():
            menu.exec_(event.globalPos())

    def mousePressEvent(self, event):
        """记录点击的链接"""
        if event.button() == Qt.LeftButton:
            context_data = self.page().contextMenuData()
            link_url = context_data.linkUrl()
            self._last_click_url = link_url if link_url.isValid() else None

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """双击打开链接"""
        if event.button() == Qt.LeftButton:
            if self._last_click_url and self._last_click_url.isValid():
                self.link_double_clicked.emit(self._last_click_url)
                event.accept()
                return

        super().mouseDoubleClickEvent(event)

    def copy_link_to_clipboard(self, url):
        """复制链接到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(url.toString())

    def copy_selected_text(self):
        """复制选中文本"""
        self.page().triggerAction(QWebEnginePage.Copy)

    def open_in_browser(self, url):
        """在外部浏览器打开"""
        QDesktopServices.openUrl(url)
