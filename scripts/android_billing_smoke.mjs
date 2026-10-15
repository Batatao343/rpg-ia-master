// SPEC-194 emulator smoke: mock API + built web/dist on :8765, WebView driven over CDP (adb forward).
// Usage: node scripts/android_billing_smoke.mjs <evidence_dir>   (emulator up, debug APK with
// -PplayBillingFake=true installed; app launched by this script). Proves plugin wiring, NOT real billing.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const OUT = path.resolve(process.argv[2] || 'docs/spec194/evidence');
const DIST = path.resolve('web/dist');
const ADB = path.join(process.env.ANDROID_HOME || process.env.LOCALAPPDATA + '/Android/Sdk', 'platform-tools', 'adb.exe');
const PKG = 'dev.rpgia.valoria.staging';
fs.mkdirSync(OUT, { recursive: true });
const adb = (...a) => execFileSync(ADB, a, { encoding: 'utf8' }).trim();
const sleep = ms => new Promise(r => setTimeout(r, ms));

const ACCT = 'c'.repeat(64);
const state = { disabled: false, balance: 0, requests: [], verify: [] };
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.png': 'image/png' };
const json = (res, code, body) => { res.writeHead(code, { 'content-type': 'application/json', 'cache-control': 'no-store' }); res.end(JSON.stringify(body)); };

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  let body = '';
  req.on('data', c => body += c);
  req.on('end', () => {
    const p = url.pathname;
    if (!/\.(js|css|webp|svg|png|html|ico)$/.test(p) && p !== '/') state.requests.push({ m: req.method, p, client: req.headers['x-rpg-client'] || null });
    if (p === '/auth/config') return json(res, 200, { required: true, authenticated: true, lifecycle_available: false });
    if (p === '/game/saves') return json(res, 200, []);
    if (p === '/account/balance') return json(res, 200, { available_milli: String(state.balance), reserved_milli: '0' });
    if (p === '/account/series') return json(res, 200, { period: '7d', unit: 'milli_shard', totals: { game: '0', image: '0', voice: '0' }, points: [] });
    if (p === '/account/usage' || p === '/account/purchases') return json(res, 200, { items: [], next_cursor: null });
    if (p === '/account/purchases/google/profile') return json(res, 200, { obfuscated_account_id: ACCT, purchases_disabled: state.disabled });
    if (p === '/account/purchases/google/products') return json(res, 200, { items: [
      { product_id: 'estilhas_pack_small', sku_id: 'gp_small', shard_milli: '5000' },
      { product_id: 'estilhas_cancel_test', sku_id: 'gp_cancel', shard_milli: '5000' },
      { product_id: 'estilhas_pending_test', sku_id: 'gp_pending', shard_milli: '5000' }] });
    if (p === '/account/purchases/google/verify') {
      const b = JSON.parse(body || '{}');
      state.verify.push({ ...b, purchase_token: b.purchase_token?.slice(0, 12) + '...' });
      state.balance += 5000;
      return json(res, 200, { status: 'fulfilled', state: 'consumed', product_id: b.product_id, shard_milli: '5000', consumed: true });
    }
    if (p.startsWith('/account/checkout')) return json(res, 403, { detail: 'stripe_unavailable_on_android' });
    const file = path.join(DIST, p === '/' ? 'index.html' : p);
    if (file.startsWith(DIST) && fs.existsSync(file) && fs.statSync(file).isFile()) {
      res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream' });
      return res.end(fs.readFileSync(file));
    }
    if (p.startsWith('/data') || p.startsWith('/game') || p.startsWith('/auth')) return json(res, 404, { detail: 'mock_not_found' });
    res.writeHead(200, { 'content-type': 'text/html' }); res.end(fs.readFileSync(path.join(DIST, 'index.html')));
  });
}).listen(8765, '0.0.0.0');

