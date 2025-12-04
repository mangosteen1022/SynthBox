import time
from PyQt5 import QtCore
from curl_cffi import requests
from v5.core.utils import capture_error
import logging

log = logging.getLogger("SynthBox")


class ReadEmail:

    def __init__(self, username, password):
        self.bearer_token_expire = None
        self.bearer_token = None
        self.username = username
        self.password = password

    @capture_error()
    def login(self):
        url = "http://49.51.41.157:8000/login"
        json_data = {"username": self.username, "password": self.password}
        res = requests.post(url, json=json_data)
        if res.status_code == 200:
            self.bearer_token = res.json()["access_token"]
            self.bearer_token_expire = time.time()
            return True
        else:
            return False

    def get_email_by_subject_and_recipient(self, subject, to):
        url = "http://49.51.41.157:8000/email"
        params = {"subject": subject, "to": to}
        try:
            res = requests.get(url, params=params, headers={"Authorization": f"Bearer {self.bearer_token}"}, timeout=5)
        except Exception as e:
            print(e)
            return None
        if res.status_code == 200:
            if not res.json() or not res.json().get("metadata"):
                return None
            if isinstance(res.json(), dict):
                raw_data = res.json()["metadata"].get("raw_data")
                if not raw_data:
                    return None
                return raw_data
        elif res.status_code == 401:
            try:
                if res.json().get("detail") in ["Token has expired", "Could not validate credentials"]:
                    self.login()
                    return self.get_email_by_subject_and_recipient(subject, to)
            except Exception as e:
                print(e)
            return None
        return None

    def get_email_message(self, subject, to):
        if not self.bearer_token or time.time() - self.bearer_token_expire > 12000:
            if not self.login():
                return "登录失败"
        subject = subject.strip()
        to = to.strip().lower()
        if to.startswith("mailto:"):
            to = to.replace("mailto:", "").strip()
        if not subject or not to:
            return "请先输入主题和收件人"
        raw_data = self.get_email_by_subject_and_recipient(subject, to)
        if not raw_data:
            return "未找到邮件"
        return raw_data

    @staticmethod
    @capture_error(is_traceback=True)
    def get_all_subjects():
        """获取全部需要拦截的邮件主题"""
        url = "http://49.51.41.157:8000/eligible_subject/"
        res = requests.get(url, timeout=2)
        if res.status_code == 200:
            if subjects := res.json().get("subjects"):
                return subjects
        return None


class GetMailContent(QtCore.QObject):
    finished = QtCore.pyqtSignal(str)

    def __init__(self, client, subject, _to, parent=None):
        super().__init__()
        self.client = client
        self.subject = subject
        self.to = _to

    def get_email_message(self):
        return self.client.get_email_message(self.subject, self.to)

    @QtCore.pyqtSlot()  # 明确这是一个槽函数
    def run(self):
        """执行耗时任务并发送结果信号"""
        try:
            msg = self.get_email_message()
            self.finished.emit(str(msg))

        except Exception as e:
            log.exception(f"读取邮件时发生错误: {e}")
            self.finished.emit(str(e))
