// SPEC-389 R11: o presságio frustrado aparece em "Efeitos da rodada".
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
const { renderToStaticMarkup: html } = require('react-dom/server');
const h = require('react').createElement;

const frustrado = { ator_id: 'enemy_goblin_1', ator_nome: 'Goblin', lado: 'inimigo', carta_id: null, carta_nome: null,
  alvo_id: null, alvo_nome: null, origem: 'turno', rotulo: null, resultado: 'efeito', dano: null,
  efeito: 'Presságio frustrado: Goblin', tipo: 'pressagio_frustrado' };

test('pressagio_frustrado_aparece_em_efeitos_da_rodada', async () => {
  const { RoundBoard } = await load('../src/components/combat/RoundBoard.tsx');
  const out = html(h(RoundBoard, { entries: [frustrado], round: 1 }));
  const fx = out.split('Efeitos da rodada')[1];
  assert.match(fx, /Presságio frustrado: Goblin/);
  assert.match(out, /data-efeito="pressagio_frustrado"/);
});
