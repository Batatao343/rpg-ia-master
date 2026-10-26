// SPEC-216 Etapa 1: superficie mobile derivada do workspace da SPEC-204 (sem estado proprio).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const model = await load('../src/workspace/workspaceModel.ts');
const surf = await load('../src/workspace/mobileSurface.ts');
const { DEFAULT_WORKSPACE: D, workspaceReducer: r, effectiveMode, CONTEXT_TABS } = model;
const { mobileSurface, isMobileViewport, shouldAutoOpenCombat, SURFACES, SURFACE_LABELS, registerBackBridge, offChatSurface, returnToChat } = surf;

test('mobile_surface_single_below_breakpoint: nunca dois valores visiveis', () => {
  const states = [D, r(D, { type: 'open_tab', tab: 'mapa', single: true }), r(D, { type: 'set_mode', mode: 'chat' }),
    r(D, { type: 'set_mode', mode: 'context' }), r(D, { type: 'toggle_split' }), r(D, { type: 'combat_started' })];
  for (const px of [320, 390, 768, 899]) {
    assert.equal(isMobileViewport(px), true);
    for (const s of states) {
      const v = mobileSurface(s, px);
      assert.ok(v === 'chat' || CONTEXT_TABS.includes(v), `${px}: ${v}`);
    }
  }
  assert.equal(isMobileViewport(900), false);
  assert.deepEqual([...SURFACES], ['chat', ...CONTEXT_TABS]);
});

test('mobile_surface_matches_effectiveMode_900_1100', () => {
  for (const s of [D, r(D, { type: 'open_tab', tab: 'bestiario', single: true }), r(D, { type: 'set_mode', mode: 'context' })]) {
    for (const px of [320, 600, 899, 900, 1000, 1099]) {
      assert.equal(mobileSurface(s, px) === 'chat', effectiveMode(s, px) !== 'context');
      assert.notEqual(effectiveMode(s, px), 'split');
    }
  }
});

test('switch_and_back_preserves_draft_and_pending: a troca so mexe na apresentacao', () => {
  const a = r(D, { type: 'open_tab', tab: 'codex', single: true });
  assert.equal(mobileSurface(a, 390), 'codex');
  const b = r(a, { type: 'close_context', single: true });
  assert.equal(mobileSurface(b, 390), 'chat');
  // a aba e o historico seguem no reducer da 204; rascunho/ação pendente vivem em outros modulos (nao tocados)
  assert.equal(b.tab, 'codex');
  assert.deepEqual(b.history, a.history);
  assert.equal(mobileSurface(r(b, { type: 'open_tab', tab: 'codex', single: true }), 390), 'codex');
});

test('combat_started_offers_combat_after_narration', () => {
  assert.equal(shouldAutoOpenCombat(false, true, false), false);
  assert.equal(shouldAutoOpenCombat(false, true, true), true);
  assert.equal(shouldAutoOpenCombat(true, true, true), false);
  assert.equal(shouldAutoOpenCombat(false, false, true), false);
  assert.equal(mobileSurface(r(D, { type: 'combat_started' }), 390), 'combate');
});

test('back_policy_returns_to_chat_first', async () => {
  const { decideBack } = await load('../src/native/backPolicy.ts');
  assert.equal(decideBack('play', false, false, true), 'chat');
  assert.equal(decideBack('play', true, true, true), 'chat');   // voltar ao chat e seguro mesmo ocupado
  assert.equal(decideBack('play', false, false, false), 'minimize');
  assert.equal(decideBack('play', true, false, false), 'ignore');
  // ponte: so volta quando ha outra superficie
  assert.equal(returnToChat(), false);
  let surface = 'mapa';
  const off = registerBackBridge({ offChat: () => surface !== 'chat', toChat: () => { surface = 'chat'; } });
  assert.equal(offChatSurface(), true);
  assert.equal(returnToChat(), true);
  assert.equal(surface, 'chat');
  assert.equal(returnToChat(), false);
  off();
  assert.equal(offChatSurface(), false);
});

test('SPEC-321 R11: o rótulo da superfície chat é "Crônica" (id inalterado)', () => {
  assert.equal(SURFACE_LABELS.chat, 'Crônica');
  assert.ok(SURFACES.includes('chat'));
});
