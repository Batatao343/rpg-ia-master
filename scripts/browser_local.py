"""Gut-check visual local reproduzível com Playwright Python."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def find_chrome() -> Path | None:
    configured = os.getenv("RPG_BROWSER_EXECUTABLE")
    if configured:
        path = Path(configured)
        if not path.is_file():
            raise RuntimeError("RPG_BROWSER_EXECUTABLE não existe")
        return path
    root = Path.home() / ".agent-browser" / "browsers"
    candidates = list(root.glob("chrome-*/chrome.exe" if os.name == "nt" else "chrome-*/chrome"))
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def _probe_viewport(browser: Any, base_url: str, width: int, height: int) -> dict:
    page = browser.new_page(viewport={"width": width, "height": height})
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_responses: list[dict[str, object]] = []
    page.on(
        "console",
        lambda message: console_errors.append(message.text[:300])
        if message.type == "error" else None,
    )
    page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
    page.on(
        "response",
        lambda item: failed_responses.append({
            "status": item.status,
            "origin": urlsplit(item.url).netloc,
            "path": urlsplit(item.url).path[:160],
        }) if item.status >= 400 else None,
    )
    try:
        response = page.goto(base_url, wait_until="networkidle", timeout=30_000)
        layout = None
        previous = None
        stable_samples = 0
        for _ in range(8):
            page.wait_for_timeout(250)
            layout = page.evaluate("""({
                scrollWidth: document.documentElement.scrollWidth,
                clientWidth: document.documentElement.clientWidth
            })""")
            stable_samples = stable_samples + 1 if layout == previous else 0
            previous = layout
            if stable_samples >= 2:
                break
        dimensions = layout or {"scrollWidth": 0, "clientWidth": 0}
        content = bool(page.locator("body").inner_text().strip())
        overflow = dimensions["scrollWidth"] > dimensions["clientWidth"]
        overflow_elements = page.evaluate("""
            [...document.querySelectorAll('body *')].filter((element) => {
              const box = element.getBoundingClientRect();
              return box.right > document.documentElement.clientWidth + 1 || box.left < -1;
            }).slice(0, 8).map((element) => ({
              tag: element.tagName.toLowerCase(),
              className: String(element.className || '').slice(0, 80)
            }))
        """)
        overlay = bool(page.locator(
            ".vite-error-overlay,#webpack-dev-server-client-overlay,[data-nextjs-dialog]"
        ).count())
        invalid_scene_aria = bool(page.locator(".scene-art[aria-label]").count())
        passed = bool(
            response and response.ok and content and not overflow and not overlay
            and not console_errors and not page_errors and not invalid_scene_aria
        )
        return {
            "width": width, "height": height,
            "http_status": response.status if response else None,
            "content": content, "overflow": overflow,
            "dimensions": dimensions, "overflow_elements": overflow_elements,
            "error_overlay": overlay, "console_errors": console_errors,
            "page_errors": len(page_errors),
            "failed_responses": failed_responses,
            "invalid_scene_aria": invalid_scene_aria,
            "passed": passed,
        }
    finally:
        page.close()


def run(base_url: str, *, output: Path | None = None) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("browser gate exige: uv sync --extra browser") from exc

    result = {"status": "passed", "viewports": {}, "errors": []}
    with sync_playwright() as playwright:
        executable = find_chrome()
        browser = playwright.chromium.launch(
            executable_path=str(executable) if executable else None,
            headless=True,
        )
        try:
            for label, width, height in (("desktop", 1440, 900), ("mobile_390", 390, 844)):
                probe = _probe_viewport(browser, base_url, width, height)
                if not probe["passed"]:
                    first = probe
                    probe = _probe_viewport(browser, base_url, width, height)
                    probe["retry"] = {
                        "performed": True,
                        "first_console_errors": first["console_errors"],
                        "first_overflow": first["overflow"],
                    }
                result["viewports"][label] = probe
                if not probe["passed"]:
                    result["errors"].append(label)
        finally:
            browser.close()
    result["status"] = "passed" if not result["errors"] else "failed"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result["errors"]:
        raise RuntimeError(json.dumps(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--output", type=Path, default=Path("readiness_artifacts/browser.json"),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.base_url, output=args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
