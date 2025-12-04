"""邮件同步模块"""

import logging
from typing import Dict, Any, List

from ..auth.msal_client import MSALClient

log = logging.getLogger("SynthBox")


class MailSync:
    """
    邮件同步类，负责处理邮件的同步、查询等操作
    """
    
    def __init__(self, msal_client: MSALClient):
        """
        初始化邮件同步器
        
        Args:
            msal_client: MSAL客户端实例
        """
        self.msal_client = msal_client
        self.logger = logging.getLogger(__name__)
    
    def sync_mail_changes(self, delta_link: str = None) -> Dict[str, Any]:
        """
        同步邮件变更
        
        Args:
            delta_link: 上次同步的delta link
        
        Returns:
            包含邮件变更和新delta link的字典
        """
        try:
            result = self.msal_client.get_messages_delta(delta_link)
            return {
                "success": True,
                "data": result,
                "delta_link": result.get("@odata.deltaLink")
            }
        except Exception as e:
            self.logger.error(f"邮件同步失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_recent_mails(self, days_ago: int = 7, limit: int = 100) -> Dict[str, Any]:
        """
        获取最近几天的邮件
        
        Args:
            days_ago: 天数
            limit: 返回邮件数量限制
        
        Returns:
            邮件列表
        """
        try:
            result = self.msal_client.list_messages_since(days_ago=days_ago, top=limit)
            return {
                "success": True,
                "mails": result.get("value", [])
            }
        except Exception as e:
            self.logger.error(f"获取最近邮件失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_unread_mails(self, limit: int = 50) -> Dict[str, Any]:
        """
        获取未读邮件
        
        Args:
            limit: 返回邮件数量限制
        
        Returns:
            未读邮件列表
        """
        try:
            result = self.msal_client.list_unread_messages(top=limit)
            return {
                "success": True,
                "mails": result.get("value", [])
            }
        except Exception as e:
            self.logger.error(f"获取未读邮件失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def search_mails(self, search_query: str, limit: int = 50) -> Dict[str, Any]:
        """
        搜索邮件
        
        Args:
            search_query: 搜索关键词
            limit: 返回邮件数量限制
        
        Returns:
            搜索结果
        """
        try:
            # 使用Graph API的搜索功能
            filter_str = f"contains(subject, '{search_query}') or contains(bodyPreview, '{search_query}')"
            result = self.msal_client.list_messages(filter_str=filter_str, top=limit)
            return {
                "success": True,
                "mails": result.get("value", [])
            }
        except Exception as e:
            self.logger.error(f"搜索邮件失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_mail_folders(self) -> Dict[str, Any]:
        """
        获取邮件文件夹列表
        
        Returns:
            文件夹列表
        """
        try:
            result = self.msal_client.list_mail_folders()
            return {
                "success": True,
                "folders": result.get("value", [])
            }
        except Exception as e:
            self.logger.error(f"获取邮件文件夹失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }