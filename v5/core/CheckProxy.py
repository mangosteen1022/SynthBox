import time

import requests

from v5.core.utils import capture_error
from v5.core.ProxyGenerate import ProxyPlatform, NewProxyGenerate


class CheckProxy:
    def __init__(self, local_ip, pia_api=None, ip_queue=None):
        self.region = None
        self.timezone = None
        self.query = None
        self.ip_city = None
        self.local_ip = local_ip
        self.pia_api = pia_api
        self.ip_queue = ip_queue
        self.ip = self.ip_queue.get().split(":")
        self.fmt_ip = self.fmt_proxy()

    def extract_ip(self):
        if self.pia_api and self.local_ip:
            url = f"http://{self.local_ip}:{self.pia_api}/api/get_ip_list?num=1&country=US&state=all&city=all&zip=all&isp=all&ip_time=1&t=2&port={self.ip[1]}"
            doc = requests.get(url)
            if doc.status_code == 200 and doc.json():
                print(doc.json())
                return True
        else:
            if not self.ip_queue.empty():
                self.ip = self.ip_queue.get().split(":")
                self.fmt_ip = self.fmt_proxy()
                return True
            else:
                self.ip, self.fmt_ip = None, None
                return

    @capture_error(is_traceback=False)
    def fmt_proxy(self):
        if len(self.ip) == 2:
            return f"socks5://{':'.join(self.ip)}"
        else:
            return f"socks5://{'@'.join([':'.join(self.ip[2:]), ':'.join(self.ip[:2])])}"

    @capture_error(is_traceback=False)
    def ip_timezone_info(self):
        res = requests.get(
            "http://ip-api.com/json/?fields=61439",
            proxies={"http": self.fmt_ip, "https": self.fmt_ip},
            timeout=10,
        )
        if res.status_code == 200:
            self.query = res.json()["query"]
            self.timezone = res.json()["timezone"]
            self.region = res.json()["region"]
            self.ip_city = res.json()["city"]
            return True

    def check(self, is_extract=None):
        if is_extract:
            while not self.extract_ip():
                if self.ip_queue.empty():
                    return self.ip, self.fmt_ip, self.query, self.timezone, self.region, self.ip_city
                time.sleep(3)
        ip_timezone_info_count = 0
        while self.ip_timezone_info() is None:
            if ip_timezone_info_count > 2:
                return self.check(is_extract=True)
            ip_timezone_info_count += 1
            time.sleep(2)
        return self.ip, self.fmt_ip, self.query, self.timezone, self.region, self.ip_city

    def format(self):
        return self.ip, self.fmt_ip, self.query, self.timezone, self.region, self.ip_city


class CheckProxyByProxyGenerate:
    proxy_generate = NewProxyGenerate()

    def __init__(self, platform: str, username, password, country="US", state: str = None, city: str = None, timeout=5):
        self.region = None
        self.timezone = None
        self.query = None
        self.ip_city = None
        self.fmt_ip = None
        self.ip = None
        self.platform = platform
        self.username = username
        self.password = password
        self.country = country
        self.state = state
        self.city = city
        self.timeout = timeout

    @capture_error(is_traceback=True)
    def fmt_proxy(self):
        self.ip = self.proxy_generate.get(
            platform=self.platform,
            username=self.username,
            password=self.password,
            country=self.country,
            state=self.state,
            city=self.city,
            timeout=self.timeout,
        )
        if self.ip:
            self.ip = self.ip.split(":")
        else:
            return
        if len(self.ip) == 2:
            return f"socks5://{':'.join(self.ip)}"
        else:
            return f"socks5://{'@'.join([':'.join(self.ip[2:]), ':'.join(self.ip[:2])])}"

    @capture_error(is_traceback=True)
    def check(self):
        while not self._check():
            time.sleep(3)
        return self.ip, self.fmt_ip, self.query, self.timezone, self.region, self.ip_city

    @capture_error(is_traceback=True)
    def _check(self):
        self.fmt_ip = self.fmt_proxy()
        if not self.fmt_ip:
            print(1)
            return None
        res = requests.get(
            "http://ip-api.com/json/?fields=61439",
            proxies={"http": self.fmt_ip, "https": self.fmt_ip},
            timeout=10,
        )
        if res.status_code == 200:
            self.query = res.json()["query"]
            self.timezone = res.json()["timezone"]
            self.region = res.json()["region"]
            self.ip_city = res.json()["city"]
            return True

    def format(self):
        self.fmt_ip = self.fmt_proxy()
        if not self.fmt_ip:
            return None, None, None, None, None, None
        return self.ip, self.fmt_ip, self.query, self.timezone, self.region, self.ip_city


if __name__ == "__main__":
    print(
        CheckProxyByProxyGenerate(
            ProxyPlatform.STARRY, username="4526", password="EARfjz", country="US", state="ca"
        ).format()
    )
