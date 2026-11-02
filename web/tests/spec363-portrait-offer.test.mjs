// SPEC-363 R3/R4: oferta do retrato com e sem mira; 503 apaga a oferta daquele inimigo.
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

const enemy = {
  id: 'e1', name: 'Goblin', role: 'enemy', vit: 5, max: 5, conditions: [], intel: [], engagedNames: [],
  retrato: { estado: 'marcador', src: null, familia: 'bruto', icone: 'dark', alt: 'x', proprio: false,
    gerar: { preco_estilhas: 3, escopo: 'tipo' } },
};

test('oferta_aparece_sem_mira_e_com_mira_fora_do_botao', async () => {
  const { TargetChip } = await load('../src/combat/TargetChip.tsx');
  const none = html(h(TargetChip, { p: enemy, aim: undefined, onPick() {}, onGenerate() {} }));
  assert.match(none, /data-gen-portrait="e1"/);
  const aimed = html(h(TargetChip, { p: enemy, aim: { valid: true }, onPick() {}, onGenerate() {} }));
  assert.match(aimed, /data-gen-portrait="e1"/);
  // sem botão aninhado: o botão do alvo não contém o botão da oferta
  const btn = aimed.match(/<button[^>]*data-target="e1"[\s\S]*?<\/button>/)[0];
  assert.doesNotMatch(btn, /data-gen-portrait/);
});

test('sem_onGenerate_sem_oferta', async () => {
  const { TargetChip } = await load('../src/combat/TargetChip.tsx');
  assert.doesNotMatch(html(h(TargetChip, { p: enemy, aim: { valid: true }, onPick() {} })), /data-gen-portrait/);
});

test('503_esconde_a_oferta_so_do_inimigo', async () => {
  const { shouldHidePortraitOffer, withoutPortraitOffer } = await load('../src/lib/portraitOrder.ts');
  assert.equal(shouldHidePortraitOffer(503, 'image_generation_disabled'), true);
  assert.equal(shouldHidePortraitOffer(503, 'image_pricing_unavailable'), true);
  assert.equal(shouldHidePortraitOffer(402, undefined), false);
  const g = { x: 1, combat: { enemies: [{ id: 'e1', retrato: { gerar: { preco_estilhas: 3 } } }, { id: 'e2', retrato: { gerar: { preco_estilhas: 3 } } }] } };
  const out = withoutPortraitOffer(g, 'e1');
  assert.equal(out.combat.enemies[0].retrato.gerar, null);
  assert.ok(out.combat.enemies[1].retrato.gerar);
  assert.equal(withoutPortraitOffer(out, 'e1'), out);
});
