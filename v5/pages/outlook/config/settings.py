"""应用配置管理（单例）"""

from v5.core.config import config_manager


class AppConfig:
    """应用配置管理（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # ==================== HTTP配置 ====================
        self.server_host = config_manager.get("server_host", "127.0.0.1")
        self.server_port = int(config_manager.get("server_port", 8000))
        self.base_url = f"http://{self.server_host}:{self.server_port}"
        self.request_timeout = 30
        self.request_retries = 3

        # ==================== MSAL配置 ====================
        self.msal_client_id = (
            config_manager.get("msal_client_id", "f4a5101b-9441-48f4-968f-3ef3da7b7290") or ""
        ).strip()
        self.msal_authority = "https://login.microsoftonline.com/common"
        self.msal_scopes = ["User.Read", "Mail.Read", "Mail.ReadWrite", "Mail.Send"]
        self.msal_port = 53100
        self.msal_default_timeout = 15
        self.msal_send_mail_timeout = 30

        # ==================== 邮件配置 ====================
        self.mail_batch_size = 50
        self.mail_max_sync_per_account = 10000
        self.mail_default_sync_days = 30
        self.mail_sync_threads = 5

        # ==================== 线程池配置 ====================
        self.login_pool_max_workers = 30
        self.mail_check_pool_max_workers = 20

        # ==================== 数据库配置 ====================
        self.db_path = "accounts.db"
        self.db_max_connections = 5

        # ==================== 应用UI配置 ====================
        self.ui_refresh_interval = 500  # ms
        self.ui_default_page_size = 20

        # ==================== 安全配置 ====================
        self.token_dir = "tokens"
        self.token_max_age_days = 30

        self._initialized = True
