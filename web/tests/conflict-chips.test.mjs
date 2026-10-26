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
