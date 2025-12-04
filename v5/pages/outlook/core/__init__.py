"""核心模块"""

# 认证模块
from .auth.msal_client import MSALClient

# API客户端
from .api.client import ApiService

# 邮件处理
from .mail.sync import MailSync

__all__ = [
    "MSALClient",
    "ApiService",
    "MailSync",
]