// SPEC-208: contrato do design system de efeitos (tokens CSS<->JS, registry, política de import).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const here = (rel) => fileURLToPath(new URL(rel, import.meta.url));

async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [here(entry)], bundle: true, write: false,
    format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const css = readFileSync(here('../src/design/tokens.css'), 'utf8');
const cssVar = (name) => {
  const m = css.match(new RegExp(`--${name}:\\s*([^;]+);`));
  assert.ok(m, `token --${name} ausente em tokens.css`);
  return m[1].trim();
};

test('R2: tokens de duracao, easing, elevacao, estado e foco existem em tokens.css', () => {
  for (const n of ['dur-instant', 'dur-fast', 'dur-base', 'dur-slow', 'ease-out', 'ease-in-out', 'ease-spring-soft',
    'elev-0', 'elev-1', 'elev-2', 'elev-3', 'state-hover', 'state-pressed', 'state-selected', 'state-armed',
    'state-disabled', 'focus-ring', 'danger-dim', 'ink-soft']) cssVar(n);
});

test('R2: faixas de duracao (instant<=80, fast 120-160, base 200-280, slow<=450)', async () => {
  const { DURATION_MS } = await load('../src/design/tokens.ts');
  assert.ok(DURATION_MS.instant <= 80);
  assert.ok(DURATION_MS.fast >= 120 && DURATION_MS.fast <= 160);
  assert.ok(DURATION_MS.base >= 200 && DURATION_MS.base <= 280);
  assert.ok(DURATION_MS.slow <= 450);
});

test('R3: paridade tokens.css <-> tokens.ts', async () => {
  const t = await load('../src/design/tokens.ts');
  for (const [name, ms] of Object.entries(t.DURATION_MS)) {
    assert.equal(cssVar(`dur-${name}`), `${ms}ms`, `duracao ${name}`);
  }
  assert.equal(cssVar('ease-out'), 'var(--ease)');
  const legacy = readFileSync(here('../src/styles.css'), 'utf8').match(/--ease:\s*cubic-bezier\(([^)]+)\)/)[1];
  assert.deepEqual(legacy.split(',').map(Number), [...t.EASING['ease-out']]);
  for (const name of ['ease-in-out', 'ease-spring-soft']) {
    const raw = cssVar(name).match(/cubic-bezier\(([^)]+)\)/)[1];
    assert.deepEqual(raw.split(',').map(Number), [...t.EASING[name]], name);
  }
  for (const n of t.ELEVATION_TOKENS) cssVar(n);
  for (const n of t.STATE_TOKENS) cssVar(n);
});

test('R2: tokens legados nao foram renomeados nem removidos', () => {
  const root = readFileSync(here('../src/styles.css'), 'utf8');
  for (const n of ['bg', 'surface', 'line', 'ink', 'accent', 'accent-glow', 'danger', 'danger-bright', 'mana', 'stamina',
    'r-sm', 'r-md', 'r-pill', 'shadow-deep', 'ease', 'z-hud', 'z-banner', 'z-overlay']) {
    assert.match(root, new RegExp(`--${n}:`), `--${n}`);
  }
});

test('R1: registry completo, matrix_ref valido na matriz da SPEC-201, teste existente, interruptible literal', async () => {
  const { EFFECTS } = await load('../src/design/effects.registry.ts');
  const tokens = await load('../src/design/tokens.ts');
  const matrix = readFileSync(here('../../docs/spec201/matriz-efeitos.md'), 'utf8');
  const spec = readFileSync(here('../e2e/effects.spec.ts'), 'utf8');
  const required = ['id', 'matrix_ref', 'reason', 'trigger', 'states', 'duration_token', 'easing_token',
    'interruptible', 'reduced_motion_fallback', 'cost', 'test', 'data_dependency', 'sound'];
  assert.ok(EFFECTS.length >= 15);
  const ids = new Set();
  for (const e of EFFECTS) {
    for (const k of required) assert.ok(k in e, `${e.id}: campo ${k}`);
    assert.ok(!ids.has(e.id), `id duplicado ${e.id}`); ids.add(e.id);
    assert.match(e.matrix_ref, /^M\d{2}$/, `${e.id}: matrix_ref`);
    assert.match(matrix, new RegExp(`^\\| ${e.matrix_ref} \\|`, 'm'), `${e.id}: ${e.matrix_ref} ausente na matriz`);
    assert.equal(e.interruptible, true);
    assert.equal(e.sound, null);
    assert.ok(e.reason.length > 8 && e.reduced_motion_fallback.length > 4, `${e.id}: textos`);
    assert.ok(e.states.start && e.states.end);
    assert.ok(e.duration_token in tokens.DURATION_MS, `${e.id}: duration_token`);
    assert.ok(e.easing_token in tokens.EASING, `${e.id}: easing_token`);
    assert.ok(['css', 'transform', 'layout'].includes(e.cost.cpu));
    assert.ok(['none', 'player-authorized'].includes(e.data_dependency));
    const [file, name] = e.test.split('::');
    assert.equal(file, 'e2e/effects.spec.ts');
    assert.ok(spec.includes(`"${name}:`) || spec.includes(`\`${name}:`) || spec.includes(`'${name}:`), `${e.id}: sem teste "${name}:" no spec`);
  }
});

