// SPEC-321 R10: Enter envia, Shift+Enter quebra linha, IME não envia; textarea cresce até 4 linhas.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}
const { shouldSubmitOnKey, composerHeight } = await load('../src/workspace/composerKeys.ts');

test('Enter envia', () => {
  assert.equal(shouldSubmitOnKey({ key: 'Enter', shiftKey: false }), true);
});

test('Shift+Enter quebra linha (não envia)', () => {
  assert.equal(shouldSubmitOnKey({ key: 'Enter', shiftKey: true }), false);
});

test('composição de IME (isComposing ou keyCode 229) não envia', () => {
  assert.equal(shouldSubmitOnKey({ key: 'Enter', shiftKey: false, isComposing: true }), false);
  assert.equal(shouldSubmitOnKey({ key: 'Enter', shiftKey: false, keyCode: 229 }), false);
});

test('outras teclas e Enter com modificador não enviam', () => {
  assert.equal(shouldSubmitOnKey({ key: 'a', shiftKey: false }), false);
  assert.equal(shouldSubmitOnKey({ key: 'Enter', shiftKey: false, ctrlKey: true }), false);
});

test('altura cresce até 4 linhas e depois rola', () => {
  assert.equal(composerHeight(44, 22, 20), 44);
  assert.equal(composerHeight(200, 22, 20), 108);
});
