import asyncio
import errno
import socket
import threading
from multiprocessing import Process, Queue

from PyQt5 import QtCore
from _queue import Empty
from curl_cffi import requests
from mitmproxy import http
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from v5.core.ProxyGenerate import ProxyPlatform, NewProxyGenerate
from .async_cache_backend import FileCacheBackend
from .base_addon import BaseAddon
from v5.core.utils import get_cert_path
import logging

log = logging.getLogger("SynthBox")
cache_client = FileCacheBackend()
proxy_generate = None
THREAD_LOCK = threading.Lock()


class TabStatus:
    class Starting:
        color: str = "#2bd4f9"
        show: str = "启动中"

    class Running:
        color: str = "#28a745"
        show: str = "运行中"

    class Stopping:
        color: str = "#2bd4f9"
        show: str = "停止中"

    class Stopped:
        color: str = "#dc3545"
        show: str = "已停止"

    class Error:
        color: str = "#f92b3b"
        show: str = "运行错误"

    class Delete:
        color: str = "#a8abad"
        show: str = "删除中"


class MitmproxySignals(QtCore.QObject):
    notification = QtCore.pyqtSignal(str, str)
    log_message = QtCore.pyqtSignal(str)
    instance_ip = QtCore.pyqtSignal(int, str)
    status_changed = QtCore.pyqtSignal(int, str)
    traffic_update = QtCore.pyqtSignal(int, dict)


class MitmproxyAddon(BaseAddon):
    def __init__(self, port: int, pc, msg):
        super().__init__()
        self.port = port
        self.msg = msg
        self.proxy_host = pc["proxy_host"]
        self.proxy_port = pc["proxy_port"]
        self.proxy_user = pc["proxy_user"]
        self.proxy_pass = pc["proxy_pass"]
        self.proxy_scheme = pc["scheme"]
        self.ticker_task: asyncio.Task | None = None

    async def responseheaders(self, flow: http.HTTPFlow):
        if flow.metadata.get("cffi_response"):
            await self.curl_response(flow)

    async def request(self, flow: http.HTTPFlow):
        print(flow.request.pretty_url)
        await self.find_and_deserialize_response(flow)

    async def response(self, flow: http.HTTPFlow):
        if flow.metadata.get("cffi_response"):
            datas = self.extract_object(flow)
            asyncio.create_task(self.make_serialize_response(datas))

    def running(self):
        """当代理完全启动并运行时被调用。"""
        self.ticker_task = asyncio.create_task(self.ticker())
        self.msg.put({"status_changed": (self.port, TabStatus.Running.show)})

    async def error(self, flow):
        """当发生错误时被调用。"""
        error_message = str(flow.error)
        log.error(f"[{self.port}]{error_message}")
        if cffi_response := flow.metadata.get("cffi_response"):
            cffi_response.close()

    def done(self):
        if self.ticker_task:
            self.ticker_task.cancel()
        self.msg.put({"status_changed": (self.port, TabStatus.Stopped.show)})

    async def ticker(self):
        """流量监控"""
        try:
            while True:
                await asyncio.sleep(1.0)
                async with self._lock:
                    if self.upload_bytes > 0 or not self.stats_queue.empty():
                        self.download_bytes = await self.get_download_bytes()
                        data_to_emit = {
                            "up": (self.upload_bytes, self.upload_save_bytes),
                            "down": (self.download_bytes, self.download_save_bytes),
                        }
                        self.msg.put({"traffic_update": (self.port, data_to_emit)})
                    self.upload_bytes = 0
                    self.download_bytes = 0
                    self.upload_save_bytes = 0
                    self.download_save_bytes = 0
        except asyncio.CancelledError:
            log.info(f"[{self.port}] Ticker task has been cancelled gracefully.")
        except Exception as e:
            log.info(f"[{self.port}] Ticker task encountered an error: {e}")


