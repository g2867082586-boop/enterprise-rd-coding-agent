import logging
from typing import Any, Callable

from redis.exceptions import RedisError
from rq import Queue

from app.config import get_settings
from app.infrastructure.redis_client import get_redis


logger = logging.getLogger("enterprise.jobs")


def enqueue(function: Callable[..., Any], *args: object, job_id: str | None = None) -> dict[str, str]:
    settings = get_settings()
    try:
        queue = Queue(settings.job_queue_name, connection=get_redis())
        job = queue.enqueue(
            function,
            *args,
            job_id=job_id,
            job_timeout=max(settings.agent_request_timeout_seconds, 600),
            result_ttl=86_400,
            failure_ttl=604_800,
        )
        return {"mode": "redis_rq", "job_id": str(job.id)}
    except (RedisError, OSError) as exc:
        if settings.redis_required or not settings.job_inline_fallback:
            raise RuntimeError("后台任务队列不可用") from exc
        logger.warning("Redis queue unavailable; explicit inline development fallback")
        function(*args)
        return {"mode": "inline_fallback", "job_id": job_id or ""}
