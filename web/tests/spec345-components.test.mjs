// SPEC-345: marcação SSR de TargetChip (R1), OnboardingHint (R10.2), CombatDeckTab (R7.2) e fightChipLabel (R9.2).
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

const base = { id: 'b1', name: 'Bandido 1', role: 'enemy', vit: 0, max: 8, conditions: [], intel: [], engagedNames: [] };

test('targetchip_sem_vitalidade', async () => {
  const { TargetChip } = await load('../src/combat/TargetChip.tsx');
  const out = html(h(TargetChip, { p: base, aim: undefined, onPick() {} }));
  assert.match(out, /tchip__vit is-spent">sem Vitalidade</);
  assert.match(out, /tchip__bar is-spent/);
  assert.doesNotMatch(out, /0\/8/);
});

test('targetchip_aria_mira_sem_vitalidade', async () => {
  const { TargetChip } = await load('../src/combat/TargetChip.tsx');
  const out = html(h(TargetChip, { p: base, aim: { valid: true }, onPick() {} }));
  assert.match(out, /aria-label="Alvo: Bandido 1, sem Vitalidade — o próximo golpe fere"/);
});

test('targetchip_jogador_zero_inalterado', async () => {
  const { TargetChip } = await load('../src/combat/TargetChip.tsx');
  const out = html(h(TargetChip, { p: { ...base, role: 'player', name: 'Herói' }, aim: undefined, onPick() {} }));
  assert.match(out, />0\/8</);
  assert.doesNotMatch(out, /sem Vitalidade/);
});

test('onboarding_compact_details', async () => {
  const { OnboardingHint } = await load('../src/components/OnboardingHint.tsx');
  const compact = html(h(OnboardingHint, { gameId: 'g', compact: true }));
  assert.match(compact, /^<details class="onboard onboard--compact"/);
  assert.doesNotMatch(compact, /<details[^>]* open/);
  assert.match(compact, /<summary[^>]*>[\s\S]*Você escreve, o mundo responde/);
  const full = html(h(OnboardingHint, { gameId: 'g' }));
  assert.match(full, /^<aside class="onboard"/);
});

test('fight_chip_label', async () => {
  const { fightChipLabel } = await load('../src/workspace/fightChip.ts');
  assert.deepEqual(fightChipLabel(3, true), { visible: 'R3', sr: 'Em combate, rodada 3' });
  assert.equal(fightChipLabel(3, false).visible, 'em combate');
});
