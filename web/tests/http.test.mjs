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

function uploadFixture() {
  let instance;
  globalThis.document = { cookie: 'rpg_csrf=voice%2Dtoken' };
  globalThis.XMLHttpRequest = class {
    upload = {}; headers = {}; status = 200; responseText = '{"text":"Abro a porta","operation_id":"stable-op","billing_status":"settled"}';
    constructor() { instance = this; }
    open(method, path) { this.method = method; this.path = path; }
    setRequestHeader(key, value) { this.headers[key] = value; }
    send(body) { this.body = body; }
    abort() { this.onabort(); }
  };
  return () => instance;
}

test('raw voice upload carries Blob MIME, CSRF, cookies and operation ID and exposes upload completion', async () => {
  const { uploadAudio } = await load('http'); const xhr = uploadFixture(); let uploaded = 0;
  const audio = new Blob(['bytes'], { type: 'audio/ogg;codecs=opus' });
  const pending = uploadAudio(audio, 'stable-op', new AbortController().signal, () => uploaded++);
  assert.equal(xhr().body, audio); assert.equal(xhr().withCredentials, true);
  assert.equal(xhr().method, 'POST'); assert.equal(xhr().path, '/account/transcriptions');
  assert.equal(xhr().headers['content-type'], audio.type); assert.equal(xhr().headers['x-csrf-token'], 'voice-token');
  assert.equal(xhr().headers['x-operation-id'], 'stable-op');
  xhr().upload.onload(); assert.equal(uploaded, 1); xhr().onload();
  assert.equal((await pending).text, 'Abro a porta');
});

test('voice abort and timeout reject without automatic replay', async () => {
  const { uploadAudio } = await load('http'); const xhr = uploadFixture(); const abort = new AbortController();
  const pending = uploadAudio(new Blob(['a']), 'one', abort.signal, () => {});
  abort.abort(); await assert.rejects(pending, { name: 'AbortError' });
  const timeout = uploadAudio(new Blob(['a']), 'two', new AbortController().signal, () => {});
  xhr().ontimeout(); await assert.rejects(timeout, /demorou/);
});

test('voice failure is typed and announces an actionable fallback', async () => {
  const { uploadAudio, HttpError } = await load('http'); const xhr = uploadFixture();
  const pending = uploadAudio(new Blob(['a']), 'one', new AbortController().signal, () => {});
  xhr().status = 503; xhr().responseText = '{"detail":"speech_disabled"}'; xhr().onload();
  await assert.rejects(pending, error => error instanceof HttpError && error.code === 'speech_disabled' && /Continue digitando/.test(error.message));
  const malformed = uploadAudio(new Blob(['a']), 'two', new AbortController().signal, () => {});
  xhr().responseText = 'null'; xhr().status = 200; xhr().onload();
  await assert.rejects(malformed, /Resposta.*inválida/);
});
