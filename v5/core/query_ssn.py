import copy

from PyQt5 import QtCore
from curl_cffi import requests
import logging
from queue import Queue
log = logging.getLogger("SynthBox")
labels = ["firstname", "middle_name", "lastname", "ssn", "birthday", "street", "city", "state", "zip",
          "email", "phone", "other1", "other2", "other3"]

def perform_query(info):
    """执行单次查询并返回结果"""
    first_name, last_name, street, state, zip_code = info
    url = "http://ssn.iclemail.com/get/fcssn2.php"
    params = {"fname": first_name, "lname": last_name, "st": state, "address": street, "zip": zip_code}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        res.raise_for_status()  # 检查HTTP错误
        result = res.json()
        data = result.get("data")
        if data:
            details = [dict(zip(result['fields'], d)) for d in data]
            return details
    except Exception as e:
        return "查询失败"
    return None

class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(str, object)

class QuerySSN(QtCore.QRunnable):
    def __init__(self, org_addr, info):
        super().__init__()
        self.signals = WorkerSignals()  # 实例化信号类
        self.org_addr = org_addr
        self.info = info

    @QtCore.pyqtSlot()  # 明确这是一个槽函数
    def run(self):
        msg = perform_query(self.info)
        if isinstance(msg, str) or isinstance(msg, list):
            self.signals.finished.emit(self.org_addr, msg)
        else:
            self.signals.finished.emit(self.org_addr, [])



class QueryWorker(QtCore.QRunnable):
    fields = ["firstname", "lastname", "street", "state", "zip"]
    def __init__(self, file_details):
        super().__init__()
        self.file_details = file_details
        self.org_addr = None
        self.info = None
        self.signals = WorkerSignals() # 实例化信号类

    @QtCore.pyqtSlot()
    def run(self):
        """执行耗时任务"""
        addr = self.file_details.get()
        _addr = [addr.get(_, "") for _ in self.fields]
        self.org_addr = ",".join(_addr)
        self.info = _addr
        msg = perform_query(self.info)
        if isinstance(msg, str):
            self.signals.finished.emit(self.org_addr, msg)
            self.file_details.put(addr)
        elif isinstance(msg, list):
            self.signals.finished.emit(self.org_addr, msg)
        else:
            self.signals.finished.emit(self.org_addr, [])

def validate_and_format_zip(zip_code_str):
    if not isinstance(zip_code_str, str):
        return None
    cleaned_zip = zip_code_str.strip()
    digits_only = cleaned_zip.replace('-', '')
    if not digits_only.isdigit():
        return None
    length = len(digits_only)
    if length == 5:
        return digits_only
    elif length == 4:
        return digits_only.zfill(5)
    elif length == 9:
        return f"{digits_only[:5]}-{digits_only[5:]}"
    else:
        return None

def format_details(file_name, config):
    process_details = Queue()
    with open(file_name, "r", encoding="utf-8", errors="ignore") as file:
        details = file.readlines()
    separator = config.get("delimiter")
    separators = ["\t", "|", "----", " ", ","]
    if separator == "tab":
        separator = "\t"
    if separator in separators:
        del separators[separators.index(separator)]
    label_list = []
    for label in labels:
        if value := config.get(label):
            label_list.append([label, value])
    label_list.sort(key=lambda x: int(x[1]) if ":" not in x[1] else int(x[1].split(":")[0]))
    for li, v in enumerate(label_list):
        value = v[1].split(":")
        if len(value) == 1:
            label_list[li] = [v[0], str(int(value[0]) - 1)]
        else:
            label_list[li] = [
                v[0],
                f"{int(value[0]) - 1 if value[0] else 0}:{value[1]}",
            ]
    data = {}
    for detail in details:
        detail = detail.replace("\n", "").strip()
        detail = detail.split(separator)
        data.clear()
        if detail != [""] and len(detail) >= len(set(map(lambda x: x[1], label_list))):
            resolved = []
            for label in label_list:
                if label[0] in resolved:
                    continue
                repeat = []
                for l2 in label_list:
                    if l2[0] != label[0]:
                        if label[1] == l2[1]:
                            repeat.append(l2[0])
                            resolved.append(l2[0])
                if repeat:
                    for sep in separators:
                        if sep in detail[int(label[1])]:
                            if "first_name" in repeat or "last_name" in repeat:
                                val = detail[int(label[1])].split(sep)
                                data[label[0]] = val[0]
                                data[repeat[0]] = val[-1]
                            else:
                                val = detail[int(label[1])].split(sep, maxsplit=len(repeat))
                                data[label[0]] = val[0]
                                for ri, rv in enumerate(repeat):
                                    data[rv] = val[ri + 1]
                else:
                    value = label[1].split(":")
                    try:
                        if len(value) == 1:
                            data[label[0]] = detail[int(value[0])].strip() if detail[int(value[0])] else ""
                        else:
                            data[label[0]] = detail[
                                             int(value[0]) if value[0] else 0: (
                                                 int(value[1]) if value[1] else len(detail))
                                             ]
                    except (IndexError,):
                        pass

            if data.get("ssn", None):
                data["ssn"] = (
                    data["ssn"].strip()
                    if len(data["ssn"].strip()) == 9
                    else (9 - len(data["ssn"].strip())) * "0" + data["ssn"].strip()
                )
            if data.get("zip", None):
                data["zip"] = validate_and_format_zip(data["zip"])
            process_details.put(copy.deepcopy(data))
        else:
            print(f"错误格式: {separator.join(detail)}")
    return process_details