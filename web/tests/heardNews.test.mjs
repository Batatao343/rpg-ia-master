import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/heardNews.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const mk = (text, day) => ({ day, period: 'Noite', location_id: 'x', location_name: 'Brekmar', text, source: 'pulse', turn: day });

test('orderNews: newest first, empty/undefined safe', async () => {
  const m = await load();
  assert.deepEqual(m.orderNews([mk('a', 1), mk('b', 2)]).map((n) => n.text), ['b', 'a']);
  assert.deepEqual(m.orderNews(undefined), []);
  assert.deepEqual(m.orderNews([]), []);
});

test('newsLabel: Dia N · Período · Local', async () => {
  const m = await load();
  assert.equal(m.newsLabel(mk('a', 3)), 'Dia 3 · Noite · Brekmar');
  assert.equal(m.newsLabel({ ...mk('a', 3), period: '' }), 'Dia 3 · Brekmar');
});

test('newsLabel: date_label substitui o Dia N (SPEC-307)', async () => {
  const m = await load();
  assert.equal(m.newsLabel({ ...mk('a', 3), date_label: '3º dia de Vorrnak, Sino de Cobre — Ano 112 da Era 7' }),
    '3º dia de Vorrnak, Sino de Cobre — Ano 112 da Era 7 · Noite · Brekmar');
});
