"""
Redis Cache Service
Provides caching for external API calls and Pub/Sub for real-time progress.
"""

import json
import hashlib
import asyncio
from typing import Optional, Any, Dict, Callable
from datetime import datetime

import redis.asyncio as aioredis

from app.config import settings
from app.utils.logging import logger


class RedisCache:
    """
    Redis cache with Pub/Sub support.
    
    - Caches external API responses (search results) with configurable TTL.
    - Publishes agent progress events on per-session channels.
    - Subscribes to channels for WebSocket fan-out.
    """

    _instance: Optional["RedisCache"] = None
    _client: Optional[aioredis.Redis] = None
    _pubsub: Optional[aioredis.client.PubSub] = None
    _subscriber_task: Optional[asyncio.Task] = None

    # -----------------------------------------------------------------
    # Singleton access
    # -----------------------------------------------------------------
    @classmethod
    def get_instance(cls) -> "RedisCache":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # -----------------------------------------------------------------
    # Connection lifecycle
    # -----------------------------------------------------------------
    async def connect(self):
        """Establish connection to Redis."""
        if not settings.redis_url:
            logger.warning("REDIS_URL not set — Redis features disabled")
            return

        try:
            # For rediss:// URLs (managed Redis with TLS), we must accept self-signed certs.
            # redis-py accepts `ssl_cert_reqs` as a string via from_url().
            kwargs: Dict[str, Any] = {
                "decode_responses": True,
                "socket_connect_timeout": 5,
                "retry_on_timeout": True,
            }
            if settings.redis_url and settings.redis_url.startswith("rediss://"):
                import ssl as _ssl
                kwargs["ssl_cert_reqs"] = "none"

            self._client = aioredis.from_url(
                settings.redis_url,
                **kwargs,
            )
            await self._client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e} — running without cache")
            self._client = None

    async def disconnect(self):
        """Close Redis connection."""
        if self._subscriber_task and not self._subscriber_task.done():
            self._subscriber_task.cancel()
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._client:
            await self._client.close()
            logger.info("Redis connection closed")

    @property
    def available(self) -> bool:
        return self._client is not None

    # -----------------------------------------------------------------
    # Generic cache helpers
    # -----------------------------------------------------------------
    @staticmethod
    def _cache_key(prefix: str, query: str) -> str:
        """Deterministic cache key from prefix + query."""
        h = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"rc:{prefix}:{h}"

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache, returns None on miss or if unavailable."""
        if not self.available:
            return None
        try:
            raw = await self._client.get(key)
            if raw is not None:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis GET failed for {key}: {e}")
        return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set a value in cache with optional TTL (seconds)."""
        if not self.available:
            return
        try:
            ttl = ttl or settings.cache_ttl
            await self._client.setex(key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.warning(f"Redis SET failed for {key}: {e}")

    # -----------------------------------------------------------------
    # Search-result caching shortcuts
    # -----------------------------------------------------------------
    async def get_search_cache(self, api_name: str, query: str) -> Optional[Any]:
        key = self._cache_key(api_name, query)
        result = await self.get(key)
        if result is not None:
            logger.info(f"Cache HIT for {api_name} query: {query[:60]}")
        return result

    async def set_search_cache(self, api_name: str, query: str, data: Any, ttl: Optional[int] = None):
        key = self._cache_key(api_name, query)
        await self.set(key, data, ttl)
        logger.debug(f"Cached {api_name} results for: {query[:60]}")

    # -----------------------------------------------------------------
    # Pub / Sub — progress broadcasting
    # -----------------------------------------------------------------
    async def publish_progress(self, session_id: str, message: Dict[str, Any]):
        """Publish a progress event to the session channel."""
        if not self.available:
            return
        try:
            channel = f"progress:{session_id}"
            await self._client.publish(channel, json.dumps(message, default=str))
        except Exception as e:
            logger.warning(f"Redis PUBLISH failed: {e}")

    async def subscribe_progress(self, session_id: str, callback: Callable):
        """
        Subscribe to progress events for a session.
        Calls `callback(message_dict)` for each incoming event.
        Returns a cleanup coroutine the caller should await when done.
        """
        if not self.available:
            return None

        channel = f"progress:{session_id}"
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)

        async def _listener():
            try:
                async for msg in pubsub.listen():
                    if msg["type"] == "message":
                        try:
                            data = json.loads(msg["data"])
                            await callback(data)
                        except Exception as e:
                            logger.warning(f"Pub/Sub callback error: {e}")
            except asyncio.CancelledError:
                pass
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()

        task = asyncio.create_task(_listener())

        async def cleanup():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        return cleanup


# Module-level convenience accessor
def get_redis() -> RedisCache:
    return RedisCache.get_instance()
