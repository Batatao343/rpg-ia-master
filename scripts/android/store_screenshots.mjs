// SPEC-198: captures Play Store phone screenshots from the emulator against STAGING (synthetic user).
// Usage: node scripts/android/store_screenshots.mjs <user.json> <outdir> [pkg]
// user.json = {email,password,game_id} from a synthetic staging user (cleanup afterwards!). Debug APK (WebView debuggable) installed.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const [userFile, outDir, PKG = 'dev.rpgia.valoria.staging'] = process.argv.slice(2);
const U = JSON.parse(fs.readFileSync(userFile, 'utf8'));
const ADB = path.join(process.env.LOCALAPPDATA + '/Android/Sdk', 'platform-tools', 'adb.exe');
fs.mkdirSync(outDir, { recursive: true });
const adb = (...a) => execFileSync(ADB, a, { encoding: 'utf8' }).trim();
const sleep = ms => new Promise(r => setTimeout(r, ms));
adb('shell', 'am', 'force-stop', PKG);
adb('shell', 'pm', 'clear', PKG);
adb('shell', 'am', 'start', '-n', `${PKG}/.MainActivity`);
let sock;
for (let i = 0; i < 60 && !sock; i++) {
  await sleep(1000);
  const pid = adb('shell', 'pidof', PKG).split(/\s+/)[0];
  if (!pid) continue;
  sock = adb('shell', 'cat', '/proc/net/unix').split('\n').map(l => l.trim().split(/\s+/).pop()).find(n => n?.startsWith('@webview_devtools_remote_') && n.endsWith('_' + pid));
}
if (!sock) throw new Error('no devtools socket');
adb('forward', 'tcp:9345', `localabstract:${sock.slice(1)}`);
let target;
for (let i = 0; i < 40 && !target; i++) {
  try { target = (await (await fetch('http://127.0.0.1:9345/json')).json()).find(t => t.type === 'page'); } catch {}
  if (!target) await sleep(1000);
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r));
let id = 0; const waiting = new Map();
ws.addEventListener('message', m => { const d = JSON.parse(m.data); waiting.get(d.id)?.(d); });
const send = (method, params = {}) => new Promise(r => { const n = ++id; waiting.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
const ev = async e => (await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true })).result?.result?.value;
let n = 0;
const shot = async name => { await sleep(1500); const f = path.join(outDir, `${String(++n).padStart(2, '0')}_${name}.png`);
  fs.writeFileSync(f, execFileSync(ADB, ['exec-out', 'screencap', '-p'], { maxBuffer: 1 << 28 })); console.log('shot', f); };
const text = () => ev('document.body.innerText.slice(0,300)');
await sleep(4000);
await shot('login');
// log in through the app's own API (same origin, browser-set Origin), then reload into the session
const login = await ev(`fetch('/auth/login',{method:'POST',credentials:'include',headers:{'content-type':'application/json'},body:JSON.stringify({email:${JSON.stringify(U.email)},password:${JSON.stringify(U.password)},captcha_token:'XXXX.DUMMY.TOKEN.XXXX'})}).then(r=>r.status)`);
console.log('login status', login);
await send('Page.reload');
await sleep(5000);
await shot('home_saves');
console.log(await text());
const click = t => ev(`(() => { const e=[...document.querySelectorAll('button,a,li,div')].filter(x=>x.children.length<4 && x.textContent.trim().toLowerCase().includes(${JSON.stringify(t.toLowerCase())})).pop(); if(!e) return false; e.click(); return true; })()`);
console.log('open save', await click(U.game_name || 'Spec197'));
await sleep(6000);
await shot('narrative');
console.log((await text()).split(String.fromCharCode(10)).join(' | '));
// character sheet / map / chronicle buttons: try common labels, screenshot each that exists
for (const label of ['Ficha', 'Mapa', 'Crônica', 'Inventário']) {
  if (await click(label)) { await sleep(2500); await shot(label.toLowerCase().normalize('NFD').replace(/[^a-z]/g, '')); await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape' }); await ev('history.back()'); await sleep(1000); }
}
const acc = await click('Conta'); console.log('account', acc);
ws.close();
