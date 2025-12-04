"""时间戳辅助工具（统一使用UTC ISO格式）"""

from datetime import datetime, timezone, timedelta


class DateTimeHelper:
    """时间戳辅助工具（统一使用UTC ISO格式）"""

    @staticmethod
    def now() -> str:
        """
        返回当前UTC时间
        格式：YYYY-MM-DDTHH:MM:SSZ
        """
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def days_ago(days: int) -> str:
        """返回N天前的UTC时间"""
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def hours_ago(hours: int) -> str:
        """返回N小时前的UTC时间"""
        dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def parse(timestamp_str: str) -> datetime:
        """解析时间戳字符串"""
        if not timestamp_str:
            return None

        # 处理可能的格式
        if timestamp_str.endswith("Z"):
            # 标准格式
            try:
                # 先尝试不带微秒
                return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except:
                # 再尝试带微秒
                timestamp_str = timestamp_str[:-1]  # 去掉Z
                if "." in timestamp_str:
                    # 截断微秒到6位
                    parts = timestamp_str.split(".")
                    timestamp_str = f"{parts[0]}.{parts[1][:6]}"
                return datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
        else:
            # 非标准格式，尝试解析
            return datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)

    @staticmethod
    def format(dt: datetime) -> str:
        """格式化datetime对象为标准格式"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def is_valid_format(timestamp_str: str) -> bool:
        """检查时间戳格式是否正确"""
        import re

        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        return bool(re.match(pattern, timestamp_str))

    @staticmethod
    def ensure_format(timestamp_str: str) -> str:
        """确保时间戳格式正确"""
        if not timestamp_str:
            return None

        # 如果已经是正确格式，直接返回
        if DateTimeHelper.is_valid_format(timestamp_str):
            return timestamp_str

        # 否则尝试解析并重新格式化
        dt = DateTimeHelper.parse(timestamp_str)
        if dt:
            return DateTimeHelper.format(dt)
        return None
