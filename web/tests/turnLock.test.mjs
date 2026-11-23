// SPEC-427 I2: a trava síncrona do turno em voo.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/turnLock.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

test('turn lock: só o dono solta com token; sem token solta sempre', async () => {
  const { lockTurn, unlockTurn, turnLocked } = await load();
  assert.equal(turnLocked(), false);
  lockTurn(7);
  assert.equal(turnLocked(), true);
  unlockTurn(6); // turno antigo (já invalidado) não solta a trava do mais novo
  assert.equal(turnLocked(), true);
  unlockTurn(7);
  assert.equal(turnLocked(), false);
  lockTurn(8); unlockTurn();
  assert.equal(turnLocked(), false);
});
