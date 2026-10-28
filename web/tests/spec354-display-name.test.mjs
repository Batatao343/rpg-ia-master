// SPEC-354 R9.3: nunca um id cru como nome exibível.
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

test('humaniza_ids', async () => {
  const { humanizeId, looksLikeId, displayName } = await load('../src/combat/displayName.ts');
  assert.equal(humanizeId('npc_ketil'), 'Ketil');
  assert.equal(humanizeId('enemy_goblin_2'), 'Goblin 2');
  assert.equal(looksLikeId('npc_ketil'), true);
  assert.equal(looksLikeId('Ketil'), false);
  assert.equal(displayName('npc_ketil', 'npc_ketil'), 'Ketil');
  assert.equal(displayName('Ketil', 'npc_ketil'), 'Ketil');
  assert.equal(displayName('Saqueador de Marfim', 'enemy_x_1'), 'Saqueador de Marfim');
});

test('prefere_nome_de_npc_e_do_grupo_conhecidos', async () => {
  const { displayName } = await load('../src/combat/displayName.ts');
  assert.equal(displayName('npc_ketil', 'npc_ketil', { npcs: [{ name: 'Ketil Pé-de-Ferro' }] }), 'Ketil Pé-de-Ferro');
  assert.equal(displayName('npc_mirela', 'npc_mirela', { party: [{ name: 'Mirela' }] }), 'Mirela');
  assert.equal(displayName('enemy_x_1', 'enemy_x_1', { labels: new Map([['enemy_x_1', 'Bandido']]) }), 'Bandido');
});
