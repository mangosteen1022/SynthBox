"""对话框组件"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDateEdit, QDialogButtonBox
from PyQt5.QtCore import QDate


class DateRangeDialog(QDialog):
    """时间范围选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择时间范围")
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 开始时间
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("开始日期:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-1))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        start_layout.addWidget(self.start_date)
        layout.addLayout(start_layout)

        # 结束时间
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("结束日期:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        end_layout.addWidget(self.end_date)
        layout.addLayout(end_layout)

        # 快捷按钮
        shortcuts_layout = QHBoxLayout()
        shortcuts_layout.addWidget(QLabel("快捷选择:"))

        btn_today = QPushButton("今天")
        btn_today.clicked.connect(self.select_today)
        shortcuts_layout.addWidget(btn_today)

        btn_week = QPushButton("本周")
        btn_week.clicked.connect(self.select_this_week)
        shortcuts_layout.addWidget(btn_week)

        btn_month = QPushButton("本月")
        btn_month.clicked.connect(self.select_this_month)
        shortcuts_layout.addWidget(btn_month)

        btn_year = QPushButton("今年")
        btn_year.clicked.connect(self.select_this_year)
        shortcuts_layout.addWidget(btn_year)

        layout.addLayout(shortcuts_layout)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def select_today(self):
        """选择今天"""
        today = QDate.currentDate()
        self.start_date.setDate(today)
        self.end_date.setDate(today)

    def select_this_week(self):
        """选择本周"""
        today = QDate.currentDate()
        monday = today.addDays(1 - today.dayOfWeek())
        self.start_date.setDate(monday)
        self.end_date.setDate(today)

    def select_this_month(self):
        """选择本月"""
        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)
        self.start_date.setDate(first_day)
        self.end_date.setDate(today)

    def select_this_year(self):
        """选择今年"""
        today = QDate.currentDate()
        first_day = QDate(today.year(), 1, 1)
        self.start_date.setDate(first_day)
        self.end_date.setDate(today)

    def get_date_range(self):
        """获取选择的时间范围（返回UTC格式）"""
        start = self.start_date.date().toString("yyyy-MM-dd") + "T00:00:00Z"
        end_date = self.end_date.date().addDays(1)
        end = end_date.toString("yyyy-MM-dd") + "T00:00:00Z"
        return start, end
