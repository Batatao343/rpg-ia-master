// SPEC-342: lógica pura do acabamento do Baralho (strings D-342-7, presságio, cena, fila).
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
const queue = [
  { uid: 'a', cardId: 'golpe', name: 'Golpe', targetId: 'e1', folego: 1, entropia: 0 },
  { uid: 'b', cardId: 'aparar', name: 'Aparar', folego: 1, entropia: 0 },
];

test('endText: marginália em 1ª pessoa, com e sem "Sem matar."', () => {
  assert.equal(d.endText(queue, false), 'Encerro a rodada: Golpe, Aparar.');
  assert.equal(d.endText(queue, true), 'Encerro a rodada: Golpe, Aparar. Sem matar.');
});

test('objectiveLine: os 6 tipos e o resultado', () => {
  const o = (tipo, extra = {}) => ({ tipo, rodada: 2, resultado: null, ...extra });
  assert.equal(d.objectiveLine(o('sobreviver_n_rodadas', { n: 6 })), 'Resista até a rodada 6 (faltam 4)');
  assert.equal(d.objectiveLine(o('sobreviver_n_rodadas', { n: 1 })), 'Resista até a rodada 1 (faltam 0)');
  assert.equal(d.objectiveLine(o('proteger', { alvo_nome: 'Mira' })), 'Mantenha Mira de pé');
  assert.equal(d.objectiveLine(o('alcancar_zona', { alvo_nome: 'a ponte' })), 'Alcance a ponte');
  assert.equal(d.objectiveLine(o('destruir_objeto', { alvo_nome: 'o altar' })), 'Destrua o altar');
  assert.equal(d.objectiveLine(o('interromper_ritual', { alvo_nome: 'o mago', n: 5 })), 'Derrube o mago antes da rodada 5, ou o ritual se completa');
  assert.equal(d.objectiveLine(o('capturar_vivo')), 'Leve-os vivos (use "Sem matar")');
  assert.equal(d.objectiveLine(o('proteger', { resultado: 'cumprido' })), 'Objetivo cumprido');
  assert.equal(d.objectiveLine(o('proteger', { resultado: 'falhou' })), 'Objetivo perdido');
});

test('clockLine: antes, no limiar e ativo', () => {
  const r = (rodada, ativo) => ({ desde: 5, teto: 12, rodada, ativo });
  assert.equal(d.clockLine(r(1, false)), 'Relógio do Abismo: desperta na rodada 5');
  assert.equal(d.clockLine(r(4, false)), 'Relógio do Abismo: desperta na rodada 5');
  assert.equal(d.clockLine(r(5, true)), 'O Abismo se aproxima: +1 Carga por rodada');
  assert.equal(d.clockLine(r(12, true)), 'O Abismo se aproxima: +1 Carga por rodada');
  assert.match(d.clockBody(r(5, true)), /rodada 5 em diante[\s\S]*rodada 12/);
});

test('omenView: velada (null e desconhecido), faixa, valor e carta', () => {
  assert.deepEqual({ ...d.omenView(null, 'Lobo') }, { icon: 'dark', text: 'Intenção velada', num: null, card: null, veiled: true, spoken: 'Lobo: Intenção velada' });
  assert.equal(d.omenView({ actor_id: 'e', tipo: 'desconhecido', alvo_id: null, valor_estimado: null, faixa: null, carta_nome: null, sinal: 'x' }, 'Lobo').veiled, true);
  const base = { actor_id: 'e', tipo: 'ataque', alvo_id: null, valor_estimado: null, faixa: [4, 8], carta_nome: null, sinal: 'ergue a lâmina' };
  assert.equal(d.omenView(base, 'Lobo').num, '4–8');
  assert.equal(d.omenView({ ...base, valor_estimado: 6, faixa: null }, 'Lobo').num, '~6');
  const v = d.omenView({ ...base, carta_nome: 'Talho' }, 'Lobo');
  assert.equal(v.card, 'Talho');
  assert.equal(v.icon, 'card-active');
});

test('OMEN_ICON cobre todos os TIPOS e só usa ícones que existem', async () => {
  const src = readFileSync(fileURLToPath(new URL('../src/design/icons.tsx', import.meta.url)), 'utf8');
  for (const t of d.TIPOS) {
    const icon = d.OMEN_ICON[t];
    assert.ok(icon, t);
    assert.match(src, new RegExp(`"${icon}":`), icon);
  }
  const py = readFileSync(fileURLToPath(new URL('../../services/enemy_intent.py', import.meta.url)), 'utf8');
  for (const t of d.TIPOS) assert.ok(py.includes(`"${t}"`), `tipo ${t} existe no servidor`);
});

test('BLOCK_TEXT e previewParts iguais à D-342-7; nada de "turno" nas strings', () => {
  assert.deepEqual({ ...d.BLOCK_TEXT }, {
    fardo: 'Fardo: pesa na mão, não se joga', sem_folego: 'Falta fôlego', limite: 'Não cabe mais nada nesta rodada',
    ja_na_fila: 'Já vai na fila', entropia: 'A Entropia não basta',
  });
  const p = { chance_acerto_pct: 55, chance_critico_pct: 9, dano_min: 4, dano_max: 7, ferimento_provavel: null, efeitos_extra: ['Sangramento'], pressagio_frustrado: false };
  assert.deepEqual({ ...d.previewParts(p) }, { chance: '55 %', rest: '4–7 de dano · pode Sangrar' });
  assert.deepEqual({ ...d.previewParts({ ...p, aproximado: true, dano_max: 0, efeitos_extra: [] }) }, { chance: '≈ 55 %', rest: '' });
  for (const text of Object.values(d.BLOCK_TEXT)) assert.doesNotMatch(text, /turno/i);
  assert.doesNotMatch(d.endText(queue, true), /turno/i);
});

test('cardTargets: si não mira; aliado cai nos amigos; conhecido manda', () => {
  assert.deepEqual(d.cardTargets({ alvo: 'si' }, ['x'], ['e1'], ['player']), []);
  assert.deepEqual(d.cardTargets({ alvo: 'aliado' }, undefined, ['e1'], ['player', 'a1']), ['player', 'a1']);
  assert.deepEqual(d.cardTargets({ alvo: 'inimigo' }, undefined, ['e1', 'e2'], ['player']), ['e1', 'e2']);
  assert.deepEqual(d.cardTargets({ alvo: 'inimigo' }, ['e2'], ['e1', 'e2'], ['player']), ['e2']);
});
