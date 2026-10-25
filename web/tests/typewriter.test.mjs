import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/hooks/useTypewriter.ts', import.meta.url))],
  bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent',
  plugins: [{ name: 'react-stub', setup(b) {
    b.onResolve({ filter: /^react$/ }, () => ({ path: 'react', namespace: 'stub' }));
    b.onLoad({ filter: /.*/, namespace: 'stub' }, () => ({ contents: 'export const useEffect=()=>{},useCallback=f=>f,useRef=v=>({current:v}),useState=v=>[typeof v==="function"?v():v,()=>{}];' }));
  } }] });
const hook = await import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}`);

test('non-animated entries render full text on the first frame (R7)', () => {
  assert.equal(hook.typewriterInitial('historia completa', false), 'historia completa');
  assert.equal(hook.typewriterInitial('historia completa', true), '');
});

test('effects off (reduced-motion / kill switch) reveal the whole text on the first frame (SPEC-320 R5)', () => {
  assert.equal(hook.typewriterInitial('historia completa', true, false), 'historia completa');
  assert.equal(hook.typewriterInitial('historia completa', true, true), '');
});

test('step is deterministic and reports done only when the whole text is revealed', () => {
  const text = 'abcdefghij';
  assert.deepEqual(hook.typewriterStep(text, 0, 1), { idx: 1, done: false });
  assert.deepEqual(hook.typewriterStep(text, 0, 1), hook.typewriterStep(text, 0, 1));
  assert.equal(hook.typewriterStep(text, 9, 1).done, true);
  let idx = 0, ticks = 0, done = false;
  while (!done) { ({ idx, done } = hook.typewriterStep(text, idx, 3)); ticks++; assert.ok(ticks < 50); }
  assert.equal(ticks, 4);
});

test('the hook source has no Math.random (constant cadence, SPEC-320 R7)', () => {
  const src = readFileSync(fileURLToPath(new URL('../src/hooks/useTypewriter.ts', import.meta.url)), 'utf8');
  assert.ok(!/Math\.random/.test(src));
});

test('reveal of one beat takes at most TYPEWRITER_MAX_MS for any length', () => {
  for (const len of [10, 400, 1200, 5000, 20000]) {
    const text = 'x'.repeat(len);
    const per = hook.typewriterCharsPerTick(len, 2500, 30);
    let idx = 0, ticks = 0, done = false;
    while (!done) { ({ idx, done } = hook.typewriterStep(text, idx, per)); ticks++; }
    assert.ok(ticks * 30 <= 2500 || per === hook.TYPEWRITER_BASE_STEP && len <= 2500 / 30 * per,
      `len ${len}: ${ticks * 30} ms`);
  }
  assert.equal(hook.typewriterCharsPerTick(1200, 2500, 30) >= hook.TYPEWRITER_BASE_STEP, true);
});

test('a growing text never leaves the cursor more than ~1 s behind', () => {
  // texto recebido por chunks de 80 car: ao continuar (idx > 0) o passo usa o teto de ~1 s de atraso
  const lag = hook.TYPEWRITER_LAG_MS;
  const per = hook.typewriterCharsPerTick(900, lag, 30);
  const ticks = Math.ceil(900 / per);
  assert.ok(ticks * 30 <= lag + 30);
});
