import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/combatOutcome.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const result = { encounter_id: 'g:0:1', outcome: 'victory', ended_round: 2, loot_ref: null,
  xp_event_ref: 'rc-4', result_event_id: 'res-1',
  participants: [{ participant_id: 'b1', species_label: 'Bandido', final_status: 'morto' }] };
const outcome = { receipt_id: 'rc-4', turn: 4, xp_delta: 50, level_delta: 0, gold_delta: 0,
  items_gained: [], quests_completed: [], source: 'combat' };

test('SPEC-203: rewards só do recibo do turno de término', async () => {
  const { rewardLines, casualtyLines, resultFrom, shouldShowResult, OUTCOME_TITLES } = await load();
  assert.deepEqual(rewardLines(result, outcome), ['+50 XP']);
  assert.deepEqual(rewardLines(result, { ...outcome, receipt_id: 'other' }), []);
  assert.deepEqual(casualtyLines(result), ['Bandido — abatido']);
  assert.equal(resultFrom({}), null);
  assert.equal(shouldShowResult(result, 'res-1'), false);
  assert.equal(shouldShowResult(result, null), true);
  assert.equal(OUTCOME_TITLES.fled, 'Você escapou');
});
