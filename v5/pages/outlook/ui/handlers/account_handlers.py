"""账号相关处理逻辑"""

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QMenu, QMessageBox
from typing import List, Dict, Any
import logging

log = logging.getLogger("SynthBox")


class AccountHandler:
    """
    账号相关处理类，负责处理账号的加载、管理、右键菜单等功能
    """
    
    def __init__(self, page):
        self.page = page
        self.init_connections()
    
    def init_connections(self):
        """初始化信号连接"""
        # 顶部工具栏
        self.page.btnTopSearch.clicked.connect(self.on_search)
        self.page.btnRefresh.clicked.connect(self.load_accounts)
        
        # 账号表格
        self.page.tableAccounts.customContextMenuRequested.connect(self.show_account_menu)
        self.page.tableAccounts.selectionModel().selectionChanged.connect(self.on_account_selected)
    
    def load_accounts(self):
        """加载账号列表"""
        pass
    
    def on_accounts_loaded(self, data):
        """账号加载成功"""
        pass
    
    def on_load_error(self, error_msg):
        """加载失败"""
        pass
    
    def on_search(self):
        """搜索"""
        pass
    
    def get_selected_accounts(self):
        """获取选中的账号信息"""
        pass
    
    def show_account_menu(self, position):
        """显示账号右键菜单"""
        pass
    
    def on_account_selected(self):
        """账号选择改变（加载邮件列表）"""
        pass