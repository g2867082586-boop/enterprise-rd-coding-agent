from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    app_env: str = "development"
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2
    llm_temperature: float = 0.1
    allow_mock_fallback: bool = True
    embedding_provider: str = "lexical"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"
    embedding_min_score: float = 0.35
    lexical_min_score: float = 0.01
    knowledge_corpus: str = "mock"
    enterprise_knowledge_dir: str = "knowledge_base/enterprise"
    mock_knowledge_dir: str = "knowledge_base/mock"
    knowledge_catalog_path: str = "knowledge_base/catalog/catalog.json"
    database_provider: str = "sqlite"
    sqlite_path: str = "data/nebula_shop.db"
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3308
    mysql_database: str = "nebula_shop"
    mysql_admin_user: str = "root"
    mysql_admin_password: str = ""
    mysql_readonly_user: str = "nebula_reader"
    mysql_readonly_password: str = ""
    mysql_app_user: str = "nebula_app"
    mysql_app_password: str = ""
    mysql_order_user: str = "nebula_order"
    mysql_order_password: str = ""
    db_query_timeout_seconds: int = 5
    db_max_rows: int = 100
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_required: bool = False
    job_queue_name: str = "enterprise-agent"
    job_inline_fallback: bool = True
    order_event_poll_seconds: float = 2.0
    upload_dir: str = "data/uploads"
    knowledge_index_versions_dir: str = "data/vector_store/versions"
    max_upload_bytes: int = 26_214_400
    max_pdf_pages: int = 300
    allowed_origins: str = ""
    browser_channel: str = "chrome"
    browser_headless: bool = True
    browser_timeout_ms: int = 30_000
    browser_allowed_hosts: str = "localhost,127.0.0.1"
    sample_app_url: str = "http://127.0.0.1:8000/"
    trace_dir: str = "data/traces"
    checkpoint_path: str = "data/checkpoints.sqlite"
    approval_checkpoint_path: str = "data/approval-checkpoints.sqlite"
    knowledge_index_path: str = "data/vector_store/index.json"
    max_agent_iterations: int = 8
    max_tool_calls: int = 6
    agent_timeout_seconds: int = 120
    agent_max_steps: int = 6
    agent_max_replans: int = 2
    agent_request_timeout_seconds: int = 180
    dev_rebuild_token: str = ""
    frontend_url: str = "http://127.0.0.1:5173"
    session_cookie_name: str = "nebula_session"
    session_ttl_hours: int = 24
    session_cookie_secure: bool = False
    csrf_enabled: bool = False
    auth_rate_limit_per_minute: int = 10
    chat_rate_limit_per_minute: int = 12
    chat_max_concurrent_per_user: int = 1
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "enterprise-rd-agent-v2"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    otel_enabled: bool = False
    otel_service_name: str = "enterprise-rd-agent"
    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_headers: str = ""

    def validate_runtime(self) -> list[str]:
        problems: list[str] = []
        if self.llm_provider == "openai_compatible":
            missing = [name for name, value in {
                "LLM_API_KEY": self.llm_api_key, "LLM_BASE_URL": self.llm_base_url,
                "LLM_MODEL": self.llm_model,
            }.items() if not value]
            if missing:
                problems.append(f"real LLM configuration missing: {', '.join(missing)}")
        if self.embedding_provider == "openai_compatible":
            missing = [name for name, value in {
                "EMBEDDING_API_KEY": self.embedding_api_key,
                "EMBEDDING_BASE_URL": self.embedding_base_url,
                "EMBEDDING_MODEL": self.embedding_model,
            }.items() if not value]
            if missing:
                problems.append(f"embedding configuration missing: {', '.join(missing)}")
        if self.langsmith_tracing and not self.langsmith_api_key:
            problems.append("LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is missing")
        if self.app_env == "production":
            if not self.session_cookie_secure:
                problems.append("SESSION_COOKIE_SECURE must be true in production")
            if not self.csrf_enabled:
                problems.append("CSRF_ENABLED must be true in production")
            if not self.redis_url:
                problems.append("REDIS_URL is required in production")
            if self.database_provider != "mysql":
                problems.append("production requires DATABASE_PROVIDER=mysql")
            if not self.mysql_order_password:
                problems.append("MYSQL_ORDER_PASSWORD is required in production")
            if self.mysql_order_password and self.mysql_order_password == self.mysql_app_password:
                problems.append("MYSQL_ORDER_PASSWORD must differ from MYSQL_APP_PASSWORD")
        return problems

    def project_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else ROOT_DIR / path

    @property
    def database_url(self) -> str:
        if self.database_provider == "mysql":
            from urllib.parse import quote_plus

            user = quote_plus(self.mysql_readonly_user)
            password = quote_plus(self.mysql_readonly_password)
            return (
                f"mysql+pymysql://{user}:{password}@{self.mysql_host}:"
                f"{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
            )
        path = self.project_path(self.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"

    @property
    def application_database_url(self) -> str:
        """Writable URL for authentication/chat data; business tools keep using database_url."""
        if self.database_provider == "mysql":
            from urllib.parse import quote_plus

            if not self.mysql_app_password:
                raise RuntimeError("MYSQL_APP_PASSWORD must be set for MySQL web features")
            user = quote_plus(self.mysql_app_user)
            password = quote_plus(self.mysql_app_password)
            return (
                f"mysql+pymysql://{user}:{password}@{self.mysql_host}:"
                f"{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
            )
        return self.database_url

    @property
    def migration_database_url(self) -> str:
        if self.database_provider == "mysql":
            from urllib.parse import quote_plus

            if not self.mysql_admin_password:
                raise RuntimeError("MYSQL_ADMIN_PASSWORD must be set for MySQL migrations")
            user = quote_plus(self.mysql_admin_user)
            password = quote_plus(self.mysql_admin_password)
            return (
                f"mysql+pymysql://{user}:{password}@{self.mysql_host}:"
                f"{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
            )
        return self.database_url

    @property
    def order_database_url(self) -> str:
        """Writable URL restricted to order-domain tables in MySQL mode."""
        if self.database_provider == "mysql":
            from urllib.parse import quote_plus

            password_value = self.mysql_order_password or (
                self.mysql_app_password if self.app_env != "production" else ""
            )
            if not password_value:
                raise RuntimeError("MYSQL_ORDER_PASSWORD must be set for order write features")
            user = quote_plus(self.mysql_order_user)
            password = quote_plus(password_value)
            return (
                f"mysql+pymysql://{user}:{password}@{self.mysql_host}:"
                f"{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
            )
        return self.database_url

    @property
    def cors_origins(self) -> list[str]:
        configured = [item.strip() for item in self.allowed_origins.split(",") if item.strip()]
        return configured or [self.frontend_url]


@lru_cache
def get_settings() -> Settings:
    return Settings()
