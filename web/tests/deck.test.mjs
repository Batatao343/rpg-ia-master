// SPEC-209: histórico de evolução (Jornada) derivado da crônica pública + contrato do deck.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const here = (rel) => fileURLToPath(new URL(rel, import.meta.url));
async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [here(entry)], bundle: true, write: false,
    format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

test('R11: Jornada lista só marcos de nível/subclasse, mais recente primeiro', async () => {
  const { evolutionHistory } = await load('../src/components/tabs/journey.ts');
  const out = evolutionHistory([
    { entries: [
      { kind: 'milestone', text: 'O herói alcançou o nível 2.' },
      { kind: 'milestone', text: 'Ayla chegou ao porto.' },
      { kind: 'note', text: 'O herói alcançou o nível 9.' },
    ] },
    { entries: [{ kind: 'milestone', text: 'A subclasse Carmesim foi escolhida.' }] },
  ]);
  assert.deepEqual(out, ['A subclasse Carmesim foi escolhida.', 'O herói alcançou o nível 2.']);
  assert.deepEqual(await load('../src/components/tabs/journey.ts').then((m) => m.evolutionHistory(undefined)), []);
});

test('R15: DeckCard não sugere ilustração (sem <img> nem placeholder de arte)', () => {
  const src = readFileSync(here('../src/components/tabs/DeckCard.tsx'), 'utf8');
  assert.doesNotMatch(src, /<img|VisualArtwork|ilustra/i);
});

test('R7/R14: o deck anuncia por aria-live e não usa role=status (componente sempre montado)', () => {
  const src = readFileSync(here('../src/components/tabs/CombatDeckTab.tsx'), 'utf8');
  assert.match(src, /aria-live="polite"/);
  assert.doesNotMatch(src, /role="status"/);
});

test('R9: animações do deck só transform/opacity e sem loop infinito', () => {
  const css = readFileSync(here('../src/components/tabs/tabs.css'), 'utf8');
  assert.doesNotMatch(css, /infinite/);
  for (const m of css.matchAll(/transition:\s*([^;}]+)[;}]/g)) assert.match(m[1], /^(transform|opacity|none)\b/, m[1]);
});

test('R13: deck e ficha mostram "atualizando…" quando o dado pode estar atrasado', () => {
  const deck = readFileSync(here('../src/components/tabs/CombatDeckTab.tsx'), 'utf8');
  assert.match(deck, /\(saving \|\| busy\) && <span className="deck__sync">[^<]*atualizando…/);
  const sheet = readFileSync(here('../src/components/tabs/CharacterTab.tsx'), 'utf8');
  assert.match(sheet, /busy && <span className="char-sync">[^<]*atualizando…/);
  const tab = readFileSync(here('../src/workspace/tabs/CombateTab.tsx'), 'utf8');
  assert.match(tab, /<CombatDeckTab [^>]*busy=\{busy\}/);
});
