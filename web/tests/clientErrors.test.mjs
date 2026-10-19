import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load(name) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(`../src/${name}.ts`, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent',
    define: { __RPG_BUILD__: JSON.stringify('abcdef1+202610191345') } });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

function setNav(value) {
  Object.defineProperty(globalThis, 'navigator', { value, configurable: true, writable: true });
}

function capture() {
  const bodies = [];
  setNav({ sendBeacon: (url, blob) => { bodies.push({ url, blob }); return true; } });
  return bodies;
}

const STACK = `TypeError: Cannot read properties of undefined (reading 'nome do jogador@mail.com')
    at Codex (https://rpg.example/assets/index-Bx1.js?token=SEGREDO:1:2345)
    at https://rpg.example/assets/vendor-9a.js:12:7`;

test('payload: so nome/codigo/rota template/frames, nunca a mensagem nem query', async () => {
  const { buildPayload } = await load('lib/clientErrors');
  const err = new TypeError('jogador@mail.com abriu a porta');
  err.stack = STACK;
  const p = buildPayload({ kind: 'render', error: err, code: 'render_failed',
    route: '/game/8a6e0804-2bd0-4672-b79d-d97358571b25/codex?email=x@y.com', requestId: 'abc123def456' }, 1000);
  assert.deepEqual(p.stack, ['assets/index-Bx1.js:1:2345', 'assets/vendor-9a.js:12:7']);
  assert.equal(p.route, '/game/{id}/codex');
  assert.equal(p.error_name, 'TypeError');
  assert.equal(p.build, 'abcdef1+202610191345');
  assert.equal(p.client, 'web');
  const text = JSON.stringify(p);
  assert.ok(!text.includes('@') && !text.includes('SEGREDO') && !text.includes('porta'));
});

test('dedupe: mesma assinatura <= 1x/min; teto 20 por sessao', async () => {
  const { reportClientError, resetClientErrors } = await load('lib/clientErrors');
  const bodies = capture();
  resetClientErrors();
  assert.equal(reportClientError({ kind: 'network', code: 'fetch_failed', route: '/game/saves' }, 0), true);
  assert.equal(reportClientError({ kind: 'network', code: 'fetch_failed', route: '/game/saves' }, 30_000), false);
  assert.equal(reportClientError({ kind: 'network', code: 'fetch_failed', route: '/game/saves' }, 61_000), true);
  for (let i = 0; i < 40; i++) reportClientError({ kind: 'sse', code: `c${i}` }, 100_000);
  assert.equal(bodies.length, 20);
  assert.equal(bodies[0].url, '/telemetry/client-error');
});

test('falha do beacon nunca gera outro beacon nem lanca', async () => {
  const { reportClientError, resetClientErrors } = await load('lib/clientErrors');
  resetClientErrors();
  let calls = 0;
  setNav({ sendBeacon: () => { calls++; throw new Error('boom'); } });
  assert.equal(reportClientError({ kind: 'unhandled', error: new Error('x') }, 0), false);
  assert.equal(calls, 1);
});

test('http: fetch sem resposta reporta kind=network com request_id e relanca o TypeError', async () => {
  const { http } = await load('http');
  const bodies = capture();
  globalThis.document = { cookie: '' };
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(http('/game/saves'), error => error instanceof TypeError);
  const sent = JSON.parse(await bodies.at(-1).blob.text());
  assert.equal(sent.kind, 'network');
  assert.equal(sent.route, '/game/saves');
  assert.match(sent.request_id, /^[0-9a-f]{12}$/);
});
