import asyncio
import pickle
from abc import ABC, abstractmethod
import hashlib
import os
import time


import aiofiles
import aiofiles.os
from redis import asyncio as aioredis
import logging
log = logging.getLogger("SynthBox")


class CacheBackend(ABC):
    """异步缓存后端的抽象基类"""

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        pass

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl_sec: int | None = None):
        pass

    @abstractmethod
    async def delete(self, key: str):
        pass

    @staticmethod
    def build_key(url: str) -> str:
        return hashlib.md5(url.encode("utf-8")).hexdigest()


class FileCacheBackend(CacheBackend):

    def __init__(self, config: dict | None = None):
        super().__init__()
        if config and isinstance(config, dict):
            self.base_cache_dir = config.get("name", "Cache")
        else:
            self.base_cache_dir = "Cache"
        os.makedirs(self.base_cache_dir, exist_ok=True)
        self.meta_dir = os.path.join(self.base_cache_dir, "meta")
        self.body_dir = os.path.join(self.base_cache_dir, "body")
        os.makedirs(self.meta_dir, exist_ok=True)
        os.makedirs(self.body_dir, exist_ok=True)

    def _get_paths(self, key: str) -> tuple[str, str]:
        """根据key生成元数据和内容体的文件路径。"""
        # 文件名直接使用key，不再替换字符，因为key已经是md5
        meta_path = os.path.join(self.meta_dir, f"{key}.meta")
        body_path = os.path.join(self.body_dir, f"{key}.body")
        return meta_path, body_path

    async def set(self, key: str, value: tuple, ttl_sec: int | None = None):
        """
        现在 value 是一个元组: (status_code, headers_list, content_bytes)
        """
        status_code, headers_list, content_bytes, origin_content_length = value
        meta_filepath, body_filepath = self._get_paths(key)
        expire_at = time.time() + ttl_sec if ttl_sec and ttl_sec > 0 else None
        metadata_to_pickle = (status_code, headers_list, expire_at, origin_content_length)

        try:
            # 异步写入元数据文件
            async with aiofiles.open(meta_filepath, "wb") as f:
                await f.write(pickle.dumps(metadata_to_pickle))
            # 异步写入原始响应体文件
            async with aiofiles.open(body_filepath, "wb") as f:
                await f.write(content_bytes)
        except IOError as e:
            print(f"FileCacheBackend Error: 写入缓存失败 for key '{key}': {e}")
            # 如果失败，尝试清理，避免产生孤儿文件
            await self.delete(key)

    async def get(self, key: str) -> tuple | None:
        """
        返回一个包含 (status_code, headers_list, body_filepath) 的元组，
        或者在未找到或已过期时返回 None。
        """
        meta_filepath, body_filepath = self._get_paths(key)

        try:
            if not await aiofiles.os.path.exists(meta_filepath):
                return None

            async with aiofiles.open(meta_filepath, "rb") as f:
                status_code, headers_list, expire_at, origin_content_length = pickle.loads(await f.read())

            if expire_at and time.time() > expire_at:
                await self.delete(key)  # 删除过期的缓存
                return None

            if not await aiofiles.os.path.exists(body_filepath):
                await self.delete(key)  # 删除不完整的缓存（有meta但无body）
                return None

            async with aiofiles.open(body_filepath, "rb") as f:
                body = await f.read()
            return status_code, headers_list, body, origin_content_length

        except Exception as e:
            print(f"从缓存文件加载失败: {e}，将删除可能损坏的缓存。")
            await self.delete(key)
            return None

    async def delete(self, key: str):
        """异步删除一个缓存项对应的所有文件。"""
        meta_filepath, body_filepath = self._get_paths(key)
        try:
            if await aiofiles.os.path.exists(meta_filepath):
                await aiofiles.os.remove(meta_filepath)
        except OSError as e:
            print(f"删除元数据文件失败: {e}")
        try:
            if await aiofiles.os.path.exists(body_filepath):
                await aiofiles.os.remove(body_filepath)
        except OSError as e:
            print(f"删除内容文件失败: {e}")

    async def clear_timeout_cache(self):
        count = 0
        for path in await aiofiles.os.listdir(self.meta_dir):
            try:
                _path = os.path.join(self.meta_dir,path)
                async with aiofiles.open(_path, "rb") as f:
                    status_code, headers_list, expire_at, origin_content_length = pickle.loads(await f.read())
                if expire_at and time.time() > expire_at:
                    await self.delete(path.split(".")[0])
                    count += 1
            except (FileNotFoundError,OSError) as e:
                log.exception(str(e))
        return count


class RedisCacheBackend(CacheBackend):
    def __init__(self, config: dict | None):
        super().__init__()
        if not config or not isinstance(config, dict):
            raise ValueError("RedisCacheBackend requires a config dict.")

        # 使用 redis.asyncio.Redis 创建异步客户端
        self.client = aioredis.Redis(
            host=config.get("host", "localhost"),
            port=config.get("port", 6379),
            db=config.get("db", 0),
            password=config.get("password"),
            decode_responses=False,  # 保持 False 以便存储和检索 bytes
        )

    async def get(self, key: str) -> bytes | None:
        try:
            # 使用 await 调用异步方法
            return await self.client.get(key)
        except Exception as e:
            print(f"RedisCacheBackend Error: Get 操作失败 key '{key}': {e}")
            return None

    async def set(self, key: str, value: bytes, ttl_sec: int | None = None):
        try:
            if ttl_sec is not None and ttl_sec > 0:
                # 使用 await 调用异步方法
                await self.client.setex(key, ttl_sec, value)
            else:
                await self.client.set(key, value)
        except Exception as e:
            print(f"RedisCacheBackend Error: 写入键 '{key}' 失败: {e}")

    async def delete(self, key: str):
        try:
            # 使用 await 调用异步方法
            await self.client.delete(key)
        except Exception as e:
            print(f"RedisCacheBackend Error: 删除键 '{key}' 失败: {e}")

    async def close(self):
        """提供一个优雅关闭连接池的方法"""
        await self.client.close()


if __name__ == '__main__':
    cache = FileCacheBackend()
    cache.clear_timeout_cache()

