from PyQt5.QtCore import QObject, QSettings


class ConfigManager(QObject):
    # 如果需要，也可以在这里定义信号，比如当配置变化时
    # setting_changed = pyqtSignal(str, object)

    def __init__(self):
        super().__init__()
        # 使用 QSettings 来持久化存储配置
        self.settings = QSettings("SynthBox", "setting")

    def get(self, key, default_value=None):
        return self.settings.value(key, default_value)

    def set(self, key, value):
        self.settings.setValue(key, value)
        # self.setting_changed.emit(key, value) # 发射信号通知其他组件


# 创建一个全局唯一的配置管理器实例
config_manager = ConfigManager()