async function cdp() {
  adb('shell', 'am', 'force-stop', PKG);
  adb('shell', 'am', 'start', '-n', `${PKG}/.MainActivity`);
  let sock;
  for (let i = 0; i < 40 && !sock; i++) {
    await sleep(1000);
    const pid = adb('shell', 'pidof', PKG).split(/\s+/)[0];
    if (!pid) continue;
    const socks = adb('shell', 'cat', '/proc/net/unix').split('\n').map(l => l.trim().split(/\s+/).pop()).filter(n => n?.startsWith('@webview_devtools_remote_'));
    sock = socks.find(s => s.endsWith('_' + pid));
  }
  if (!sock) throw new Error('no devtools socket');
  adb('forward', 'tcp:9344', `localabstract:${sock.slice(1)}`);
  let target;
  for (let i = 0; i < 30 && !target; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:9344/json')).json();
      target = list.find(t => t.type === 'page' && t.url.includes('10.0.2.2'));
    } catch { /* retry */ }
    if (!target) await sleep(1000);
  }
  if (!target) throw new Error('no page target');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r));
  let id = 0; const waiting = new Map();
  ws.addEventListener('message', m => { const d = JSON.parse(m.data); waiting.get(d.id)?.(d); });
  const send = (method, params = {}) => new Promise(r => { const n = ++id; waiting.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
  const ev = async expr => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result?.result?.value;
  return { send, ev, close: () => ws.close() };
}

const results = { spec: 'SPEC-194', mode: 'PLAY_BILLING_FAKE debug build + mock API (NOT real Play Billing)', steps: [] };
const step = (name, ok, detail) => { results.steps.push({ name, ok, detail }); console.log(ok ? 'PASS' : 'FAIL', name, detail ?? ''); };
let shot = 0;
async function screenshot(c, name) {
  const r = await c.send('Page.captureScreenshot', { format: 'jpeg', quality: 45 });
  fs.writeFileSync(path.join(OUT, `${String(++shot).padStart(2, '0')}_${name}.jpg`), Buffer.from(r.result.data, 'base64'));
}
async function waitFor(c, expr, ms = 15000) {
  const t = Date.now();
  while (Date.now() - t < ms) { if (await c.ev(expr)) return true; await sleep(300); }
  return false;
}
const clickBuy = (c, label) => c.ev(`(() => { const li=[...document.querySelectorAll('.checkout-packages li')]; const el = li.find(x => ${label ? `x.textContent.includes(${JSON.stringify(label)})` : 'true'}); if(!el) return false; el.querySelector('button').click(); return true; })()`);
const text = c => c.ev('document.body.innerText');

const c = await cdp();
try {
  await c.send('Page.enable');
  step('platform is android', (await c.ev('globalThis.Capacitor?.getPlatform?.()')) === 'android');
  step('plugin registered natively', (await c.ev("!!(globalThis.Capacitor?.PluginHeaders||[]).find(p=>p.name==='PlayBilling')")) === true);
  step('Conta link visible', await waitFor(c, "[...document.querySelectorAll('button')].some(b=>b.textContent.startsWith('Conta'))"));
  await c.ev("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Conta')).click()");
  step('Play packages listed with Store price', await waitFor(c, "document.querySelectorAll('.checkout-packages li').length===3"));
  const t1 = await text(c);
  step('price shown is fake Store price R$ 9,99 (backend sends none)', (t1.match(/R\$\s?9,99/g) || []).length === 3);
  step('Stripe checkout NOT requested', !state.requests.some(r => r.p.startsWith('/account/checkout')));
  step('requests carry X-RPG-Client: android', state.requests.every(r => r.client === 'android'));
  await screenshot(c, 'products');

  await clickBuy(c, 'pack_small') || await clickBuy(c);
  step('purchase -> purchaseUpdated -> /verify called once', await waitFor(c, 'true') && await (async () => { for (let i = 0; i < 30 && state.verify.length < 1; i++) await sleep(300); return state.verify.length === 1; })(), state.verify);
  step('verify body = product_id + fake token + order id only', state.verify[0] && Object.keys(state.verify[0]).sort().join() === 'order_id,product_id,purchase_token' && state.verify[0].purchase_token.startsWith('fake-'));
  step('UI confirms only after server answer', await waitFor(c, "document.body.innerText.includes('Compra confirmada pelo servidor')"));
  await screenshot(c, 'fulfilled');

  const before = state.verify.length;
  const cancelIdx = await c.ev("[...document.querySelectorAll('.checkout-packages li')].findIndex(x => x.textContent.length>0)");
  // product order = small, cancel, pending ; li text has no id, so click by index
  const clickIdx = i => c.ev(`document.querySelectorAll('.checkout-packages li')[${i}].querySelector('button').click()`);
  await clickIdx(1);
  step('cancel path: notice, no verify', await waitFor(c, "document.body.innerText.includes('Compra cancelada')") && state.verify.length === before);
  await screenshot(c, 'cancelled');
  await clickIdx(2);
  step('pending path: notice, no verify, no credit', await waitFor(c, "document.body.innerText.includes('Pagamento pendente')") && state.verify.length === before && state.balance === 5000);
  await screenshot(c, 'pending');

  state.disabled = true;
  await clickIdx(0);
  step('kill switch: neutral message, billing never launched', await waitFor(c, "document.body.innerText.includes('temporariamente indisponíveis')") && state.verify.length === before);
  await screenshot(c, 'disabled');
} catch (e) {
  step('smoke exception', false, String(e));
}
results.requests_seen = [...new Set(state.requests.map(r => `${r.m} ${r.p}`))];
results.verify_calls = state.verify;
results.passed = results.steps.every(s => s.ok);
fs.writeFileSync(path.join(OUT, 'emulator_smoke.json'), JSON.stringify(results, null, 2));
c.close(); server.close();
process.exit(results.passed ? 0 : 1);
