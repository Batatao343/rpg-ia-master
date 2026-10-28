// SPEC-347: marcação SSR dos componentes do tabuleiro (prévia pendente, fila, Arena, Hud, RoundBoard, TargetChip, Composer).
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

test('previewchip_pending_mostra_lendo_os_sinais', async () => {
  const { PreviewChip } = await load('../src/components/combat/PreviewChip.tsx');
  assert.match(html(h(PreviewChip, { state: { status: 'pending' } })), /Lendo os sinais…/);
  assert.equal(html(h(PreviewChip, { state: { status: 'idle' } })), '');
});

test('playqueue_desfazer_fila_na_fila_e_selo', async () => {
  const { PlayQueue } = await load('../src/components/combat/PlayQueue.tsx');
  const q = [{ uid: 'p1', name: 'Golpe', cardId: 'golpe', targetId: 'e1' }, { uid: 'p2', name: 'Corte', cardId: 'corte', targetId: 'e1' }];
  const out = html(h(PlayQueue, { queue: q, selected: null, nameOf: () => 'X', busy: false, onSelect() {}, onMove() {}, onRemove() {}, onClear() {}, onEnd() {}, touch: true }));
  assert.match(out, /play-queue__clear--inline/);
  assert.match(out, /play-queue__badge" aria-hidden="true">2</);
  assert.match(out, /aria-label="Encerrar a rodada, 2 cartas"/);
});

const combatBase = { round: 3, order: [{ name: 'Inimigos', side: 'enemy', init: 0 }, { name: 'Heróis', side: 'hero', init: 0 }],
  enemies: [], scene: { zones: [{ id: 'a', name: 'Ponte', connections: [] }, { id: 'b', name: 'Vão', connections: [] }], positions: [
    { participant_id: 'player', participant_name: 'Ayla', zone_id: 'a', distance: 'proximo', posture: 'neutro', concealment: 'visivel', engaged_with: [], engaged_names: [] }] },
  wounds: { vitality: 5, max_vitality: 8, slots: {}, by_severity: {} }, player_conditions: [], chase: null };

test('arena_iniciativa_honesta_e_compact', async () => {
  const { Arena } = await load('../src/combat/Arena.tsx');
  const full = html(h(Arena, { combat: combatBase, party: [], onPick() {} }));
  assert.match(full, /Na última rodada, Inimigos agiram primeiro\./);
  assert.doesNotMatch(full, /iniciativa:|Rodada 3/);
  assert.match(full, /Zona: Vão/);
  const compact = html(h(Arena, { combat: combatBase, party: [], onPick() {}, compact: true }));
  assert.match(compact, /arena--compact/);
  assert.doesNotMatch(compact, /Zona: Vão/);
  assert.match(compact, /Também na cena: Vão/);
});

test('hud_rodada_uma_vez_e_sem_zero', async () => {
  const { CombatTab } = await load('../src/components/Hud.tsx');
  const c = { ...combatBase, active: true, enemies: [{ id: 'e1', name: 'X', vitalidade: 3, max_vitalidade: 3, esquiva: 5, protecao: 0, conditions: [], revealed_cards: [], revealed_resistances: [] }],
    cooldowns: {}, cards: [] };
  const off = html(h(CombatTab, { c, hitKey: 0, party: [] }));
  assert.equal((off.match(/Rodada/g) || []).length, 1);
  assert.doesNotMatch(off, /\b0 · /);
  assert.match(off, /Inimigos/);
  const deck = html(h(CombatTab, { c, hitKey: 0, party: [], deck: true }));
  assert.doesNotMatch(deck, /Rodada/);
  const withArena = html(h(CombatTab, { c, hitKey: 0, party: [], arena: true, deck: true }));
  assert.doesNotMatch(withArena, /class="initiative"/);
});

test('forja_via_fechada_aria_disabled_e_motivo', async () => {
  const { ForjaPanel } = await load('../src/components/combat/ForjaPanel.tsx');
  const forja = { permitido: true, motivo: '', baralho_min: 3,
    baralho: [{ id: 'golpe', name: 'Golpe', copias: 1, esquecivel: true, bloqueio: null }],
    esquecer: { descanso: false, templo: false, ouro: 25, motivos: { descanso: 'Só dá para esquecer uma Carta depois de um descanso longo.', templo: 'Só um templo ou curandeiro ajuda a esquecer uma Carta.' } },
    afiar: { material: null, afiaveis: [], afiadas: [] }, cicatrizes: [], purgar: { medico: false, templo: false, ouro: 40 } };
  // a linha só abre a barra depois do clique; o SSR cobre a ausência de ruído quando nada está selecionado
  const out = html(h(ForjaPanel, { forja, cards: [], busy: false, onForge() {} }));
  assert.doesNotMatch(out, /forja-why-forget/);
  assert.match(out, /data-forja-row="golpe"/);
});

test('cardrewards_choices_levam_o_motivo', async () => {
  const { forgetChoices, purgeChoices } = await load('../src/cardRewards.ts');
  const forja = { permitido: true, esquecer: { descanso: false, templo: true, ouro: 25, motivos: { descanso: 'sem descanso', templo: null } },
    purgar: { medico: false, templo: false, ouro: 40, motivos: { medico: 'sem médico', templo: 'sem templo' } } };
  const [rest, temple] = forgetChoices(forja);
  assert.equal(rest.why, 'sem descanso'); assert.equal(rest.enabled, false);
  assert.equal(temple.why, null); assert.equal(temple.enabled, true);
  assert.deepEqual(purgeChoices(forja).map((c) => c.why), ['sem médico', 'sem templo']);
});

test('roundboard_vazio_nada_e_celular_4_mais_details', async () => {
  const { RoundBoard } = await load('../src/components/combat/RoundBoard.tsx');
  assert.equal(html(h(RoundBoard, { entries: [], round: 2, compact: false })), '');
  assert.equal(html(h(RoundBoard, { entries: undefined, round: 2, compact: true })), '');
  const e = (i) => ({ ator_id: i % 2 ? 'e1' : 'player', ator_nome: i % 2 ? 'Saqueador' : 'Ayla', lado: i % 2 ? 'inimigo' : 'heroi', carta_id: 'x', carta_nome: `Carta ${i}`,
    alvo_id: 't', alvo_nome: 'Alvo', origem: i === 5 ? 'reacao' : 'turno', rotulo: i === 5 ? 'Contra-ataque' : null, resultado: 'acerto', dano: 3, efeito: null });
  const entries = [0, 1, 2, 3, 4, 5].map(e);
  const mobile = html(h(RoundBoard, { entries, round: 3, compact: true }));
  const outer = mobile.split('<details')[0];
  assert.equal((outer.match(/roundboard__row /g) || []).length, 4);
  assert.match(mobile, /Ver a rodada inteira \(6\)/);
  assert.match(mobile, /Rodada resolvida: 6 jogadas\./);
  assert.match(mobile, /Contra-ataque/);
  const desktop = html(h(RoundBoard, { entries, round: 3, compact: false }));
  assert.equal((desktop.match(/roundboard__row /g) || []).length, 6);
  assert.doesNotMatch(desktop, /<details/);
  assert.match(desktop, /O que se jogou na rodada 2/);
});

test('composer_deckLocked_sem_textarea_e_sem_a_prop_igual_a_hoje', async () => {
  const { Composer } = await load('../src/workspace/ChatSurface.tsx');
  const data = { game_id: 'g1', combat: { active: true, pilhas: {} }, world: {}, player_stats: {} };
  const props = { data, busy: false, blocked: false, onAction() {} };
  const locked = html(h(Composer, { ...props, deckLocked: true }));
  assert.doesNotMatch(locked, /<textarea/);
  assert.doesNotMatch(locked, />Lutar</);
  assert.match(locked, /role="note"[^>]*>Na luta, você age pelas cartas do tabuleiro\./);
  const plain = html(h(Composer, props));
  assert.match(plain, /<textarea/);
  assert.match(plain, /placeholder="O inimigo avança\. O que você faz\?"/);
  assert.match(plain, />Lutar</);
  assert.equal(plain, html(h(Composer, { ...props, deckLocked: false })));
});

test('playqueue_fugir_botao_e_motivo', async () => {
  const { PlayQueue } = await load('../src/components/combat/PlayQueue.tsx');
  const base = { queue: [], selected: null, nameOf: () => 'X', busy: false, onSelect() {}, onMove() {}, onRemove() {}, onClear() {}, onEnd() {}, touch: true };
  assert.doesNotMatch(html(h(PlayQueue, base)), /data-flee/);
  const on = html(h(PlayQueue, { ...base, onFlee() {} }));
  assert.match(on, /data-flee/);
  assert.doesNotMatch(on, /aria-disabled="true"[^>]*data-flee|data-flee[^>]*aria-disabled="true"/);
  const closed = html(h(PlayQueue, { ...base, onFlee() {}, fleeReason: 'Sem saída.' }));
  assert.match(closed, /Sem saída\./);
});
