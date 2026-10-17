import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/dossiers.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const memory = () => { const m = new Map(); return { get: (k) => m.get(k) ?? null, set: (k, v) => m.set(k, v), raw: m }; };

test('marker: ausente = novo; versao maior = atualizado; igual = nada', async () => {
  const d = await load();
  assert.equal(d.markerFor({ id: 'a', version: 3 }, {}), 'new');
  assert.equal(d.markerFor({ id: 'a', version: 5 }, { a: 3 }), 'updated');
  assert.equal(d.markerFor({ id: 'a', version: 3 }, { a: 3 }), null);
  assert.equal(d.markerFor({ id: 'a', version: 2 }, { a: 3 }), null);
});

test('markedCount so conta dossies fornecidos (visiveis)', async () => {
  const d = await load();
  const items = [{ id: 'a', version: 1 }, { id: 'b', version: 2 }];
  assert.equal(d.markedCount(items, { a: 1 }), 1);
  assert.equal(d.markedCount([], {}), 0);
});

test('seen round-trip por game_id + aba; nunca regride versao', async () => {
  const d = await load();
  const store = memory();
  d.saveSeen(store, 'g1', 'npcs', d.withSeen({}, { id: 'a', version: 4 }));
  assert.deepEqual(d.loadSeen(store, 'g1', 'npcs'), { a: 4 });
  assert.deepEqual(d.loadSeen(store, 'g2', 'npcs'), {});
  assert.deepEqual(d.loadSeen(store, 'g1', 'locais'), {});
  const kept = d.withSeen({ a: 4 }, { id: 'a', version: 2 });
  assert.equal(kept.a, 4);
});

test('sem localStorage / storage lancando / JSON corrompido => vazio (tudo novo), sem erro', async () => {
  const d = await load();
  const boom = { get() { throw new Error('blocked'); }, set() { throw new Error('blocked'); } };
  assert.deepEqual(d.loadSeen(boom, 'g', 't'), {});
  assert.doesNotThrow(() => d.saveSeen(boom, 'g', 't', { a: 1 }));
  const bad = memory(); bad.set(d.seenKey('g', 't'), '{nao-json');
  assert.deepEqual(d.loadSeen(bad, 'g', 't'), {});
  const weird = memory(); weird.set(d.seenKey('g', 't'), JSON.stringify({ a: 'x', b: 2 }));
  assert.deepEqual(d.loadSeen(weird, 'g', 't'), { b: 2 });
});

test('projecao atrasada: generated_at_turn < turno atual', async () => {
  const d = await load();
  assert.equal(d.isProjectionBehind({ generated_at_turn: 3 }, 5), true);
  assert.equal(d.isProjectionBehind({ generated_at_turn: 5 }, 5), false);
  assert.equal(d.isProjectionBehind({ generated_at_turn: 5 }, undefined), false);
});
