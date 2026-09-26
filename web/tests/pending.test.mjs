import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
const source = await readFile(new URL('../src/pendingOperation.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }});
const pending = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

function storage() {
  const data = {};
  globalThis.localStorage = { getItem: key => data[key] || null,
    setItem: (key, value) => { data[key] = value; }, removeItem: key => { delete data[key]; } };
}

test('reload and retry preserve operation ID and original payload', async () => {
  storage();
  const first = await pending.preparePending('a', 'game', 'Observo', {});
  const second = await pending.preparePending('a', 'game', 'Outro pedido', {});
  assert.equal(second.operation_id, first.operation_id);
  assert.equal(second.payload.input_text, 'Observo');
  assert.equal(pending.loadPending('b', 'game'), null);
  assert.equal(pending.loadPending('a', 'other'), null);
  pending.clearPending('a', 'game');
  assert.equal(pending.loadPending('a', 'game'), null);
});

test('failure to persist prevents dispatch and malformed storage is rejected', async () => {
  storage();
  globalThis.localStorage.setItem = () => { throw new Error('quota'); };
  await assert.rejects(pending.preparePending('a', 'game', 'Observo', {}), /quota/);
  globalThis.localStorage.getItem = () => '{"version":1,"owner":"a","game_id":"game"}';
  assert.equal(pending.loadPending('a', 'game'), null);
});
