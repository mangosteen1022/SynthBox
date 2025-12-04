import asyncio
import json
import time

import jmespath
from bs4 import BeautifulSoup
from curl_cffi import AsyncSession, CurlError, Session, requests
from curl_cffi.requests.exceptions import RequestException, Timeout
from lxml import html
from mitmproxy import http
import logging
import re
from .formatter import formatter

log = logging.getLogger("SynthBox")
from .utils import (
    get_curl_impersonate,
    get_all_curl_impersonate,
    get_origin_content_length,
    SAFE_HEADERS_TO_CACHE,
    RESOURCE_SUFFIX,
    RESOURCE_CONTENT_TYPES,
    normalized_url,
    FORBIDDEN_DIRECTIVES,
)
from v4.core.utils import capture_error

from .async_cache_backend import FileCacheBackend
from v4.core.config import config_manager

cache_client = FileCacheBackend()
# --- Configuration ---
RETRY_LIMIT = 3
RETRY_DELAY = 5


class BaseAddon:
    all_curl_impersonate = get_all_curl_impersonate()

    def __init__(self):
        self.msg = None
        self.sessions = {}
        self.proxy_host = None
        self.proxy_port = None
        self.proxy_user = None
        self.proxy_pass = None
        self.proxy_scheme = None
        self.upload_bytes = 0
        self.download_bytes = 0
        self.upload_save_bytes = 0
        self.download_save_bytes = 0
        self._lock = asyncio.Lock()
        self.stats_queue = asyncio.Queue()
        self.writing_in_progress = set()
        self.EXTRACTORS = {
            "re:": self.curl_response_extract_re,
            "xpath:": self.curl_response_extract_xpath,
            "bs4:": self.curl_response_extract_bs4,
            "json:": self.curl_response_extract_json,
        }

    @capture_error(is_traceback=True)
    def create_session(self, flow: http.HTTPFlow) -> AsyncSession | None:
        ua = flow.request.headers.get("user-agent")
        impersonate = get_curl_impersonate(ua, self.all_curl_impersonate)
        if not impersonate:
            impersonate = "chrome136"
        if not self.sessions.get(impersonate):
            if self.proxy_host and self.proxy_port:
                hots_port = f"{self.proxy_host}:{self.proxy_port}"
                if self.proxy_scheme == "socks5":
                    self.proxy_scheme = "socks5h"
                if self.proxy_user and self.proxy_pass:
                    proxy = f"{self.proxy_scheme}://{self.proxy_user}:{self.proxy_pass}@{hots_port}"
                else:
                    proxy = f"{self.proxy_scheme}://{hots_port}"

                sess = AsyncSession(
                    impersonate=impersonate, proxies={"all": proxy}, allow_redirects=False, verify=False
                )
            else:
                sess = AsyncSession(impersonate=impersonate, allow_redirects=False, verify=False)
            print(f"创建curl_sess对象:{impersonate}")
            self.sessions[impersonate] = sess
            self.msg.put({"log_message": "创建curl_sess对象:" + impersonate})
        return self.sessions[impersonate]

    @staticmethod
    def direct(flow: http.HTTPFlow):
        """请求直连,不使用代理"""
        flow.metadata["direct"] = True
        if hasattr(flow, "server_conn") and flow.server_conn:
            flow.server_conn.via = None

    async def curl_request(self, flow: http.HTTPFlow):
        if flow.error:  # 这是除缓存命中外的请求,他必然不会有flow.response,除非我手动添加响应体
            return
        retries = 0
        # TODO https://www.google.com/recaptcha/enterprise/clr  400问题
        while retries < RETRY_LIMIT:
            cffi_response = None
            try:
                sess = self.create_session(flow)
                kwargs: dict = {
                    "method": flow.request.method,
                    "url": flow.request.pretty_url,
                    "headers": flow.request.headers,
                    "stream": True,
                    "timeout": (15, 40),
                }

                if flow.metadata.get("direct"):
                    kwargs["proxies"] = None
                if flow.request.content:
                    kwargs["data"] = flow.request.raw_content
                _task = asyncio.create_task(sess.request(**kwargs))
                cffi_response = await asyncio.wait_for(_task, timeout=20)
                flow.response = http.Response.make(
                    status_code=cffi_response.status_code,
                    content=b"",
                    headers=cffi_response.headers.raw,
                )
                flow.metadata["cffi_response"] = cffi_response
                return
            except (CurlError, asyncio.TimeoutError) as e:
                if flow.error:
                    return
                if cffi_response:
                    await cffi_response.aclose()
                retries += 1
                if retries < RETRY_LIMIT:
                    await asyncio.sleep(RETRY_DELAY)
        flow.kill()
        return

    async def curl_stream_response(self, flow: http.HTTPFlow):
        """针对音视频/直播等的流式传输"""

    @staticmethod
    def curl_response_extract_re(doc_pattern: str, content: str):
        try:
            results = re.findall(doc_pattern, content)
            if results:
                return results
            else:
                return []
        except re.error as e:
            log.exception(str(e))
            return None

    @staticmethod
    def curl_response_extract_xpath(doc_pattern: str, content: str):
        try:
            tree = html.fromstring(content)
            results = tree.xpath(doc_pattern)
            if not results:
                return []
            processed_results = []
            for item in results:
                if isinstance(item, str):
                    processed_results.append(item.strip())
                else:
                    processed_results.append(item.text_content().strip())
            return processed_results
        except Exception as e:
            log.exception(str(e))
            return None

    @staticmethod
    def curl_response_extract_bs4(doc_pattern: str, content: str):
        try:
            soup = BeautifulSoup(content, "lxml")
            elements = soup.select(doc_pattern)
            if not elements:
                return []
            results = [elem.get_text(strip=True) for elem in elements]
            return results
        except Exception as e:
            log.exception(str(e))
            return None

    @staticmethod
    def curl_response_extract_json(doc_pattern: str, content: str):
        try:
            json_data = json.loads(content)
            queries = [q.strip() for q in doc_pattern.split(",")]

            results = []
            for query in queries:
                found = jmespath.search(query, json_data)
                results.append(found if found is not None else "")
            return results
        except json.JSONDecodeError:
            log.warning("无法将内容解析为JSON。")
            return None  # 内容不是有效的JSON
        except Exception as e:
            log.exception(f"JSON提取过程中发生错误: {e}")
            return None

    @capture_error(is_traceback=True)
    async def curl_response_extract(self, content, url):
        """针对特定网页内容的提取"""
        if url_pattern_list := config_manager.get("url_pattern_list"):
            try:
                if isinstance(content, bytes):
                    content = content.decode("utf-8", errors="ignore")
            except (AttributeError, TypeError):
                return
            for url_pattern, doc_pattern, scripts in url_pattern_list:
                url_matches = False
                if url_pattern.startswith("re:"):
                    if re.search(url_pattern[3:], url):
                        url_matches = True
                elif url_pattern in url:
                    url_matches = True
                if url_matches:
                    for prefix, extractor_func in self.EXTRACTORS.items():
                        if doc_pattern.startswith(prefix):
                            doc_pattern = doc_pattern[len(prefix) :]
                            result = extractor_func(doc_pattern, content)
                            if result and isinstance(result, list):
                                format_result = formatter(scripts, result)
                                self.msg.put({"notification": ("网页内容提取成功", format_result)})
                                return

    async def curl_response_filling(self, flow: http.HTTPFlow):
        """针对特定网页内容的填充"""

    @capture_error(is_traceback=True)
    async def curl_response(self, flow: http.HTTPFlow):
        cffi_response = flow.metadata["cffi_response"]
        try:
            if flow.error or (flow.response and flow.response.content):
                await cffi_response.aclose()
                return
            _task = asyncio.create_task(cffi_response.acontent())
            content = await asyncio.wait_for(_task, timeout=30)
            final_headers = [
                (k, v)
                for k, v in cffi_response.headers.raw
                if k.lower() not in [b"content-encoding", b"content-length", b"transfer-encoding"]
            ]
            if content:  # and not cffi_response.headers.get("transfer-encoding")
                final_headers.append((b"content-length", str(len(content)).encode()))
            flow.response = http.Response.make(
                status_code=cffi_response.status_code,
                content=content,
                headers=final_headers,
            )
        except asyncio.TimeoutError:
            log.error(f"下载响应体超时（超过30秒）: {flow.request.pretty_url}")
            flow.kill()
        except RequestException as e:
            log.error(f"curl_response 阶段失败: {e}", exc_info=True)
            flow.kill()
        finally:
            await cffi_response.aclose()

    @staticmethod
    def filter_headers(headers, body):
        safe_headers = []
        has_content_length = False
        for k, v in headers:
            if k.lower() in SAFE_HEADERS_TO_CACHE:
                if k == b"content-encoding":
                    continue
                if k == b"content-length":
                    v = str(len(body)).encode()
                safe_headers.append((k, v))
        if body and not has_content_length:
            safe_headers.append((b"content-length", str(len(body)).encode()))
        return safe_headers

    @capture_error(is_traceback=True)
    def extract_object(self, flow):
        cffi_response = flow.metadata["cffi_response"]
        all_data = {
            "curl_content_length": cffi_response.headers.get("content-length"),
            "curl_content_encoding": cffi_response.headers.get("content-encoding"),
            "flow_response_content": flow.response.content,
            "flow_is_cached": flow.metadata["is_cached"],
            "normalize_url": flow.metadata["normalize_url"],
            "flow_response_headers": flow.response.headers.fields,
            "flow_response_status_code": flow.response.status_code,
            "origin_content_length": None,
            "url_path": flow.metadata["url_path"],
            "is_need_cache": self.is_need_cache(flow),
        }
        return all_data

    @staticmethod
    @capture_error(is_traceback=True)
    async def calculate_file_size(data: dict):
        """计算文件大小"""
        if ocl := data["curl_content_length"]:
            data["origin_content_length"] = str(ocl)
        elif content_encoding := data["curl_content_encoding"]:
            if content_encoding in ["gzip", "br", "deflate", "zstd"]:
                try:
                    loop = asyncio.get_running_loop()
                    ocl = await asyncio.wait_for(
                        loop.run_in_executor(
                            None, get_origin_content_length, data["flow_response_content"], content_encoding
                        ),
                        60,
                    )
                    data["origin_content_length"] = str(ocl)
                except (asyncio.TimeoutError, Exception) as e:
                    log.error(f"后台重压缩失败 (encoding: {content_encoding}): {e}")
        if not data["origin_content_length"]:
            data["origin_content_length"] = str(len(data["flow_response_content"]))

    @capture_error(is_traceback=True)
    async def make_serialize_response(self, data: dict):
        # 获取特定网页内容
        await self.curl_response_extract(data["flow_response_content"], data["normalize_url"])
        cache_key = cache_client.build_key(data["normalize_url"])
        try:
            await self.calculate_file_size(data)
            if data["origin_content_length"].isdigit():
                await self.stats_queue.put(int(data["origin_content_length"]))
            if data["flow_response_content"] and data["flow_is_cached"] is False:
                if data["is_need_cache"] and cache_key not in self.writing_in_progress:
                    self.writing_in_progress.add(cache_key)
                    # 原始响应头部大小
                    origin_content_length = int(data["origin_content_length"])
                    # 清理头部信息
                    safe_headers = self.filter_headers(data["flow_response_headers"], data["flow_response_content"])
                    data_to_cache = (
                        data["flow_response_status_code"],
                        safe_headers,
                        data["flow_response_content"],
                        origin_content_length,
                    )
                    try:
                        await cache_client.set(cache_key, data_to_cache, ttl_sec=24 * 60 * 60)
                        self.msg.put({"log_message": f"缓存写入成功:{data['url_path']}"})
                    except Exception as e:
                        log.error(f"序列化失败: {e}")
        except Exception as e:
            log.error(f"后台缓存任务发生错误: {e}", exc_info=True)
        finally:
            if cache_key in self.writing_in_progress:
                self.writing_in_progress.discard(cache_key)

    @capture_error(is_traceback=True)
    async def find_and_deserialize_response(self, flow: http.HTTPFlow):
        url_path, normalize_url = self.get_cache_key(flow)
        flow.metadata["url_path"], flow.metadata["normalize_url"] = url_path, normalize_url
        cache_key = cache_client.build_key(flow.metadata["normalize_url"])
        if flow.request.method == "GET" and (cache_info := await cache_client.get(cache_key)):
            try:
                status_code, headers_list, body, origin_content_length = cache_info
                flow.response = http.Response.make(
                    status_code=status_code,
                    content=body,
                    headers=headers_list,
                )
                async with self._lock:
                    self.download_save_bytes += origin_content_length
                    self.upload_save_bytes += len(flow.request.raw_content)
                flow.metadata["is_cached"] = True
                self.msg.put({"log_message": f"缓存读取成功:{url_path}"})
                return
            except Exception as e:
                log.error(f"反序列化失败: {e}")

        async with self._lock:
            self.upload_bytes += len(flow.request.raw_content)
        flow.metadata["is_cached"] = False
        if flow.request.headers.get("upgrade", "").lower() == "websocket":
            return
        await self.curl_request(flow)

    @staticmethod
    @capture_error(is_traceback=True)
    def get_cache_key(flow: http.HTTPFlow) -> str:
        return normalized_url(flow.request.pretty_url)

    @staticmethod
    @capture_error(is_traceback=True)
    def get_content_type(flow: http.HTTPFlow):
        return flow.response.headers.get("content-type", "").lower()

    @staticmethod
    @capture_error(is_traceback=True)
    def get_is_cache(flow: http.HTTPFlow):
        all_control = [
            flow.request.headers.get("cache-control", "").lower(),
            flow.request.headers.get("pragma", "").lower(),
            flow.response.headers.get("cache-control", "").lower(),
        ]
        cs = []
        for _cs in all_control:
            cs.extend([i.strip() for i in _cs.split(",")])
        if any(list(map(lambda x: x in FORBIDDEN_DIRECTIVES, cs))):
            return True
        return False

    @staticmethod
    def filter_link_ignore_list(url, ignore_list):
        result_list = []
        for i in ignore_list:
            if i.startswith("re:"):
                result_list.append(True if re.search(i[3:], url) else False)
            else:
                result_list.append(i in url)
        return result_list

    @capture_error(is_traceback=True)
    def is_need_cache(self, flow: http.HTTPFlow):
        filter_list = [
            flow.request.method != "GET",
            not (200 <= flow.response.status_code < 300),
            self.get_is_cache(flow),
            "set-cookie" in flow.response.headers,
            "cookie" in flow.response.headers.get("vary", "").lower(),
            not flow.metadata.get("url_path", "").endswith(RESOURCE_SUFFIX),
            not self.get_content_type(flow).startswith(RESOURCE_CONTENT_TYPES),
        ]
        if link_ignore_list := config_manager.get("link_ignore_list"):
            _list = self.filter_link_ignore_list(flow.metadata.get("normalize_url", ""), link_ignore_list)
            filter_list.append(any(_list))
        if any(filter_list):
            return None
        return True

    @capture_error(is_traceback=True)
    async def get_download_bytes(self):
        download_this_second = 0
        while not self.stats_queue.empty():
            try:
                size = self.stats_queue.get_nowait()
                download_this_second += size
            except asyncio.QueueEmpty:
                break
        return download_this_second

    def is_filter_req(self):
        # 过滤特定请求,使用mitm原始进行请求
        ...
