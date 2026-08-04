from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    kwargs = {"pool_pre_ping": True}
    if settings.database_provider == "mysql":
        kwargs["connect_args"] = {
            "connect_timeout": settings.db_query_timeout_seconds,
            "read_timeout": settings.db_query_timeout_seconds,
            "write_timeout": settings.db_query_timeout_seconds,
        }
    return create_engine(settings.database_url, **kwargs)


@lru_cache
def get_app_engine() -> Engine:
    """Writable engine restricted to web application tables in MySQL mode."""
    settings = get_settings()
    kwargs = {"pool_pre_ping": True}
    if settings.database_provider == "mysql":
        kwargs["connect_args"] = {
            "connect_timeout": settings.db_query_timeout_seconds,
            "read_timeout": settings.db_query_timeout_seconds,
            "write_timeout": settings.db_query_timeout_seconds,
        }
    return create_engine(settings.application_database_url, **kwargs)


@lru_cache
def get_order_engine() -> Engine:
    """Writable engine whose MySQL account is limited to order-domain tables."""
    settings = get_settings()
    kwargs = {"pool_pre_ping": True}
    if settings.database_provider == "mysql":
        kwargs["connect_args"] = {
            "connect_timeout": settings.db_query_timeout_seconds,
            "read_timeout": settings.db_query_timeout_seconds,
            "write_timeout": settings.db_query_timeout_seconds,
        }
    return create_engine(settings.order_database_url, **kwargs)
