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
