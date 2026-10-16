import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/codexKnowledge.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const stamp = { knowledge_kind: 'rumor', certainty: 'reported', source_kind: 'npc_claim',
  source_ref: 'bestiary:x', label: 'Rumor', first_seen_turn: 2, last_updated_turn: 5, stale: false };

test('count uses server meta.counts when present, .length as fallback', async () => {
  const m = await load();
  const codex = { locations: [{}, {}], factions: [], characters: [], creatures: [], secrets: [] };
  assert.equal(m.categoryCount(codex, 'locations'), 2);
  assert.equal(m.categoryCount({ ...codex, meta: { taxonomy_version: 1, counts: { locations: 1 }, redactions: 0 } }, 'locations'), 1);
});

test('tooltip uses only label and turns; badge shows label and stale suffix', async () => {
  const m = await load();
  assert.equal(m.knowledgeTooltip(stamp), 'Rumor · visto no turno 2 · atualizado no turno 5');
  assert.ok(!m.knowledgeTooltip(stamp).includes('bestiary:x'));
  assert.equal(m.knowledgeTooltip({ ...stamp, first_seen_turn: null, last_updated_turn: null }), 'Rumor');
  assert.equal(m.knowledgeBadgeText(stamp), 'Rumor');
  assert.equal(m.knowledgeBadgeText({ ...stamp, label: 'Relato', stale: true }), 'Relato · pode estar desatualizado');
  assert.equal(m.knowledgeTooltip(undefined), '');
});
