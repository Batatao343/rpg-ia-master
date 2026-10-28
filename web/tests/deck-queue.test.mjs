// SPEC-334 R2/R3/R4/R5: lógica pura da mão, Fôlego (com Pacto), fila e prévia.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/combat/deck.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const card = (id, o = {}) => ({ id, name: id, custo_folego: 1, custo_entropia: 0, jogavel: true, ...o });
const piles = { folego: 3, folego_max: 3, folego_emprestado: 0, pacto_max: 2 };
const hand = [card('golpe'), card('guarda'), card('golpe'), card('pesada', { custo_folego: 2 }), card('fardo', { jogavel: false })];

test('Fôlego: a fila gasta pips próprios e só então pede emprestado (Pacto)', async () => {
  const d = await load();
  let q = d.enqueue([], hand[3], 'e1', 'a'); // 2
  assert.deepEqual(d.folegoState(piles, q), { spent: 2, free: 1, borrowed: 0, room: 2 });
  q = d.enqueue(q, hand[0], 'e1', 'b'); // 3
  q = d.enqueue(q, hand[1], undefined, 'c'); // 4 -> 1 emprestado
  assert.deepEqual(d.folegoState(piles, q), { spent: 4, free: 0, borrowed: 1, room: 2 });
});

test('bloqueios: Fardo, sem Fôlego (nem Pacto), cópia já na fila, fila cheia, Entropia', async () => {
  const d = await load();
  assert.equal(d.blockReason(hand[4], hand, 4, [], piles, null), 'fardo');
  const noRoom = { ...piles, folego_emprestado: 2 };
  assert.equal(d.blockReason(hand[2], hand, 2, d.enqueue([], hand[3], 'e', 'x'), noRoom, null), null); // 1 pip livre
  assert.equal(d.blockReason(hand[3], hand, 3, d.enqueue([], hand[3], 'e', 'x'), noRoom, null), 'ja_na_fila');
  assert.equal(d.blockReason(card('g2', { custo_folego: 2 }), [card('g2', { custo_folego: 2 })], 0,
    d.enqueue([], hand[3], 'e', 'x'), noRoom, null), 'sem_folego'); // 2 pedidos, 1 livre, Pacto cheio
  assert.equal(d.blockReason(hand[0], hand, 0, d.enqueue([], hand[0], 'e', 'y'), piles, null), 'ja_na_fila');
  assert.equal(d.blockReason(hand[2], hand, 2, d.enqueue([], hand[0], 'e', 'y'), piles, null), null); // 2ª cópia ok
  const cara = card('x', { custo_entropia: 3 });
  assert.equal(d.blockReason(cara, [cara], 0, [], piles, 2), 'entropia');
  const eight = Array.from({ length: 8 }, (_, i) => ({ uid: String(i), cardId: `c${i}`, name: 'c', folego: 0, entropia: 0 }));
  assert.equal(d.blockReason(hand[1], hand, 1, eight, piles, null), 'limite');
});

test('fila: reordenar, cancelar e montar `jogadas` na ordem escolhida (1 request)', async () => {
  const d = await load();
  let q = d.enqueue(d.enqueue([], hand[0], 'e1', 'a'), hand[1], undefined, 'b');
  q = d.move(q, 'b', -1);
  assert.deepEqual(d.toJogadas(q), [{ card_id: 'guarda' }, { card_id: 'golpe', target_id: 'e1' }]);
  assert.equal(d.move(q, 'b', -1), q); // já é o primeiro
  assert.deepEqual(d.toJogadas(d.remove(q, 'b')), [{ card_id: 'golpe', target_id: 'e1' }]);
});

test('texto da carta: palavra-chave em negrito casa com o glossário (tooltip)', async () => {
  const d = await load();
  const gl = { rachadura: { nome: 'Rachadura', regra: '+25% de dano por N rodadas.' } };
  const segs = d.ruleSegments('**Rachadura** 2. Causa 3 de dano.', gl);
  assert.equal(segs[0].bold, true);
  assert.equal(segs[0].tip.regra, '+25% de dano por N rodadas.');
  assert.equal(segs[1].bold, false);
  assert.deepEqual(d.keywordRules('**Rachadura** 2.', gl), ['Rachadura: +25% de dano por N rodadas.']);
  assert.equal(d.ruleSegments('**Desconhecida**', gl)[0].tip, undefined);
});

test('prévia e presságio: texto curto, só o lado do jogador', async () => {
  const d = await load();
  const p = { chance_acerto_pct: 55, chance_critico_pct: 10, dano_min: 4, dano_max: 7, ferimento_provavel: null, efeitos_extra: ['Sangramento'], pressagio_frustrado: false };
  assert.equal(d.previewLine(p), '55 % · 4–7 de dano · pode Sangrar');
  assert.equal(d.previewLine({ ...p, chance_acerto_pct: 42.5, dano_min: 3, dano_max: 3, efeitos_extra: [], pressagio_frustrado: true }),
    '43 % · 3 de dano · frustra o presságio');
  const pr = { actor_id: 'e1', tipo: 'ataque', alvo_id: 'player', valor_estimado: null, faixa: [3, 6], carta_nome: null, sinal: 'ergue a lâmina' };
  assert.equal(d.pressagioLine(pr, () => 'Lobo'), 'Lobo: ergue a lâmina (3–6)');
  assert.equal(d.pressagioLine({ ...pr, faixa: null }, () => undefined), 'Inimigo: ergue a lâmina');
});
