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
const { htmlToPlain, revealHtml } = await load('../src/revealHtml.ts');
const { mdLite } = await load('../src/lib.ts');

test('revealHtml cuts by visible characters and closes open tags', () => {
  const html = mdLite('Um **herói** &  <b> *sombrio*');
  const plain = htmlToPlain(html);
  assert.equal(plain, 'Um herói &  <b> sombrio');
  assert.equal(revealHtml(html, plain.length), html);
  assert.equal(revealHtml(html, 0), '');
  assert.equal(revealHtml(html, 5), 'Um <strong>he</strong>');
  // entidade conta como 1 caractere e nunca é cortada ao meio
  const amp = revealHtml(html, 10);
  assert.ok(!/&[a-z]*$/.test(amp), amp);
});

test('mdLite runs at most once per received chunk, not once per tick (R8)', () => {
  let calls = 0;
  const parse = (t) => { calls++; return mdLite(t); };
  let text = '';
  for (const chunk of ['A **noite** ', 'cai sobre ', 'o *porto*.']) {
    text += chunk;
    const html = parse(text);               // 1 parse por chunk recebido
    const plain = htmlToPlain(html);
    for (let n = 0; n <= plain.length; n += 3) revealHtml(html, n); // dezenas de ticks sem parse
  }
  assert.equal(calls, 3);
});

test('StoryLog parses markdown from memoized text, never from the per-tick displayed text', () => {
  const src = readFileSync(fileURLToPath(new URL('../src/components/StoryLog.tsx', import.meta.url)), 'utf8');
  assert.ok(/useMemo\(\(\) => mdLite\(entry\.text\), \[entry\.text\]\)/.test(src));
  assert.ok(!/mdLite\(displayedText\)/.test(src));
  assert.ok(!/thinking__dot|className="thinking"/.test(src));
});
