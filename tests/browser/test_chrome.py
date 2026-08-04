from pathlib import Path

import pytest

from app.tools.browser_tool import browser_check


@pytest.mark.browser
def test_installed_google_chrome_checks_local_page(live_server) -> None:
    result = browser_check(f"{live_server}/", "系统运行正常", "#system-status", "pytest-browser")
    assert result["ok"], result
    assert result["browser_channel"] == "chrome"
    assert Path(result["screenshot_path"]).exists()
    assert not result["console_errors"]

