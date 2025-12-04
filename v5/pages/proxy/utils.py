import re
from curl_cffi.requests.impersonate import BrowserType
import zstandard as zstd
import zlib
import gzip
import brotli
from urllib.parse import urlparse, urlunparse

from user_agents import parse

SAFE_HEADERS_TO_CACHE = {
    # --- 核心内容与缓存控制 ---
    b"content-type",
    b"content-length",
    b"content-encoding",
    # b"content-md5",
    b"cache-control",
    b"content-language",
    b"content-disposition",
    b"expires",
    b"etag",
    b"last-modified",
    b"vary",
    b"accept-ranges",
    # b"digest",
    # b"want-digest",
    # --- CORS 与安全策略 (推荐保留) ---
    b"access-control-allow-origin",
    b"access-control-allow-credentials",
    b"access-control-allow-headers",
    b"access-control-allow-methods",
    b"access-control-expose-headers",
    b"strict-transport-security",
    b"content-security-policy-report-only",
    b"content-security-policy",
    b"cross-origin-opener-policy",
    b"cross-origin-resource-policy",
    b"referrer-policy",
    b"permissions-policy",
    # --- 浏览器行为指令 (推荐保留) ---
    b"x-content-type-options",
    b"x-xss-protection",
    b"x-frame-options",
    b"x-ua-compatible",
    b"origin-agent-cluster",
    b"accept-ch",
    b"link",
    b"refresh",
    b"critical-ch",
}
RESOURCE_SUFFIX = (
    # 脚本 (Scripts)
    "js",
    "mjs",  # JavaScript Module
    "wasm",  # WebAssembly
    # 样式表 (Stylesheets)
    "css",
    # 图像 (Images)
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",  # 现代图像格式
    "avif",  # 下一代图像格式
    "svg",  # 矢量图像
    "ico",  # 图标
    "bmp",
    "tiff",
    # 字体 (Fonts)
    "woff",
    "woff2",  # 现代字体格式
    "ttf",  # TrueType
    "otf",  # OpenType
    "eot",  # Embedded OpenType (旧版IE)
    # 数据格式 (Data Formats)
    "json",
    "xml",
    "jsonp",  # JSON with Padding
    "map",  # Source Map for JS/CSS
    # 音视频 (Audio/Video)
    "mp3",
    "mp4",
    "wav",
    "ogg",  # Ogg Vorbis Audio
    "oga",  # Ogg Audio
    "ogv",  # Ogg Video
    "webm",  # WebM Video/Audio
    "aac",  # AAC Audio
    "flac",  # FLAC Audio
    "mov",  # QuickTime Movie
    # 文档 (Documents)
    # "html",
    # "htm",
    # "pdf",
    # 压缩包 (Archives)
    "zip",
    "rar",
    "7z",
    "gz",
    "tar",
)
RESOURCE_CONTENT_TYPES = (
    # 脚本 (Scripts)
    "application/javascript",
    "application/x-javascript",
    "text/javascript",
    "application/wasm",
    # "application/binary",
    # 样式表 (Stylesheets)
    "text/css",
    # 图像 (Images)
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/avif",
    "image/svg+xml",
    "image/x-icon",
    "image/vnd.microsoft.icon",
    # 字体 (Fonts)
    "font/woff",
    "application/font-woff",  # 旧版
    "font/woff2",
    "font/ttf",
    "font/otf",
    "application/vnd.ms-fontobject",  # .eot
    # 数据格式 (Data Formats)
    # "application/json",
    # "application/manifest+json",
    # "application/xml",
    # "text/xml",
    # "text/plain",
    # 音视频 (Audio/Video)
    "audio/mpeg",  # .mp3
    "audio/mp4",  # .m4a
    "video/mp4",  # .mp4
    "audio/wav",
    "audio/ogg",  # .oga
    "video/ogg",  # .ogv
    "application/ogg",
    "video/webm",
    "audio/webm",
    "audio/aac",
    "audio/flac",
    "video/quicktime",  # .mov
    "application/vnd.yt-ump",
    # 文档 (Documents)
    # "text/html",
    "application/pdf",
    # 通用二进制流 (可以代表任何文件)
    # "application/octet-stream",
)
FORBIDDEN_DIRECTIVES = {"no-store", "private"}


def segment_browser_version_and_type(useragent: str) -> (int, str):
    if not useragent:
        return None, None, None
    try:
        user_agent = parse(useragent)
        browser_family = user_agent.browser.family
        version_tuple = user_agent.browser.version
        major_version = version_tuple[0] if version_tuple else 0
        return int(major_version), user_agent.is_mobile, browser_family
    except Exception:
        # 如果库解析失败或遇到未知格式，返回默认值
        return None, None, None


def get_curl_impersonate(useragent: str, all_impersonate: dict):
    version, is_mobile, family = segment_browser_version_and_type(useragent)
    if not version and not family:
        return None
    family = family.lower()
    if family not in list(all_impersonate.keys()):
        return f"chrome136"
    versions = [x[-1] for x in all_impersonate.get(family) if (x[0] if is_mobile else (not x[0]))]
    available_versions = [v for v in versions if v <= str(version)]
    if available_versions:
        return f"chrome{max(available_versions)}"
    else:
        return f"chrome{min(versions)}"


def get_all_curl_impersonate():
    browser_version = {}

    def spilt_underline(s):
        if not s:
            return (None,) * 2
        if "_" in s:
            _ = s.split("_")
            sf, sv = re.findall(r"([a-zA-Z_]+)(\w+)", _[0])[0]
            sv = "_".join([sv, _[1]])
        else:
            sf, sv = re.findall(r"([a-zA-Z_]+)(\w+)", s)[0]
        return sf, sv

    for b in BrowserType:
        f, d, v = None, None, None
        if "_" in b and not b[-1].isdigit():
            d, f = b[::-1].split("_", maxsplit=1)
            d, f = d[::-1], f[::-1]
        f, v = spilt_underline(f if f else b)
        if browser_version.get(f):
            browser_version[f].append((d, v))
        else:
            browser_version[f] = [(d, v)]
    return browser_version


def get_origin_content_length(content: bytes, content_encoding: str) -> int:
    try:
        if content_encoding == "gzip":
            recompressed_size = len(gzip.compress(content))
        elif content_encoding == "br":
            recompressed_size = len(brotli.compress(content))
        elif content_encoding == "deflate":
            recompressed_size = len(zlib.compress(content))
        elif content_encoding == "zstd":
            recompressed_size = len(zstd.compress(content))
        else:
            recompressed_size = len(content)
    except (Exception,) as e:
        recompressed_size = len(content)
    return recompressed_size


def normalized_url(url):
    """序列化后的请求的URL。"""
    parsed = urlparse(url)
    path = parsed.path if parsed.path else "/"
    query = "&".join(sorted(parsed.query.split("&"))) if parsed.query else ""
    return path, urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.params, query, parsed.fragment))
