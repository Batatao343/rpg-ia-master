import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

const { outputFiles } = await build({
  entryPoints: [fileURLToPath(new URL('../src/lib/turnLatency.ts', import.meta.url))],
  bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent',
});
const mod = await import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}`);

function fakePerf() {
  let t = 1000;
  const marks = [], measures = [];
  return {
    advance: (ms) => { t += ms; },
    marks, measures,
    now: () => t,
    mark: (n) => { marks.push(n); },
    measure: (n, s, e) => { measures.push([n, s, e]); },
  };
}

test('marks follow submit < ack < ttfmc <= ttlt <= state', () => {
  const perf = fakePerf();
  const tr = new mod.TurnLatencyTracker('a1', 'stream', perf);
  tr.submit();
  perf.advance(30); tr.firstBytes();
  perf.advance(10); tr.event('accepted', { game_id: 'g' });
  perf.advance(900); tr.event('phase', { node: 'dm_router', status: 'done' });
  perf.advance(4000); tr.event('route', { route: 'storyteller' });
  tr.event('visual', {});
  tr.event('narrative', { chunk: 'Era uma vez', done: false });
  perf.advance(5); tr.event('narrative', { chunk: '', done: true });
  perf.advance(5); tr.event('state', {});
  const s = tr.summary();
  assert.equal(s.ack_ms, 30);
  assert.ok(s.ack_ms < s.ttfmc_ms);
  assert.ok(s.ttfmc_ms <= s.ttlt_ms && s.ttlt_ms <= s.state_ms);
  assert.equal(s.first_phase_ms, 940);
  assert.equal(s.outcome, 'ok');
  assert.ok(perf.marks.includes('rpg:turn:a1:submit'));
  assert.ok(perf.marks.includes('rpg:turn:a1:ttfmc'));
  assert.ok(perf.measures.some(([n]) => n === 'rpg:turn:a1:ttfmc:ms'));
});

test('accepted, ping, phase, route and visual never define TTFMC', () => {
  const perf = fakePerf();
  const tr = new mod.TurnLatencyTracker('a2', 'stream', perf);
  tr.submit();
  perf.advance(5); tr.firstBytes();
  tr.event('accepted', { game_id: 'g' });
  tr.event('phase', {});
  tr.event('route', {});
  tr.event('visual', {});
  tr.event('narrative', { chunk: '   \n', done: false });   // so espacos nao conta
  assert.equal(tr.summary().ttfmc_ms, null);
  assert.equal(tr.summary().ack_ms, 5);
  perf.advance(7); tr.event('narrative', { chunk: 'texto', done: false });
  assert.equal(tr.summary().ttfmc_ms, 12);
});

test('first occurrence wins and submit is required first', () => {
  const perf = fakePerf();
  const tr = new mod.TurnLatencyTracker('a3', 'stream', perf);
  tr.firstBytes();                                     // antes do submit: ignorado
  assert.equal(tr.summary().ack_ms, null);
  tr.submit();
  perf.advance(10); tr.firstBytes();
  perf.advance(10); tr.firstBytes();
  assert.equal(tr.summary().ack_ms, 10);
});

test('POST fallback records ttfmc = ttlt = state', () => {
  const perf = fakePerf();
  const tr = new mod.TurnLatencyTracker('a4', 'post', perf);
  tr.submit();
  perf.advance(8200); tr.completePost();
  const s = tr.summary();
  assert.equal(s.transport, 'post');
  assert.equal(s.ttfmc_ms, 8200);
  assert.equal(s.ttfmc_ms, s.ttlt_ms);
  assert.equal(s.ttlt_ms, s.state_ms);
});

test('no-op without performance support', () => {
  const tr = new mod.TurnLatencyTracker('a5', 'stream', null);
  tr.submit(); tr.firstBytes(); tr.event('narrative', { chunk: 'x', done: true });
  assert.equal(tr.summary().ttfmc_ms, null);
});

test('reporter is off until the server enables it, then sends, and gives up after a failure', async () => {
  mod.resetReporterForTests();
  let sent = 0;
  const send = async () => { sent++; };
  const summary = { action_id: 'a', transport: 'stream', ack_ms: 1, first_phase_ms: 2, ttfmc_ms: 3, ttlt_ms: 4, state_ms: 5, outcome: 'ok' };
  assert.equal(await mod.reportClientLatency(summary, send), false);   // default: desligado
  assert.equal(sent, 0);
  mod.setClientLatencyReport(true);
  assert.equal(await mod.reportClientLatency(summary, send), true);
  assert.equal(await mod.reportClientLatency(summary, send), true);
  assert.equal(sent, 2);
  assert.equal(await mod.reportClientLatency(summary, async () => { throw new Error('x'); }), false);
  assert.equal(await mod.reportClientLatency(summary, send), false);   // desistiu
  assert.equal(sent, 2);
  mod.resetReporterForTests();
});

test('old turn marks are cleared beyond KEEP_RECENT_TURNS (long sessions do not accumulate)', () => {
  const cleared = [];
  const perf = { ...fakePerf(), clear: (n) => cleared.push(n) };
  const total = mod.KEEP_RECENT_TURNS + 2;
  for (let i = 0; i < total; i++) {
    const t = new mod.TurnLatencyTracker(`rot-${i}`, 'post', perf);
    t.submit();
    t.completePost();
  }
  assert.ok(cleared.some((n) => n.includes('rot-0:')), 'oldest turn cleared');
  assert.ok(cleared.some((n) => n.includes('rot-1:')), 'second oldest cleared');
  assert.ok(!cleared.some((n) => n.includes(`rot-${total - 1}:`)), 'latest turn kept');
});
