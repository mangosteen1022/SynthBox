from PyQt5.QtCore import QObject, pyqtSignal


class AppSignals(QObject):
    """
    一个全局的、单例的信号总线，用于整个应用程序的跨组件通信。
    """

    # ------------------ 通用信号 ------------------

    # 日志消息信号 (您已有的)
    # 参数: str (消息内容)
    log_message_sent = pyqtSignal(str)

    # 状态栏消息更新信号
    # 参数: str (消息文本), int (显示毫秒数, 0为永久)
    status_bar_updated = pyqtSignal(str, int)

    # 页面切换请求信号
    # 有时一个子页面想触发切换到另一个页面，可以通过此信号通知主窗口
    # 参数: str (目标页面的 page_id_name)
    page_change_requested = pyqtSignal(str)

    # ------------------ 业务相关信号 ------------------

    # 用户认证状态变化信号
    # 参数: bool (是否已登录), dict (用户信息, 登录时提供)
    user_auth_changed = pyqtSignal(bool, dict)

    # 代理实例状态变化信号 (您已有的)
    # 参数: int (端口号), str (状态字符串)
    proxy_status_changed = pyqtSignal(int, str)

    # 代理实例IP更新信号 (您已有的)
    # 参数: int (端口号), str (IP地址)
    proxy_ip_updated = pyqtSignal(int, str)

    # 代理流量更新信号 (您已有的)
    # 参数: int (端口号), dict (流量数据)
    proxy_traffic_updated = pyqtSignal(int, dict)

    # ... 您可以根据应用的复杂性在这里添加更多全局信号 ...
    # 例如：主题切换、配置保存、数据库连接状态等


# 创建一个全局唯一的实例
# 其他模块可以通过 from signals import app_signals 来导入并使用它
app_signals = AppSignals()
