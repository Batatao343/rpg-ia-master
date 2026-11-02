// SPEC-363 R32/R33: motivo do destino da loja e cabeçalho do Acervo.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'cjs', platform: 'node', logLevel: 'silent' });
  const mod = { exports: {} };
  new Function('module', 'exports', 'require', outputFiles[0].text)(mod, mod.exports, require);
  return mod.exports;
}

test('baralho_cheio_so_com_o_motivo_baralho_cheio', async () => {
  const { destinoLabel } = await load('../src/cardRewards.ts');
  assert.match(destinoLabel('acervo', 'baralho_cheio'), /Baralho cheio/);
  for (const m of ['limite_de_copias', 'preparadas_cheias', 'sem_baralho', undefined, null]) {
    assert.doesNotMatch(destinoLabel('acervo', m), /Baralho cheio/);
    assert.match(destinoLabel('acervo', m), /Acervo/);
  }
  assert.equal(destinoLabel('baralho'), 'vai para o Baralho');
});

test('acervo_fala_de_baralho_quando_ha_baralho', async () => {
  const { acervoHeader } = await load('../src/cardRewards.ts');
  const h = acervoHeader({ total: 14, maximo: 24 }, 4, 24);
  assert.equal(h.title, 'Baralho');
  assert.equal(h.count, '14/24');
  assert.match(h.updated(5), /Baralho atualizado/);
  const p = acervoHeader(undefined, 4, 24);
  assert.equal(p.title, 'Preparação');
  assert.equal(p.count, '4/24');
});
