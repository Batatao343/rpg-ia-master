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
