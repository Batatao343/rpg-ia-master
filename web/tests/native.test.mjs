import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load(name) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(`../src/${name}.ts`, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

test('platform detection: web by default, android only via native Capacitor', async () => {
  const { clientPlatform, isAndroidClient } = await load('native/platform');
  delete globalThis.Capacitor;
  assert.equal(clientPlatform(), 'web');
  globalThis.Capacitor = { isNativePlatform: () => false, getPlatform: () => 'web' };
  assert.equal(isAndroidClient(), false);
  globalThis.Capacitor = { isNativePlatform: () => true, getPlatform: () => 'android' };
  assert.equal(isAndroidClient(), true);
  delete globalThis.Capacitor;
});

test('purchase adapter selection by platform; Android stub is not available yet', async () => {
  const { selectPurchaseAdapter } = await load('purchases/index');
  const skus = async () => ({ items: [{ sku_id: 's1', gross_brl: '9.90', shard_milli: '1000' }] });
  const web = selectPurchaseAdapter('web', skus);
  assert.equal(web.kind, 'stripe');
  assert.equal(web.supportsWebCheckout, true);
  assert.deepEqual((await web.listProducts()).map(p => p.productId), ['s1']);
  const android = selectPurchaseAdapter('android', skus);
  assert.equal(android.kind, 'google_play');
  assert.equal(android.supportsWebCheckout, false);
  for (const call of [() => android.listProducts(), () => android.purchase('p', 'acct'), () => android.restorePending()])
    await assert.rejects(call, /not_available_until_spec_194_native/);
});

test('back policy never exits mid-action and minimizes at root', async () => {
  const { decideBack } = await load('native/backPolicy');
  assert.equal(decideBack('play', true, false), 'ignore');
  assert.equal(decideBack('play', false, true), 'ignore');
  assert.equal(decideBack('account', false, false), 'back');
  assert.equal(decideBack('simulator', false, false), 'back');
  assert.equal(decideBack('play', false, false), 'minimize');
  assert.equal(decideBack('saves', false, false), 'minimize');
});

test('native boot refresh is exposed as a single-shot helper (no retry loop)', async () => {
  const { refreshSessionOnce } = await load('http');
  globalThis.document = { cookie: 'rpg_csrf=abc' };
  let calls = 0, seen;
  globalThis.fetch = async (url, o) => { calls++; seen = { url, csrf: o.headers.get('X-CSRF-Token'), m: o.method }; return new Response('{}', { status: 401 }); };
  assert.equal(await refreshSessionOnce(), false);
  assert.equal(calls, 1);
  assert.deepEqual(seen, { url: '/auth/refresh', csrf: 'abc', m: 'POST' });
  globalThis.fetch = async () => { throw new Error('offline'); };
  assert.equal(await refreshSessionOnce(), false);
});
