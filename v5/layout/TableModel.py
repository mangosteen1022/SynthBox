from PyQt5 import QtCore


class TableModel(QtCore.QAbstractTableModel):
    """一个通用的、基于列表数据的表格模型（支持局部更新）"""

    def __init__(self, data, headers, parent=None):
        super().__init__(parent)
        self._data = data[:] if data else []
        self._headers = headers[:] if headers else []
        # 如果第一列是“序号”，初始化时也重算
        if self._headers and self._headers[0] == "序号":
            self.recalc_serial(0)

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self._headers)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or role != QtCore.Qt.DisplayRole:
            return None
        try:
            return str(self._data[index.row()][index.column()])
        except Exception:
            return ""

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            try:
                return self._headers[section]
            except Exception:
                return None
        return None

    # 注意：方法名沿用你原来的“全量替换”，不是 Qt 的 setData 语义
    def setData(self, data, headers):
        """完全更新模型数据与表头"""
        self.beginResetModel()
        self._data = data[:] if data else []
        self._headers = headers[:] if headers else []
        # 自动重算“序号”
        if self._headers and self._headers[0] == "序号":
            self.recalc_serial(0, emit_signal=False)
        self.endResetModel()

    # 新增：单元格局部更新
    def update_cell(self, row: int, col: int, value) -> bool:
        if row < 0 or row >= len(self._data):
            return False
        if col < 0 or col >= len(self._headers):
            return False
        try:
            self._data[row][col] = value
        except Exception:
            return False
        top_left = self.index(row, col)
        self.dataChanged.emit(top_left, top_left, [QtCore.Qt.DisplayRole])
        return True

    # 新增：整行更新（values 长度小于列数时按实际长度更新）
    def update_row(self, row: int, values) -> bool:
        if row < 0 or row >= len(self._data):
            return False
        if not isinstance(values, (list, tuple)):
            return False
        try:
            for c in range(min(len(values), len(self._headers))):
                self._data[row][c] = values[c]
        except Exception:
            return False
        left = self.index(row, 0)
        right = self.index(row, len(self._headers) - 1)
        self.dataChanged.emit(left, right, [QtCore.Qt.DisplayRole])
        return True

    # 新增：追加多行
    def append_rows(self, rows):
        if not rows:
            return
        start = len(self._data)
        end = start + len(rows) - 1
        self.beginInsertRows(QtCore.QModelIndex(), start, end)
        self._data.extend(rows)
        self.endInsertRows()
        # 自动重算“序号”
        if self._headers and self._headers[0] == "序号":
            self.recalc_serial(start)

    # 新增：删除行
    def remove_rows(self, row: int, count: int = 1):
        if row < 0 or count <= 0:
            return
        last = min(row + count - 1, len(self._data) - 1)
        if last < row:
            return
        self.beginRemoveRows(QtCore.QModelIndex(), row, last)
        del self._data[row : last + 1]
        self.endRemoveRows()
        # 自动重算“序号”
        if self._headers and self._headers[0] == "序号":
            self.recalc_serial(row)

    # 新增：重算“序号”列（仅当首列为“序号”时有效）
    def recalc_serial(self, start_row: int = 0, emit_signal: bool = True):
        if not self._headers or self._headers[0] != "序号":
            return
        n = len(self._data)
        if n == 0:
            return
        start_row = max(0, min(start_row, n - 1))
        for i in range(start_row, n):
            # 保障每行至少有一列
            if not self._data[i]:
                self._data[i] = [i + 1]
            else:
                self._data[i][0] = i + 1
        if emit_signal:
            top_left = self.index(start_row, 0)
            bottom_right = self.index(n - 1, 0)
            self.dataChanged.emit(top_left, bottom_right, [QtCore.Qt.DisplayRole])
