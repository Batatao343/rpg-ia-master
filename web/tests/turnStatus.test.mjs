import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load(rel) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(rel, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}`);
}
const m = await load('../src/turnWait.ts');

test('phase ledger accumulates in order without duplicates (R2)', () => {
  let l = m.EMPTY_LEDGER;
  for (const label of [m.PHASE_TEXTS.campaign_manager, m.PHASE_TEXTS.dm_router, m.PHASE_TEXTS.dm_router,
    m.ROUTE_TEXTS.storyteller, m.PHASE_TEXTS.storyteller, m.PHASE_TEXTS.archivist, null]) l = m.addPhase(l, label);
  assert.deepEqual(l.phases, [m.PHASE_TEXTS.campaign_manager, m.PHASE_TEXTS.dm_router, m.PHASE_TEXTS.storyteller]);
  assert.equal(l.current, m.PHASE_TEXTS.archivist);
  assert.equal(new Set([...l.phases, l.current]).size, l.phases.length + 1);
});

test('phase texts carry no emoji', () => {
  for (const t of [...Object.values(m.PHASE_TEXTS), ...Object.values(m.ROUTE_TEXTS)])
    assert.ok(!/\p{Extended_Pictographic}/u.test(t), t);
});

test('wait tiers cross at 8 s (reassure) and 25 s (retry)', () => {
  assert.equal(m.REASSURE_MS, 8000);
  assert.equal(m.RETRY_MS, 25000);
  assert.equal(m.waitTier(0), 'none');
  assert.equal(m.waitTier(7999), 'none');
  assert.equal(m.waitTier(8000), 'reassure');
  assert.equal(m.waitTier(24999), 'reassure');
  assert.equal(m.waitTier(25000), 'retry');
});

test('stage machine: narrative(done) -> state goes narrated -> idle (SPEC-316 hooks)', () => {
  let s = m.nextStage('idle', 'submit');
  assert.equal(s, 'waiting');
  s = m.nextStage(s, 'narrative-done');
  assert.equal(s, 'narrated');
  assert.equal(m.nextStage(s, 'state'), 'idle');
  // erro depois da narração: preserva o estágio de falha até o retry
  assert.equal(m.nextStage(s, 'error-after-narration'), 'failed-after-narration');
  // sem SPEC-316 (sem done antes do state) nada de "narrated"
  assert.equal(m.nextStage('idle', 'narrative-done'), 'idle');
  assert.equal(m.nextStage(m.nextStage('idle', 'submit'), 'state'), 'idle');
});

test('opening: only the first narration of a session and the first after a location change', () => {
  let memo = { gid: '', seen: false, loc: '' };
  const step = (gid, loc, text) => { const r = m.nextOpening(memo, gid, loc, text); memo = r.memo; return r.opening; };
  assert.equal(step('g1', 'Porto', 'A névoa sobe.'), true);
  assert.equal(step('g1', 'Porto', 'Você caminha.'), false);
  assert.equal(step('g1', 'Floresta', 'As árvores se fecham.'), true);
  assert.equal(step('g1', 'Floresta', 'Outro beat.'), false);
  assert.equal(step('g2', 'Porto', 'Nova jornada.'), true);
});

test('opening is never used when the text starts with dash or quote', () => {
  for (const t of ['— Quem vem lá?', '“Parado!”', '"Alto"', '«Salve»', '  — recuado'])
    assert.equal(m.openingAllowed(t, true), false, t);
  assert.equal(m.openingAllowed('Quem vem lá?', true), true);
  assert.equal(m.openingAllowed('Quem vem lá?', false), false);
});

test('capitular CSS is gated by data-opening and has no glow', () => {
  const css = readFileSync(fileURLToPath(new URL('../src/styles.css', import.meta.url)), 'utf8');
  assert.ok(/\.msg--story\[data-opening\] \.msg__body::first-letter/.test(css));
  assert.ok(!/\.msg--story \.msg__body::first-letter/.test(css));
  assert.ok(!/first-child \.msg__body::first-letter/.test(css));
  assert.ok(!/\.thinking/.test(css));
});
