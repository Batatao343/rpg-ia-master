import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/workspace/tabs/mapModel.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}
const src = (p) => readFileSync(fileURLToPath(new URL(p, import.meta.url)), 'utf8');

test('periodsLabel: 0, 1 e N periodos em pt-BR', async () => {
  const m = await load();
  assert.equal(m.periodsLabel(0), 'sem custo de tempo');
  assert.equal(m.periodsLabel(1), '1 período');
  assert.equal(m.periodsLabel(3), '3 períodos');
});

test('nextNodeIndex: seta move para o vizinho mais proximo na direcao', async () => {
  const m = await load();
  const pts = [{ x: 50, y: 50 }, { x: 80, y: 50 }, { x: 20, y: 52 }, { x: 50, y: 90 }];
  assert.equal(m.nextNodeIndex(pts, 0, 'ArrowRight'), 1);
  assert.equal(m.nextNodeIndex(pts, 0, 'ArrowLeft'), 2);
  assert.equal(m.nextNodeIndex(pts, 0, 'ArrowDown'), 3);
  assert.equal(m.nextNodeIndex(pts, 0, 'ArrowUp'), -1);
  assert.equal(m.nextNodeIndex(pts, 0, 'Enter'), -1);
});

test('MapTab: viajar e acao de chat, desabilitado com razao, sem mutacao local', () => {
  const tab = src('../src/workspace/tabs/MapTab.tsx');
  assert.match(tab, /onAction\(`Viajo para \$\{option\.name\}`\)/);
  assert.match(tab, /disabled=\{!canTravel\}/);
  assert.match(tab, /gate\.blocked\) reason = gate\.reason/);
  // nome de no adjacente so existe como dado do servidor; nada de fog desenhado a partir de /data/map global
  assert.match(src('../src/api.ts'), /getGameMap/);
  assert.doesNotMatch(tab, /api\.getMap\(\)/);
  assert.doesNotMatch(tab, /role="status"/);
  // interior: a saida (travel_option do pai, custo 0) fica habilitada na ancora
  assert.match(tab, /node\.state === "atual" && !option\) reason = "Você já está aqui\."/);
});

test('mapa: nenhuma animacao infinita nova e fallback legado so com game_id', () => {
  const css = src('../src/workspace/tabs/map.css');
  assert.doesNotMatch(css, /infinite|animation/);
  assert.match(src('../src/components/WorldMap.tsx'), /api\.getMap\(gameId\)/);
});
