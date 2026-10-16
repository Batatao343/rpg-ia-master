import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/outcomeToast.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}
const o = { receipt_id: 'r1', turn: 1, xp_delta: 50, level_delta: 1, level_after: 2, gold_delta: 5,
  items_gained: [{ id: 'p', name: 'Poção', qty: 2 }], quests_completed: [{ id: 'q', title: 'Achar o anel' }], source: 'mixed' };

test('formats xp, level, gold, items and quests', async () => {
  const { outcomeLines } = await load();
  assert.deepEqual(outcomeLines(o), ['+50 XP', 'Nível 2!', '+5 ouro', '+2 Poção', 'Missão concluída: Achar o anel']);
});

test('no lines for empty/zero outcomes; repeated receipt is not new', async () => {
  const { outcomeLines, isNewReceipt } = await load();
  assert.deepEqual(outcomeLines({ ...o, xp_delta: 0, level_delta: 0, gold_delta: 0, items_gained: [], quests_completed: [] }), []);
  assert.equal(isNewReceipt(o, null), true);
  assert.equal(isNewReceipt(o, 'r1'), false);
  assert.equal(isNewReceipt(null, null), false);
});
