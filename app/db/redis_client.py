import redis.asyncio as redis

from app.core.config import settings


redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis | None:
    """
    Return the current async Redis client.

    Call this instead of importing `redis_client` elsewhere: `from redis_client import redis_client`
    binds the value at import time and stays `None` after `connect_redis()` reassigns the global.
    """
    return redis_client


async def connect_redis() -> None:
    global redis_client
    redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


async def disconnect_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None

