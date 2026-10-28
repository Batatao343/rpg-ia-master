// SPEC-347: marcação SSR dos componentes do tabuleiro (prévia pendente, fila, Arena, Hud, RoundBoard, TargetChip, Composer).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'cjs', platform: 'node', jsx: 'automatic', logLevel: 'silent',
    external: ['react', 'react-dom', 'react/jsx-runtime'] });
  const mod = { exports: {} };
  new Function('module', 'exports', 'require', outputFiles[0].text)(mod, mod.exports, require);
  return mod.exports;
}
const { renderToStaticMarkup: html } = require('react-dom/server');
const h = require('react').createElement;

test('previewchip_pending_mostra_lendo_os_sinais', async () => {
  const { PreviewChip } = await load('../src/components/combat/PreviewChip.tsx');
  assert.match(html(h(PreviewChip, { state: { status: 'pending' } })), /Lendo os sinais…/);
  assert.equal(html(h(PreviewChip, { state: { status: 'idle' } })), '');
});

test('playqueue_desfazer_fila_na_fila_e_selo', async () => {
  const { PlayQueue } = await load('../src/components/combat/PlayQueue.tsx');
  const q = [{ uid: 'p1', name: 'Golpe', cardId: 'golpe', targetId: 'e1' }, { uid: 'p2', name: 'Corte', cardId: 'corte', targetId: 'e1' }];
  const out = html(h(PlayQueue, { queue: q, selected: null, nameOf: () => 'X', busy: false, onSelect() {}, onMove() {}, onRemove() {}, onClear() {}, onEnd() {}, touch: true }));
  assert.match(out, /play-queue__clear--inline/);
  assert.match(out, /play-queue__badge" aria-hidden="true">2</);
  assert.match(out, /aria-label="Encerrar a rodada, 2 cartas"/);
});

const combatBase = { round: 3, order: [{ name: 'Inimigos', side: 'enemy', init: 0 }, { name: 'Heróis', side: 'hero', init: 0 }],
  enemies: [], scene: { zones: [{ id: 'a', name: 'Ponte', connections: [] }, { id: 'b', name: 'Vão', connections: [] }], positions: [
    { participant_id: 'player', participant_name: 'Ayla', zone_id: 'a', distance: 'proximo', posture: 'neutro', concealment: 'visivel', engaged_with: [], engaged_names: [] }] },
  wounds: { vitality: 5, max_vitality: 8, slots: {}, by_severity: {} }, player_conditions: [], chase: null };

test('arena_iniciativa_honesta_e_compact', async () => {
  const { Arena } = await load('../src/combat/Arena.tsx');
  const full = html(h(Arena, { combat: combatBase, party: [], onPick() {} }));
  assert.match(full, /Na última rodada, Inimigos agiram primeiro\./);
  assert.doesNotMatch(full, /iniciativa:|Rodada 3/);
  assert.match(full, /Zona: Vão/);
  const compact = html(h(Arena, { combat: combatBase, party: [], onPick() {}, compact: true }));
  assert.match(compact, /arena--compact/);
  assert.doesNotMatch(compact, /Zona: Vão/);
  assert.match(compact, /Também na cena: Vão/);
});

test('hud_rodada_uma_vez_e_sem_zero', async () => {
  const { CombatTab } = await load('../src/components/Hud.tsx');
  const c = { ...combatBase, active: true, enemies: [{ id: 'e1', name: 'X', vitalidade: 3, max_vitalidade: 3, esquiva: 5, protecao: 0, conditions: [], revealed_cards: [], revealed_resistances: [] }],
    cooldowns: {}, cards: [] };
  const off = html(h(CombatTab, { c, hitKey: 0, party: [] }));
  assert.equal((off.match(/Rodada/g) || []).length, 1);
  assert.doesNotMatch(off, /\b0 · /);
  assert.match(off, /Inimigos/);
  const deck = html(h(CombatTab, { c, hitKey: 0, party: [], deck: true }));
  assert.doesNotMatch(deck, /Rodada/);
  const withArena = html(h(CombatTab, { c, hitKey: 0, party: [], arena: true, deck: true }));
  assert.doesNotMatch(withArena, /class="initiative"/);
});
