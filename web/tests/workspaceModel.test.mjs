// SPEC-204: reducer/clamp/storage do workspace (chat + contexto), sem React.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const model = await load('../src/workspace/workspaceModel.ts');
const { DEFAULT_WORKSPACE: D, workspaceReducer: r, clampRatio, effectiveMode } = model;

function storage({ throwing = false } = {}) {
  const data = {};
  const impl = { getItem: key => data[key] ?? null, key: i => Object.keys(data)[i],
    get length() { return Object.keys(data).length; },
    setItem: (key, value) => { data[key] = String(value); }, removeItem: key => { delete data[key]; } };
  if (throwing) {
    Object.defineProperty(globalThis, 'localStorage', { configurable: true, get() { throw new Error('SecurityError'); } });
  } else {
    Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: impl, writable: true });
  }
  return data;
}

test('default_is_split_half', () => {
  assert.equal(D.version, 1);
  assert.equal(D.mode, 'split');
  assert.ok(Math.abs(D.ratio - 0.5) <= 0.01);
  assert.deepEqual(D.history, [D.tab]);
  assert.equal(D.cursor, 0);
});

test('open_tab_from_chat_goes_split', () => {
  const chat = r(D, { type: 'set_mode', mode: 'chat' });
  assert.equal(chat.mode, 'chat');
  const s = r(chat, { type: 'open_tab', tab: 'mapa' });
  assert.equal(s.mode, 'split');
  assert.equal(s.tab, 'mapa');
  assert.equal(s.history.at(-1), 'mapa');
  // context continua context
  const ctx = r(r(D, { type: 'set_mode', mode: 'context' }), { type: 'open_tab', tab: 'codex' });
  assert.equal(ctx.mode, 'context');
});

test('open_same_tab_does_not_push_history', () => {
  const s = r(D, { type: 'open_tab', tab: D.tab });
  assert.deepEqual(s.history, D.history);
});

test('history_back_forward_and_cap_50', () => {
  let s = r(D, { type: 'open_tab', tab: 'mapa' });
  s = r(s, { type: 'open_tab', tab: 'codex' });
  s = r(s, { type: 'back' });
  assert.equal(s.tab, 'mapa');
  s = r(s, { type: 'back' });
  assert.equal(s.tab, D.tab);
  const atStart = r(s, { type: 'back' });
  assert.equal(atStart, s, 'back no início é no-op');
  s = r(s, { type: 'forward' });
  s = r(s, { type: 'forward' });
  assert.equal(s.tab, 'codex');
  assert.equal(r(s, { type: 'forward' }), s, 'forward no fim é no-op');
  const tabs = ['codex', 'personagem', 'combate', 'bestiario', 'mapa'];
  for (let i = 0; i < 120; i++) s = r(s, { type: 'open_tab', tab: tabs[i % 5] });
  assert.equal(s.history.length, 50);
  assert.equal(s.cursor, 49);
  assert.equal(s.tab, s.history[49]);
});

test('back_from_chat_reopens_split', () => {
  let s = r(D, { type: 'open_tab', tab: 'mapa' });
  s = r(s, { type: 'set_mode', mode: 'chat' });
  s = r(s, { type: 'back' });
  assert.equal(s.mode, 'split');
  assert.equal(s.tab, D.tab);
});

test('open_after_back_truncates_forward', () => {
  let s = r(D, { type: 'open_tab', tab: 'mapa' });
  s = r(s, { type: 'open_tab', tab: 'codex' });
  s = r(s, { type: 'back' });
  s = r(s, { type: 'open_tab', tab: 'bestiario' });
  assert.deepEqual(s.history, [D.tab, 'mapa', 'bestiario']);
  assert.equal(r(s, { type: 'forward' }), s);
});

test('combat_started_from_chat_opens_combate_split', () => {
  let s = r(D, { type: 'set_ratio', ratio: 0.8 });
  s = r(s, { type: 'set_mode', mode: 'chat' });
  s = r(s, { type: 'combat_started' });
  assert.equal(s.mode, 'split');
  assert.equal(s.tab, 'combate');
  assert.ok(Math.abs(s.ratio - 0.5) <= 0.01);
  assert.equal(s.lastSolo, 'context', 'telas estreitas mostram o Combate');
});

