import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load(name) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(`../src/${name}.ts`, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const ACCT = 'a'.repeat(64);
function setup(over = {}) {
  const listeners = {};
  const calls = { verify: [], launch: [], profile: 0 };
  const plugin = {
    addListener: async (n, cb) => { listeners[n] = cb; return { remove() {} }; },
    getProducts: async ({ productIds }) => ({ products: productIds.map(id => ({ productId: id, title: 't', formattedPrice: 'R$ 4,99 (Store)' })) }),
    purchase: async o => { calls.launch.push(o); return over.purchaseResult || { started: true }; },
    queryPendingPurchases: async () => ({ purchases: over.owned || [] }),
  };
  const backend = {
    profile: async () => { calls.profile++; return over.profile || { obfuscated_account_id: ACCT, purchases_disabled: false }; },
    products: async () => ({ items: [{ product_id: 'p1', sku_id: 'gp_1', shard_milli: '5000' }] }),
    verify: async b => { calls.verify.push(b); return over.verify ? over.verify(b) : { status: 'fulfilled', shard_milli: '5000' }; },
  };
  return { plugin, backend, calls, listeners };
}
const ev = (state = 'PURCHASED', token = 'tok-' + 'x'.repeat(20)) => ({ purchaseToken: token, productId: 'p1', orderId: 'GPA.1', purchaseState: state });

test('price shown comes only from the Store object, never from the backend', async () => {
  const { AndroidPlayAdapter } = await load('purchases/androidPlay');
  const s = setup();
  s.backend.products = async () => ({ items: [{ product_id: 'p1', sku_id: 'gp_1', shard_milli: '5000', gross_brl: '0.01', price: '0,01' }] });
  const a = new AndroidPlayAdapter(s.plugin, s.backend);
  const list = await a.listProducts();
  assert.equal(list[0].displayPrice, 'R$ 4,99 (Store)');
  assert.equal(list[0].shardMilli, '5000');
  s.plugin.getProducts = async () => ({ products: [] });   // product missing in Store -> not offered
  assert.deepEqual(await a.listProducts(), []);
});

test('purchase passes the server obfuscated id; cancel never calls verify', async () => {
  const { AndroidPlayAdapter } = await load('purchases/androidPlay');
  const s = setup({ purchaseResult: { cancelled: true } });
  const a = new AndroidPlayAdapter(s.plugin, s.backend);
  const seen = [];
  a.subscribe(r => seen.push(r.status));
  const r = await a.purchase('p1');
  assert.equal(r.status, 'cancelled');
  assert.equal(s.calls.launch[0].obfuscatedAccountId, ACCT);
  assert.equal(s.calls.verify.length, 0);
  assert.deepEqual(seen, ['cancelled']);
});

test('PENDING event shows pending and never verifies or credits', async () => {
  const { AndroidPlayAdapter } = await load('purchases/androidPlay');
  const s = setup();
  const a = new AndroidPlayAdapter(s.plugin, s.backend);
  const seen = [];
  a.subscribe(r => seen.push(r.status));
  await a.purchase('p1');
  s.listeners.purchaseUpdated(ev('PENDING'));
  await a.idle();
  assert.deepEqual(seen, ['pending']);
  assert.equal(s.calls.verify.length, 0);
});

test('PURCHASED event: server decides; tampered fields are only forwarded, and server pending => pending', async () => {
  const { AndroidPlayAdapter } = await load('purchases/androidPlay');
  const s = setup({ verify: () => ({ status: 'pending' }) });
  const a = new AndroidPlayAdapter(s.plugin, s.backend);
  const seen = [];
  a.subscribe(r => seen.push(r));
  await a.purchase('p1');
  s.listeners.purchaseUpdated({ ...ev(), shard_milli: '999999999', credited: true, price: '0' });
  await a.idle();
  assert.equal(s.calls.verify.length, 1);
  assert.deepEqual(Object.keys(s.calls.verify[0]).sort(), ['order_id', 'product_id', 'purchase_token']);
  assert.equal(seen.at(-1).status, 'pending');
  assert.equal(seen.at(-1).shardMilli, undefined);
});

test('verify failure surfaces as error, not fulfilled, and can be retried', async () => {
  const { AndroidPlayAdapter } = await load('purchases/androidPlay');
  let n = 0;
  const s = setup({ verify: () => { if (n++ === 0) throw new Error('google_play_unconfigured'); return { status: 'fulfilled', shard_milli: '5000' }; } });
  const a = new AndroidPlayAdapter(s.plugin, s.backend);
  const [first] = await Promise.all([a.handle(ev())]);
  assert.equal(first.status, 'error');
  assert.equal(first.code, 'google_play_unconfigured');
  assert.equal((await a.handle(ev())).status, 'fulfilled');
});

test('resume resend dedupes: same token verified once while in flight and after fulfilled', async () => {
  const { AndroidPlayAdapter } = await load('purchases/androidPlay');
  const owned = [ev('PURCHASED', 'tok-' + 'y'.repeat(20)), ev('PURCHASED', 'tok-' + 'y'.repeat(20)), ev('PENDING', 'tok-' + 'z'.repeat(20))];
  const s = setup({ owned });
  const a = new AndroidPlayAdapter(s.plugin, s.backend);
  const out = await a.restorePending();
  assert.deepEqual(out.map(r => r.status), ['fulfilled', 'fulfilled', 'pending']);
  assert.equal(s.calls.verify.length, 1);
  await a.restorePending();                       // next resume
  assert.equal(s.calls.verify.length, 1);
});

test('server kill switch: no launchBillingFlow, no products, neutral flag set', async () => {
  const { AndroidPlayAdapter } = await load('purchases/androidPlay');
  const s = setup({ profile: { purchases_disabled: true } });
  const a = new AndroidPlayAdapter(s.plugin, s.backend);
  assert.deepEqual(await a.listProducts(), []);
  assert.equal(a.disabled, true);
  const r = await a.purchase('p1');
  assert.equal(r.status, 'disabled');
  assert.equal(s.calls.launch.length, 0);
  // re-enabled on the server -> flag follows the next read
  s.backend.profile = async () => ({ obfuscated_account_id: ACCT, purchases_disabled: false });
  assert.equal((await a.purchase('p1')).status, 'started');
  assert.equal(a.disabled, false);
  assert.equal(s.calls.launch.length, 1);
});

test('concurrent restorePending calls share one query and one verify per token', async () => {
  const { AndroidPlayAdapter } = await load('purchases/androidPlay');
  let queries = 0;
  const s = setup({ owned: [ev()] });
  const q = s.plugin.queryPendingPurchases;
  s.plugin.queryPendingPurchases = async () => { queries++; await new Promise(r => setTimeout(r, 10)); return q(); };
  const a = new AndroidPlayAdapter(s.plugin, s.backend);
  await Promise.all([a.restorePending(), a.restorePending(), a.restorePending()]);
  assert.equal(queries, 1);
  assert.equal(s.calls.verify.length, 1);
  await a.restorePending();                       // later call runs again, token already fulfilled
  assert.equal(queries, 2);
  assert.equal(s.calls.verify.length, 1);
});
