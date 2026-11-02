// SPEC-363 R19-R21: alvos da mão, fallback sem escondidos e 409 que tira só a jogada recusada.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'cjs', platform: 'node', logLevel: 'silent' });
  const mod = { exports: {} };
  new Function('module', 'exports', 'require', outputFiles[0].text)(mod, mod.exports, require);
  return mod.exports;
}

test('servidor_manda_alvos_da_mao_e_vence_o_fallback', async () => {
  const { cardTargets } = await load('../src/combat/deck.ts');
  const card = { id: 'bas_x', alvo: 'inimigo', valid_targets: ['e2'] };
  assert.deepEqual(cardTargets(card, undefined, ['e1', 'e2'], ['player']), ['e2']);
  assert.deepEqual(cardTargets({ id: 'b', alvo: 'inimigo' }, undefined, ['e2'], ['player']), ['e2']);
  assert.deepEqual(cardTargets({ id: 'c', alvo: 'si' }, undefined, ['e2'], ['player']), []);
});

test('fallback_exclui_escondidos', async () => {
  const { visibleEnemyIds } = await load('../src/combat/deck.ts');
  assert.deepEqual(visibleEnemyIds([{ id: 'a', concealment: 'visivel' }, { id: 'b', concealment: 'escondido' }, { id: 'c' }]), ['a', 'c']);
});

test('409_tira_so_a_jogada_recusada', async () => {
  const { dropRejectedPlay } = await load('../src/combat/deck.ts');
  const q = [{ uid: '1', cardId: 'x', name: 'Corte' }, { uid: '2', cardId: 'y', name: 'Golpe' }, { uid: '3', cardId: 'x', name: 'Corte' }];
  const r = dropRejectedPlay(q, 2, 'x');
  assert.deepEqual(r.queue.map((p) => p.uid), ['1', '2']);
  assert.equal(r.note, 'Corte perdeu o alvo — escolha de novo.');
  // índice errado cai na 1ª da mesma carta; sem pista, nada muda
  assert.deepEqual(dropRejectedPlay(q, 1, 'x').queue.map((p) => p.uid), ['2', '3']);
  assert.equal(dropRejectedPlay(q, undefined, undefined).queue, q);
});

test('http_le_play_index_do_detail', async () => {
  const { playInfo } = await load('../src/http.ts');
  assert.deepEqual(playInfo({ detail: { code: 'invalid_target', play_index: 0, card_id: 'bas_x' } }), { playIndex: 0, cardId: 'bas_x' });
  assert.deepEqual(playInfo({ detail: 'x' }), {});
});
