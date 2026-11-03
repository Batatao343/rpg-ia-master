// SPEC-371 R15: presságio com golpe preparado (prenuncio) e contra-jogo no chip do inimigo.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';

const require = createRequire(import.meta.url);
async function load(entry) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(entry, import.meta.url))],
    bundle: true, write: false, format: 'cjs', platform: 'node', jsx: 'automatic', logLevel: 'silent',
    external: ['react', 'react-dom', 'react/jsx-runtime'] });
  const mod = { exports: {} };
  new Function('module', 'exports', 'require', outputFiles[0].text)(mod, mod.exports, require);
  return mod.exports;
}
const d = await load('../src/combat/deck.ts');
const base = { actor_id: 'e', tipo: 'ataque', alvo_id: null, valor_estimado: null, faixa: [4, 8], carta_nome: null, sinal: 'ergue a lâmina' };

test('omenView sem prenuncio/contra_jogo: sem chaves novas (saves e respostas antigas)', () => {
  const v = d.omenView(base, 'Lobo');
  assert.equal('prenuncio' in v, false);
  assert.equal('saber' in v, false);
  assert.equal(v.spoken, 'Lobo: ergue a lâmina (4–8)');
});

test('omenView mostra o prenuncio mesmo sem a flag do saber (P4)', () => {
  const v = d.omenView({ ...base, prenuncio: 'Lobo abre as mandíbulas.' }, 'Lobo');
  assert.equal(v.prenuncio, 'Lobo abre as mandíbulas.');
  assert.match(v.spoken, /Lobo abre as mandíbulas\./);
  assert.equal('saber' in v, false);
});

test('omenView leva o contra-jogo com "Você sabe:" no texto falado', () => {
  const v = d.omenView({ ...base, prenuncio: 'Lobo abre as mandíbulas.', contra_jogo: 'Mantenha distância.' }, 'Lobo');
  assert.equal(v.saber, 'Mantenha distância.');
  assert.match(v.spoken, /Você sabe: Mantenha distância\./);
});

test('omenView velada ainda mostra o prenuncio', () => {
  const v = d.omenView({ ...base, tipo: 'desconhecido', prenuncio: 'Lobo se encolhe.' }, 'Lobo');
  assert.equal(v.veiled, true);
  assert.equal(v.prenuncio, 'Lobo se encolhe.');
});
