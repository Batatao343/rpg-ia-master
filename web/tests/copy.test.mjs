import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = fileURLToPath(new URL('../src', import.meta.url));
function files(dir) {
  return readdirSync(dir).flatMap(n => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : /\.(tsx?|css)$/.test(n) ? [p] : [];
  });
}
// SPEC-323 R3: jargão de dev/IA não aparece para o jogador (comentários e código fora do alvo; só literais de texto).
const stripComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:"'`])\/\/.*$/gm, '$1');
const all = files(SRC).map(p => [p, stripComments(readFileSync(p, 'utf8'))]);

test('sem "zero LLM", "Simular combate" nem custo técnico em US$ fixo na UI do jogador', () => {
  for (const [p, s] of all) {
    assert.doesNotMatch(s, /LLM/i, p);
    assert.doesNotMatch(s, />\s*Simular combate/, p);
    assert.doesNotMatch(s, /Narração por IA/, p);
  }
});

test('"Custo técnico" só atrás do flag de debug', () => {
  const log = readFileSync(join(SRC, 'components/StoryLog.tsx'), 'utf8');
  assert.match(log, /debugEnabled\(\) && entry\.technicalCostUsd/);
});

test('estados vazios não terminam em "— ainda."', () => {
  for (const [p, s] of all) assert.doesNotMatch(s, /—\s*ainda\./, p);
});

test('sem alusão a lobo/Witcher no código-fonte da web', () => {
  for (const [p, s] of all) assert.doesNotMatch(s, /\blobo\b|wolf|witcher/i, p);
});

test('aria-label do mapa só anuncia perigo de nó visitado', () => {
  const s = readFileSync(join(SRC, 'components/WorldMap.tsx'), 'utf8');
  assert.ok(s.includes('(known ? `, perigo ${danger}` : "")'));
});
