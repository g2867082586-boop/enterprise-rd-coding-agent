from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.agent.graph import close_graph
from app.api.routes_agent import router as agent_router
from app.api.routes_health import router as health_router
from app.api.routes_admin import router as admin_router
from app.auth.routes import router as auth_router
from app.chat.routes import router as chat_router
from app.config import get_settings
from app.observability import configure_observability
from app.orders.routes import router as orders_router
from app.knowledge.routes import router as knowledge_router
from app.security.csrf import CSRFMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_observability()
    yield
    await close_graph()


app = FastAPI(title="Enterprise R&D Knowledge Agent", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Rebuild-Token", "X-CSRF-Token", "Idempotency-Key"],
)
app.add_middleware(CSRFMiddleware)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(agent_router)
app.include_router(admin_router)
app.include_router(orders_router)
app.include_router(knowledge_router)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><link rel="icon" href="data:,"><title>星云商城研发助手</title></head>
<body><main><h1>星云商城研发助手</h1><p id="system-status">系统运行正常</p>
<p>Mock LLM / TF-IDF 词法检索降级模式</p></main></body></html>"""
