// SPEC-367 R4: depois de confirmar o retrato pago, a oferta some e o chip mostra "gerando" (helper puro).
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
  { id: 'e4', name: 'Lobo', retrato: offer('tipo') },
] } });

test('marca_o_clicado_e_o_irmao_de_mesmo_tipo_sem_tocar_o_unico', async () => {
  const { withPortraitPending } = await load('../src/lib/portraitOrder.ts');
  const d = data();
  const out = withPortraitPending(d, 'e1');
  const by = Object.fromEntries(out.combat.enemies.map((e) => [e.id, e.retrato]));
  assert.equal(by.e1.estado, 'gerando'); assert.equal(by.e1.gerar, null);
  assert.equal(by.e2.estado, 'gerando'); assert.equal(by.e2.gerar, null);
  assert.deepEqual(by.e3.gerar, d.combat.enemies[2].retrato.gerar); // unico: não toca
  assert.deepEqual(by.e4.gerar, d.combat.enemies[3].retrato.gerar); // outro tipo
  assert.equal(d.combat.enemies[0].retrato.estado, 'marcador'); // imutável
});

test('clicado_unico_marca_so_ele', async () => {
  const { withPortraitPending } = await load('../src/lib/portraitOrder.ts');
  const out = withPortraitPending(data(), 'e3');
  assert.equal(out.combat.enemies[2].retrato.estado, 'gerando');
  assert.deepEqual(out.combat.enemies[0].retrato.gerar.escopo, 'tipo');
});

test('mesmo_objeto_quando_nada_muda', async () => {
  const { withPortraitPending } = await load('../src/lib/portraitOrder.ts');
  const d = data();
  assert.equal(withPortraitPending(d, 'inexistente'), d);
  const noOffer = { combat: { enemies: [{ id: 'e1', name: 'Goblin', retrato: { ...offer('tipo'), gerar: null } }] } };
  assert.equal(withPortraitPending(noOffer, 'e1'), noOffer);
  const none = { combat: null };
  assert.equal(withPortraitPending(none, 'e1'), none);
});
