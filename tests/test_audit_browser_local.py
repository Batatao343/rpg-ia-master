"""Authenticated local browser smoke. No real LLM or image provider."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from scripts.browser_local import find_chrome

pytestmark = pytest.mark.browser_local


@pytest.mark.parametrize('width', [390, 1440])
def test_authenticated_stream_reload_history_and_art_dialog(width, tmp_path):
    base = os.getenv('RPG_AUDIT_BROWSER_URL')
    if not base:
        pytest.skip('RPG_AUDIT_BROWSER_URL required (audit_local_server only)')
    from urllib.parse import urlsplit
    assert urlsplit(base).hostname in {'127.0.0.1', 'localhost'}
    pw = pytest.importorskip('playwright.sync_api')
    chrome = find_chrome()
    email = f'audit-{uuid4().hex}@example.test'
    with pw.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=str(chrome) if chrome else None, headless=True)
        context = browser.new_context(viewport={'width': width, 'height': 900})
        page = context.new_page()
        errors = []
        cleanups = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        try:
            page.goto(base)
            page.get_by_label('E-mail', exact=True).fill(email)
            page.get_by_label('Senha', exact=True).fill('LocalAuditOnly-2026!')
            page.get_by_role('button', name='Criar uma conta local').click()
            page.get_by_role('button', name='Criar conta', exact=True).click()
            page.get_by_role('button', name='2 Origem').wait_for(timeout=30_000)
            page.get_by_role('button', name='2 Origem').click()
            enlarge = page.get_by_role('button', name='Ampliar imagem de').first
            enlarge.click()
            dialog = page.get_by_role('dialog')
            assert dialog.is_visible()
            assert dialog.locator('img').evaluate('i => getComputedStyle(i).objectFit') == 'contain'
            page.keyboard.press('Escape')
            assert not dialog.count()
            assert enlarge.evaluate('e => document.activeElement === e')
            assert not page.locator('button button').count()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')

            csrf = next(c['value'] for c in context.cookies() if c['name'] == 'rpg_csrf')
            headers = {'X-CSRF-Token': csrf, 'Origin': base}
            options = page.request.get(base + '/data/options').json()
            payload = {'name': 'Auditoria', 'class_name': options['classes'][0],
                       'race': options['races'][0], 'region': options['regions'][0],
                       'action_id': str(uuid4())}
            created = page.request.post(base + '/game/new', data=payload, headers=headers)
            assert created.status == 200, created.text()
            gid = created.json()['game_id']
            art = page.request.post(base + f'/game/{gid}/art/player/confirm',
                                    data={'action_id': str(uuid4())}, headers=headers)
            assert art.status == 200, art.text()
            from tests.fakes.local_portrait import publish_portrait
            cleanups.append(publish_portrait(gid, art.json()['generation_id']))
            reloaded_state = page.request.get(base + '/game/state', params={'game_id': gid}).json()
            assert reloaded_state['portrait_generation_id'] == art.json()['generation_id']
            art_status = page.request.get(base + f"/game/{gid}/art/{art.json()['generation_id']}").json()
            assert art_status['status'] == 'ready' and len(art_status['assets']) == 2
            page.reload()
            page.get_by_role('button', name='Auditoria', exact=False).first.click()
            page.get_by_placeholder('O que você faz?', exact=False).wait_for(timeout=15_000)
            portrait = page.locator('.generated-portrait img')
            portrait.wait_for(state='attached')
            page.wait_for_function("document.querySelector('.generated-portrait img')?.naturalWidth > 0")
            assert portrait.evaluate('i => getComputedStyle(i).objectFit') == 'contain'
            before = page.request.get(base + '/game/history', params={'game_id': gid}).json()
            text = 'Observo o ambiente com atenção.'
            sent = []
            page.on('request', lambda request: sent.append(request.post_data_json)
                    if request.url.endswith('/game/action/stream') else None)
            page.get_by_placeholder('O que você faz?', exact=False).fill(text)
            with page.expect_response(lambda r: '/game/action/stream' in r.url, timeout=45_000):
                page.get_by_role('button', name='Agir', exact=True).click()
            page.wait_for_function("!Object.keys(localStorage).some(k => k.startsWith('valoria:pending:'))", timeout=45_000)
            after = page.request.get(base + '/game/history', params={'game_id': gid}).json()
            assert len(after['entries']) >= len(before['entries']) + 2
            assert sum(e['text'] == text for e in after['entries']) == 1
            assert len(sent) == 1
            replay = page.request.post(base + '/game/action', data=sent[0], headers=headers)
            assert replay.status == 200, replay.text()
            replay_history = page.request.get(base + '/game/history', params={'game_id': gid}).json()
            assert replay_history == after
            divergent = page.request.post(base + '/game/action',
                data={**sent[0], 'input_text': 'Uma ação diferente com o mesmo ID.'}, headers=headers)
            assert divergent.status == 409
            page.reload()
            page.get_by_role('button', name='Auditoria', exact=False).first.click()
            page.get_by_text(text, exact=True).wait_for()
            assert not errors
            page.screenshot(path=str(tmp_path / f'audit-{width}.png'))
            # Only this test's synthetic game. Auth fixtures remain local only.
            page.request.delete(base + f'/game/save/{gid}', headers={**headers, 'Idempotency-Key': str(uuid4())})
        finally:
            browser.close()
            for cleanup in cleanups:
                cleanup()