test('combat_started_in_context_switches_tab_only', () => {
  let s = r(D, { type: 'set_mode', mode: 'context' });
  s = r(s, { type: 'set_ratio', ratio: 0.7 });
  s = r(s, { type: 'combat_started' });
  assert.equal(s.mode, 'context');
  assert.equal(s.tab, 'combate');
  assert.equal(s.ratio, 0.7);
  const split = r(r(D, { type: 'set_ratio', ratio: 0.6 }), { type: 'combat_started' });
  assert.equal(split.mode, 'split');
  assert.equal(split.ratio, 0.6);
});

test('combat_ended_keeps_combate_tab', () => {
  const s = r(r(D, { type: 'combat_started' }), { type: 'combat_ended' });
  assert.equal(s.tab, 'combate');
  assert.equal(s.mode, 'split');
});

test('toggle_split_and_last_solo', () => {
  let s = r(D, { type: 'set_mode', mode: 'context' });
  s = r(s, { type: 'set_mode', mode: 'split' });
  s = r(s, { type: 'toggle_split' });
  assert.equal(s.mode, 'context');
  s = r(s, { type: 'toggle_split' });
  assert.equal(s.mode, 'split');
});

test('close_context_wide_and_single', () => {
  const wide = r(D, { type: 'close_context', single: false });
  assert.equal(wide.mode, 'chat');
  const single = r(r(D, { type: 'open_tab', tab: 'mapa', single: true }), { type: 'close_context', single: true });
  assert.equal(single.mode, 'split', 'preferência split preservada em tela estreita');
  assert.equal(effectiveMode(single, 390), 'chat');
});

test('set_ratio_bounds', () => {
  assert.equal(r(D, { type: 'set_ratio', ratio: 4 }).ratio, 0.95);
  assert.equal(r(D, { type: 'set_ratio', ratio: -1 }).ratio, 0.05);
  assert.equal(r(D, { type: 'set_ratio', ratio: Number.NaN }), D);
});

test('clamp_respects_min_px', () => {
  assert.equal(clampRatio(0.1, 1000), 0.38);
  assert.equal(clampRatio(0.9, 1000), 0.64);
  assert.equal(clampRatio(0.5, 1000), 0.5);
  assert.equal(clampRatio(0.2, 600), 0.5, 'sem espaço para ambos: volta ao centro');
});

test('effective_mode_below_1100_is_single', () => {
  assert.equal(effectiveMode(D, 1440), 'split');
  assert.equal(effectiveMode(D, 1099), 'chat');
  const opened = r(D, { type: 'open_tab', tab: 'mapa', single: true });
  assert.equal(effectiveMode(opened, 768), 'context');
  assert.equal(opened.mode, 'split');
  assert.equal(effectiveMode(r(D, { type: 'set_mode', mode: 'context' }), 390), 'context');
});

// ---- storage (R9) ----

test('load_invalid_json_returns_default', async () => {
  const data = storage();
  const st = await load('../src/workspace/workspaceStorage.ts');
  data['valoria:workspace:v1:me:g1'] = '{not json';
  assert.equal(st.loadWorkspace('me', 'g1'), null);
  data['valoria:workspace:v1:me:g1'] = JSON.stringify({ version: 1, mode: 'split', ratio: 'x', tab: 'mapa', lastSolo: 'chat' });
  assert.equal(st.loadWorkspace('me', 'g1'), null);
  data['valoria:workspace:v1:me:g1'] = JSON.stringify({ version: 1, mode: 'split', ratio: 0.5, tab: 'ficha', lastSolo: 'chat' });
  assert.equal(st.loadWorkspace('me', 'g1'), null, 'aba antiga/desconhecida é descartada');
});

test('load_wrong_version_returns_default', async () => {
  const data = storage();
  const st = await load('../src/workspace/workspaceStorage.ts');
  data['valoria:workspace:v1:me:g1'] = JSON.stringify({ version: 2, mode: 'split', ratio: 0.5, tab: 'mapa', lastSolo: 'chat' });
  assert.equal(st.loadWorkspace('me', 'g1'), null);
});

test('save_then_load_round_trip_without_history', async () => {
  const data = storage();
  const st = await load('../src/workspace/workspaceStorage.ts');
  let s = r(D, { type: 'open_tab', tab: 'mapa' });
  s = r(s, { type: 'set_ratio', ratio: 0.7 });
  st.saveWorkspace('me', 'g1', s);
  const raw = JSON.parse(data['valoria:workspace:v1:me:g1']);
  assert.equal(raw.history, undefined, 'histórico não é persistido');
  assert.equal(raw.draft, undefined, 'rascunho nunca vai para o disco');
  const back = st.loadWorkspace('me', 'g1');
  assert.equal(back.tab, 'mapa');
  assert.equal(back.ratio, 0.7);
  assert.equal(back.mode, 'split');
  assert.deepEqual(back.history, ['mapa']);
});

