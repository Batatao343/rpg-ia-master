import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/hooks/useTypewriter.ts', import.meta.url))],
  bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent',
  plugins: [{ name: 'react-stub', setup(b) {
    b.onResolve({ filter: /^react$/ }, () => ({ path: 'react', namespace: 'stub' }));
    b.onLoad({ filter: /.*/, namespace: 'stub' }, () => ({ contents: 'export const useEffect=()=>{},useRef=v=>({current:v}),useState=v=>[typeof v==="function"?v():v,()=>{}];' }));
  } }] });
const hook = await import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}`);

test('non-animated entries render full text on the first frame (R7)', () => {
  assert.equal(hook.typewriterInitial('historia completa', false), 'historia completa');
  assert.equal(hook.typewriterInitial('historia completa', true), '');
});

test('step reports done only when the whole text is revealed', () => {
  const text = 'abcdefghij';
  assert.deepEqual(hook.typewriterStep(text, 0, 0), { idx: 1, done: false });
  assert.equal(hook.typewriterStep(text, 9, 0).done, true);
  let idx = 0, ticks = 0, done = false;
  while (!done) { ({ idx, done } = hook.typewriterStep(text, idx, 0.5)); ticks++; assert.ok(ticks < 50); }
});
