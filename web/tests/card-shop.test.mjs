import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/cardRewards.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const base = { id: 'neu1_br_x', name: 'X', raridade: 'comum', custo_folego: 1, custo_entropia: 0, texto: '', descricao: '',
  preco: 40, conhecida: false, destino: 'baralho', bloqueio: null };

test('oferta livre habilita Comprar com o preço', async () => {
  const { shopOfferState } = await load();
  assert.deepEqual(shopOfferState(base), { enabled: true, label: 'Comprar por 40 de ouro' });
});

test('conhecida, sem ouro e keeper desabilitam com o texto do servidor', async () => {
  const { shopOfferState } = await load();
  assert.deepEqual(shopOfferState({ ...base, conhecida: true, bloqueio: 'Você já conhece essa Carta.' }),
    { enabled: false, label: 'Você já conhece essa Carta.' });
  assert.deepEqual(shopOfferState({ ...base, bloqueio: 'Faltam 10 de ouro.' }), { enabled: false, label: 'Faltam 10 de ouro.' });
  assert.equal(shopOfferState({ ...base, bloqueio: 'Okka recusa negociar com você.' }).enabled, false);
});

test('rótulos de destino', async () => {
  const { DESTINO_LABEL } = await load();
  assert.equal(DESTINO_LABEL.baralho, 'vai para o Baralho');
  assert.match(DESTINO_LABEL.acervo, /Acervo/);
});
