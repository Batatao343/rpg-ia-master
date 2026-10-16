import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

// SPEC-202 R13: rótulo passivo de quem respondeu (sem seletor).
const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/lib.ts', import.meta.url))],
  bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
const lib = await import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}`);

const brunna = { kind: 'npc', id: 'npc_mv_brunna_ponte_alta', name: 'Brunna Ponte-Alta', reason: 'direct_address' };
const narrador = { kind: 'narrator', id: 'narrator', name: 'Narrador', reason: 'npc_absent_known' };

test('NPC identificado usa o nome canônico', () => {
  assert.equal(lib.roleLabel('narrator', 'NPC', brunna), 'Brunna Ponte-Alta');
});

test('narrador numa rota de NPC (ausente/mediação) vira "Narrador"', () => {
  assert.equal(lib.roleLabel('narrator', 'NPC', narrador), 'Narrador');
});

test('sem speaker mantém o rótulo legado por tipo', () => {
  assert.equal(lib.roleLabel('narrator', 'NPC'), 'Diálogo');
  assert.equal(lib.roleLabel('narrator', 'COMBAT', null), 'Combate');
  assert.equal(lib.roleLabel('player', 'STORY', brunna), 'Você');
});

test('histórico: speaker_* vira Speaker; linha legada fica null', () => {
  assert.deepEqual(lib.speakerFromHistory({ speaker_kind: 'npc', speaker_id: 'x', speaker_name: 'X' }),
    { kind: 'npc', id: 'x', name: 'X' });
  assert.equal(lib.speakerFromHistory({}), null);
  assert.equal(lib.speakerFromHistory({ speaker_kind: 'bogus' }), null);
});
