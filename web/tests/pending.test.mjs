import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/pendingOperation.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

function storage() {
  const data = {};
  globalThis.localStorage = { getItem: key => data[key] || null, key: i => Object.keys(data)[i],
    get length() { return Object.keys(data).length; },
    setItem: (key, value) => { data[key] = value; }, removeItem: key => { delete data[key]; } };
}

test('reload and retry preserve operation ID and original payload', async () => {
  storage();
  const pending = await load();
  const first = await pending.preparePending('a', 'game', 'Observo', {});
  const second = await pending.preparePending('a', 'game', 'Outro pedido', {});
  assert.equal(second.operation_id, first.operation_id);
  assert.equal(second.payload.input_text, 'Observo');
  assert.equal(pending.loadPending('b', 'game'), null);
  assert.equal(pending.loadPending('a', 'other'), null);
  pending.clearPending('a', 'game');
  assert.equal(pending.loadPending('a', 'game'), null);
});

test('malformed storage is rejected', async () => {
  storage();
  const pending = await load();
  globalThis.localStorage.getItem = () => '{"version":1,"owner":"a","game_id":"game"}';
  assert.equal(pending.loadPending('a', 'game'), null);
});

test('blocked storage degrades to memory without throwing (R6)', async () => {
  const boom = () => { throw new DOMException('denied', 'SecurityError'); };
  globalThis.localStorage = { getItem: boom, setItem: boom, removeItem: boom, key: boom, get length() { return boom(); } };
  const pending = await load();
  const row = await pending.preparePending('a', 'game', 'Observo', {});
  assert.equal(row.volatile, true);
  assert.equal(pending.loadPending('a', 'game').operation_id, row.operation_id);
  pending.clearOwner('a');
  assert.equal(pending.loadPending('a', 'game'), null);
});

test('storage missing entirely is tolerated', async () => {
  delete globalThis.localStorage;
  const pending = await load();
  const row = await pending.preparePending('a', 'game', 'x', {});
  assert.equal(row.volatile, true);
});

test('status table decides whether the pending command is dropped (R2)', async () => {
  const { shouldClearPending } = await load();
  const table = [
    [400, 'x', true], [404, 'game_not_found', true], [422, 'validation_error', true],
    [409, 'operation_conflict', true], [409, 'operation_request_mismatch', true],
    [409, 'Esta saga terminou. A crônica permanece como memorial', true],
    [409, 'operation_in_progress', false], [409, 'stale_version', false],
    [500, 'boom', false], [503, 'x', false],
  ];
  for (const [status, code, expected] of table) assert.equal(shouldClearPending(status, code), expected, `${status} ${code}`);
});

test('clearPendingIfOwn clears only the pending of that operation (SPEC-320 P1-1)', async () => {
  storage();
  const pending = await load();
  const first = await pending.preparePending('a', 'game', 'Observo', {});
  assert.equal(pending.clearPendingIfOwn('a', 'game', first.operation_id), true);
  assert.equal(pending.loadPending('a', 'game'), null);
});

test('clearPendingIfOwn keeps a newer operation when an old flow finishes late', async () => {
  storage();
  const pending = await load();
  const old = await pending.preparePending('a', 'game', 'Primeira', {});
  pending.clearPending('a', 'game');
  const newer = await pending.preparePending('a', 'game', 'Segunda', {});
  assert.notEqual(newer.operation_id, old.operation_id);
  assert.equal(pending.clearPendingIfOwn('a', 'game', old.operation_id), false);
  assert.equal(pending.loadPending('a', 'game')?.operation_id, newer.operation_id);
});

// SPEC-420 R1: a origem do operation_id vem de quem o gerou, não do localStorage.
test('preparePendingWithOrigin creates once then reuses', async () => {
  storage();
  const pending = await load();
  const first = await pending.preparePendingWithOrigin('a', 'game', 'Observo', {});
  const second = await pending.preparePendingWithOrigin('a', 'game', 'Outro pedido', {});
  assert.equal(first.created, true);
  assert.equal(second.created, false);
  assert.equal(second.operation.operation_id, first.operation.operation_id);
  assert.equal(second.operation.payload.input_text, 'Observo');
});

test('created again after clearPending', async () => {
  storage();
  const pending = await load();
  const first = await pending.preparePendingWithOrigin('a', 'game', 'Observo', {});
  pending.clearPending('a', 'game');
  const again = await pending.preparePendingWithOrigin('a', 'game', 'Observo', {});
  assert.equal(again.created, true);
  assert.notEqual(again.operation.operation_id, first.operation.operation_id);
});

test('blocked storage still reports origin', async () => {
  const boom = () => { throw new DOMException('denied', 'SecurityError'); };
  globalThis.localStorage = { getItem: boom, setItem: boom, removeItem: boom, key: boom, get length() { return boom(); } };
  const pending = await load();
  const first = await pending.preparePendingWithOrigin('a', 'game', 'Observo', {});
  const second = await pending.preparePendingWithOrigin('a', 'game', 'Observo', {});
  assert.equal(first.created, true);
  assert.equal(first.operation.volatile, true);
  assert.equal(second.created, false);
  assert.equal(second.operation.operation_id, first.operation.operation_id);
});

test('created is not persisted', async () => {
  storage();
  const pending = await load();
  await pending.preparePendingWithOrigin('a', 'game', 'Observo', {});
  const raw = Object.values(Object.fromEntries(
    Array.from({ length: globalThis.localStorage.length }, (_, i) => {
      const k = globalThis.localStorage.key(i); return [k, globalThis.localStorage.getItem(k)]; })));
  assert.ok(raw.length > 0);
  for (const row of raw) assert.equal('created' in JSON.parse(row), false);
});
