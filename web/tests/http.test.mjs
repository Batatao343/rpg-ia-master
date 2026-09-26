import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

async function load(name) {
  const source = await readFile(new URL(`../src/${name}.ts`, import.meta.url), 'utf8');
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }});
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}#${Math.random()}`);
}

test('POST stream sends CSRF and cookies', async () => {
  const { http } = await load('http');
  globalThis.document = { cookie: 'rpg_csrf=abc' };
  globalThis.fetch = async (url, options) => {
    assert.equal(options.credentials, 'include');
    assert.equal(options.headers.get('X-CSRF-Token'), 'abc');
    return new Response('ok');
  };
  await http('/game/action/stream', { method: 'POST', body: '{}' });
});

test('concurrent 401s refresh only once, repeating the same body', async () => {
  const { http } = await load('http');
  let refreshes = 0, fresh = false;
  globalThis.fetch = async (url, options) => {
    if (url === '/auth/refresh') {
      refreshes++;
      await new Promise(resolve => setTimeout(resolve, 10));
      fresh = true;
      return new Response('{}');
    }
    assert.equal(options.body, '{"action_id":"stable"}');
    return new Response('{}', { status: fresh ? 200 : 401 });
  };
  await Promise.all([1, 2, 3].map(() => http('/game/action', { method: 'POST', body: '{"action_id":"stable"}' })));
  assert.equal(refreshes, 1);
});

test('refresh failure is typed and does not loop', async () => {
  const { http, HttpError } = await load('http');
  let calls = 0;
  globalThis.fetch = async () => { calls++; return new Response('{"detail":"expired"}', { status: 401 }); };
  await assert.rejects(http('/game/action', { method: 'POST' }), error => error instanceof HttpError && error.status === 401);
  assert.equal(calls, 2);
});
