// SPEC-363 R16: o tabuleiro fecha no mesmo render da morte / fim do combate.
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

test('tabuleiro_fecha_com_morte_ou_combate_inativo', async () => {
  const { boardClosed } = await load('../src/combat/boardState.ts');
  assert.equal(boardClosed({ combat: { active: true } }), false);
  assert.equal(boardClosed({ death_pending: true, combat: { active: true } }), true);
  assert.equal(boardClosed({ game_over: true }), true);
  assert.equal(boardClosed({ combat: { active: false } }), true);
  assert.equal(boardClosed({ combat: { active: true } }, true), true);
  assert.equal(boardClosed(null), false);
});
