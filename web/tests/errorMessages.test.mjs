import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load(name) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(`../src/${name}.ts`, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

test('every backend catalog code has a pt-BR message', async () => {
  const { missingCatalogCodes } = await load('lib/errorMessages');
  assert.deepEqual(missingCatalogCodes(), []);
});

test('unknown codes never surface raw; server prose is preserved', async () => {
  const { messageFor, GENERIC_MESSAGE, errMsg } = await load('lib/errorMessages');
  assert.equal(messageFor('some_new_backend_code'), GENERIC_MESSAGE);
  assert.equal(messageFor('credentials_invalid'), 'E-mail ou senha incorretos.');
  assert.equal(messageFor('game_not_found', 'Jogo não encontrado.'), 'Jogo não encontrado.');
  assert.equal(messageFor('game_not_found', 'game_not_found'), 'Não encontramos esta campanha.');
  assert.equal(errMsg(new Error('credentials_invalid')), 'E-mail ou senha incorretos.');
  assert.equal(errMsg(new Error('totally_unknown_code')), GENERIC_MESSAGE);
});

test('support code is the first 8 chars of the request id', async () => {
  const { supportCode } = await load('lib/errorMessages');
  assert.equal(supportCode('2be5aa81-d8be-46e8-9d90-390b6004612'), '2be5aa81');
  assert.equal(supportCode(undefined), undefined);
});

test('HttpError carries request id from header/body and a friendly message', async () => {
  const { http } = await load('http');
  globalThis.document = { cookie: '' };
  globalThis.window = undefined;
  let sent = '';
  globalThis.fetch = async (url, options) => {
    sent = options.headers.get('X-Request-ID');
    return new Response(JSON.stringify({ detail: 'credentials_invalid', code: 'credentials_invalid',
      request_id: 'srv-req-0001' }), { status: 401, headers: { 'X-Request-ID': 'srv-req-0001' } });
  };
  await assert.rejects(http('/auth/login', { method: 'POST', body: '{}' }), (error) => {
    assert.equal(error.code, 'credentials_invalid');
    assert.equal(error.requestId, 'srv-req-0001');
    assert.equal(error.message, 'E-mail ou senha incorretos.');
    return true;
  });
  assert.match(sent, /^[A-Za-z0-9._:-]{8,64}$/);
});

test('prose detail with body.code keeps stable code and server prose', async () => {
  const { http } = await load('http');
  globalThis.document = { cookie: '' };
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Jogo não encontrado.', code: 'game_not_found',
    request_id: 'abcdef123456' }), { status: 404 });
  await assert.rejects(http('/game/state'), (error) => {
    assert.equal(error.code, 'game_not_found');
    assert.equal(error.message, 'Jogo não encontrado.');
    assert.equal(error.requestId, 'abcdef123456');
    return true;
  });
});

test('network failure still exposes the locally generated request id', async () => {
  const { http } = await load('http');
  globalThis.document = { cookie: '' };
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(http('/game/state'), (error) => {
    assert.ok(error instanceof TypeError);          // o erro original segue (fallback SSE->POST)
    assert.ok(error.requestId && error.requestId.length >= 8);
    return true;
  });
});
