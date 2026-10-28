// SPEC-347: lógica pura do front (percentual inteiro, rótulos de tipo com acento).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'cjs', platform: 'node', jsx: 'automatic', logLevel: 'silent',
    external: ['react', 'react-dom', 'react/jsx-runtime'] });
  const mod = { exports: {} };
  new Function('module', 'exports', 'require', outputFiles[0].text)(mod, mod.exports, require);
  return mod.exports;
}

test('fmtPct_inteiro_nunca_0_ou_100_falsos', async () => {
  const { fmtPct } = await load('../src/combat/deck.ts');
  assert.equal(fmtPct(64.9), '65 %');
  assert.equal(fmtPct(56.8), '57 %');
  assert.equal(fmtPct(99.6), '99 %');
  assert.equal(fmtPct(0.3), '1 %');
  assert.equal(fmtPct(0), '0 %');
  assert.equal(fmtPct(100), '100 %');
});

test('previewLine_aproximado_mantem_prefixo', async () => {
  const { previewLine } = await load('../src/combat/deck.ts');
  const line = previewLine({ chance_acerto_pct: 64.9, chance_critico_pct: 8, dano_min: 3, dano_max: 6, ferimento_provavel: null, efeitos_extra: [], pressagio_frustrado: false, aproximado: true });
  assert.match(line, /^≈ 65 %/);
});

test('type_label_cobre_todos_os_tipos_do_baralho', async () => {
  const { TYPE_LABEL } = await load('../src/components/tabs/DeckCard.tsx');
  for (const t of ['ativa', 'reacao', 'utilitaria', 'passiva', 'virtude']) {
    assert.ok(TYPE_LABEL[t], t);
    assert.notEqual(TYPE_LABEL[t], t);
  }
  assert.equal(TYPE_LABEL.utilitaria, 'Utilitária');
});
