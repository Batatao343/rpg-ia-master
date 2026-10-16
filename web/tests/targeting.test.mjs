import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/combat/targeting.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const card = (over = {}) => ({ id: 'golpe', name: 'Golpe', type: 'ativa', target_kind: 'enemy', cost: 1, ready: true,
  valid_targets: ['e1', 'e2'], invalid_reason: null, rupture_ready: false, ...over });
const enemies = [{ id: 'e1' }, { id: 'e2' }];

test('reducer: idle -> aiming -> submitting -> idle', async () => {
  const t = await load();
  let s = t.IDLE;
  s = t.targetingReducer(s, { type: 'aim', source: { kind: 'card', cardId: 'golpe' } });
  assert.equal(s.phase, 'aiming');
  s = t.targetingReducer(s, { type: 'submit' });
  assert.equal(s.phase, 'submitting');
  // durante o envio a mira fica bloqueada (R14)
  assert.equal(t.targetingReducer(s, { type: 'aim', source: { kind: 'card', cardId: 'x' } }).phase, 'submitting');
  assert.equal(t.targetingReducer(s, { type: 'cancel' }).phase, 'submitting');
  assert.equal(t.targetingReducer(s, { type: 'release' }).phase, 'idle');
});

test('reducer: Esc cancela, mesma carta cancela, outra carta substitui', async () => {
  const t = await load();
  const a = { kind: 'card', cardId: 'a' }, b = { kind: 'card', cardId: 'b' };
  let s = t.targetingReducer(t.IDLE, { type: 'aim', source: a });
  assert.equal(t.targetingReducer(s, { type: 'cancel' }).phase, 'idle');
  assert.equal(t.targetingReducer(s, { type: 'aim', source: a }).phase, 'idle');
  const swapped = t.targetingReducer(s, { type: 'aim', source: b });
  assert.deepEqual(swapped.source, b);
});

test('planCard: com alvo = mira; suporte so em si = direto; bloqueios', async () => {
  const t = await load();
  assert.equal(t.planCard(card(), enemies, false).mode, 'aim');
  assert.equal(t.planCard(card({ valid_targets: ['e1'] }), enemies, false).mode, 'aim'); // 2 gestos (R1)
  const support = card({ target_kind: 'self', valid_targets: ['player'] });
  const plan = t.planCard(support, enemies, false);
  assert.equal(plan.mode, 'direct'); assert.equal(plan.directTarget, 'player');
  const blocked = t.planCard(card({ valid_targets: [], invalid_reason: 'no_entropy' }), enemies, false);
  assert.equal(blocked.mode, 'blocked'); assert.equal(blocked.reason, 'no_entropy');
  assert.equal(t.planCard(card(), enemies, true).mode, 'blocked'); // busy
});

test('planCard: servidor antigo (sem valid_targets) cai no 1o inimigo vivo', async () => {
  const t = await load();
  const legacy = card({ valid_targets: undefined, invalid_reason: undefined });
  const plan = t.planCard(legacy, enemies, false);
  assert.equal(plan.mode, 'direct'); assert.equal(plan.directTarget, 'e1');
  assert.equal(t.planCard({ ...legacy, ready: false }, enemies, false).mode, 'blocked');
});

test('planBasic: um alvo executa direto (P1), varios mira, manobra sem alvo direta', async () => {
  const t = await load();
  const atk = (targets) => ({ kind: 'attack', valid_targets: targets, invalid_reason: null, cost: 0 });
  assert.equal(t.planBasic(atk(['e1']), false).mode, 'direct');
  assert.equal(t.planBasic(atk(['e1', 'e2']), false).mode, 'aim');
  assert.equal(t.planBasic(atk([]), false).mode, 'blocked');
  assert.equal(t.planBasic({ kind: 'flee', valid_targets: [], invalid_reason: null, cost: 0 }, false).mode, 'direct');
});

test('payloads: nenhum numero local; texto estavel para retry com mesmo action_id', async () => {
  const t = await load();
  const [text, opts] = t.cardPayload(card({ rupture_ready: true }), 'e2', 'Lobo', true, undefined);
  assert.equal(text, 'Declaro Ruptura e uso Golpe em Lobo.');
  assert.deepEqual(opts, { card_id: 'golpe', target_id: 'e2', ruptura: true, reaction_card_id: undefined });
  const [self, selfOpts] = t.cardPayload(card({ target_kind: 'self' }), 'player', 'Ayla', false);
  assert.equal(self, 'Uso Golpe.'); assert.equal(selfOpts.target_id, undefined);
  const [atkText, atkOpts] = t.basicPayload({ kind: 'attack', valid_targets: ['e1'], invalid_reason: null, cost: 0 }, 'e1', 'Lobo');
  assert.equal(atkText, 'Ataque básico em Lobo.'); assert.equal(atkOpts.action_kind, 'attack');
});
