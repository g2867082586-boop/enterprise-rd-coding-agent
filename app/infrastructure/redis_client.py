import logging
import time
from functools import lru_cache
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.config import get_settings


logger = logging.getLogger("enterprise.redis")


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=2,
        health_check_interval=30,
    )


def redis_health() -> dict[str, Any]:
    try:
        return {"ok": bool(get_redis().ping()), "mode": "redis"}
    except RedisError as exc:
        return {"ok": False, "mode": "redis", "error": str(exc)[:200]}


def distributed_rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool | None:
    """Return True when allowed, False when limited, and None when Redis is unavailable."""
    bucket = int(time.time()) // window_seconds
    redis_key = f"rate:{key}:{bucket}"
    try:
        pipeline = get_redis().pipeline()
        pipeline.incr(redis_key)
        pipeline.expire(redis_key, window_seconds + 2)
        count, _ = pipeline.execute()
        return int(count) <= limit
    except RedisError:
        if get_settings().redis_required:
            raise RuntimeError("Redis is required but unavailable")
        logger.warning("Redis rate limiter unavailable; using process-local fallback")
        return None


def publish_event(stream: str, payload: dict[str, object]) -> str | None:
    try:
        return str(get_redis().xadd(stream, payload, maxlen=2000, approximate=True))
    except RedisError:
        if get_settings().redis_required:
            raise RuntimeError("Redis is required but unavailable")
        return None


def acquire_lock(key: str, ttl_seconds: int) -> bool | None:
    try:
        return bool(get_redis().set(f"lock:{key}", "1", ex=ttl_seconds, nx=True))
    except RedisError:
        if get_settings().redis_required:
            raise RuntimeError("Redis is required but unavailable")
        return None


def release_lock(key: str) -> None:
    try:
        get_redis().delete(f"lock:{key}")
    except RedisError:
        if get_settings().redis_required:
            raise RuntimeError("Redis is required but unavailable")
