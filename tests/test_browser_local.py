from __future__ import annotations

import os

import pytest

from scripts.browser_local import find_chrome, run


pytestmark = pytest.mark.browser_local


def test_browser_encontra_chrome_local_sem_cloud():
    chrome = find_chrome()
    if chrome is not None:
        assert chrome.is_file()
        assert ".agent-browser" in str(chrome)


def test_browser_real_desktop_mobile_opt_in(tmp_path):
    base_url = os.getenv("RPG_BROWSER_BASE_URL")
    if not base_url:
        pytest.skip("RPG_BROWSER_BASE_URL ausente")
    result = run(base_url, output=tmp_path / "browser.json")
    assert result["status"] == "passed"
    assert result["viewports"]["mobile_390"]["overflow"] is False
