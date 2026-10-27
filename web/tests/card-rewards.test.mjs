import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/cardRewards.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const forja = {
  permitido: true, motivo: '', baralho_min: 12,
  baralho: [{ id: 'san_corte', name: 'Corte', copias: 1, esquecivel: true }],
  esquecer: { descanso: true, templo: false, ouro: 25 },
  afiar: { material: null, afiaveis: [], afiadas: [] },
  cicatrizes: [{ scar_id: 'scar_braco_0', card_id: 'mld_cicatriz_braco', name: 'Braço de Cinza' }],
  purgar: { templo: false, medico: true, ouro: 40 },
};

test('SPEC-333: recusar o espólio mostra o ouro que o servidor prometeu', async () => {
  const { refuseLabel, RARITY_LABEL } = await load();
  assert.equal(refuseLabel(15), 'Deixar o espólio (+15 de ouro)');
  assert.equal(RARITY_LABEL.abissal, 'Abissal');
});

test('SPEC-333: vias da Forja só ligam quando o servidor permite', async () => {
  const { forgetChoices, purgeChoices } = await load();
  assert.deepEqual(forgetChoices(forja).map((c) => [c.via, c.enabled]), [['descanso', true], ['templo', false]]);
  assert.deepEqual(purgeChoices(forja).map((c) => [c.via, c.enabled]), [['medico', true], ['templo', false]]);
  const bloqueada = { ...forja, permitido: false };
  assert.ok(forgetChoices(bloqueada).every((c) => !c.enabled));
  assert.ok(purgeChoices(bloqueada).every((c) => !c.enabled));
});

test('SPEC-333: sem baralho nem cicatriz a Forja não aparece', async () => {
  const { forgeHasContent } = await load();
  assert.equal(forgeHasContent(undefined), false);
  assert.equal(forgeHasContent({ ...forja, baralho: [], cicatrizes: [] }), false);
  assert.equal(forgeHasContent(forja), true);
});