def process_mitmproxy_process(proxy_config: dict, send: Queue, receive: Queue):
    opts = Options()
    config_dir = get_cert_path()
    opts.confdir = config_dir
    opts.listen_host = proxy_config["listen_host"]
    opts.listen_port = proxy_config["listen_port"]
    opts.ssl_insecure = True
    opts.http2 = True

    loop = asyncio.new_event_loop()
    master = DumpMaster(options=opts, with_dumper=False, with_termlog=False, loop=loop)
    addon_instance = MitmproxyAddon(proxy_config["listen_port"], proxy_config, send)
    master.addons.add(addon_instance)

    async def main_loop():
        shutdown_task = asyncio.create_task(check_shutdown_signal(receive))
        await master.run()
        shutdown_task.cancel()

    async def check_shutdown_signal(queue: Queue):
        """在后台异步检查队列，直到收到 'shutdown' 信号。"""
        while True:
            try:
                if not queue.empty():
                    signal = queue.get_nowait()
                    if signal == "shutdown":
                        master.shutdown()
                        break
                    else:
                        pass
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                break

    asyncio.run(main_loop())


class MitmproxyWorker(QtCore.QThread):
    must_proxy_params = {"listen_host", "listen_port"}

    def __init__(self, proxy_config: dict, signals: MitmproxySignals, parent=None):
        super().__init__(parent)
        self.message_queue = Queue()
        self.receive_queue = Queue()
        self.pc = proxy_config
        self.signals: MitmproxySignals = signals
        self.ip_address: str | None = None
        self.process = None
        self.__is_running = True

    def _check_public_ip(self):
        self.signals.log_message.emit(f"端口 {self.pc['listen_host']}: 正在检测网络出口IP...")
        proxy = None
        if self.pc["scheme"] and self.pc["proxy_host"] and self.pc["proxy_port"]:
            scheme = self.pc["scheme"]
            if scheme == "socks5":
                scheme = "socks5h"
            proxy = f"{scheme}://"
            if self.pc["proxy_user"] and self.pc["proxy_pass"]:
                proxy += f"{self.pc['proxy_user']}:{self.pc['proxy_pass']}@"
            proxy += f"{self.pc['proxy_host']}:{self.pc['proxy_port']}"
        try:
            response = requests.get("https://api.ipify.org", proxies={"all": proxy}, verify=False)
            self.ip_address = response.text
        except Exception as e:
            error_msg = f"IP检测失败: {str(e)[:50]}..."
            log.exception(error_msg)
            self.signals.instance_ip.emit(self.pc["listen_host"], error_msg)
            self.signals.log_message.emit(f"端口 {self.pc['listen_host']}: {error_msg}")

    def run(self):
        try:
            if not self.must_proxy_params.issubset(set(self.pc.keys())):
                self.signals.instance_ip.emit(self.pc["listen_port"], "检测失败")
                self.signals.status_changed.emit(self.pc["listen_port"], TabStatus.Error.show)
                return
            self._check_public_ip()
            if not self.ip_address:
                self.signals.instance_ip.emit(self.pc["listen_port"], "检测失败")
                self.signals.status_changed.emit(self.pc["listen_port"], TabStatus.Error.show)
                return
            self.signals.instance_ip.emit(self.pc["listen_port"], self.ip_address)
            self.process = Process(
                target=process_mitmproxy_process, args=(self.pc, self.message_queue, self.receive_queue), daemon=False
            )
            self.process.start()
            while self.__is_running:
                try:
                    message = self.message_queue.get(timeout=1)
                    if message.get("status_changed"):
                        _port, _msg = message["status_changed"]
                        self.signals.status_changed.emit(*message["status_changed"])
                        if _msg == TabStatus.Stopped.show:
                            break
                    elif message.get("traffic_update"):  # 流量统计
                        _port, _msg = message["traffic_update"]
                        self.signals.traffic_update.emit(*message["traffic_update"])
                    elif message.get("log_message"):  # 消息通知
                        self.signals.log_message.emit(message["log_message"])

                    elif message.get("notification"):  # 弹窗提醒
                        self.signals.notification.emit(*message["notification"])

                except (Exception, KeyboardInterrupt, Empty) as e:
                    pass
        except Exception as e:
            error_msg = f"MitmproxyWorker 线程发生致命错误: {e}"
            log.exception(error_msg)
            self.signals.log_message.emit(f"端口 {self.pc['listen_port']}: {error_msg}")
            self.signals.status_changed.emit(self.pc["listen_port"], TabStatus.Error.show)
        finally:
            self.signals.status_changed.emit(self.pc["listen_port"], TabStatus.Stopped.show)

    def stop(self):
        """请求停止代理服务。"""
        self.__is_running = False
        try:
            self.receive_queue.put("shutdown")
            self.process.join(timeout=1)
        except Exception as e:
            log.exception(f"发送关闭命令时出错: {e}")
        try:
            if self.process and self.process.is_alive():
                self.process.terminate()
                self.process.join(1)
        except Exception as e:
            log.exception(f"发送关闭命令时出错1: {e}")


class NetworkIpWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(str)

    @staticmethod
    def _get_network_ip():
        try:
            res = requests.get(
                "http://ip-api.com/json/?fields=query",
                timeout=5,
            )
            if res.status_code == 200:
                return res.json()["query"]
        except Exception as e:
            pass
        return "网络不可用"

    @QtCore.pyqtSlot()  # 明确这是一个槽函数
    def run(self):
        """执行耗时任务并发送结果信号"""
        ip_address = self._get_network_ip()
        self.finished.emit(ip_address)


class ClearCache(QtCore.QObject):
    finished = QtCore.pyqtSignal(str)

    @staticmethod
    async def clear_cache():
        return await cache_client.clear_timeout_cache()

    @QtCore.pyqtSlot()  # 明确这是一个槽函数
    def run(self):
        """执行耗时任务并发送结果信号"""
        try:
            msg = asyncio.run(self.clear_cache())
            self.finished.emit(str(msg))

        except Exception as e:
            log.exception(f"清理缓存时发生错误: {e}")
            self.finished.emit(str(e))


def check_port_using(port: int, host: str = "0.0.0.0"):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
    except socket.error as e:
        if e.errno == errno.EADDRINUSE:
            return True
        return True
    finally:
        s.close()

    return False


def get_socket_hostname():
    default_hostname = ["127.0.0.1", "0.0.0.0"]
    hostname = socket.gethostname()
    # 获取所有IPv4地址
    local_ips = [ip for ip in socket.gethostbyname_ex(hostname)[2] if ":" not in ip]  # 简单过滤IPv6
    if not local_ips:
        return default_hostname
    return default_hostname + local_ips


def format_proxy(proxy: str = None):
    """格式化代理"""
    if not proxy:
        return (None,) * 4
    host, port, username, password = (None,) * 4
    ps = proxy.split(":")
    if len(ps) == 4 and ps[2] and ps[3]:
        host, port, username, password = ps
    elif len(ps) == 2:
        host, port = ps
    if port and port.isdigit() and host:
        return host, int(port), username, password
    return (None,) * 4


def split_state_city(state_city: str):
    state, city = "", ""
    for _ in ["|", ",", "\t", "----"]:
        if _ in state_city:
            state_city = state_city.split(_)
            if len(state_city[0]) == 2:
                state, city = state_city[0], state_city[1]
            else:
                state, city = state_city[1], state_city[0]
            break
    else:
        if len(state_city) == 2:
            state, city = state_city, ""
    return state, city


def generate_proxy(platform, username, password, country, state="", city="", timeout=10):
    global proxy_generate
    if not proxy_generate:
        proxy_generate = NewProxyGenerate()
    try:
        return proxy_generate.get(
            ProxyPlatform(platform), username, password, country=country, state=state, city=city, timeout=timeout
        )
    except (Exception,) as e:
        log.exception(str(e))
        return None


units = ["b", "kb", "mb", "gb", "tb", "pb", "eb", "zb", "bb"]


def traffic_conversion(flow: float, unit="b"):
    if flow >= 1024:
        return traffic_conversion(flow / 1024, unit=units[units.index(unit) + 1])
    return f"{flow:.2f}{unit}"