test('storage_throwing_is_silent', async () => {
  storage({ throwing: true });
  const st = await load('../src/workspace/workspaceStorage.ts');
  const errors = [];
  const original = console.error;
  console.error = (...args) => errors.push(args);
  try {
    assert.equal(st.loadWorkspace('me', 'g1'), null);
    st.saveWorkspace('me', 'g1', D);
    st.clearWorkspaceOwner('me');
  } finally { console.error = original; }
  assert.deepEqual(errors, []);
});

test('keys_are_owner_and_game_scoped', async () => {
  const data = storage();
  const st = await load('../src/workspace/workspaceStorage.ts');
  st.saveWorkspace('me', 'g1', r(D, { type: 'open_tab', tab: 'mapa' }));
  st.saveWorkspace('me', 'g2', r(D, { type: 'open_tab', tab: 'codex' }));
  st.saveWorkspace('you', 'g1', r(D, { type: 'open_tab', tab: 'bestiario' }));
  assert.ok('valoria:workspace:v1:me:g1' in data);
  assert.equal(st.loadWorkspace('me', 'g1').tab, 'mapa');
  assert.equal(st.loadWorkspace('me', 'g2').tab, 'codex');
  assert.equal(st.loadWorkspace('you', 'g1').tab, 'bestiario');
  assert.equal(st.loadWorkspace('me', 'g3'), null);
});

test('clear_owner_removes_only_owner_keys', async () => {
  const data = storage();
  const st = await load('../src/workspace/workspaceStorage.ts');
  data['valoria:pending:v1:me:g1'] = 'keep';
  st.saveWorkspace('me', 'g1', D);
  st.saveWorkspace('me', 'g2', D);
  st.saveWorkspace('you', 'g1', D);
  st.clearWorkspaceOwner('me');
  assert.deepEqual(Object.keys(data).sort(), ['valoria:pending:v1:me:g1', 'valoria:workspace:v1:you:g1']);
});

// ---- chat session store (R7/R8) ----

test('chat_session_store_is_keyed_by_game', async () => {
  const store = await load('../src/workspace/chatSessionStore.ts');
  store.setChatSession('a', { draft: 'olá' });
  store.setChatSession('a', { scrollTop: 40, atBottom: false });
  store.setChatSession('b', { draft: 'outro' });
  assert.deepEqual(store.getChatSession('a'), { draft: 'olá', scrollTop: 40, atBottom: false });
  assert.equal(store.getChatSession('b').draft, 'outro');
  assert.equal(store.getChatSession('c').draft, '');
  store.forgetChatSession('a');
  assert.equal(store.getChatSession('a').draft, '');
  store.forgetAllChatSessions();
  assert.equal(store.getChatSession('b').draft, '');
});

// ---- inventário (R5): todo filho das 8 abas antigas monta a partir da nova shell ----

test('legacy_tab_inventory_is_mounted_by_new_shell', () => {
  const read = (p) => readFileSync(fileURLToPath(new URL(p, import.meta.url)), 'utf8');
  const shell = ['../src/workspace/ContextSurface.tsx', '../src/workspace/tabs/PersonagemTab.tsx', '../src/components/tabs/CharacterTab.tsx',
    '../src/workspace/tabs/CombateTab.tsx', '../src/workspace/tabs/BestiarioTab.tsx',
    '../src/workspace/tabs/MapTab.tsx']
    .map(read).join('\n');
  for (const name of ['FichaTab', 'CombatTab', 'PeopleTab', 'FactionsTab', 'QuestsTab', 'ChronicleTab',
    'CodexTab', 'WorldMap', 'GeneratedPortrait', 'CardHand', 'ReactionPrompt']) {
    assert.match(shell, new RegExp(`<${name}[\\s/>]`), `${name} deixou de ser montável pela shell`);
  }
  const play = read('../src/components/PlayScreen.tsx');
  for (const name of ['CardHand', 'ReactionPrompt', 'SceneZones', 'WoundTrack', 'Hud']) {
    assert.doesNotMatch(play, new RegExp(`<${name}[\\s/>]`), `${name} não pode renderizar fora da aba (R10)`);
  }
  assert.doesNotMatch(play, /tactical-dock/);
});
