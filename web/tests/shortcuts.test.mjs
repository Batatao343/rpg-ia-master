// SPEC-324: matchShortcut pura — Alt+dígito (Win/Linux), Ctrl+Option+dígito (mac), nunca Ctrl/⌘+dígito.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}
const { matchShortcut, shortcutKeys, ariaShortcut, SHORTCUTS } = await load('../src/workspace/shortcuts.ts');
const ev = (o) => ({ key: '', code: '', ...o });

test('Alt+2..6 abrem os painéis na ordem de sempre (Windows/Linux)', () => {
  const order = ['codex', 'personagem', 'combate', 'bestiario', 'mapa'];
  order.forEach((tab, i) => {
    const n = i + 2;
    assert.equal(matchShortcut(ev({ key: String(n), code: `Digit${n}`, altKey: true }), 'other'), `tab:${tab}`);
  });
});

test('Ctrl/⌘+dígito não é atalho (o navegador fica com ele)', () => {
  assert.equal(matchShortcut(ev({ key: '2', code: 'Digit2', ctrlKey: true }), 'other'), null);
  assert.equal(matchShortcut(ev({ key: '2', code: 'Digit2', metaKey: true }), 'mac'), null);
  // Ctrl+Alt no Windows é AltGr
  assert.equal(matchShortcut(ev({ key: '2', code: 'Digit2', altKey: true, ctrlKey: true }), 'other'), null);
});

test('foco em campo de texto: só Alt+1 passa', () => {
  assert.equal(matchShortcut(ev({ key: '3', code: 'Digit3', altKey: true }), 'other', true), null);
  assert.equal(matchShortcut(ev({ key: '1', code: 'Digit1', altKey: true }), 'other', true), 'composer');
  assert.equal(matchShortcut(ev({ key: '?', code: 'Slash', shiftKey: true }), 'other', true), null);
  assert.equal(matchShortcut(ev({ key: 'ArrowLeft', code: 'ArrowLeft', altKey: true }), 'other', true), null);
});

test('? fora de campo abre a folha; com Ctrl/Alt não', () => {
  assert.equal(matchShortcut(ev({ key: '?', code: 'Slash', shiftKey: true }), 'other', false), 'help');
  assert.equal(matchShortcut(ev({ key: '?', code: 'Slash', shiftKey: true, ctrlKey: true }), 'other', false), null);
});

test('macOS: Ctrl+Option+dígito (Option sozinho gera caractere e não vale)', () => {
  assert.equal(matchShortcut(ev({ key: '¡', code: 'Digit1', altKey: true }), 'mac'), null);
  assert.equal(matchShortcut(ev({ key: '¡', code: 'Digit1', altKey: true, ctrlKey: true }), 'mac'), 'composer');
  assert.equal(matchShortcut(ev({ key: '£', code: 'Digit3', altKey: true, ctrlKey: true }), 'mac'), 'tab:personagem');
});

test('Alt+←/→ e Alt+\\ ', () => {
  assert.equal(matchShortcut(ev({ key: 'ArrowLeft', code: 'ArrowLeft', altKey: true }), 'other'), 'back');
  assert.equal(matchShortcut(ev({ key: 'ArrowRight', code: 'ArrowRight', altKey: true }), 'mac'), 'forward');
  assert.equal(matchShortcut(ev({ key: '\\', code: 'Backslash', altKey: true }), 'other'), 'split');
  assert.equal(matchShortcut(ev({ key: '\\', code: 'Backslash', ctrlKey: true }), 'other'), null);
});

test('ABNT2: IntlBackslash e key barra também alternam; ariaShortcut(help) = ?', () => {
  assert.equal(matchShortcut(ev({ key: ']', code: 'IntlBackslash', altKey: true }), 'other'), 'split');
  assert.equal(matchShortcut(ev({ key: '\\', code: '', altKey: true }), 'other'), 'split');
  assert.equal(ariaShortcut('help', 'other'), '?');
});

test('rótulos e aria-keyshortcuts por plataforma', () => {
  assert.equal(shortcutKeys('tab:codex', 'other'), 'Alt+2');
  assert.equal(shortcutKeys('tab:codex', 'mac'), 'Ctrl+Option+2');
  assert.equal(ariaShortcut('tab:mapa', 'other'), 'Alt+6');
  assert.equal(ariaShortcut('tab:mapa', 'mac'), 'Control+Alt+6');
  assert.equal(ariaShortcut('back', 'other'), 'Alt+ArrowLeft');
  assert.equal(SHORTCUTS.length, 10);
});
