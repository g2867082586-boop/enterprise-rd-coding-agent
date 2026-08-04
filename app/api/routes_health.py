from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database.connection import get_engine
from app.infrastructure.redis_client import redis_health


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "llm_mode": settings.llm_provider,
        "retrieval_mode": settings.embedding_provider,
        "database_provider": settings.database_provider,
        "knowledge_corpus": settings.knowledge_corpus,
        "llm_api_key_set": str(bool(settings.llm_api_key)).lower(),
        "embedding_api_key_set": str(bool(settings.embedding_api_key)).lower(),
        "configuration_status": "ok" if not settings.validate_runtime() else "incomplete",
    }


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> JSONResponse:
    settings = get_settings()
    checks: dict[str, object] = {
        "configuration": {"ok": not settings.validate_runtime(), "problems": settings.validate_runtime()},
        "redis": redis_health(),
        "index": {"ok": settings.project_path(settings.knowledge_index_path).exists()},
    }
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = {"ok": True, "provider": settings.database_provider}
    except Exception as exc:
        checks["database"] = {
            "ok": False, "provider": settings.database_provider, "error": str(exc)[:200]
        }
    required = ["configuration", "database", "index"]
    if settings.redis_required:
        required.append("redis")
    ready = all(bool(checks[name].get("ok")) for name in required if isinstance(checks[name], dict))
    return JSONResponse(
        {"status": "ready" if ready else "not_ready", "checks": checks},
        status_code=200 if ready else 503,
    )
