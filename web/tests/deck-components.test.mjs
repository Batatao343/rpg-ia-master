// SPEC-334 R1/R2/R3/R5/R6/R8: marcação dos componentes do combate (SSR, sem navegador).
// Snapshot visual em 390/1440 e a jornada de jogo são Playwright (autoria separada).
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
const React = require('react');
const h = React.createElement;

const gl = { rachadura: { nome: 'Rachadura', regra: '+25% de dano por N rodadas.' } };
const piles = {
  mao: [
    { id: 'golpe', name: 'Golpe', custo_folego: 1, custo_entropia: 0, jogavel: true, alvo: 'inimigo', texto: '**Rachadura** 2. Causa 3 de dano.', palavras_chave: ['rachadura'] },
    { id: 'fardo', name: 'Fardo', custo_folego: 0, custo_entropia: 0, jogavel: false, texto: '' },
  ],
  listas: { compra: [{ id: 'a', name: 'Aparar' }], descarte: [], exaurida: [] },
  compra: 1, descarte: 0, exaurida: 0, folego: 3, folego_max: 3, folego_emprestado: 0, pacto_max: 2,
};

test('mão: nome, pips de Fôlego, negrito de palavra-chave, regra para leitor de tela e atalho', async () => {
  const { Hand } = await load('../src/components/combat/Hand.tsx');
  const out = html(h(Hand, { piles, glossary: gl, reasons: [null, 'fardo'], armedIndex: null, busy: false, onPlay() {} }));
  assert.match(out, /data-keyword="Rachadura"/);
  assert.match(out, /aria-keyshortcuts="1"/);
  assert.match(out, /aria-describedby="deck-card-0-rules"/);
  assert.match(out, /Rachadura: \+25% de dano por N rodadas\./); // regra no sr-only (sem hover)
  assert.match(out, /Pilhas[\s\S]*Compra 1 · Descarte 0 · Exaurida 0/); // contadores na sublinha do botão
  assert.match(out, /aria-disabled="true"[^>]*>[\s\S]*Fardo: pesa na mão, não se joga/); // esmaecida com motivo
});

test('Fôlego: o Pacto aparece como pips emprestados com o aviso do custo', async () => {
  const { FolegoPips } = await load('../src/components/combat/FolegoPips.tsx');
  const none = html(h(FolegoPips, { piles, state: { spent: 0, free: 3, borrowed: 0, room: 2 } }));
  assert.doesNotMatch(none, /O Abismo empresta/);
  assert.match(none, /role="status"><\/span>/); // R20: status sempre montado (vazio)
  assert.match(none, /Fôlego 3 de 3/);
  const out = html(h(FolegoPips, { piles, state: { spent: 4, free: 0, borrowed: 1, room: 2 } }));
  assert.match(out, /folego__pip--pacto is-reserved/);
  assert.match(out, /class="folego__pips" aria-hidden="true"/); // o texto é a fonte acessível
  assert.match(out, /role="status">O Abismo empresta 1 de fôlego: custa Entropia e \+1 Carga\./);
});

test('fila: Encerrar a rodada desligado sem fila; com fila mostra a contagem e Esc', async () => {
  const { PlayQueue } = await load('../src/components/combat/PlayQueue.tsx');
  const base = { selected: null, nameOf: () => 'Lobo', busy: false, onSelect() {}, onMove() {}, onRemove() {}, onClear() {}, onEnd() {}, touch: false };
  const empty = html(h(PlayQueue, { ...base, queue: [] }));
  assert.match(empty, /data-end-turn="true"[^>]*aria-disabled="true"/);
  const q = [{ uid: 'a', cardId: 'golpe', name: 'Golpe', targetId: 'e1', folego: 1, entropia: 0 }];
  const out = html(h(PlayQueue, { ...base, queue: q, selected: 'a' }));
  assert.match(out, /btn btn--primary play-queue__submit/);
  assert.match(out, /Encerrar a rodada<\/span><small[^>]*>1 carta/);
  assert.doesNotMatch(out, /Enter\)?<\/|\(1\)/);
  assert.match(out, /Desfazer \(Esc\)/);
  assert.match(out, /aria-label="Cancelar Golpe"/);
  assert.match(out, /Golpe[\s\S]*→ Lobo/);
});

test('prévia e log: anunciáveis e sem render quando vazios', async () => {
  const { PreviewChip } = await load('../src/components/combat/PreviewChip.tsx');
  const { MechLog } = await load('../src/components/combat/MechLog.tsx');
  const ok = html(h(PreviewChip, { state: { status: 'ok', result: { chance_acerto_pct: 55, chance_critico_pct: 9, dano_min: 4, dano_max: 7, ferimento_provavel: null, efeitos_extra: ['Sangramento'], pressagio_frustrado: false } } }));
  assert.match(ok, /role="status"/);
  assert.match(ok, /Seu golpe/);
  assert.match(ok, /preview-chip__num">55 %<[\s\S]*4–7 de dano · pode Sangrar/);
  assert.equal(html(h(PreviewChip, { state: { status: 'idle' } })), '');
  assert.equal(html(h(MechLog, { lines: [], round: 2 })), '');
  const log = html(h(MechLog, { lines: ['Você · Golpe → Lobo · 2d10 6 + 7 +2 = 15 vs 12 · acerto · 5 dano'], round: 3 }));
  assert.match(log, /<details[\s\S]*Os dados da rodada 3/);
  assert.match(log, /mech-log__who">Você</);
});
