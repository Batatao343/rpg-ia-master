import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/contextSuggestions.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const base = { npcs: [], quest: { main: { objective: '', current_step: 0, beats: [] } }, combat: { active: false } };

test('NPC em cena vira "Falar com X"; fora de cena ou morto, não', async () => {
  const { suggestionsFor } = await load();
  const s = suggestionsFor({ ...base, npcs: [
    { name: 'Jev', in_scene: true, status: '' }, { name: 'Ausente', in_scene: false }, { name: 'Defunto', in_scene: true, status: 'morto' }] });
  const labels = s.map(x => x.label);
  assert.ok(labels.includes('Falar com Jev'));
  assert.ok(!labels.some(l => /Ausente|Defunto/.test(l)));
  assert.equal(s.find(x => x.label === 'Falar com Jev').text, 'Falo com Jev');
});

test('sem NPC em cena não sugere conversa; sempre oferece descansar', async () => {
  const { suggestionsFor } = await load();
  const s = suggestionsFor(base);
  assert.ok(!s.some(x => /^Falar com/.test(x.label)));
  assert.ok(s.some(x => x.label === 'Descansar'));
});

test('beat atual vira "Seguir objetivo"; máximo 4 itens', async () => {
  const { suggestionsFor } = await load();
  const data = { ...base,
    npcs: ['A', 'B', 'C', 'D'].map(name => ({ name, in_scene: true })),
    quest: { main: { objective: 'x', current_step: 1, beats: [{ description: 'um', status: 'done' }, { description: 'Achar o sino', status: 'pending' }] } } };
  const s = suggestionsFor(data);
  assert.ok(s.length <= 4);
  assert.ok(s.some(x => x.label === 'Seguir objetivo' && /Achar o sino/.test(x.text)));
});

test('em combate, game over ou simulação não sugere nada', async () => {
  const { suggestionsFor } = await load();
  assert.deepEqual(suggestionsFor({ ...base, combat: { active: true } }), []);
  assert.deepEqual(suggestionsFor({ ...base, game_over: true }), []);
  assert.deepEqual(suggestionsFor({ ...base, combat_simulation: { enabled: true } }), []);
  assert.deepEqual(suggestionsFor(null), []);
});
