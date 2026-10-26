import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/artOffers.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

test('dedupeOffers: uma oferta por NPC (subject_id ou label); cenas intactas', async () => {
  const { dedupeOffers } = await load();
  const out = dedupeOffers([
    { offer_id: '1', type: 'npc', subject_id: 'mendigo', label: 'Mendigo' },
    { offer_id: '2', type: 'npc', subject_id: 'mendigo', label: 'Mendigo' },
    { offer_id: '3', type: 'npc', subject_id: 'msg', label: 'Mensageiro' },
    { offer_id: '4', type: 'scene' }, { offer_id: '5', type: 'scene' },
    { offer_id: '6', type: 'npc' },
  ]);
  assert.deepEqual(out.map((o) => o.offer_id), ['1', '3', '4', '5', '6']);
});
