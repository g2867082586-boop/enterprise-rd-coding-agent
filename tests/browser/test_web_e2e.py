import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page

from app.config import ROOT_DIR


def wait_for(url: str, process: subprocess.Popen[str]) -> None:
    for _ in range(120):
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(f"development service exited: {stdout}\n{stderr}")
        try:
            if httpx.get(url, timeout=0.5).status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError(f"service did not become ready: {url}")


@pytest.fixture
def web_stack(tmp_path: Path) -> Iterator[str]:
    backend_url = "http://127.0.0.1:8766"
    frontend_url = "http://127.0.0.1:5174"
    env = os.environ.copy()
    env.update({
        "DATABASE_PROVIDER": "sqlite",
        "SQLITE_PATH": str(tmp_path / "web-e2e.db"),
        "FRONTEND_URL": frontend_url,
        "VITE_API_BASE_URL": backend_url,
        "KNOWLEDGE_CORPUS": "mock",
    })
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT_DIR, env=env, check=True, capture_output=True, text=True,
    )
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8766"],
        cwd=ROOT_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    node = shutil.which("node")
    vite = ROOT_DIR / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    if not node or not vite.exists():
        backend.terminate()
        pytest.skip("frontend dependencies are not installed")
    frontend = subprocess.Popen(
        [node, str(vite), "--host", "127.0.0.1", "--port", "5174"],
        cwd=ROOT_DIR / "frontend", env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        wait_for(f"{backend_url}/health", backend)
        wait_for(frontend_url, frontend)
        yield frontend_url
    finally:
        for process in (frontend, backend):
            process.terminate()
        for process in (frontend, backend):
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.mark.browser
def test_register_login_chat_history_sources_and_logout_in_google_chrome(
    web_stack: str, page: Page
) -> None:
    page.goto(f"{web_stack}/register", wait_until="networkidle")
    page.get_by_label("用户名").fill("chrome_e2e_user")
    page.get_by_label("显示名称").fill("Chrome 验收用户")
    page.get_by_label("邮箱").fill("chrome-e2e@example.test")
    page.get_by_label("密码", exact=True).fill("Chrome12345")
    page.get_by_label("确认密码").fill("Chrome12345")
    page.get_by_role("button", name="创建账号").click()
    page.wait_for_url("**/login")

    page.get_by_label("用户名或邮箱").fill("chrome_e2e_user")
    page.get_by_label("密码").fill("Chrome12345")
    page.get_by_role("button", name="进入工作台").click()
    page.wait_for_url("**/chat")
    page.get_by_role("button", name="用户登录接口需要哪些参数？").click()
    page.get_by_text("星云助手").wait_for(timeout=60_000)
    source_button = page.get_by_role("button", name=re.compile(r"查看 \d+ 个知识来源"))
    source_button.wait_for(timeout=60_000)
    source_button.click()
    page.get_by_role("heading", name="用户服务接口").wait_for()

    page.reload(wait_until="networkidle")
    page.get_by_text("用户登录接口需要哪些参数？", exact=True).last.wait_for()
    screenshot = ROOT_DIR / "data" / "screenshots" / "web-e2e-chrome.png"
    page.screenshot(path=str(screenshot), full_page=True)
    page.get_by_label("退出登录").click()
    page.wait_for_url("**/login")
    page.goto(f"{web_stack}/chat")
    page.wait_for_url("**/login")
