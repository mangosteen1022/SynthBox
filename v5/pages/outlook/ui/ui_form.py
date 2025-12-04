# -*- coding: utf-8 -*-
# ui.py
import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWebEngineWidgets import QWebEngineView


class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(1440, 860)
        self.verticalLayout = QtWidgets.QVBoxLayout(Form)
        self.verticalLayout.setObjectName("verticalLayout")

        # 顶部工具条（仅搜索字段+搜索框+搜索按钮；右侧：刷新/服务开关/打开页面）
        self.topBarWidget = QtWidgets.QWidget(Form)
        self.topBarWidget.setObjectName("topBarWidget")
        self.topBarWidget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.horizontalLayout_top = QtWidgets.QHBoxLayout(self.topBarWidget)
        self.horizontalLayout_top.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_top.setSpacing(6)

        self.comboSearchField = QtWidgets.QComboBox(self.topBarWidget)
        self.comboSearchField.setObjectName("comboSearchField")
        self.horizontalLayout_top.addWidget(self.comboSearchField)

        self.editTopSearch = QtWidgets.QLineEdit(self.topBarWidget)
        self.editTopSearch.setObjectName("editTopSearch")
        self.horizontalLayout_top.addWidget(self.editTopSearch)

        self.btnTopSearch = QtWidgets.QPushButton(self.topBarWidget)
        self.btnTopSearch.setObjectName("btnTopSearch")
        self.horizontalLayout_top.addWidget(self.btnTopSearch)

        # 左右拉伸分隔，左侧靠左，右侧按钮靠右
        self._spacerTop = QtWidgets.QWidget(self.topBarWidget)
        self._spacerTop.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.horizontalLayout_top.addWidget(self._spacerTop)

        # 右侧按钮：刷新 / 服务开关 / 打开页面
        self.btnRefresh = QtWidgets.QPushButton(self.topBarWidget)
        self.btnRefresh.setObjectName("btnRefresh")
        self.horizontalLayout_top.addWidget(self.btnRefresh)

        self.btnServerToggle = QtWidgets.QPushButton(self.topBarWidget)
        self.btnServerToggle.setObjectName("btnServerToggle")
        self.btnServerToggle.setCheckable(True)
        self.horizontalLayout_top.addWidget(self.btnServerToggle)

        self.btnOpenIndex = QtWidgets.QPushButton(self.topBarWidget)
        self.btnOpenIndex.setObjectName("btnOpenIndex")
        self.horizontalLayout_top.addWidget(self.btnOpenIndex)

        self.verticalLayout.addWidget(self.topBarWidget)

        # 主体：两列（左：账号表+分页；右：上Tab/下详情）
        self.splitterRoot = QtWidgets.QSplitter(Form)
        self.splitterRoot.setOrientation(QtCore.Qt.Horizontal)
        self.splitterRoot.setObjectName("splitterRoot")
        self.verticalLayout.addWidget(self.splitterRoot)

        # 左：账号表 + 分页（QToolBar 模式）
        self.widgetMiddle = QtWidgets.QWidget(self.splitterRoot)
        self.widgetMiddle.setObjectName("widgetMiddle")
        self.verticalLayout_mid = QtWidgets.QVBoxLayout(self.widgetMiddle)
        self.verticalLayout_mid.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_mid.setSpacing(6)

        self.tableAccounts = QtWidgets.QTableView(self.widgetMiddle)
        self.tableAccounts.setObjectName("tableAccounts")
        self.tableAccounts.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tableAccounts.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tableAccounts.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tableAccounts.verticalHeader().setVisible(False)
        self.tableAccounts.horizontalHeader().setStretchLastSection(True)
        self.tableAccounts.setSortingEnabled(True)
        self.verticalLayout_mid.addWidget(self.tableAccounts)

        # 分页工具条（QToolBar）
        self.pagerToolbar = QtWidgets.QToolBar(self.widgetMiddle)
        self.pagerToolbar.setObjectName("pagerToolbar")
        self.pagerToolbar.setIconSize(QtCore.QSize(16, 16))
        self.pagerToolbar.setMovable(False)

        self.btnPagePrev = QtWidgets.QPushButton("上一页", self.pagerToolbar)
        self.btnPagePrev.setObjectName("btnPagePrev")
        act_prev = QtWidgets.QWidgetAction(self.pagerToolbar)
        act_prev.setDefaultWidget(self.btnPagePrev)
        self.pagerToolbar.addAction(act_prev)

        self.lblPageInfo = QtWidgets.QLabel("第 1/1 页（共 0 条）", self.pagerToolbar)
        self.lblPageInfo.setObjectName("lblPageInfo")
        act_info = QtWidgets.QWidgetAction(self.pagerToolbar)
        act_info.setDefaultWidget(self.lblPageInfo)
        self.pagerToolbar.addAction(act_info)

        self.btnPageNext = QtWidgets.QPushButton("下一页", self.pagerToolbar)
        self.btnPageNext.setObjectName("btnPageNext")
        act_next = QtWidgets.QWidgetAction(self.pagerToolbar)
        act_next.setDefaultWidget(self.btnPageNext)
        self.pagerToolbar.addAction(act_next)

        spacer_mid = QtWidgets.QWidget(self.pagerToolbar)
        spacer_mid.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        act_spacer_mid = QtWidgets.QWidgetAction(self.pagerToolbar)
        act_spacer_mid.setDefaultWidget(spacer_mid)
        self.pagerToolbar.addAction(act_spacer_mid)

        self.lblPageSize = QtWidgets.QLabel("每页", self.pagerToolbar)
        self.lblPageSize.setObjectName("lblPageSize")
        act_lbl_size = QtWidgets.QWidgetAction(self.pagerToolbar)
        act_lbl_size.setDefaultWidget(self.lblPageSize)
        self.pagerToolbar.addAction(act_lbl_size)

        self.comboPageSize = QtWidgets.QComboBox(self.pagerToolbar)
        self.comboPageSize.setObjectName("comboPageSize")
        self.comboPageSize.addItems(["10", "20", "50", "100", "500", "1000"])
        act_pagesize = QtWidgets.QWidgetAction(self.pagerToolbar)
        act_pagesize.setDefaultWidget(self.comboPageSize)
        self.pagerToolbar.addAction(act_pagesize)

        self.lblGoPage = QtWidgets.QLabel("跳转到", self.pagerToolbar)
        self.lblGoPage.setObjectName("lblGoPage")
        act_lbl_go = QtWidgets.QWidgetAction(self.pagerToolbar)
        act_lbl_go.setDefaultWidget(self.lblGoPage)
        self.pagerToolbar.addAction(act_lbl_go)

        self.spinPage = QtWidgets.QSpinBox(self.pagerToolbar)
        self.spinPage.setObjectName("spinPage")
        self.spinPage.setMinimum(1)
        self.spinPage.setMaximum(999999)
        self.spinPage.setFixedWidth(80)
        act_spin = QtWidgets.QWidgetAction(self.pagerToolbar)
        act_spin.setDefaultWidget(self.spinPage)
        self.pagerToolbar.addAction(act_spin)

        self.btnGoPage = QtWidgets.QPushButton("前往", self.pagerToolbar)
        self.btnGoPage.setObjectName("btnGoPage")
        act_gopage = QtWidgets.QWidgetAction(self.pagerToolbar)
        act_gopage.setDefaultWidget(self.btnGoPage)
        self.pagerToolbar.addAction(act_gopage)

        self.verticalLayout_mid.addWidget(self.pagerToolbar)

        # 右：上下分割
        self.splitterRight = QtWidgets.QSplitter(self.splitterRoot)
        self.splitterRight.setOrientation(QtCore.Qt.Vertical)
        self.splitterRight.setObjectName("splitterRight")

        # 右上：Tab
        self.tabs = QtWidgets.QTabWidget(self.splitterRight)
        self.tabs.setObjectName("tabs")

        # Tab1 当前账号
        self.tabCurrent = QtWidgets.QWidget()
        self.tabCurrent.setObjectName("tabCurrent")
        self.verticalLayout_tab1 = QtWidgets.QVBoxLayout(self.tabCurrent)
        self.verticalLayout_tab1.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_tab1.setSpacing(6)

        self.splitterTab1 = QtWidgets.QSplitter(self.tabCurrent)
        self.splitterTab1.setOrientation(QtCore.Qt.Horizontal)
        self.splitterTab1.setObjectName("splitterTab1")
        self.verticalLayout_tab1.addWidget(self.splitterTab1)

        # 左：文件夹 + 账号信息编辑区
        self.widgetTab1Left = QtWidgets.QWidget(self.splitterTab1)
        self.widgetTab1Left.setObjectName("widgetTab1Left")
        self.verticalLayout_tab1Left = QtWidgets.QVBoxLayout(self.widgetTab1Left)
        self.verticalLayout_tab1Left.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_tab1Left.setSpacing(6)

        self.groupVersion = QtWidgets.QGroupBox(self.widgetTab1Left)
        self.groupVersion.setObjectName("groupVersion")
        self.groupVersion.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.formLayout_version = QtWidgets.QFormLayout(self.groupVersion)
        self.formLayout_version.setContentsMargins(6, 6, 6, 6)
        self.formLayout_version.setHorizontalSpacing(10)
        self.formLayout_version.setVerticalSpacing(4)

        self.comboVersion = QtWidgets.QComboBox(self.groupVersion)
        self.comboVersion.setObjectName("comboVersion")
        self.comboVersion.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.formLayout_version.addRow(self._form_label("查看版本"), self.comboVersion)

        self.editPwd = QtWidgets.QLineEdit(self.groupVersion)
        self.editPwd.setObjectName("editPwd")
        self.formLayout_version.addRow(self._form_label("密码"), self.editPwd)

        self.comboStatus = QtWidgets.QComboBox(self.groupVersion)
        self.comboStatus.setObjectName("comboStatus")
        self.comboStatus.addItems(["未登录", "登录成功", "登录失败"])
        self.formLayout_version.addRow(self._form_label("状态"), self.comboStatus)

        self.editRecEmails = QtWidgets.QLineEdit(self.groupVersion)
        self.editRecEmails.setObjectName("editRecEmails")
        self.formLayout_version.addRow(self._form_label("辅助邮箱"), self.editRecEmails)

        self.editRecPhones = QtWidgets.QLineEdit(self.groupVersion)
        self.editRecPhones.setObjectName("editRecPhones")
        self.formLayout_version.addRow(self._form_label("辅助电话"), self.editRecPhones)

        self.editNote = QtWidgets.QLineEdit(self.groupVersion)
        self.editNote.setObjectName("editNote")
        self.formLayout_version.addRow(self._form_label("备注"), self.editNote)

        self.widgetVersionBtns = QtWidgets.QWidget(self.groupVersion)
        self.widgetVersionBtns.setObjectName("widgetVersionBtns")
        self.horizontalLayout_versionBtns = QtWidgets.QHBoxLayout(self.widgetVersionBtns)
        self.horizontalLayout_versionBtns.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_versionBtns.setSpacing(6)
        self.btnVersionSave = QtWidgets.QPushButton(self.widgetVersionBtns)
        self.btnVersionSave.setObjectName("btnVersionSave")
        self.horizontalLayout_versionBtns.addWidget(self.btnVersionSave)
        self.btnVersionReload = QtWidgets.QPushButton(self.widgetVersionBtns)
        self.btnVersionReload.setObjectName("btnVersionReload")
        self.horizontalLayout_versionBtns.addWidget(self.btnVersionReload)
        spacer_ver = QtWidgets.QSpacerItem(20, 10, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_versionBtns.addItem(spacer_ver)
        self.formLayout_version.addRow(self.widgetVersionBtns)

        self.verticalLayout_tab1Left.addWidget(self.groupVersion)
        spacer_tab1_left = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_tab1Left.addItem(spacer_tab1_left)

        # 右：搜索 + 邮件表格
        self.widgetMailRight = QtWidgets.QWidget(self.splitterTab1)
        self.widgetMailRight.setObjectName("widgetMailRight")
        self.verticalLayout_mailRight = QtWidgets.QVBoxLayout(self.widgetMailRight)
        self.verticalLayout_mailRight.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_mailRight.setSpacing(6)

        self.mailToolbar = QtWidgets.QToolBar(self.widgetMailRight)
        self.mailToolbar.setObjectName("mailToolbar")

        self.comboTab1Field = QtWidgets.QComboBox(self.mailToolbar)
        self.comboTab1Field.setObjectName("comboTab1Field")
        self.mailToolbar.addWidget(self.comboTab1Field)

        self.comboTab1Cond = QtWidgets.QComboBox(self.mailToolbar)
        self.comboTab1Cond.setObjectName("comboTab1Cond")
        self.mailToolbar.addWidget(self.comboTab1Cond)

        self.editTab1Query = QtWidgets.QLineEdit(self.mailToolbar)
        self.editTab1Query.setObjectName("editTab1Query")
        self.mailToolbar.addWidget(self.editTab1Query)

        self.btnTab1Search = QtWidgets.QPushButton(self.mailToolbar)
        self.btnTab1Search.setObjectName("btnTab1Search")
        self.mailToolbar.addWidget(self.btnTab1Search)

        self.btnTab1Clear = QtWidgets.QPushButton(self.mailToolbar)
        self.btnTab1Clear.setObjectName("btnTab1Clear")
        self.mailToolbar.addWidget(self.btnTab1Clear)

        self.btnTab1Compose = QtWidgets.QPushButton(self.mailToolbar)
        self.btnTab1Compose.setObjectName("btnTab1Compose")
        self.mailToolbar.addWidget(self.btnTab1Compose)

        self.verticalLayout_mailRight.addWidget(self.mailToolbar)
        self.tableMails = QtWidgets.QTableView(self.widgetMailRight)
        self.tableMails.setObjectName("tableMails")
        self.tableMails.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tableMails.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tableMails.verticalHeader().setVisible(False)
        self.tableMails.horizontalHeader().setStretchLastSection(True)
        self.tableMails.setSortingEnabled(True)
        self.verticalLayout_mailRight.addWidget(self.tableMails)

        self.tabs.addTab(self.tabCurrent, "")

        # Tab2
        self.tabSearch = QtWidgets.QWidget()
        self.tabSearch.setObjectName("tabSearch")
        self.verticalLayout_tab2 = QtWidgets.QVBoxLayout(self.tabSearch)
        self.verticalLayout_tab2.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_tab2.setSpacing(6)
        self.searchToolbar = QtWidgets.QToolBar(self.tabSearch)
        self.searchToolbar.setObjectName("searchToolbar")
        self.radioAll = QtWidgets.QRadioButton(self.searchToolbar)
        self.searchToolbar.addWidget(self.radioAll)
        self.radioUnread = QtWidgets.QRadioButton(self.searchToolbar)
        self.searchToolbar.addWidget(self.radioUnread)
        self.comboField = QtWidgets.QComboBox(self.searchToolbar)
        self.searchToolbar.addWidget(self.comboField)
        self.comboCond = QtWidgets.QComboBox(self.searchToolbar)
        self.searchToolbar.addWidget(self.comboCond)
        self.editSearch = QtWidgets.QLineEdit(self.searchToolbar)
        self.searchToolbar.addWidget(self.editSearch)
        self.comboScope = QtWidgets.QComboBox(self.searchToolbar)
        self.searchToolbar.addWidget(self.comboScope)
        self.chkOnlySelected = QtWidgets.QCheckBox(self.searchToolbar)
        self.searchToolbar.addWidget(self.chkOnlySelected)
        self.btnSearchRun = QtWidgets.QPushButton(self.searchToolbar)
        self.searchToolbar.addWidget(self.btnSearchRun)
        self.btnSearchClear = QtWidgets.QPushButton(self.searchToolbar)
        self.searchToolbar.addWidget(self.btnSearchClear)
        self.verticalLayout_tab2.addWidget(self.searchToolbar)

        self.tableSearch = QtWidgets.QTableView(self.tabSearch)
        self.tableSearch.setObjectName("tableSearch")
        self.tableSearch.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tableSearch.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tableSearch.verticalHeader().setVisible(False)
        self.tableSearch.horizontalHeader().setStretchLastSection(True)
        self.tableSearch.setSortingEnabled(True)
        self.verticalLayout_tab2.addWidget(self.tableSearch)
        self.tabs.addTab(self.tabSearch, "")

        # Tab3
        self.tabOutbox = QtWidgets.QWidget()
        self.tabOutbox.setObjectName("tabOutbox")
        self.verticalLayout_tab3 = QtWidgets.QVBoxLayout(self.tabOutbox)
        self.verticalLayout_tab3.setContentsMargins(6, 6, 6, 6)
        self.verticalLayout_tab3.setSpacing(6)
        self.tableOutbox = QtWidgets.QTableView(self.tabOutbox)
        self.tableOutbox.setObjectName("tableOutbox")
        self.tableOutbox.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tableOutbox.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tableOutbox.verticalHeader().setVisible(False)
        self.tableOutbox.horizontalHeader().setStretchLastSection(True)
        self.tableOutbox.setSortingEnabled(True)
        self.verticalLayout_tab3.addWidget(self.tableOutbox)
        self.tabs.addTab(self.tabOutbox, "")

        # 右下：详情区
        self.widgetBottom = QtWidgets.QWidget(self.splitterRight)
        self.widgetBottom.setObjectName("widgetBottom")
        self.verticalLayout_bottom = QtWidgets.QVBoxLayout(self.widgetBottom)
        self.verticalLayout_bottom.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_bottom.setSpacing(6)

        self.headerPanel = QtWidgets.QFrame(self.widgetBottom)
        self.headerPanel.setObjectName("headerPanel")
        self.verticalLayout_header = QtWidgets.QVBoxLayout(self.headerPanel)
        self.verticalLayout_header.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_header.setSpacing(6)

        self.widgetHeaderBtns = QtWidgets.QWidget(self.headerPanel)
        self.horizontalLayout_headerBtns = QtWidgets.QHBoxLayout(self.widgetHeaderBtns)
        self.horizontalLayout_headerBtns.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_headerBtns.setSpacing(6)

        self.btnReply = QtWidgets.QPushButton(self.widgetHeaderBtns)
        self.btnReply.setObjectName("btnReply")
        self.horizontalLayout_headerBtns.addWidget(self.btnReply)
        self.btnForward = QtWidgets.QPushButton(self.widgetHeaderBtns)
        self.btnForward.setObjectName("btnForward")
        self.horizontalLayout_headerBtns.addWidget(self.btnForward)
        self.btnOpenInBrowser = QtWidgets.QPushButton(self.widgetHeaderBtns)
        self.btnOpenInBrowser.setObjectName("btnOpenInBrowser")
        self.horizontalLayout_headerBtns.addWidget(self.btnOpenInBrowser)
        spacerHead = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_headerBtns.addItem(spacerHead)

        self.verticalLayout_header.addWidget(self.widgetHeaderBtns)

        self.lblSubject = QtWidgets.QLabel(self.headerPanel)
        font = self.lblSubject.font()
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        self.lblSubject.setFont(font)
        self.lblSubject.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.verticalLayout_header.addWidget(self.lblSubject)

        self.gridHeader = QtWidgets.QGridLayout()
        self.gridHeader.setHorizontalSpacing(12)
        self.gridHeader.setVerticalSpacing(4)
        self.labelFrom = QtWidgets.QLabel(self.headerPanel)
        self.gridHeader.addWidget(self.labelFrom, 0, 0, 1, 1)
        self.valFrom = QtWidgets.QLabel(self.headerPanel)
        self.gridHeader.addWidget(self.valFrom, 0, 1, 1, 1)
        self.labelTo = QtWidgets.QLabel(self.headerPanel)
        self.gridHeader.addWidget(self.labelTo, 1, 0, 1, 1)
        self.valTo = QtWidgets.QLabel(self.headerPanel)
        self.gridHeader.addWidget(self.valTo, 1, 1, 1, 1)
        self.labelDate = QtWidgets.QLabel(self.headerPanel)
        self.gridHeader.addWidget(self.labelDate, 3, 0, 1, 1)
        self.valDate = QtWidgets.QLabel(self.headerPanel)
        self.gridHeader.addWidget(self.valDate, 3, 1, 1, 1)

        self.verticalLayout_header.addLayout(self.gridHeader)
        self.verticalLayout_bottom.addWidget(self.headerPanel)

        self.viewer = QWebEngineView(self.widgetBottom)
        self.verticalLayout_bottom.addWidget(self.viewer)

        # 左右比例 1:2
        self.splitterRoot.setSizes([480, 960])
        self.splitterRight.setSizes([540, 320])

        self.retranslateUi(Form)
        self.tabs.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def _form_label(self, text):
        lbl = QtWidgets.QLabel(text, self.groupVersion)
        lbl.setMinimumWidth(68)
        return lbl

    def retranslateUi(self, Form):
        _ = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_("Form", "Mail UI"))

        # 顶部
        self.comboSearchField.clear()
        self.comboSearchField.addItems(
            [_("Form", "邮箱"), _("Form", "辅助邮箱"), _("Form", "辅助电话"), _("Form", "备注")]
        )
        self.editTopSearch.setPlaceholderText(_("Form", "输入搜索关键字"))
        self.btnTopSearch.setText(_("Form", "搜索"))
        self.btnRefresh.setText(_("Form", "刷新"))
        self.btnRefresh.setToolTip(_("Form", "点击后刷新页面数据"))
        self.btnServerToggle.setText(_("Form", "启动API"))
        self.btnServerToggle.setToolTip(_("Form", "点击启动/停止 FastAPI（后续）"))
        self.btnOpenIndex.setText(_("Form", "打开页面"))
        self.btnOpenIndex.setToolTip(_("Form", "在浏览器中打开 /index 页面（后续）"))

        # 分页工具条
        self.lblPageInfo.setText(_("Form", "第 1/1 页（共 0 条）"))
        self.lblPageSize.setText(_("Form", "每页"))
        self.lblGoPage.setText(_("Form", "跳转到"))
        self.btnPagePrev.setText(_("Form", "上一页"))
        self.btnPageNext.setText(_("Form", "下一页"))
        self.btnGoPage.setText(_("Form", "前往"))

        # Tab1
        self.tabs.setTabText(self.tabs.indexOf(self.tabCurrent), _("Form", "当前账号"))
        self.editTab1Query.setPlaceholderText(_("Form", "在当前文件夹内搜索"))
        self.btnTab1Search.setText(_("Form", "搜索"))
        self.btnTab1Clear.setText(_("Form", "清空"))
        self.btnTab1Compose.setText(_("Form", "发送新邮件"))

        # 账号信息
        self.groupVersion.setTitle(_("Form", "账号信息"))
        self.editPwd.setPlaceholderText(_("Form", "留空表示不修改"))
        self.editRecEmails.setPlaceholderText(_("Form", "多个邮箱用逗号或分号分隔"))
        self.editRecPhones.setPlaceholderText(_("Form", "多个电话用逗号或分号分隔"))
        self.editNote.setPlaceholderText(_("Form", "保存时的备注（建议填写）"))
        self.btnVersionSave.setText(_("Form", "保存新版本"))
        self.btnVersionReload.setText(_("Form", "刷新"))

        # Tab2
        self.tabs.setTabText(self.tabs.indexOf(self.tabSearch), _("Form", "邮件搜索"))
        self.radioAll.setText(_("Form", "全部"))
        self.radioUnread.setText(_("Form", "未读"))
        self.editSearch.setPlaceholderText(_("Form", "搜索关键字"))
        self.comboScope.clear()
        self.comboScope.addItems([_("Form", "当前文件夹"), _("Form", "所有文件夹")])
        self.chkOnlySelected.setText(_("Form", "仅选择的邮件"))
        self.btnSearchRun.setText(_("Form", "搜索"))
        self.btnSearchClear.setText(_("Form", "清空"))

        # Tab3
        self.tabs.setTabText(self.tabs.indexOf(self.tabOutbox), _("Form", "发件箱"))

        # 详情区
        self.btnReply.setText(_("Form", "回复"))
        self.btnForward.setText(_("Form", "转发"))
        self.btnOpenInBrowser.setText(_("Form", "在浏览器中查看"))
        self.lblSubject.setText(_("Form", "示例主题"))
        self.labelFrom.setText(_("Form", "发件人"))
        self.valFrom.setText(_("Form", ""))
        self.labelTo.setText(_("Form", "收件人"))
        self.valTo.setText(_("Form", ""))
        self.labelDate.setText(_("Form", "时间"))
        self.valDate.setText(_("Form", ""))
