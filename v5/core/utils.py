import random

import json

import os
import sys
import traceback
import ntplib
import logging
from curl_cffi import BrowserType
from enum import Enum, auto
from functools import wraps
from typing import Union, Tuple


log = logging.getLogger("SynthBox")


class ProxyPlatform(Enum):
    S911 = "s911"
    SIP2WORLD = "sip2world"
    STARRY = "sstarry"


def resource_path(relative_path):
    """
    获取资源的绝对路径，无论是开发环境还是打包后的环境都适用。
    """
    if hasattr(sys, "_MEIPASS"):
        # 如果是 PyInstaller 打包后的环境
        # sys._MEIPASS 指向解压后的临时文件夹的根目录
        base_path = sys._MEIPASS
    else:
        # 如果是正常的开发环境
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_icon_path(icon_name: str = None):
    """使用 resource_path 来获取图标的绝对路径"""
    if icon_name:
        return resource_path(os.path.join("icons", icon_name))
    return resource_path("icons")


def get_json_path(json_name: str = None):
    """使用 resource_path 来获取json的绝对路径"""
    if json_name:
        return resource_path(os.path.join("json", json_name))
    return resource_path("json")


def get_cert_path(cert_name: str = None):
    """使用 resource_path 来获取证书的绝对路径"""
    if cert_name:
        return resource_path(os.path.join("certs", cert_name))
    return resource_path("certs")


def get_db_path(db_name: str = None):
    """使用 resource_path 来获取数据库的绝对路径"""
    if db_name:
        return resource_path(os.path.join("db", db_name))
    return resource_path("db")


def capture_error(
    is_traceback: bool = False,
    error_value: Union[Tuple[None, False, ...], None, False] = None,
    exception: Tuple = (Exception, AssertionError, KeyboardInterrupt),
):
    def decorator(func):
        @wraps(func)
        def wrap(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
            except exception as error:
                if is_traceback:
                    traceback.print_exc()
                    log.exception(str(error))
                return error_value
            else:
                return result

        return wrap

    return decorator


class LayoutState(Enum):
    FULL = auto()
    MEDIUM = auto()
    COMPACT = auto()


def get_network_time_ntp():
    """从 NTP 服务器获取网络时间"""
    # 一个公共的NTP服务器池
    ntp_server = "pool.ntp.org"

    try:
        client = ntplib.NTPClient()
        response = client.request(ntp_server, version=3, timeout=5)
        return response.tx_time
    except Exception as e:
        print(f"从 NTP 服务器获取时间时出错: {e}")
        return None


class UserAgent:
    # with open(get_json_path("NewUserAgent.json"), "r") as f:
    with open(r"C:\Users\Administrator\Desktop\SynthBox\v4\json\NewUserAgent.json", "r") as f:
        chrome = json.load(f)
    chrome_windows = "Windows NT 10.0; Win64; x64"
    chrome_mac = "Macintosh; Intel Mac OS X 10_15_7"
    chrome_linux = "X11; Linux x86_64"
    chrome_format = "Mozilla/5.0 (%s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/%s Safari/537.36"

    def __init__(self, version: int | str = None, platform=None):
        self.platform = platform or random.choice(["windows", "mac", "linux"])
        if self.platform not in ["windows", "mac", "linux"]:
            raise ValueError("Invalid platform.")
        self.version = str(version) if version else random.choice(list(self.chrome.get(self.platform).keys()))
        self.detailed_version = random.choice(self.chrome.get(self.platform).get(str(self.version), []))
        self._user_agent = self.chrome_format % (
            self.__getattribute__(f"chrome_{self.platform}"),
            self.detailed_version,
        )

    def __str__(self):
        return self._user_agent


def sess_edition(sess, platform="windows"):
    user_agent = UserAgent(platform=platform)
    sess.headers.update({"User-Agent": str(user_agent)})
    chrome_versions = [int(i.value[6:9]) for i in BrowserType if i.value.startswith("chrome") and "_" not in i.value][
        :-1
    ]
    available_versions = [v for v in chrome_versions if v <= int(user_agent.version)]
    if available_versions:
        sess.impersonate = f"chrome{max(available_versions)}"
    else:
        sess.impersonate = f"chrome{min(chrome_versions)}"
    if sess.impersonate == "chrome133":
        sess.impersonate = "chrome133a"
    print(sess.impersonate)
    return user_agent.detailed_version
