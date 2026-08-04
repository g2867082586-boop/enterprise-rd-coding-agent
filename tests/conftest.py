import os
import subprocess
import sys
import time
from collections.abc import Iterator

import httpx
import pytest
import pytest_asyncio
from playwright.sync_api import sync_playwright

from app.config import get_settings
from app.agent.graph import close_graph
from app.database.connection import get_engine
from app.database.connection import get_app_engine
from app.database.connection import get_order_engine
from app.database.models import Base
from scripts.init_database import init_database


@pytest.fixture(autouse=True)
def reset_runtime_caches(tmp_path, request: pytest.FixtureRequest) -> Iterator[None]:
    mysql_test = request.node.get_closest_marker("mysql") is not None
    real_llm_test = request.node.get_closest_marker("real_llm") is not None
    if not real_llm_test:
        os.environ["LLM_PROVIDER"] = "mock"
    if not mysql_test:
        os.environ["DATABASE_PROVIDER"] = "sqlite"
        os.environ["SQLITE_PATH"] = str(tmp_path / "test.db")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_app_engine.cache_clear()
    get_order_engine.cache_clear()
    if not mysql_test:
        Base.metadata.create_all(get_app_engine())
    yield
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    if get_app_engine.cache_info().currsize:
        get_app_engine().dispose()
    get_app_engine.cache_clear()
    if get_order_engine.cache_info().currsize:
        get_order_engine().dispose()
    get_order_engine.cache_clear()
    get_settings.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def close_checkpoint_after_test() -> Iterator[None]:
    yield
    await close_graph()


@pytest.fixture
def seeded_database() -> dict[str, object]:
    return init_database()


@pytest.fixture
def live_server() -> Iterator[str]:
    port = 8765
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise RuntimeError(f"test server exited: {stdout}\n{stderr}")
            try:
                if httpx.get(f"{url}/health", timeout=0.5).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            raise RuntimeError("test server did not become ready")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture
def page() -> Iterator[object]:
    settings = get_settings()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=settings.browser_channel, headless=settings.browser_headless)
        context = browser.new_context(accept_downloads=False)
        page = context.new_page()
        page.set_default_timeout(settings.browser_timeout_ms)
        yield page
        context.close()
        browser.close()
