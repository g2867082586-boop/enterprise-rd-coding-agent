"""Run with: python -m app.jobs.worker"""

from rq import Queue, Worker

from app.config import get_settings
from app.infrastructure.redis_client import get_redis


def main() -> None:
    settings = get_settings()
    worker = Worker([Queue(settings.job_queue_name, connection=get_redis())], connection=get_redis())
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
