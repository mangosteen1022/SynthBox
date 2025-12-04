"""Microsoft Outlook 邮件管理页面"""

from pathlib import Path
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QUrl, Qt, QTimer
from PyQt5.QtWidgets import QMenu, QMessageBox, QDialog
import webbrowser
import logging

from v4.pages.base.page import BasePage
from v4.layout.TableModel import TableModel

# 导入本地模块
from .config import AppConfig
from .core import ApiService
from .ui import Ui_Form, StatusDelegate, DateRangeDialog, CustomWebEnginePage, CustomWebEngineView
from .workers import ApiWorker, LoginThreadPool, MailCheckThreadPool, MailCheckTask, MailBodyDownloadWorker
from .services import ServerThread

log = logging.getLogger("SynthBox")


class MicrosoftPage(BasePage, Ui_Form):
    """Microsoft Outlook 邮件管理页面"""

    page_id_name = "new_microsoft"
    display_text = "邮件工具1"
    icon_path = "mic.png"
    order = 23

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.replace_webview()

        # 服务管理
        self.server_thread = None
        self.login_pool = LoginThreadPool(max_workers=30)
        self.mail_check_pool = MailCheckThreadPool(max_workers=20)
        self.api = ApiService()

        # UI状态
        self.current_account_id = None
        self.current_page = 1
        self.page_size = 20
        self.total_pages = 1
        self.total_items = 0
        self.accounts_data = []

        # 工作线程管理
        self.active_workers = {}
        self.worker_counter = 0

        # 邮件数据
        self.current_mails = []
        self.current_mail_id = None

        # 初始化
        self.init_ui()
        self.init_connections()

        # 延迟加载
        QTimer.singleShot(100, self.load_accounts)

    def replace_webview(self):
        """替换 QWebEngineView 为自定义控件"""
        old_viewer = self.viewer
        parent_layout = self.verticalLayout_bottom
        index = parent_layout.indexOf(old_viewer)
        parent_layout.removeWidget(old_viewer)
        old_viewer.deleteLater()

        self.viewer = CustomWebEngineView(self.widgetBottom)
        self.viewer.setObjectName("viewer")
        parent_layout.insertWidget(index, self.viewer)

        custom_page = CustomWebEnginePage(self.viewer)
        self.viewer.setPage(custom_page)
        custom_page.titleChanged.connect(self.on_viewer_title_changed)

    def init_ui(self):
        """初始化UI设置"""
        # 设置账号表格模型
        headers = ["序号", "ID", "邮箱", "状态", "用户名", "生日", "版本", "更新时间"]
        self.account_model = TableModel([], headers)
        self.tableAccounts.setModel(self.account_model)

        # 设置状态列的自定义委托
        self.tableAccounts.setItemDelegateForColumn(3, StatusDelegate())

        # 隐藏不必要的列
        self.tableAccounts.setColumnHidden(1, True)  # ID
        self.tableAccounts.setColumnHidden(4, True)  # 用户名
        self.tableAccounts.setColumnHidden(5, True)  # 生日
        self.tableAccounts.setColumnHidden(6, True)  # 版本

        # 设置列宽
        self.tableAccounts.setColumnWidth(0, 50)
        self.tableAccounts.setColumnWidth(2, 200)
        self.tableAccounts.setColumnWidth(3, 100)
        self.tableAccounts.setColumnWidth(7, 100)

        # 设置右键菜单
        self.tableAccounts.setContextMenuPolicy(Qt.CustomContextMenu)

        # 设置邮件表格模型
        mail_headers = ["ID", "(文件夹)发件人", "主题", "时间", "大小"]
        self.mail_model = TableModel([], mail_headers)
        self.tableMails.setModel(self.mail_model)

        # 隐藏ID列
        self.tableMails.setColumnHidden(0, True)

        # 设置列宽
        self.tableMails.setColumnWidth(1, 200)
        self.tableMails.setColumnWidth(2, 300)
        self.tableMails.setColumnWidth(3, 150)
        self.tableMails.setColumnWidth(4, 80)

        # 设置邮件表格右键菜单
        self.tableMails.setContextMenuPolicy(Qt.CustomContextMenu)

        # 设置分页
        self.comboPageSize.setCurrentText("20")

        # 禁用分页按钮
        self.btnPagePrev.setEnabled(False)
        self.btnPageNext.setEnabled(False)
        self.clear_mail_viewer()

    def init_connections(self):
        """初始化信号连接"""
        # 顶部工具栏
        self.btnTopSearch.clicked.connect(self.on_search)
        self.btnRefresh.clicked.connect(self.load_accounts)
        self.btnServerToggle.clicked.connect(self.toggle_server)
        self.btnOpenIndex.clicked.connect(self.open_index_page)

        # 分页控件
        self.btnPagePrev.clicked.connect(self.prev_page)
        self.btnPageNext.clicked.connect(self.next_page)
        self.btnGoPage.clicked.connect(self.goto_page)
        self.comboPageSize.currentTextChanged.connect(self.on_page_size_changed)

        # 账号表格
        self.tableAccounts.customContextMenuRequested.connect(self.show_account_menu)
        self.tableAccounts.selectionModel().selectionChanged.connect(self.on_account_selected)

        # 邮件表格
        self.tableMails.selectionModel().selectionChanged.connect(self.on_mail_selected)
        self.tableMails.customContextMenuRequested.connect(self.show_mail_menu)

        # Tab1的搜索功能
        self.btnTab1Search.clicked.connect(self.on_tab1_search)
        self.btnTab1Clear.clicked.connect(self.on_tab1_clear)
        self.editTab1Query.returnPressed.connect(self.on_tab1_search)

        # 搜索框回车
        self.editTopSearch.returnPressed.connect(self.on_search)

        # 登录线程池信号
        self.login_pool.signals.task_started.connect(self.on_login_started)
        self.login_pool.signals.task_progress.connect(self.on_login_progress)
        self.login_pool.signals.task_success.connect(self.on_login_success)
        self.login_pool.signals.task_error.connect(self.on_login_error)
        self.login_pool.signals.task_finished.connect(self.on_login_finished)
        self.login_pool.signals.all_finished.connect(self.on_all_login_finished)

        # 邮件检测线程池信号
        self.mail_check_pool.signals.task_started.connect(self.on_mail_check_started)
        self.mail_check_pool.signals.task_progress.connect(self.on_mail_check_progress)
        self.mail_check_pool.signals.task_success.connect(self.on_mail_check_success)
        self.mail_check_pool.signals.task_error.connect(self.on_mail_check_error)
        self.mail_check_pool.signals.task_finished.connect(self.on_mail_check_finished)
        self.mail_check_pool.signals.all_finished.connect(self.on_all_mail_check_finished)

        # 账号信息按钮
        self.btnVersionSave.clicked.connect(self.save_account_info)
        self.btnVersionReload.clicked.connect(self.reload_account_info)

    def create_api_worker(self, method, endpoint, params=None, json_data=None):
        """创建API工作线程"""
        worker = ApiWorker(method, endpoint, params, json_data)
        self.worker_counter += 1
        worker_id = f"api_worker_{self.worker_counter}"
        self.active_workers[worker_id] = worker
        worker.finished_work.connect(lambda wid=worker_id: QTimer.singleShot(100, lambda: self.cleanup_worker(wid)))
        return worker

    def cleanup_worker(self, worker_id):
        """清理工作线程"""
        try:
            if worker_id in self.active_workers:
                worker = self.active_workers[worker_id]
                if worker.isRunning():
                    worker.quit()
                    worker.wait(1000)
                del self.active_workers[worker_id]
                worker.deleteLater()
        except Exception as e:
            self.send_log(f"清理工作线程时出错: {str(e)}")

    # ==================== 账号列表加载 ====================
    def load_accounts(self):
        """加载账号列表"""
        self.send_log("正在加载账号列表...")

        params = {"page": self.current_page, "size": self.page_size}

        # 搜索条件
        search_field = self.comboSearchField.currentText()
        search_text = self.editTopSearch.text().strip()

        if search_text:
            if search_field == "邮箱":
                params["email_contains"] = search_text
            elif search_field == "辅助邮箱":
                params["recovery_email_contains"] = search_text
            elif search_field == "辅助电话":
                params["recovery_phone"] = search_text
            elif search_field == "备注":
                params["note_contains"] = search_text

        worker = self.create_api_worker("GET", "/accounts", params=params)
        worker.success.connect(self.on_accounts_loaded)
        worker.error.connect(self.on_load_error)
        worker.start()

    def on_accounts_loaded(self, data):
        """账号加载成功"""
        try:
            self.accounts_data = data.get("items", [])

            # 更新表格
            table_data = []
            for idx, account in enumerate(self.accounts_data, 1):
                row = [
                    idx,
                    account["id"],
                    account["email"],
                    account["status"],
                    account.get("username", ""),
                    account.get("birthday", ""),
                    str(account["version"]),
                    account["updated_at"],
                ]
                table_data.append(row)

            headers = ["序号", "ID", "邮箱", "状态", "用户名", "生日", "版本", "更新时间"]
            self.account_model.setData(table_data, headers)

            # 更新分页信息
            self.total_items = data.get("total", 0)
            self.total_pages = data.get("pages", 1)
            self.lblPageInfo.setText(f"第 {self.current_page}/{self.total_pages} 页（共 {self.total_items} 条）")

            # 更新分页按钮
            self.btnPagePrev.setEnabled(self.current_page > 1)
            self.btnPageNext.setEnabled(self.current_page < self.total_pages)

            # 更新页码输入
            self.spinPage.setMaximum(max(1, self.total_pages))
            self.spinPage.setValue(self.current_page)

            self.send_log(f"已加载 {len(self.accounts_data)} 个账号")

        except Exception as e:
            self.send_log(f"处理账号数据时出错: {str(e)}")

    def on_load_error(self, error_msg):
        """加载失败"""
        self.send_log(f"加载失败: {error_msg}")

    # ==================== 分页功能 ====================
    def on_search(self):
        """搜索"""
        self.current_page = 1
        self.load_accounts()

    def prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_accounts()

    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_accounts()

    def goto_page(self):
        """跳转页"""
        page = self.spinPage.value()
        if page != self.current_page and 1 <= page <= self.total_pages:
            self.current_page = page
            self.load_accounts()

    def on_page_size_changed(self, text):
        """每页大小改变"""
        try:
            new_size = int(text)
            if new_size != self.page_size:
                self.page_size = new_size
                self.current_page = 1
                self.load_accounts()
        except:
            pass

    # ==================== 账号右键菜单 ====================
    def get_selected_accounts(self):
        """获取选中的账号信息"""
        indexes = self.tableAccounts.selectionModel().selectedRows()
        selected = []
        for index in indexes:
            row = index.row()
            if 0 <= row < len(self.accounts_data):
                selected.append(self.accounts_data[row])
        return selected

    def show_account_menu(self, position):
        """显示账号右键菜单"""
        selected = self.get_selected_accounts()
        if not selected:
            return

        menu = QMenu(self)

        # 单选菜单项
        if len(selected) == 1:
            account = selected[0]
            status = account["status"]

            action_login = menu.addAction("🔐 登录")
            if status == "登录成功":
                action_login.setEnabled(False)

                # 邮件检查菜单
                mail_menu = menu.addMenu("📧 邮件")
                action_check_update = mail_menu.addAction("检测更新")
                action_full_sync = mail_menu.addAction("完整同步")
                action_time_query = mail_menu.addAction("按时间查询")

                if status != "登录成功":
                    mail_menu.setEnabled(False)

            menu.addSeparator()

            # 复制功能
            copy_menu = menu.addMenu("📋 复制")
            action_copy_email = copy_menu.addAction("邮箱地址")
            action_copy_password = copy_menu.addAction("密码")
            action_copy_both = copy_menu.addAction("邮箱和密码")
            if account.get("recovery_emails"):
                action_copy_rec_email = copy_menu.addAction("辅助邮箱")

            menu.addSeparator()
            action_delete = menu.addAction("🗑️ 删除")

        else:
            # 多选菜单
            action_batch_login = menu.addAction("🔐 批量登录")

            mail_menu = menu.addMenu("📧 批量邮件")
            action_batch_check_update = mail_menu.addAction("批量检测更新")
            action_batch_full_sync = mail_menu.addAction("批量完整同步")

            copy_menu = menu.addMenu("📋 批量复制")
            action_copy_emails = copy_menu.addAction("所有邮箱地址")
            action_copy_passwords = copy_menu.addAction("所有密码")
            action_copy_all = copy_menu.addAction("邮箱和密码（表格）")

            menu.addSeparator()
            action_batch_delete = menu.addAction("🗑️ 批量删除")

        # 添加全局操作
        menu.addSeparator()
        action_check_all = menu.addAction("🔍 检查当页所有邮箱邮件")

        # 执行菜单
        action = menu.exec_(self.tableAccounts.mapToGlobal(position))

        if not action:
            return

        action_text = action.text()

        # 处理单选操作
        if len(selected) == 1:
            account = selected[0]
            if action_text == "🔐 登录":
                self.login_account(account)
            elif action_text == "检测更新":
                self.check_mail_update(account)
            elif action_text == "完整同步":
                self.full_sync_mail(account)
            elif action_text == "按时间查询":
                self.query_mail_by_time(account)
            elif action_text == "邮箱地址":
                self.copy_to_clipboard(account["email"])
            elif action_text == "密码":
                self.copy_to_clipboard(account["password"])
            elif action_text == "邮箱和密码":
                self.copy_to_clipboard(f"{account['email']}\t{account['password']}")
            elif action_text == "辅助邮箱":
                rec_emails = "; ".join(account.get("recovery_emails", []))
                self.copy_to_clipboard(rec_emails)
            elif action_text == "🗑️ 删除":
                self.delete_account(account["id"], account["email"])
        else:
            # 处理多选操作
            if action_text == "🔐 批量登录":
                self.batch_login_accounts(selected)
            elif action_text == "批量检测更新":
                self.batch_check_mail_update(selected)
            elif action_text == "批量完整同步":
                self.batch_full_sync_mail(selected)
            elif action_text == "所有邮箱地址":
                emails = "\n".join([acc["email"] for acc in selected])
                self.copy_to_clipboard(emails)
            elif action_text == "所有密码":
                passwords = "\n".join([acc["password"] for acc in selected])
                self.copy_to_clipboard(passwords)
            elif action_text == "邮箱和密码（表格）":
                table_text = "\n".join([f"{acc['email']}\t{acc['password']}" for acc in selected])
                self.copy_to_clipboard(table_text)
            elif action_text == "🗑️ 批量删除":
                self.batch_delete_accounts(selected)

        if action_text == "🔍 检查当页所有邮箱邮件":
            self.check_all_page_mails()

    def copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        self.send_log(f"已复制到剪贴板: {text[:50]}...")

    # ==================== 登录功能 ====================
    def login_account(self, account):
        """登录单个账号"""
        if account["status"] == "登录成功":
            self.send_log(f"账号 {account['email']} 已经登录成功，跳过")
            return

        self.send_log(f"开始登录账号: {account['email']}")
        self.login_pool.add_task(account)

    def batch_login_accounts(self, accounts):
        """批量登录账号"""
        need_login = [acc for acc in accounts if acc["status"] != "登录成功"]

        if not need_login:
            self.send_log("所选账号都已登录成功")
            QMessageBox.information(self, "提示", "所选账号都已登录成功")
            return

        reply = QMessageBox.question(
            self, "批量登录", f"将要登录 {len(need_login)} 个账号，是否继续？", QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.send_log(f"开始批量登录 {len(need_login)} 个账号...")
            self.login_pool.add_tasks(need_login)

    # 登录回调
    def on_login_started(self, account_id, email):
        """登录开始"""
        self.send_log(f"[{account_id}] 开始登录: {email}")

    def on_login_progress(self, account_id, message):
        """登录进度"""
        self.send_log(f"[{account_id}] {message}")

    def on_login_success(self, account_id):
        """登录成功"""
        self.send_log(f"账号 {account_id} 登录成功")
        self.update_account_status_ui(account_id, "登录成功")
        self.send_notification("登录成功", f"账号 {account_id} 已成功登录")

    def on_login_error(self, account_id, error):
        """登录失败"""
        self.send_log(f"账号 {account_id} 登录失败: {error}")
        self.update_account_status_ui(account_id, "登录失败")

    def on_login_finished(self, account_id):
        """单个登录完成"""
        pass

    def on_all_login_finished(self, success_count, fail_count):
        """所有登录完成"""
        self.send_log(f"批量登录完成: 成功 {success_count} 个，失败 {fail_count} 个")
        self.send_notification("批量登录完成", f"成功: {success_count}, 失败: {fail_count}")

    def update_account_status_ui(self, account_id, new_status):
        """更新UI中的账号状态"""
        try:
            for row, account in enumerate(self.accounts_data):
                if account["id"] == account_id:
                    account["status"] = new_status
                    self.account_model.update_cell(row, 3, new_status)
                    break
        except Exception as e:
            self.send_log(f"更新UI状态时出错: {str(e)}")

    # ==================== 邮件检查功能 ====================
    def check_mail_update(self, account):
        """检测邮件更新（增量同步）"""
        if account["status"] != "登录成功":
            QMessageBox.warning(self, "提示", f"账号 {account['email']} 未登录")
            return

        self.send_log(f"开始检测账号 {account['email']} 的邮件更新...")
        task = MailCheckTask(account)
        task.sync_strategy = "incremental"
        self.mail_check_pool.add_task(task)

    def full_sync_mail(self, account):
        """完整同步邮件"""
        if account["status"] != "登录成功":
            QMessageBox.warning(self, "提示", f"账号 {account['email']} 未登录")
            return

        reply = QMessageBox.question(
            self,
            "确认完整同步",
            f"完整同步账号 {account['email']} 的所有邮件可能需要较长时间。\n是否继续？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.send_log(f"开始完整同步账号 {account['email']} 的邮件...")
            task = MailCheckTask(account)
            task.sync_strategy = "full"
            self.mail_check_pool.add_task(task)

    def query_mail_by_time(self, account):
        """按时间查询邮件"""
        if account["status"] != "登录成功":
            QMessageBox.warning(self, "提示", f"账号 {account['email']} 未登录")
            return

        dialog = DateRangeDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            start_date, end_date = dialog.get_date_range()

            self.send_log(f"查询账号 {account['email']} 在 {start_date} 到 {end_date} 的邮件...")

            task = MailCheckTask(account)
            task.sync_strategy = "time_range"
            task.start_date = start_date
            task.end_date = end_date
            self.mail_check_pool.add_task(task)

    def batch_check_mail_update(self, accounts):
        """批量检测邮件更新"""
        logged_in = [acc for acc in accounts if acc["status"] == "登录成功"]

        if not logged_in:
            QMessageBox.warning(self, "提示", "所选账号都未登录")
            return

        self.send_log(f"开始批量检测 {len(logged_in)} 个账号的邮件更新...")

        for account in logged_in:
            task = MailCheckTask(account)
            task.sync_strategy = "incremental"
            self.mail_check_pool.add_task(task)

    def batch_full_sync_mail(self, accounts):
        """批量完整同步"""
        logged_in = [acc for acc in accounts if acc["status"] == "登录成功"]

        if not logged_in:
            QMessageBox.warning(self, "提示", "所选账号都未登录")
            return

        reply = QMessageBox.question(
            self,
            "确认批量完整同步",
            f"将要完整同步 {len(logged_in)} 个账号的所有邮件。\n这可能需要很长时间，是否继续？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.send_log(f"开始批量完整同步 {len(logged_in)} 个账号...")

            for account in logged_in:
                task = MailCheckTask(account)
                task.sync_strategy = "full"
                self.mail_check_pool.add_task(task)

    def check_all_page_mails(self):
        """检查当页所有已登录账号的邮件"""
        logged_in = [acc for acc in self.accounts_data if acc["status"] == "登录成功"]

        if not logged_in:
            QMessageBox.information(self, "提示", "当前页没有已登录的账号")
            return

        reply = QMessageBox.question(
            self,
            "确认检查所有邮件",
            f"将要检查当前页 {len(logged_in)} 个已登录账号的邮件\n是否继续？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.send_log(f"开始检查当页 {len(logged_in)} 个账号的邮件...")

            for account in logged_in:
                task = MailCheckTask(account)
                task.sync_strategy = "incremental"
                self.mail_check_pool.add_task(task)

    # 邮件检查回调
    def on_mail_check_started(self, account_id, email):
        """邮件检查开始"""
        self.send_log(f"[{account_id}] 开始检查邮件: {email}")

    def on_mail_check_progress(self, account_id, message):
        """邮件检查进度"""
        self.send_log(f"[{account_id}] {message}")

    def on_mail_check_success(self, account_id, result):
        """邮件检查成功"""
        stats = result.get("stats", {})

        msg = f"账号 {result['email']} 邮件检查完成:\n"
        msg += f"  同步: {result.get('synced', 0)} 封新邮件\n"
        msg += f"  总计: {stats.get('total', 0)} 封\n"
        msg += f"  未读: {stats.get('unread', 0)} 封"

        if stats.get("latest"):
            latest = stats["latest"]
            msg += f"\n  最新邮件: {latest['subject'][:30]}..."
            msg += f"\n  时间: {latest['received_at']}"

        self.send_log(msg)

    def on_mail_check_error(self, account_id, error):
        """邮件检查失败"""
        self.send_log(f"账号 {account_id} 邮件检查失败: {error}")

    def on_mail_check_finished(self, account_id):
        """单个邮件检查完成"""
        pass

    def on_all_mail_check_finished(self, success_count, fail_count):
        """所有邮件检查完成"""
        self.send_log(f"邮件检查完成: 成功 {success_count} 个，失败 {fail_count} 个")
        self.send_notification("邮件检查完成", f"成功: {success_count}, 失败: {fail_count}")

    # ==================== 账号详情编辑 ====================
    def on_account_selected(self):
        """账号选择改变（加载邮件列表）"""
        selected = self.get_selected_accounts()
        if len(selected) == 1:
            account = selected[0]
            self.current_account_id = account["id"]

            # 更新账号信息区域
            self.editPwd.setText(account["password"])
            status_index = self.comboStatus.findText(account["status"])
            if status_index >= 0:
                self.comboStatus.setCurrentIndex(status_index)

            recovery_emails = account.get("recovery_emails", [])
            self.editRecEmails.setText("; ".join(recovery_emails))

            recovery_phones = account.get("recovery_phones", [])
            self.editRecPhones.setText("; ".join(recovery_phones))

            self.editNote.clear()

            self.send_log(f"已选择账号: {account['email']}")
            self.load_account_mails(account["id"])

        else:
            # 多选或未选中时清空邮件列表
            self.current_account_id = None
            self.current_mails = []
            self.mail_model.setData([], ["ID", "(文件夹)发件人", "主题", "时间", "大小"])
            self.clear_mail_viewer()

    def save_account_info(self):
        """保存账号信息"""
        if not self.current_account_id:
            QMessageBox.warning(self, "提示", "请先选择一个账号")
            return

        # 获取输入数据
        password = self.editPwd.text().strip()
        status = self.comboStatus.currentText()

        rec_emails_text = self.editRecEmails.text()
        rec_emails = [e.strip() for e in rec_emails_text.replace(",", ";").split(";") if e.strip()]

        rec_phones_text = self.editRecPhones.text()
        rec_phones = [p.strip() for p in rec_phones_text.replace(",", ";").split(";") if p.strip()]

        note = self.editNote.text().strip() or "手动更新"

        update_data = [
            {
                "id": self.current_account_id,
                "password": password if password else None,
                "status": status,
                "recovery_emails": rec_emails,
                "recovery_phones": rec_phones,
                "note": note,
                "created_by": "UI",
            }
        ]

        worker = self.create_api_worker("PUT", "/accounts/batch", json_data=update_data)
        worker.success.connect(lambda result: self.on_account_saved(result))
        worker.error.connect(lambda err: QMessageBox.warning(self, "错误", f"保存失败: {err}"))
        worker.start()

    def on_account_saved(self, result):
        """账号保存成功"""
        if result.get("success"):
            self.send_log("账号信息已保存")
            self.send_notification("保存成功", "账号信息已更新")
            self.load_accounts()
        else:
            errors = result.get("errors", [])
            if errors:
                QMessageBox.warning(self, "错误", f"保存失败: {errors[0].get('error', '未知错误')}")

    def reload_account_info(self):
        """重新加载账号信息"""
        if self.current_account_id:
            self.on_account_selected()

    def delete_account(self, account_id, email):
        """删除账号"""
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除账号 {email} (ID: {account_id}) 吗？", QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            worker = self.create_api_worker("DELETE", f"/accounts/{account_id}")
            worker.success.connect(lambda _: self.load_accounts())
            worker.error.connect(lambda msg: QMessageBox.warning(self, "错误", f"删除失败: {msg}"))
            worker.start()

    def batch_delete_accounts(self, accounts):
        """批量删除"""
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除 {len(accounts)} 个账号吗？", QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            for account in accounts:
                worker = self.create_api_worker("DELETE", f"/accounts/{account['id']}")
                worker.start()
            QTimer.singleShot(1000, self.load_accounts)

    # ==================== 邮件列表和查看 ====================
    def load_account_mails(self, account_id, page=1, size=50, folder=None, query=None):
        """加载账号的邮件列表"""
        self.send_log(f"正在加载账号 {account_id} 的邮件...")

        params = {"page": page, "size": size}
        if folder:
            params["folder"] = folder
        if query:
            params["q"] = query
        worker = self.create_api_worker("GET", f"/mail/accounts/{account_id}/mails", params=params)
        worker.success.connect(self.on_mails_loaded)
        worker.error.connect(lambda err: self.send_log(f"加载邮件失败: {err}"))
        worker.start()

    def on_mails_loaded(self, data):
        """邮件列表加载成功"""
        try:
            self.current_mails = data.get("items", [])

            # 准备表格数据
            table_data = []
            for mail in self.current_mails:
                folder_name = mail.get("folder_name", "")
                from_addr = mail.get("from_addr", "")
                from_display = f"({folder_name}) {from_addr}" if folder_name else from_addr

                subject = mail.get("subject", "(无主题)")
                received_at = mail.get("received_at", "")
                time_display = self.format_mail_time(received_at)

                size_bytes = mail.get("size_bytes", 0)
                size_display = self.format_size(size_bytes)

                row = [
                    mail["id"],
                    from_display,
                    subject,
                    time_display,
                    size_display,
                ]
                table_data.append(row)

            headers = ["ID", "(文件夹)发件人", "主题", "时间", "大小"]
            self.mail_model.setData(table_data, headers)

            self.send_log(f"已加载 {len(self.current_mails)} 封邮件")

            # 自动选中并显示第一封邮件
            if self.current_mails:
                self.tableMails.selectRow(0)
                self.load_mail_detail(self.current_mails[0]["id"])
            else:
                self.clear_mail_viewer()

        except Exception as e:
            self.send_log(f"处理邮件数据时出错: {str(e)}")

    def format_mail_time(self, time_str):
        """格式化邮件时间"""
        if not time_str:
            return ""

        try:
            from datetime import datetime

            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            local_dt = dt.astimezone()
            now = datetime.now().astimezone()

            if local_dt.date() == now.date():
                return local_dt.strftime("%H:%M")
            elif (now - local_dt).days == 1:
                return f"昨天 {local_dt.strftime('%H:%M')}"
            elif (now - local_dt).days < 7:
                weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                weekday = weekdays[local_dt.weekday()]
                return f"{weekday} {local_dt.strftime('%H:%M')}"
            elif local_dt.year == now.year:
                return local_dt.strftime("%m-%d %H:%M")
            else:
                return local_dt.strftime("%Y-%m-%d")
        except Exception:
            return time_str

    def format_size(self, size_bytes):
        """格式化文件大小"""
        if not size_bytes:
            return "-"

        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"

    def on_mail_selected(self):
        """邮件选择改变（显示邮件详情）"""
        indexes = self.tableMails.selectionModel().selectedRows()
        if not indexes:
            self.clear_mail_viewer()
            return

        row = indexes[0].row()
        if 0 <= row < len(self.current_mails):
            mail = self.current_mails[row]
            self.current_mail_id = mail["id"]
            self.load_mail_detail(mail["id"])

    def load_mail_detail(self, message_id):
        """加载邮件详情"""
        self.send_log(f"正在加载邮件 {message_id} 的详情...")
        self.show_loading_in_viewer()

        worker = self.create_api_worker("GET", f"/mail/{message_id}/preview")
        worker.success.connect(self.on_mail_detail_loaded)
        worker.error.connect(lambda err: self.show_error_in_viewer(f"加载失败: {err}"))
        worker.start()

    def on_mail_detail_loaded(self, data):
        """邮件详情加载成功"""
        try:
            message = data.get("message", {})
            body_html = data.get("body_html")
            body_plain = data.get("body_plain")

            subject = message.get("subject", "(无主题)")
            from_addr = message.get("from_addr", "")
            received_at = message.get("received_at", "")

            self.lblSubject.setText(subject)
            self.valFrom.setText(from_addr)
            self.valDate.setText(received_at)
            self.valTo.setText("")

            if body_html:
                self.display_mail_body(body_html, is_html=True)
            elif body_plain:
                self.display_mail_body(body_plain, is_html=False)
            else:
                snippet = message.get("snippet", "")
                self.show_download_prompt(snippet=snippet)

        except Exception as e:
            self.show_error_in_viewer(f"显示邮件时出错: {str(e)}")

    def on_viewer_title_changed(self, title):
        """监听 WebView 标题变化"""
        if title == "DOWNLOAD_MAIL":
            if self.current_mail_id:
                self.download_mail_body(self.current_mail_id)
            else:
                self.send_log("❌ 没有选中的邮件")

    def display_mail_body(self, content, is_html=True):
        """显示邮件正文"""
        if is_html:
            cleaned_html = self.sanitize_html(content)
            self.viewer.setHtml(cleaned_html)
        else:
            plain_html = f"""
            <html>
            <head>
                <style>
                    body {{ 
                        font-family: 'Segoe UI', Arial, sans-serif; 
                        padding: 20px;
                        line-height: 1.6;
                        color: #333;
                    }}
                    pre {{
                        white-space: pre-wrap;
                        word-wrap: break-word;
                    }}
                </style>
            </head>
            <body>
                <pre>{content}</pre>
            </body>
            </html>
            """
            self.viewer.setHtml(plain_html)

    def sanitize_html(self, html):
        """清理HTML内容"""
        import re

        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'\son\w+\s*=\s*["\'][^"\']*["\']', "", html, flags=re.IGNORECASE)

        styled_html = f"""
        <html>
        <head>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Arial, sans-serif; 
                    padding: 20px;
                    max-width: 800px;
                }}
                img {{ max-width: 100%; height: auto; }}
                a {{ color: #0066cc; }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>
        """
        return styled_html

    def show_download_prompt(self, snippet=""):
        """显示下载按钮"""
        import html

        snippet_safe = html.escape(snippet)

        html_content = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>邮件预览</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Arial, sans-serif;
                    padding: 20px;
                    background-color: #ffffff;
                }}
                .snippet {{
                    color: #333;
                    line-height: 1.6;
                    margin-bottom: 20px;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }}
                .download-btn {{
                    padding: 10px 20px;
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 14px;
                }}
                .download-btn:hover {{
                    background-color: #005a9e;
                }}
            </style>
            <script>
                function triggerDownload() {{
                    document.title = 'DOWNLOAD_MAIL';
                    setTimeout(function() {{
                        document.title = '邮件预览';
                    }}, 100);
                }}
            </script>
        </head>
        <body>
            <div class="snippet">{snippet_safe}</div>
            <button class="download-btn" onclick="triggerDownload()">点击立即下载</button>
        </body>
        </html>
        """
        self.viewer.setHtml(html_content)

    def show_loading_in_viewer(self):
        """显示加载中"""
        html = """
        <html>
        <head>
            <style>
                body {
                    font-family: 'Segoe UI', Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f5f5f5;
                }
                .loader {
                    text-align: center;
                    color: #666;
                }
                .spinner {
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #0078d4;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 20px;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        </head>
        <body>
            <div class="loader">
                <div class="spinner"></div>
                <p>正在加载邮件...</p>
            </div>
        </body>
        </html>
        """
        self.viewer.setHtml(html)

    def show_error_in_viewer(self, error_msg):
        """显示错误信息"""
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f5f5f5;
                }}
                .error {{
                    text-align: center;
                    color: #d13438;
                    padding: 40px;
                    background: white;
                    border-radius: 8px;
                }}
                .icon {{
                    font-size: 48px;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="error">
                <div class="icon">❌</div>
                <h2>加载失败</h2>
                <p>{error_msg}</p>
            </div>
        </body>
        </html>
        """
        self.viewer.setHtml(html)

    def clear_mail_viewer(self):
        """清空邮件查看器"""
        html = """
        <html>
        <head>
            <style>
                body {
                    font-family: 'Segoe UI', Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f5f5f5;
                }
                .empty {
                    text-align: center;
                    color: #999;
                }
                .icon {
                    font-size: 64px;
                    margin-bottom: 20px;
                }
            </style>
        </head>
        <body>
            <div class="empty">
                <div class="icon">📭</div>
                <p>请选择一封邮件查看</p>
            </div>
        </body>
        </html>
        """
        self.viewer.setHtml(html)
        self.lblSubject.setText("示例主题")
        self.valFrom.setText("")
        self.valTo.setText("")
        self.valDate.setText("")

    def download_mail_body(self, message_id):
        """下载邮件正文"""
        self.send_log(f"开始下载邮件 {message_id} 的正文...")
        self.show_downloading_in_viewer()

        worker = MailBodyDownloadWorker(message_id, self.current_account_id)
        worker.success.connect(self.on_mail_body_downloaded)
        worker.error.connect(lambda err: self.show_error_in_viewer(f"下载失败: {err}"))
        worker.progress.connect(lambda msg: self.send_log(msg))

        self.worker_counter += 1
        worker_id = f"download_worker_{self.worker_counter}"
        self.active_workers[worker_id] = worker
        worker.finished_work.connect(lambda wid=worker_id: QTimer.singleShot(100, lambda: self.cleanup_worker(wid)))

        worker.start()

    def show_downloading_in_viewer(self):
        """显示下载中"""
        html = """
        <html>
        <head>
            <style>
                body {
                    font-family: 'Segoe UI', Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f5f5f5;
                }
                .loader {
                    text-align: center;
                    color: #666;
                }
                .spinner {
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #0078d4;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 20px;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        </head>
        <body>
            <div class="loader">
                <div class="spinner"></div>
                <p>正在下载邮件正文...</p>
            </div>
        </body>
        </html>
        """
        self.viewer.setHtml(html)

    def on_mail_body_downloaded(self, message_id):
        """邮件正文下载完成"""
        self.send_log(f"邮件 {message_id} 下载完成")
        self.load_mail_detail(message_id)

    def show_mail_menu(self, position):
        """显示邮件右键菜单"""
        indexes = self.tableMails.selectionModel().selectedRows()
        if not indexes:
            return

        row = indexes[0].row()
        if row < 0 or row >= len(self.current_mails):
            return

        mail = self.current_mails[row]

        menu = QMenu(self)

        action_open = menu.addAction("📖 打开")
        action_download = menu.addAction("📥 下载正文")
        action_reply = menu.addAction("↩️ 回复")
        action_forward = menu.addAction("➡️ 转发")

        menu.addSeparator()

        mark_menu = menu.addMenu("🏷️ 标记为")
        action_mark_read = mark_menu.addAction("已读")
        action_mark_unread = mark_menu.addAction("未读")

        menu.addSeparator()

        action_copy_subject = menu.addAction("📋 复制主题")
        action_copy_from = menu.addAction("📋 复制发件人")

        menu.addSeparator()
        action_delete = menu.addAction("🗑️ 删除")

        action = menu.exec_(self.tableMails.mapToGlobal(position))

        if not action:
            return

        if action == action_open:
            self.load_mail_detail(mail["id"])
        elif action == action_download:
            self.download_mail_body(mail["id"])
        elif action == action_copy_subject:
            self.copy_to_clipboard(mail.get("subject", ""))
        elif action == action_copy_from:
            self.copy_to_clipboard(mail.get("from_addr", ""))

    def on_tab1_search(self):
        """Tab1 搜索邮件"""
        if not self.current_account_id:
            return

        query = self.editTab1Query.text().strip()
        self.load_account_mails(self.current_account_id, query=query)

    def on_tab1_clear(self):
        """Tab1 清空搜索"""
        self.editTab1Query.clear()
        if self.current_account_id:
            self.load_account_mails(self.current_account_id)

    # ==================== 服务器管理 ====================
    def toggle_server(self):
        """切换服务器状态"""
        if self.server_thread and self.server_thread.is_running:
            self.server_thread.stop()
            self.server_thread.quit()
            self.server_thread.wait()
            self.server_thread = None
            self.btnServerToggle.setText("启动API")
            self.btnServerToggle.setChecked(False)
            self.send_log("正在停止FastAPI服务...")
        else:
            self.server_thread = ServerThread()
            self.server_thread.server_started.connect(self.on_server_started)
            self.server_thread.server_stopped.connect(self.on_server_stopped)
            self.server_thread.server_error.connect(self.on_server_error)
            self.server_thread.start()
            self.send_log("正在启动FastAPI服务...")

    def on_server_started(self):
        """服务启动成功"""
        self.send_log("FastAPI服务已启动")
        self.btnServerToggle.setText("停止API")
        self.btnServerToggle.setChecked(True)
        QTimer.singleShot(500, self.load_accounts)

    def on_server_stopped(self):
        """服务停止"""
        self.send_log("FastAPI服务已停止")
        self.btnServerToggle.setText("启动API")
        self.btnServerToggle.setChecked(False)

    def on_server_error(self, error):
        """服务错误"""
        self.send_log(f"服务错误: {error}")

    def open_index_page(self):
        """打开网页"""
        config = AppConfig()
        webbrowser.open(f"{config.base_url}/index")

    # ==================== 清理资源 ====================
    def closeEvent(self, event):
        """关闭事件，清理资源"""
        # 停止所有工作线程
        for worker in self.active_workers.values():
            if worker.isRunning():
                worker.stop()
                if not worker.wait(3000):
                    worker.terminate()
        self.active_workers.clear()

        # 停止服务器
        if self.server_thread and self.server_thread.is_running:
            self.server_thread.stop()
            self.server_thread.quit()
            self.server_thread.wait(5000)

        super().closeEvent(event)
