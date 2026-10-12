import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

async function load(name, replacements = {}) {
  let source = await readFile(new URL(`../src/${name}.ts`, import.meta.url), 'utf8');
  for (const [from, to] of Object.entries(replacements)) source = source.replace(from, to);
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }});
  return `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`;
}
const recorderUrl = await load('voice/recorder');
const { VoiceController } = await import(await load('voice/controller', { '"./recorder"': JSON.stringify(recorderUrl) }));
const { webRecorder } = await import(recorderUrl);
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const flush = async () => { await Promise.resolve(); await Promise.resolve(); };
function harness(transcribe = async () => 'Examino a porta') {
  let stops = 0, cancels = 0;
  const states = [], texts = [];
  const adapter = { start: async () => ({ stop: async () => { stops++; return new Blob(['audio'], { type: 'audio/webm' }); }, cancel: () => { cancels++; } }) };
  const controller = new VoiceController(adapter, transcribe, s => states.push(s.phase), t => texts.push(t));
  return { controller, adapter, states, texts, stops: () => stops, cancels: () => cancels };
}

test('voice flows through upload/transcription, supplies only editable text and stops once', async () => {
  const h = harness(async (audio, signal, uploaded) => { assert.equal(audio.type, 'audio/webm'); assert.equal(signal.aborted, false); uploaded(); return '  Examino a porta  '; });
  await h.controller.start();
  const pending = h.controller.stop();
  await h.controller.stop();
  await pending;
  assert.equal(h.stops(), 1);
  assert.deepEqual(h.states, ['idle', 'recording', 'uploading', 'transcribing', 'idle']);
  assert.deepEqual(h.texts, ['Examino a porta']);
});

test('60 second deadline stops and transcribes exactly once', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const h = harness();
  await h.controller.start();
  t.mock.timers.tick(59_000);
  assert.equal(h.stops(), 0); assert.equal(h.controller.state.seconds, 59);
  t.mock.timers.tick(1_000);
  await flush();
  assert.equal(h.stops(), 1); assert.equal(h.texts.length, 1);
  t.mock.timers.tick(60_000); assert.equal(h.stops(), 1);
});

test('denied permission announces a clear error without transcript', async () => {
  const h = harness();
  h.adapter.start = async () => { throw new DOMException('denied', 'NotAllowedError'); };
  await h.controller.start();
  assert.equal(h.controller.state.phase, 'error');
  assert.match(h.controller.state.message, /Permissão.*negada/); assert.deepEqual(h.texts, []);
});

test('cancel while permission is pending fences late recorder and allows new capture', async () => {
  const h = harness(); const gate = deferred(); let lateCancelled = 0;
  h.adapter.start = () => gate.promise;
  const start = h.controller.start(); h.controller.cancel();
  gate.resolve({ cancel() { lateCancelled++; }, stop() { throw Error('must not stop/upload'); } });
  await start;
  assert.equal(lateCancelled, 1); assert.equal(h.controller.state.phase, 'idle');
  assert.deepEqual(h.texts, []);
});

test('background/unmount cancellation clears timers, releases capture and drops delayed transcript', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const gate = deferred(); let signal;
  const h = harness(async (_audio, abort) => { signal = abort; return gate.promise; });
  await h.controller.start(); h.controller.cancel(false);
  assert.equal(h.cancels(), 1); t.mock.timers.tick(60_000); assert.equal(h.stops(), 0);
  await h.controller.start(); const pending = h.controller.stop(); await flush();
  h.controller.cancel(false); assert.equal(signal.aborted, true);
  gate.resolve('Late text'); await pending; assert.deepEqual(h.texts, []);
});

test('STT error and empty transcript never yield text; retry remains available', async () => {
  const h = harness(async () => { throw Error('STT indisponível'); });
  await h.controller.start(); await h.controller.stop();
  assert.equal(h.controller.state.phase, 'error'); assert.deepEqual(h.texts, []);
  await h.controller.start(); assert.equal(h.controller.state.phase, 'recording'); h.controller.cancel();
  const empty = harness(async () => '  '); await empty.controller.start(); await empty.controller.stop();
  assert.equal(empty.controller.state.phase, 'error'); assert.deepEqual(empty.texts, []);
});

test('recorder failure immediately releases capture and announces error without waiting for hard stop', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'] });
  const h = harness(); let fail;
  const original = h.adapter.start;
  h.adapter.start = async (signal, failed) => { fail = failed; return original(signal); };
  await h.controller.start(); fail(new Error('Microfone desconectado'));
  assert.equal(h.controller.state.phase, 'error'); assert.equal(h.cancels(), 1);
  t.mock.timers.tick(60_000); assert.equal(h.stops(), 0); assert.deepEqual(h.texts, []);
});

function mediaFixture({ denied = false, mime = 'audio/mp4', late = false, constructorFail = false } = {}) {
  let releases = 0, stops = 0; const gate = deferred();
  const stream = { getTracks: () => [{ stop: () => releases++ }] };
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { mediaDevices: { getUserMedia: async () => {
    if (denied) throw new DOMException('denied', 'NotAllowedError');
    return late ? gate.promise : stream;
  } } } });
  globalThis.MediaRecorder = class {
    static isTypeSupported(type) { return type === mime; }
    constructor(_stream, options) { if (constructorFail) throw Error('constructor failure'); this.mimeType = options.mimeType; this.state = 'inactive'; }
    start() { this.state = 'recording'; }
    stop() { stops++; this.state = 'inactive'; queueMicrotask(() => { this.ondataavailable({ data: new Blob(['bytes']) }); this.onstop(); }); }
  };
  return { releases: () => releases, stops: () => stops, grant: () => gate.resolve(stream) };
}

test('web adapter negotiates MIME, stops/releases tracks and emits binary Blob', async () => {
  const f = mediaFixture(); const capture = await webRecorder.start(new AbortController().signal);
  const audio = await capture.stop(); await capture.stop();
  assert.equal(audio.type, 'audio/mp4'); assert.equal(audio.size, 5); assert.equal(f.stops(), 1); assert.ok(f.releases() >= 1);
});

test('web adapter cleans a permission grant arriving after abort and constructor failure', async () => {
  const f = mediaFixture({ late: true }); const abort = new AbortController();
  const pending = webRecorder.start(abort.signal); abort.abort(); f.grant();
  await assert.rejects(pending, { name: 'AbortError' }); assert.equal(f.releases(), 1);
  const broken = mediaFixture({ constructorFail: true });
  await assert.rejects(webRecorder.start(new AbortController().signal)); assert.equal(broken.releases(), 1);
});

test('unsupported/missing recorder or MIME returns text fallback; cancel discards data', async () => {
  mediaFixture({ mime: 'unsupported' }); await assert.rejects(webRecorder.start(new AbortController().signal), /Formato/);
  delete globalThis.MediaRecorder; await assert.rejects(webRecorder.start(new AbortController().signal), /indisponível/);
  const f = mediaFixture(); const abort = new AbortController(); const capture = await webRecorder.start(abort.signal);
  abort.abort(); await assert.rejects(capture.stop(), { name: 'AbortError' }); assert.equal(f.stops(), 1); assert.ok(f.releases());
});
