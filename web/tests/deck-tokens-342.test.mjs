// SPEC-342 R25: o CSS do Baralho só usa tokens existentes, sem cor/raio literal.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (p) => readFileSync(fileURLToPath(new URL(p, import.meta.url)), 'utf8');
const ws = read('../src/workspace.css');
const defined = new Set([...(read('../src/styles.css') + read('../src/design/tokens.css')).matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]));
const block = ws.slice(ws.indexOf('.deck-combat {'));

test('todo var(--x) do bloco do Baralho existe nos tokens', () => {
  const used = [...block.matchAll(/var\((--[a-z0-9-]+)/g)].map((m) => m[1]);
  assert.ok(used.length > 20);
  for (const v of used) assert.ok(defined.has(v) || v === '--tabbar-h' || v === '--composer-h', v);
});

test('sem hex/rgb/oklch literal nem raio literal no bloco', () => {
  assert.doesNotMatch(block, /#[0-9a-f]{3,8}\b/i);
  assert.doesNotMatch(block, /\brgba?\(|\boklch\(/);
  for (const m of block.matchAll(/border-radius:\s*([^;]+);/g)) assert.match(m[1], /var\(--r-|^0$|^50%$|inherit/, m[1]);
});

test('is-dim só esmaece nome, texto e pips (o motivo de bloqueio fica legível)', () => {
  assert.doesNotMatch(block, /\.deck-card\.is-dim\s*\{[^}]*opacity/);
  assert.match(block, /\.deck-card\.is-dim \.combat-card__name[^{]*\{ opacity: 0\.5/);
});
