"""Actual browser layout regression; opt-in, no API/provider or external network."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import pytest

from scripts.browser_local import find_chrome


pytestmark = [pytest.mark.browser_local, pytest.mark.skipif(
    os.getenv("RPG_VISUAL_BROWSER") != "1", reason="RPG_VISUAL_BROWSER=1 required")]


@pytest.mark.parametrize("width", [390, 1440])
def test_portraits_are_uncropped_and_stay_inside_cards(width: int) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    chrome = find_chrome()
    css = (Path(__file__).resolve().parents[1] / "web/src/styles.css").read_text(encoding="utf-8")
    # A portrait fixture with the same shape as the real catalog, no network.
    image_url = "data:image/svg+xml," + quote(
        '<svg xmlns="http://www.w3.org/2000/svg" width="719" height="1079">'
        '<rect width="719" height="1079" fill="tan"/></svg>')
    card = f'''<button class="card"><figure class="visual-art card__art">
        <img src="{image_url}" width="719" height="1079" alt="Portrait"/>
        <figcaption><strong>Name</strong></figcaption></figure>
        <span class="card__name">Name</span></button>'''
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(chrome) if chrome else None, headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            page.route("http://**/*", lambda route: route.abort())
            page.route("https://**/*", lambda route: route.abort())
            page.set_content(f'''<style>{css}</style><main style="padding:20px;max-width:900px">
                <div class="cards">{card}{card}</div>
                <figure class="visual-art msg__visual"><img src="{image_url}"
                    width="719" height="1079" alt="Narrative portrait"/></figure></main>''')
            page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
            rows = page.locator(".card").evaluate_all('''cards => cards.map(c => {
                const f=c.querySelector('figure'), i=f.querySelector('img');
                const cb=c.getBoundingClientRect(), fb=f.getBoundingClientRect();
                return {left:fb.left-cb.left, right:cb.right-fb.right,
                    fit:getComputedStyle(i).objectFit,
                    caption:getComputedStyle(f.querySelector('figcaption')).display,
                    ratio:i.clientWidth/i.clientHeight};
            })''')
            for row in rows:
                assert row["fit"] == "contain"
                assert row["left"] >= -1 and row["right"] >= -1
                assert row["caption"] == "none"
                assert row["ratio"] == pytest.approx(2 / 3, abs=0.01)
            assert page.locator(".msg__visual img").evaluate(
                "i => getComputedStyle(i).objectFit") == "contain"
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        finally:
            browser.close()
