// SPEC-389 R15: o "Acervo de Cartas" da Ficha mostra o rótulo de subclasse (facção) da Carta.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'cjs', platform: 'node', jsx: 'automatic', logLevel: 'silent',
    loader: { '.svg': 'dataurl', '.png': 'dataurl', '.webp': 'dataurl', '.css': 'empty' },
    external: ['react', 'react-dom', 'react/jsx-runtime'] });
  const mod = { exports: {} };
  new Function('module', 'exports', 'require', outputFiles[0].text)(mod, mod.exports, require);
  return mod.exports;
}
const { renderToStaticMarkup: html } = require('react-dom/server');
const h = require('react').createElement;

const card = (over) => ({ id: 'c', name: 'Pó nos Olhos', type: 'ativa', description: '', effect_kind: 'x', target_kind: 'enemy',
  subclass: '', prepared: true, cost: 1, frequency: 'rodada', spent: false, ready: true, has_rupture: false, ...over });
const data = (cards) => ({ player_stats: { vitalidade: 10, max_vitalidade: 10, entropy: 0, max_entropy: 0, level: 1, gold: 0, defense: 0,
  virtudes: {}, cards, pending_choices: [] }, inventory: [] });

test('acervo_mostra_subclasse_da_carta', async () => {
  const { FichaTab } = await load('../src/components/Hud.tsx');
  const withSub = html(h(FichaTab, { data: data([card({ subclass: 'Mão Sombria' })]), hpHitKey: 0 }));
  assert.match(withSub, /Pó nos Olhos[^<]*· Mão Sombria/);
  const without = html(h(FichaTab, { data: data([card({})]), hpHitKey: 0 }));
  assert.doesNotMatch(without, /Mão Sombria/);
});
