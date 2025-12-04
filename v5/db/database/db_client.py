import os
from diskcache import Cache
from v5.core.utils import get_db_path


class AppDatabase:
    _instances = {}
    _base_path = None

    def __new__(cls, *args, **kwargs):
        # 保持单例模式
        if not hasattr(cls, "instance"):
            cls.instance = super(AppDatabase, cls).__new__(cls)
        return cls.instance

    def __init__(self, base_path=None):
        if self._base_path is None:
            if base_path is None:
                self._base_path = get_db_path("database")
            else:
                self._base_path = base_path
            os.makedirs(self._base_path, exist_ok=True)

    def get_db(self, db_name: str) -> Cache:
        """
        根据名称获取一个独立的数据库实例。
        如果实例不存在，则创建它。
        """
        if db_name not in self._instances:
            db_path = os.path.join(self._base_path, db_name)
            self._instances[db_name] = Cache(db_path)

        return self._instances[db_name]

    def close_all(self):
        """关闭所有已打开的数据库连接。"""
        for db_name, cache_instance in self._instances.items():
            cache_instance.close()
        self._instances.clear()


# 创建一个全局实例，方便在任何地方导入和使用
db_client = AppDatabase()
