import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { computeBuildId } from '../scripts/buildId.mjs';

async function load(name, define = {}) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(`../src/${name}.ts`, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent', define });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const NOW = new Date(Date.UTC(2026, 9, 19, 13, 45));

test('build id: sha curto do Vercel/GIT_SHA + timestamp UTC', () => {
  assert.equal(computeBuildId({ VERCEL_GIT_COMMIT_SHA: 'ABCDEF1234567890' }, NOW, () => 'zzz'), 'abcdef1+202610191345');
  assert.equal(computeBuildId({ GIT_SHA: '0123456789abcdef' }, NOW, () => 'zzz'), '0123456+202610191345');
});

test('build id: cai no git local e depois em "dev"; nunca aceita lixo', () => {
  assert.equal(computeBuildId({}, NOW, () => 'beefcafe\n'), 'beefcaf+202610191345');
  assert.equal(computeBuildId({}, NOW, () => { throw new Error('no git'); }), 'dev+202610191345');
  assert.equal(computeBuildId({ GIT_SHA: 'nao-e-sha <script>' }, NOW, () => ''), 'dev+202610191345');
});

test('vite.config define __RPG_BUILD__', () => {
  const src = readFileSync(new URL('../vite.config.ts', import.meta.url), 'utf8');
  assert.match(src, /__RPG_BUILD__/);
  assert.match(src, /computeBuildId/);
});

test('build.ts expoe o define e cai em "dev" sem ele', async () => {
  const withDefine = await load('build', { __RPG_BUILD__: JSON.stringify('abcdef1+202610191345') });
  assert.equal(withDefine.BUILD_ID, 'abcdef1+202610191345');
  assert.equal(withDefine.buildShort(), 'abcdef1');
  const without = await load('build');
  assert.equal(without.BUILD_ID, 'dev');
});

test('toda requisicao leva X-RPG-Build', async () => {
  const { http } = await load('http', { __RPG_BUILD__: JSON.stringify('abcdef1+202610191345') });
  globalThis.document = { cookie: '' };
  let seen;
  globalThis.fetch = async (_url, options) => { seen = options.headers.get('X-RPG-Build'); return new Response('{}'); };
  await http('/game/saves');
  assert.equal(seen, 'abcdef1+202610191345');
});
