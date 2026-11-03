// SPEC-387 R8: chip otimista no clique e retrato anterior de volta no erro/cancelamento (helpers puros).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'cjs', platform: 'node', logLevel: 'silent' });
  const mod = { exports: {} };
  new Function('module', 'exports', 'require', outputFiles[0].text)(mod, mod.exports, require);
  return mod.exports;
}

const offer = (escopo) => ({ estado: 'marcador', src: null, familia: 'fera', icone: 'x', alt: 'a', proprio: false,
  gerar: { preco_estilhas: 1, preco_milli: '15', escopo } });
const data = () => ({ combat: { enemies: [
  { id: 'e1', name: 'Goblin', retrato: offer('tipo') },
  { id: 'e2', name: 'Goblin 2', retrato: offer('tipo') },
  { id: 'e3', name: 'Grishnak', retrato: offer('unico') },
] } });

test('snapshot + pending + restored devolve o retrato anterior (irmãos incluídos)', async () => {
  const m = await load('../src/lib/portraitOrder.ts');
  const d = data();
  const shot = m.snapshotPortraits(d, 'e1');
  assert.deepEqual(Object.keys(shot).sort(), ['e1', 'e2']);
  const pend = m.withPortraitPending(d, 'e1');
  assert.equal(pend.combat.enemies[0].retrato.estado, 'gerando');
  assert.equal(pend.combat.enemies[1].retrato.gerar, null);
  assert.equal(pend.combat.enemies[2].retrato.gerar.escopo, 'unico');
  const back = m.withPortraitRestored(pend, 'e1', shot);
  assert.deepEqual(back.combat.enemies, d.combat.enemies);
  assert.notEqual(back, pend);
});

test('restored é imutável e devolve o mesmo objeto quando nada muda', async () => {
  const m = await load('../src/lib/portraitOrder.ts');
  const d = data();
  const shot = m.snapshotPortraits(d, 'e3');
  assert.equal(m.withPortraitRestored(d, 'e3', shot), d); // ninguém "gerando"
  assert.equal(m.withPortraitRestored({ combat: null }, 'e3', shot).combat, null);
  assert.deepEqual(m.snapshotPortraits(d, 'nope'), {});
});
