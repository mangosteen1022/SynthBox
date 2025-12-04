"""改进的邮件同步管理器"""

import re
from typing import Dict, List, Any, Optional, Callable

from ...core.api.client import ApiService
from ...core.auth.msal_client import MSALClient
from ...utils import DateTimeHelper


class MailSyncManager:
    """邮件同步管理器"""

    def __init__(self, api_service: ApiService):
        self.api = api_service
        self.dt = DateTimeHelper()

    def sync_account_mails(
        self,
        account_id: int,
        msal_client: MSALClient,
        strategy: str = "auto",
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        同步账号邮件（主入口）

        Args:
            account_id: 账号ID
            msal_client: MSAL客户端实例
            strategy: 同步策略
                - "auto": 自动选择（优先delta > incremental > recent）
                - "full": 完整同步所有邮件
                - "incremental": 增量同步（基于时间）
                - "recent": 同步最近的邮件
            progress_callback: 进度回调函数

        Returns:
            {
                "success": bool,
                "error": str (如果失败),
                "synced": int (同步数量),
                "total_fetched": int (获取总数),
                "sync_state": dict (同步状态)
            }
        """
        pass
    
    def _sync_folders_to_db(self, account_id: int, msal_client: MSALClient) -> int:
        """同步文件夹到数据库"""
        pass
    
    def _get_all_folders(self, msal_client: MSALClient) -> List[Dict[str, Any]]:
        """获取所有邮件文件夹（包括子文件夹）"""
        pass
    
    def get_sync_state(self, account_id: int) -> Dict[str, Any]:
        """获取同步状态"""
        pass
    
    def update_sync_state(self, account_id: int, state: Dict[str, Any]):
        """更新同步状态"""
        pass
    
    def sync_with_delta(
        self,
        account_id: int,
        msal_client: MSALClient,
        sync_state: Dict,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """使用Delta查询同步所有文件夹（最高效）"""
        pass
    
    def sync_incremental(
        self,
        account_id: int,
        msal_client: MSALClient,
        sync_state: Dict,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """增量同步所有文件夹（基于时间）"""
        pass
    
    def _sync_folder_incremental(
        self,
        account_id: int,
        msal_client: MSALClient,
        folder_id: str,
        folder_name: str,
        last_sync_time: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """增量同步单个文件夹"""
        pass
    
    def sync_recent(
        self,
        account_id: int,
        msal_client: MSALClient,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """同步所有文件夹最近的邮件（默认30天）"""
        pass
    
    def _sync_folder_recent(
        self,
        account_id: int,
        msal_client: MSALClient,
        folder_id: str,
        folder_name: str,
        start_date: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        max_mails: int = 500,
    ) -> Dict[str, Any]:
        """同步单个文件夹最近的邮件"""
        pass
    
    def sync_full(
        self,
        account_id: int,
        msal_client: MSALClient,
        sync_state: Dict,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """完整同步所有文件夹的所有邮件"""
        pass
    
    def _sync_folder_full(
        self,
        account_id: int,
        msal_client: MSALClient,
        folder: Dict,
        skip_token: Optional[str],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """同步单个文件夹的所有邮件（带断点续传）"""
        pass
    
    def sync_folder_by_time_range(
        self,
        account_id: int,
        msal_client: MSALClient,
        folder_id: Optional[str],
        start_date: str,
        end_date: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """按时间范围同步文件夹（用于历史邮件）"""
        pass
    
    def save_mails_to_db(
        self,
        account_id: int,
        mails: List[Dict],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> int:
        """批量保存邮件到数据库"""
        pass
    
    def prepare_mail_data(self, account_id: int, mail: Dict) -> Dict:
        """准备邮件数据用于保存"""
        pass