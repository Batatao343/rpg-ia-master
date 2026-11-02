// SPEC-368 R6/R8a: descartar por Fôlego (Dor Surda) e escolha do descartar na fila/mão.
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

const dor = { id: 'sts_dor_surda', name: 'Dor Surda', custo_folego: 0, custo_entropia: 0, jogavel: false, descartar_folego: 1 };
const golpe = { id: 'golpe', name: 'Golpe', custo_folego: 1, custo_entropia: 0, jogavel: true };
const piles = { folego: 2, folego_max: 3, folego_emprestado: 0, pacto_max: 2 };

test('descartar: paga 1 de Fôlego PRÓPRIO, vira jogada action_kind=discard e não conta como cópia jogada', async () => {
  const d = await load('../src/combat/deck.ts');
  const hand = [dor, golpe];
  assert.equal(d.discardReason(dor, hand, 0, [], piles), null);
  assert.equal(d.discardReason(golpe, hand, 1, [], piles), null); // sem custo de descarte: nada a bloquear
  const q = d.enqueueDiscard([], dor, 'a');
  assert.deepEqual(d.toJogadas(q), [{ card_id: 'sts_dor_surda', action_kind: 'discard' }]);
  assert.equal(d.discardReason(dor, hand, 0, q, piles), 'ja_na_fila');
  assert.equal(d.blockReason(golpe, hand, 1, q, piles, null), null);
  // Fôlego próprio esgotado pela fila: o descarte não pode pedir emprestado (Pacto)
  const q2 = d.enqueue(d.enqueue([], golpe, 'e1', 'x'), golpe, 'e1', 'y');
  assert.equal(d.discardReason(dor, hand, 0, q2, piles), 'sem_folego');
  assert.equal(d.discardReason(dor, hand, 0, [], { ...piles, folego: 0 }), 'sem_folego');
});

test('descartar com escolha: as cartas marcadas seguem em `descartar` e a marcação respeita o teto', async () => {
  const d = await load('../src/combat/deck.ts');
  const q = d.enqueue([], golpe, 'e1', 'a', ['sts_dor_surda']);
  assert.deepEqual(d.toJogadas(q), [{ card_id: 'golpe', target_id: 'e1', descartar: ['sts_dor_surda'] }]);
  assert.deepEqual(d.togglePick([], 2, 2), [2]);
  assert.deepEqual(d.togglePick([2], 0, 2), [2, 0]);
  assert.deepEqual(d.togglePick([2, 0], 3, 2), [2, 0]); // teto
  assert.deepEqual(d.togglePick([2, 0], 2, 2), [0]);
});

test('mão: botão "Descartar (1 Fôlego)" só nas cartas descartáveis; recusa vem explicada', async () => {
  const { Hand } = await load('../src/components/combat/Hand.tsx');
  const p = { mao: [dor, golpe], compra: 0, descarte: 0, exaurida: 0, folego: 2, folego_max: 3, folego_emprestado: 0, pacto_max: 2 };
  const ok = html(h(Hand, { piles: p, glossary: {}, reasons: ['fardo', null], armedIndex: null, busy: false, onPlay() {},
    discardReasons: [null, null], onDiscard() {} }));
  assert.match(ok, /data-discard="sts_dor_surda"/);
  assert.match(ok, /Descartar \(1 Fôlego\)/);
  assert.equal((ok.match(/data-discard=/g) ?? []).length, 1);
  const no = html(h(Hand, { piles: p, glossary: {}, reasons: ['fardo', null], armedIndex: null, busy: false, onPlay() {},
    discardReasons: ['sem_folego', null], onDiscard() {} }));
  assert.match(no, /data-discard="sts_dor_surda"[^>]*aria-disabled="true"/);
  assert.match(no, /Falta fôlego/);
  const plain = html(h(Hand, { piles: p, glossary: {}, reasons: ['fardo', null], armedIndex: null, busy: false, onPlay() {} }));
  assert.doesNotMatch(plain, /data-discard=/);
});
