import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load(name) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(`../src/${name}.ts`, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent',
    external: ['@capacitor/app'] });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

function setNav(value) {
  Object.defineProperty(globalThis, 'navigator', { value, configurable: true, writable: true });
}

test('SPEC-259 R1/R5: codigo nativo distinto + responseCode, sem token', async () => {
  const { nativeBillingCode } = await load('purchases/androidPlay');
  assert.equal(nativeBillingCode({ code: 'billing_launch_failed', data: { responseCode: 6, debugMessage: 'x' } }),
    'billing_launch_failed:6');
  assert.equal(nativeBillingCode({ code: 'billing_bad_json' }), 'billing_bad_json');
  assert.equal(nativeBillingCode({ code: 'Token GPA.1234 secreto' }), 'billing_unknown');
  assert.equal(nativeBillingCode(null), 'billing_unknown');
});

test('SPEC-259 R5: rejeicao do plugin vira beacon kind=native e o erro segue', async () => {
  const { AndroidPlayAdapter } = await load('purchases/androidPlay');
  const sent = [];
  setNav({ sendBeacon: (_u, blob) => { sent.push(blob); return true; } });
  const err = Object.assign(new Error('billing_query_failed'), { code: 'billing_query_failed', data: { responseCode: 2 } });
  const plugin = { getProducts: async () => { throw err; }, addListener: async () => {} };
  const backend = { profile: async () => ({}), products: async () => ({ items: [{ product_id: 'p1', sku_id: 's', shard_milli: '1' }] }) };
  await assert.rejects(new AndroidPlayAdapter(plugin, backend).listProducts(), e => e === err);
  const body = JSON.parse(await sent[0].text());
  assert.equal(body.kind, 'native');
  assert.equal(body.code, 'billing_query_failed:2');
  assert.equal(body.error_name, 'PlayBillingError');
});

test('SPEC-259 R4: versao do app em formato fechado, so no Android', async () => {
  const { loadAppVersion, appVersion } = await load('native/appVersion');
  assert.equal(await loadAppVersion(async () => ({ version: '1.0.0', build: '7' }), false), null);
  assert.equal(await loadAppVersion(async () => ({ version: '1.0.0', build: '7' }), true), '1.0.0+7');
  assert.equal(appVersion(), '1.0.0+7');
  assert.equal(await loadAppVersion(async () => ({ version: '1.0 <x>', build: '7' }), true), null);
  assert.equal(await loadAppVersion(async () => { throw new Error('no plugin'); }, true), null);
});
