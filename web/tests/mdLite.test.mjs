import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/lib.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const FORBIDDEN = ['<img', '<a', '<script', '<iframe'];

test('mdLite: HTML injetado sai escapado (sem tag viva)', async () => {
  const { mdLite } = await load();
  for (const payload of [
    '<img src=x onerror=alert(1)>',
    '<a href="javascript:alert(1)">x</a>',
    '**<script>**',
    '*<script>alert(1)</script>*',
  ]) {
    const out = mdLite(payload);
    for (const bad of FORBIDDEN) assert.ok(!out.includes(bad), `${bad} em ${out}`);
    assert.ok(!out.includes('<'.concat('/a>')), out);
    // todo '<' restante pertence apenas às tags do próprio mdLite
    const tags = out.match(/<[^>]*>/g) ?? [];
    for (const t of tags) assert.ok(['<strong>', '</strong>', '<em>', '</em>'].includes(t), t);
  }
});

test('mdLite: negrito, & e entidade já escapada', async () => {
  const { mdLite } = await load();
  assert.equal(mdLite('**x**'), '<strong>x</strong>');
  assert.equal(mdLite('a & b'), 'a &amp; b');
  assert.equal(mdLite('&lt;'), '&amp;lt;');
});
