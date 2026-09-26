"""Authenticated local browser smoke. No real LLM or image provider."""
from __future__ import annotations

import os
from pathlib import Path
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
            assert page.locator('.topbar__right button').evaluate_all('''buttons => buttons.every((a, i) => {
                const x = a.getBoundingClientRect();
                return buttons.slice(i + 1).every(b => {
                    const y = b.getBoundingClientRect();
                    return x.right <= y.left || y.right <= x.left || x.bottom <= y.top || y.bottom <= x.top;
                });
            })''')
            assert page.get_by_role('button', name='Encerrar sessão').evaluate('e => !!e.closest(".topbar")')
            before = page.request.get(base + '/game/history', params={'game_id': gid}).json()
            text = 'Observo o ambiente com atenção.'
            sent = []
            page.on('request', lambda request: sent.append(request.post_data_json)
                    if request.url.endswith('/game/action/stream') else None)
            # Server commits, but neither transport delivers confirmation.
            def lose_confirmation(route):
                response = route.fetch(timeout=45_000)
                assert response.status == 200
                route.abort('failed')
            page.route('**/game/action/stream', lose_confirmation)
            page.route('**/game/action', lambda route: route.abort('failed'))
            page.get_by_placeholder('O que você faz?', exact=False).fill(text)
            page.get_by_role('button', name='Agir', exact=True).click()
            resume = page.get_by_role('button', name='Consultar / retomar ação pendente')
            pw.expect(resume).to_be_enabled(timeout=45_000)
            pending_keys = page.evaluate("Object.keys(localStorage).filter(k => k.startsWith('valoria:pending:'))")
            assert len(pending_keys) == 1
            page.unroute('**/game/action/stream', lose_confirmation)
            page.unroute('**/game/action')
            # Recover from the committed operation receipt, not another turn.
            resume.click()
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
            refresh_requests = []
            history_attempts = []
            page.on('request', lambda request: refresh_requests.append(request.url)
                    if request.url.endswith('/auth/refresh') else None)
            def expire_history_once(route):
                history_attempts.append(route.request.url)
                if len(history_attempts) == 1:
                    route.fulfill(status=401, content_type='application/json', body='{"detail":"expired"}')
                else:
                    route.continue_()
            page.route('**/game/history?*', expire_history_once)
            page.reload()
            page.get_by_role('button', name='Auditoria', exact=False).first.click()
            page.get_by_text(text, exact=True).wait_for()
            assert len(history_attempts) >= 2
            assert len(refresh_requests) == 1
            csrf = next(c['value'] for c in context.cookies() if c['name'] == 'rpg_csrf')
            headers = {'X-CSRF-Token': csrf, 'Origin': base}
            # A late response from the old campaign cannot replace the new one.
            second_payload = {**payload, 'name': 'Outra Auditoria', 'action_id': str(uuid4())}
            second = page.request.post(base + '/game/new', data=second_payload, headers=headers)
            assert second.status == 200, second.text()
            second_gid = second.json()['game_id']
            late_text = 'Examino o selo uma última vez.'
            page.route('**/game/action/stream', lose_confirmation)
            page.route('**/game/action', lambda route: route.abort('failed'))
            page.get_by_placeholder('O que você faz?', exact=False).fill(late_text)
            page.get_by_role('button', name='Agir', exact=True).click()
            resume.wait_for(state='visible', timeout=45_000)
            pw.expect(resume).to_be_enabled(timeout=45_000)
            page.unroute('**/game/action/stream', lose_confirmation)
            page.unroute('**/game/action')
            page.evaluate('''() => {
              const original = window.fetch.bind(window);
              let release;
              window.__auditReleaseState = () => release?.();
              window.__auditHoldState = true;
              window.fetch = async (...args) => {
                const response = await original(...args);
                const url = String(args[0]);
                if (window.__auditHoldState && url.includes('/game/state')) {
                  window.__auditHoldState = false;
                  window.__auditStateHeld = true;
                  await new Promise(resolve => { release = resolve; });
                }
                return response;
              };
            }''')
            resume.click()
            page.wait_for_function('window.__auditStateHeld === true', timeout=30_000)
            page.evaluate("window.dispatchEvent(new Event('rpg:auth-expired'))")
            page.get_by_label('E-mail', exact=True).fill(email)
            page.get_by_label('Senha', exact=True).fill('LocalAuditOnly-2026!')
            page.get_by_role('button', name='Entrar', exact=True).click()
            page.get_by_role('button', name='Outra Auditoria', exact=False).first.click()
            page.get_by_placeholder('O que você faz?', exact=False).wait_for(timeout=30_000)
            page.evaluate('window.__auditReleaseState()')
            page.wait_for_timeout(500)
            assert page.evaluate("localStorage.getItem('cronicas_game_id')") == second_gid
            assert not errors
            artifacts = Path(os.getenv('RPG_AUDIT_ARTIFACTS', str(tmp_path)))
            artifacts.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(artifacts / f'audit-{width}.png'))
            # Only this test's synthetic game. Auth fixtures remain local only.
            page.request.delete(base + f'/game/save/{gid}', headers={**headers, 'Idempotency-Key': str(uuid4())})
            page.request.delete(base + f'/game/save/{second_gid}', headers={**headers, 'Idempotency-Key': str(uuid4())})
        finally:
            browser.close()
            for cleanup in cleanups:
                cleanup()
