// SPEC-354 R5.5: marcação SSR do RoundBoard (jogadas × efeitos da rodada).
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
const base = { ator_id: 'player', ator_nome: 'Haldor', lado: 'heroi', carta_id: 'golpe', carta_nome: 'Golpe', alvo_id: 'enemy_bandido_1', alvo_nome: 'Bandido',
  origem: 'turno', rotulo: null, resultado: 'acerto', dano: 6, efeito: null };
const dot = { ...base, carta_id: null, carta_nome: 'Sangrando', alvo_id: null, alvo_nome: null, rotulo: 'Dano contínuo', resultado: 'efeito', dano: 1, efeito: '−1 Vitalidade' };

test('dot_no_jogador_vai_para_efeitos_sem_icone_nem_voce_como_ator', async () => {
  const { RoundBoard } = await load('../src/components/combat/RoundBoard.tsx');
  const out = html(h(RoundBoard, { entries: [base, dot], round: 3 }));
  const [plays, fx] = out.split('Efeitos da rodada');
  assert.match(fx, /Você sofre Sangrando · −1 Vitalidade/);
  assert.doesNotMatch(fx, /roundboard__who/);
  assert.doesNotMatch(plays, /Sangrando/);
});

test('queda_e_pressagio_texto_literal', async () => {
  const { RoundBoard } = await load('../src/components/combat/RoundBoard.tsx');
  const queda = { ...base, ator_id: 'enemy_bandido_1', ator_nome: 'Bandido', lado: 'inimigo', carta_id: null, carta_nome: null, alvo_id: null, alvo_nome: null, resultado: 'efeito', dano: null, efeito: 'abatido', tipo: 'queda' };
  const press = { ...queda, efeito: 'a lâmina cai', tipo: 'pressagio' };
  const out = html(h(RoundBoard, { entries: [base, queda, press], round: 3 }));
  assert.match(out, /Bandido cai \(abatido\)/);
  assert.match(out, /Presságio cumprido: a lâmina cai/);
});

test('acerto_sem_dano_nunca_so_acerto', async () => {
  const { RoundBoard } = await load('../src/components/combat/RoundBoard.tsx');
  const sem = html(h(RoundBoard, { entries: [{ ...base, dano: null }], round: 2 }));
  assert.match(sem, /Acerto · sem dano/);
  const com = html(h(RoundBoard, { entries: [{ ...base, dano: null, efeito: 'Sangrando' }], round: 2 }));
  assert.match(com, /Acerto · Sangrando/);
});

test('sem_efeitos_nao_ha_lista_e_entrada_antiga_renderiza', async () => {
  const { RoundBoard } = await load('../src/components/combat/RoundBoard.tsx');
  const out = html(h(RoundBoard, { entries: [base], round: 2 }));
  assert.doesNotMatch(out, /Efeitos da rodada/);
  assert.match(out, /Golpe/);
  assert.match(html(h(RoundBoard, { entries: [base], round: 2, title: 'O que se jogou na rodada final' })), /O que se jogou na rodada final/);
});

test('leitor_de_tela_separa_jogadas_de_efeitos', async () => {
  const { RoundBoard } = await load('../src/components/combat/RoundBoard.tsx');
  const out = html(h(RoundBoard, { entries: [base, base, dot], round: 3 }));
  assert.match(out, /Rodada resolvida: 2 jogadas e 1 efeito\./);
});
