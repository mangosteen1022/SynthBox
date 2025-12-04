import string
from enum import Enum

import json
import random
from v5.core.utils import get_json_path, ProxyPlatform
import logging

log = logging.getLogger("SynthBox")


def singleton(cls):
    """单例模式装饰器"""
    _instances = {}

    def get_instance(*args, **kwargs):
        if cls not in _instances:
            _instances[cls] = cls(*args, **kwargs)
        return _instances[cls]

    return get_instance


@singleton
class NewProxyGenerate:
    # 加载配置文件

    with open(r"C:\Users\Administrator\Desktop\SynthBox\v4\json\ProxyInfo.json", "r") as f:
        # with open(get_json_path("ProxyInfo.json"), "r") as f:
        data = json.load(f)
    # URL 格式模板
    PROXY_URL_FORMATS = {
        "s911": "us.911proxy.com:2600:{user}_area-{country}{area}_life-{timeout}_session-{session}:{password}",
        "sip2world": "93540aad5cb980f3.us.ip2world.vip:6001:{user}-zone-resi-region-{country}{area}-session-{session}-sessTime-{timeout}:{password}",
        "sstarry": "proxyus.starryproxy.com:10000:accountId-{user}-tunnelId-7051-area-{country}{area}-sessID-{session}-sessTime-{timeout}:{password}",
    }
    AllOW_COUNTRY = ["US", "CA"]

    def __init__(self):
        # 初始化数据
        self._init_proxy_data()

    def _init_proxy_data(self):
        """初始化代理数据"""
        # 911代理数据
        self.s911 = self.data["911"]
        self._process_911_data()

        # ip2world代理数据
        self.sip2world = self.data["ip2world"]
        self._process_ip2world_data()

        # starry代理数据
        self.sstarry = self.data["starry"]
        self._process_starry_data()

    def _process_911_data(self):
        """处理911代理数据"""
        # 处理城市数据
        self.s911_us_cities = self._normalize_dict(self.s911["us_city"])
        self.s911_ca_cities = self._normalize_dict(self.s911["ca_city"])
        self.s911_ca_cities.update({"quebec": "QUÉBEC"})

        # 处理州数据
        self.s911_us_states = self.s911["us_state"]
        self.s911_ca_states = self.s911["ca_state"]
        self.s911_us_full_states = self._normalize_dict(self.s911_us_states.values())
        self.s911_ca_full_states = self._normalize_dict(self.s911_ca_states.values())

    def _process_ip2world_data(self):
        """处理ip2world代理数据"""
        # 处理城市数据
        self.sip2world_us_cities = self._normalize_dict(self.sip2world["us_city"])
        self.sip2world_ca_cities = self._normalize_dict(self.sip2world["ca_city"])
        self.sip2world_ca_cities.update(
            {
                "montreal": "montréal",
                "quebec": "québec",
                "chateauguay": "châteauguay",
                "saintjerome": "saintjérôme",
                "troisrivieres": "troisrivières",
                "notredamedel'ileperrot": "notredamedel'îleperrot",
            }
        )

        # 处理州数据
        self.sip2world_us_states = self.sip2world["us_state"]
        self.sip2world_ca_states = self.sip2world["ca_state"]
        self.sip2world_us_full_states = self._normalize_dict(self.sip2world_us_states.values())
        self.sip2world_ca_full_states = self._normalize_dict(self.sip2world_ca_states.values())

    def _process_starry_data(self):
        """处理starry代理数据"""
        # 处理城市数据
        self.sstarry_us_cities = {k: self._normalize_dict(v) for k, v in self.sstarry["us_city"].items()}
        self.sstarry_ca_cities = {k: self._normalize_dict(v) for k, v in self.sstarry["ca_city"].items()}
        # 处理州数据
        self.sstarry_us_states = self.sstarry["us_state"]
        self.sstarry_ca_states = self.sstarry["ca_state"]
        self.sstarry_us_full_states = self._normalize_dict(self.sstarry_us_states.values())
        self.sstarry_ca_full_states = self._normalize_dict(self.sstarry_ca_states.values())

    @staticmethod
    def _normalize_dict(values):
        """标准化字典键值"""
        if isinstance(values, dict):
            return dict(zip([k.lower().replace(" ", "") for k in values.keys()], values.values()))
        return dict(zip([v.lower().replace(" ", "") for v in values], values))

    @staticmethod
    def _generate_sess(platform):
        key_length = 16 if platform in ["s911", "sip2world"] else random.randint(1, 6)
        return "".join(
            random.choices(
                string.digits + string.ascii_letters, k=16 if platform in ["s911", "sip2world"] else key_length
            )
        )

    @staticmethod
    def _process_country(platform, country):
        return country.upper() if platform == "s911" else country.lower()

    @staticmethod
    def _process_state_prefix(platform):
        if platform == "s911":
            return "state-"
        elif platform == "sip2world":
            return "st-"
        elif platform == "sstarry":
            return ""
        return ""

    def _process_area(self, platform, country, state, city, state_prefix):
        area = ""
        if country.upper() in self.AllOW_COUNTRY:
            cities = getattr(self, f"{platform}_{country.lower()}_cities")
            states = getattr(self, f"{platform}_{country.lower()}_states")
            full_states = getattr(self, f"{platform}_{country.lower()}_full_states")
            if platform in ["s911", "sip2world"]:
                # 确定区域
                if city and cities.get(city):
                    area = f"city-{cities[city]}"
                if state and not area:
                    if len(state) == 2 and state in states:
                        area = f"{state_prefix}{states[state]}"
                    elif state.lower() in full_states:
                        area = f"{state_prefix}{full_states[state.lower()]}"
                if not area and not city and not state:
                    area = f"{state_prefix}{random.choice(list(states.values()))}"
            elif platform in ["sstarry"]:
                if state:
                    area = f"{state_prefix}{states[state]}".lower()
                if city and cities.get(state).get(city):
                    area += f"_{cities.get(state).get(city)}".lower()
                if not area and not city and not state:
                    area = f"{state_prefix}{random.choice(list(states.values()))}".lower()
        return area

    def get(self, platform: str, username, password, country="US", state: str = None, city: str = None, timeout=15):
        """
        获取代理URL
        :param platform: 代理平台 (ProxyPlatform.S911 或 ProxyPlatform.IP2WORLD)
        :param username: 用户名
        :param password: 密码
        :param country: 国家代码 (US or CA or more)
        :param state: 州
        :param city: 城市
        :param timeout: 超时时间
        :return: 代理URL或None
        """
        # 参数验证
        if not username or not password:
            print(...)
            return None

        if platform == "sstarry" and city and not state:
            raise ValueError("starry代理城市必须同时指定州")
        city = city.lower().replace(" ", "") if city else None
        state = state.upper().replace(" ", "") if state else None
        if platform == "sstarry":
            city = city.replace("-", "") if city else None
            state = state.replace("-", "") if state else None
        states = getattr(self, f"{platform}_{country.lower()}_states")
        if not state:
            state = random.choice(list(states.keys()))
        # 生成会话ID
        session = self._generate_sess(platform)

        # 基本代理信息
        proxy = {"user": username, "password": password, "session": session}

        # 处理国家代码格式
        country = self._process_country(platform, country)
        state_prefix = self._process_state_prefix(platform)

        # 获取相应的数据集
        area = self._process_area(platform, country, state, city, state_prefix)

        # 生成代理URL
        if area:
            area = ("_" if platform in ["s911", "sstarry"] else "-") + area
        proxy.update({"country": country, "area": area, "timeout": timeout})
        return self.PROXY_URL_FORMATS[platform].format(**proxy)


if __name__ == "__main__":

    proxy_gen = NewProxyGenerate()
    for _ in range(1):
        # print(
        #     proxy_gen.get(
        #         ProxyPlatform.S911, "pro-wubowei", "885412wwsa", state="BC", city="Barrie", country="CA", timeout=60
        #     )
        # )
        print(proxy_gen.get(ProxyPlatform.STARRY, "4526", "EARfjz", country="us", state="oh", city="", timeout=60))
