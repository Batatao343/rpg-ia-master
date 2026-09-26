"""Render production components; image failures cannot poison the next asset."""
import os
from pathlib import Path
import subprocess

import pytest

from scripts.browser_local import find_chrome

pytestmark = [pytest.mark.browser_local, pytest.mark.skipif(
    os.getenv('RPG_VISUAL_BROWSER') != '1', reason='RPG_VISUAL_BROWSER=1 required')]


@pytest.fixture(scope='module')
def artwork_bundle(tmp_path_factory):
    output = tmp_path_factory.mktemp('artwork-component-bundle')
    subprocess.run(['npm.cmd' if os.name == 'nt' else 'npm', 'exec', '--', 'vite', 'build',
                    '--config', 'tests/vite.fixture.config.ts', '--outDir', str(output)],
                   cwd=Path(__file__).resolve().parents[1] / 'web', check=True, capture_output=True)
    return output


@pytest.mark.parametrize('width', [390, 1440])
def test_failed_portrait_and_scene_recover_on_asset_change(artwork_bundle, width):
    pw = pytest.importorskip('playwright.sync_api')
    with pw.sync_playwright() as runtime:
        chrome = find_chrome()
        browser = runtime.chromium.launch(executable_path=str(chrome) if chrome else None)
        try:
            page = browser.new_page(viewport={'width': width, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            def route(request):
                name = request.request.url.rsplit('/', 1)[-1]
                if name == 'fixture.js':
                    request.fulfill(path=str(artwork_bundle / name), content_type='text/javascript')
                elif name == 'style.css':
                    request.fulfill(path=str(artwork_bundle / name), content_type='text/css')
                elif name == 'good.svg':
                    request.fulfill(content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="200" height="300"><rect width="200" height="300" fill="tan"/></svg>')
                elif name == '':
                    request.fulfill(content_type='text/html; charset=utf-8', body='<meta charset="utf-8"><link rel="stylesheet" href="/style.css"><div id="fixture"></div><script src="/fixture.js"></script>')
                else:
                    request.abort()
            page.route('**/*', route)
            page.goto('http://fixture.local/')
            assert not errors, errors
            page.wait_for_function('typeof renderArtwork === "function"')
            def render(name):
                image = {'url': f'/{name}.svg', 'width': 200, 'height': 300}
                asset = {'asset_id': name, 'alt': 'Arte teste', 'variants': {'display': image, 'thumbnail': image}, 'placeholder_color': '#221100'}
                page.evaluate('([asset, scene]) => renderArtwork(asset, scene)', [asset, {'asset': asset, 'location_id': name, 'location_name': name, 'scope': 'local'}])
            render('bad')
            page.get_by_text('Arte indisponível', exact=True).wait_for()
            assert page.locator('.visual-art--fallback').count() == 1
            render('good')
            page.wait_for_function('document.images.length === 2 && [...document.images].every(i => i.naturalWidth > 0)')
            assert page.locator('.visual-art--fallback').count() == 0
            assert '280px' in page.locator('.visual-art img').get_attribute('sizes')
            button = page.get_by_role('button', name='Ampliar imagem de good')
            button.click()
            assert page.get_by_role('dialog').locator('img').evaluate('i => getComputedStyle(i).objectFit') == 'contain'
            page.keyboard.press('Escape')
            assert not page.get_by_role('dialog').count()
            assert button.evaluate('e => document.activeElement === e')
        finally:
            browser.close()
