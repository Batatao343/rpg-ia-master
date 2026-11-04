import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/combat/conflictChips.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const combat = {
  scene: { zones: [], positions: [], objects: [
    { id: 'pilar', name: 'Pilar Rachado', interactions: [{ label: 'derrubar', cost: 'acao' }, { label: 'escalar' }] },
  ] },
  companion_orders: [{ id: 'npc_brunna', name: 'Brunna' }],
  reinforcement_warning: true,
};

test('chips de objeto: um por interacao, com a frase que o servidor reconhece', async () => {
  const { objectChips } = await load();
  const chips = objectChips(combat);
  assert.deepEqual(chips.map((c) => c.text), ['derrubar Pilar Rachado.', 'escalar Pilar Rachado.']);
  assert.ok(chips.every((c) => !JSON.stringify(c).includes('effect')));
});

test('chips de ordem: um por verbo (inclui curar) e frase "<aliado>, <verbo>."', async () => {
  const { orderChips } = await load();
  const chips = orderChips(combat);
  assert.deepEqual(chips.map((c) => c.text),
    ['Brunna, atacar.', 'Brunna, proteger.', 'Brunna, curar.', 'Brunna, recuar.']);
});

test('sem os campos da API (flag fora de on) nao ha chip nem nota', async () => {
  const { objectChips, orderChips, reinforcementNote } = await load();
  for (const c of [undefined, null, {}, { scene: { zones: [], positions: [] } }]) {
    assert.deepEqual(objectChips(c), []);
    assert.deepEqual(orderChips(c), []);
    assert.equal(reinforcementNote(c), null);
  }
  assert.match(reinforcementNote(combat), /reforços/);
});

test('SPEC-391: nota do Chamado so entre o chamado e a chegada; telegrafado e cancelado ficam sem nota', async () => {
  const { callNote, reinforcementNote } = await load();
  const called = { ...combat, reinforcement: { stage: 'called', leader_id: 'cap_1', chega_na_rodada: 3 } };
  assert.equal(callNote(called, 'Capitao Teste'),
    'Reforço a caminho: chega no fim da próxima rodada. Derrube Capitao Teste para impedir.');
  assert.equal(callNote({ ...called, reinforcement: { ...called.reinforcement, stage: 'telegraphed', chega_na_rodada: null } }, 'X'), null);
  for (const c of [undefined, null, {}, { ...combat, reinforcement: undefined }]) assert.equal(callNote(c, 'X'), null);
  assert.equal(reinforcementNote(called), null); // a nota legada cede ao tabuleiro de cartas
});

test('SPEC-391: marca "acabou de chegar" so na rodada da chegada', async () => {
  const { arrivalNotes } = await load();
  const c = { round: 3, enemies: [{ id: 'a', name: 'Capitao' }, { id: 'b_r1', name: 'Capanga do bando', chegou_na_rodada: 3 }] };
  assert.deepEqual(arrivalNotes(c), ['Capanga do bando acabou de chegar.']);
  assert.deepEqual(arrivalNotes({ ...c, round: 4 }), []);
  assert.deepEqual(arrivalNotes(undefined), []);
});