test('R4: so design/primitives.tsx e os legados importam motion; combat/ e design/ nunca', () => {
  const allowed = new Set(['App.tsx', 'StoryLog.tsx', 'SceneArtwork.tsx', 'DeathModal.tsx', 'LevelUpModal.tsx', 'primitives.tsx']);
  const hits = [];
  const walk = (dir) => {
    for (const f of readdirSync(dir)) {
      const p = join(dir, f);
      if (statSync(p).isDirectory()) { walk(p); continue; }
      if (!/\.(tsx?|ts)$/.test(f)) continue;
      if (/from\s+["']motion(\/react)?["']/.test(readFileSync(p, 'utf8')) && !allowed.has(f)) hits.push(p);
    }
  };
  walk(here('../src'));
  assert.deepEqual(hits, []);
});

test('R5: bloco global de reduced-motion e MotionConfig user permanecem', () => {
  const styles = readFileSync(here('../src/styles.css'), 'utf8');
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)\s*\{\s*\*, \*::before, \*::after \{ animation: none !important; transition-duration: 0\.01ms !important; \}\s*\.ember-canvas \{ display: none; \}/);
  assert.match(readFileSync(here('../src/App.tsx'), 'utf8'), /<MotionConfig reducedMotion="user">/);
});

test('R8: sem dependencia nova de animacao (GSAP/lottie/three)', () => {
  const pkg = JSON.parse(readFileSync(here('../package.json'), 'utf8'));
  const deps = Object.keys({ ...pkg.dependencies, ...pkg.devDependencies });
  assert.deepEqual(deps.filter((d) => /gsap|lottie|three|pixi|@react-three/.test(d)), []);
});

test('R10: kill switch le ?effects=off e localStorage rpg.effects', async () => {
  const m = await load('../src/design/killswitch.ts');
  assert.equal(m.effectsKilled('?effects=off', null), true);
  assert.equal(m.effectsKilled('', 'off'), true);
  assert.equal(m.effectsKilled('?effects=on', 'on'), false);
  assert.equal(m.effectsKilled('', null), false);
});

test('R8: no bloco SPEC-208 so transform/opacity transitam (cor/sombra/largura mudam no ato)', () => {
  const styles = readFileSync(here('../src/styles.css'), 'utf8');
  const block = styles.slice(styles.indexOf('SPEC-208 — design system de efeitos'));
  assert.ok(block.length > 100, 'bloco SPEC-208 ausente');
  const bad = [];
  for (const m of block.matchAll(/transition:\s*([^;}]+)[;}]/g)) {
    for (const part of m[1].split(',')) {
      const prop = part.trim().split(/\s+/)[0];
      if (!['transform', 'opacity', 'none'].includes(prop)) bad.push(`${prop} em "${m[0].trim()}"`);
    }
  }
  assert.deepEqual(bad, []);
  // nenhuma animação infinita nova anima box-shadow/filter/width (repintura/layout por frame)
  for (const m of block.matchAll(/@keyframes\s+([\w-]+)\s*\{([^@]*?\}\s*)\}/g)) {
    assert.doesNotMatch(m[2], /box-shadow|filter|width|height|top|left/, `keyframes ${m[1]}`);
  }
});
