// SPEC-364 R18-R20: rotulo de Estilhas (plural certo), oferta "ate X" e atalho de confirmacao em milli.
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

test('estilhasLabel_singular_so_para_exatamente_1', async () => {
  const { estilhasLabel } = await load('../src/lib/estilhas.ts');
  assert.equal(estilhasLabel(1000), '1 Estilha');
  assert.equal(estilhasLabel('1000'), '1 Estilha');
  assert.equal(estilhasLabel(15), '0,015 Estilhas');
  assert.equal(estilhasLabel(2000), '2 Estilhas');
  assert.equal(estilhasLabel(0), '0 Estilhas');
});

const portrait = (gerar) => ({ estado: 'marcador', src: null, familia: 'bruto', icone: 'dark', alt: 'Retrato de Goblin', proprio: false, gerar });
const part = (gerar) => ({ id: 'e1', name: 'Goblin', role: 'enemy', conditions: [], intel: [], engagedNames: [], retrato: portrait(gerar) });

test('chip_mostra_ate_com_milli_exato', async () => {
  const { TargetChip } = await load('../src/combat/TargetChip.tsx');
  const out = html(h(TargetChip, { p: part({ preco_estilhas: 1, preco_milli: '15', escopo: 'tipo' }), aim: undefined, onPick() {}, onGenerate() {} }));
  assert.match(out, /Gerar retrato \(até 0,015 Estilhas\)/);
});

test('chip_sem_milli_usa_inteiro_com_ate_e_plural', async () => {
  const { TargetChip } = await load('../src/combat/TargetChip.tsx');
  const one = html(h(TargetChip, { p: part({ preco_estilhas: 1, escopo: 'tipo' }), aim: undefined, onPick() {}, onGenerate() {} }));
  assert.match(one, /Gerar retrato \(até 1 Estilha\)/);
  const three = html(h(TargetChip, { p: part({ preco_estilhas: 3, escopo: 'tipo' }), aim: undefined, onPick() {}, onGenerate() {} }));
  assert.match(three, /Gerar retrato \(até 3 Estilhas\)/);
});

test('atalho_de_confirmacao_em_milli', async () => {
  const { withinShownPrice } = await load('../src/lib/portraitOrder.ts');
  assert.equal(withinShownPrice('15', 1, '15'), true);     // igual ao teto exato
  assert.equal(withinShownPrice('8', 1, '15'), true);      // menor
  assert.equal(withinShownPrice('16', 1, '15'), false);    // acima do teto exato (mesmo dentro de 1 Estilha)
  assert.equal(withinShownPrice('1000', 1), true);         // sem milli: regra de hoje
  assert.equal(withinShownPrice('1001', 1), false);
  assert.equal(withinShownPrice('abc', 1, '15'), false);
});
