// SPEC-427: lógica pura da fila de uma ação (quando enfileirar, enviar ou devolver ao rascunho).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/queuedAction.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const base = (over = {}) => ({ enabled: true, busy: true, stage: 'narrated', seq: 3, delivered: false, error: false, gid: 'g',
  blocked: false, fighting: false, simulation: false, deckLocked: false, combatResultId: null, choiceId: null,
  deathOrOver: false, ...over });
const closed = (over = {}) => ({ ...base({ busy: false, stage: 'idle', delivered: true }), pendingStored: false, online: true, ...over });
const queued = { text: 'olho o céu', seq: 3, gid: 'g', combatResultId: null, choiceId: null };

test('canEnqueue só em narrated com busy, flag ligada e compositor livre', async () => {
  const { canEnqueue } = await load();
  assert.equal(canEnqueue(base(), 'olho'), true);
  for (const over of [{ enabled: false }, { stage: 'waiting' }, { stage: 'failed-after-narration' }, { stage: 'idle' },
    { busy: false }, { blocked: true }, { fighting: true }, { simulation: true }, { deckLocked: true }, { gid: null }]) {
    assert.equal(canEnqueue(base(over), 'olho'), false, JSON.stringify(over));
  }
  assert.equal(canEnqueue(base(), '   '), false);
  assert.equal(canEnqueue(base(), ''), false);
});

test('decideQueued só envia com delivered e busy falso', async () => {
  const { decideQueued } = await load();
  assert.deepEqual(decideQueued(queued, closed()), { kind: 'send' });
  assert.deepEqual(decideQueued(queued, closed({ busy: true, stage: 'narrated' })), { kind: 'wait' });
  assert.deepEqual(decideQueued(queued, closed({ delivered: false })), { kind: 'return', reason: 'narration-changed' });
  assert.deepEqual(decideQueued(queued, closed({ busy: true })), { kind: 'wait' }); // busy com stage idle: ainda espera
  // fechado mas ainda fora de idle: espera, nunca envia
  assert.deepEqual(decideQueued(queued, closed({ stage: 'narrated' })), { kind: 'wait' });
  assert.deepEqual(decideQueued(queued, closed({ stage: 'waiting' })), { kind: 'wait' });
});

test('decideQueued devolve com o motivo certo para cada caso a–k', async () => {
  const { decideQueued } = await load();
  const why = (over, q = queued) => decideQueued(q, closed(over)).reason;
  assert.equal(why({ fighting: true }), 'combat-started');                                  // a
  assert.equal(why({ combatResultId: 'r2' }), 'combat-result');                             // b
  assert.equal(why({ deathOrOver: true }), 'death');                                        // c
  assert.equal(why({ choiceId: 'c2' }), 'level-choice');                                    // d
  assert.equal(why({ error: true, delivered: false }), 'turn-error');                       // e
  assert.equal(why({ stage: 'failed-after-narration', delivered: false }), 'unsaved');      // f
  assert.equal(why({ delivered: false }), 'narration-changed');                             // g/h
  assert.equal(why({ pendingStored: true }), 'pending');                                    // i
  assert.equal(why({ seq: 4 }), 'resumed');                                                 // j
  assert.equal(why({ online: false }), 'offline');                                          // k
  // o desfecho de combate só conta se MUDOU desde o enfileiramento
  assert.deepEqual(decideQueued({ ...queued, combatResultId: 'r1' }, closed({ combatResultId: 'r1' })), { kind: 'send' });
  assert.equal(why({ combatResultId: 'r2' }, { ...queued, combatResultId: 'r1' }), 'combat-result');
});

test('decideQueued: prioridade j, f, e, g/h, a, b, c, d, i, k', async () => {
  const { decideQueued } = await load();
  const why = (over) => decideQueued(queued, closed(over)).reason;
  assert.equal(why({ seq: 4, fighting: true }), 'resumed');
  assert.equal(why({ seq: 4, busy: true }), 'resumed'); // seq nova em voo: nunca espera nem envia
  assert.equal(why({ stage: 'failed-after-narration', error: true, fighting: true }), 'unsaved');
  assert.equal(why({ error: true, delivered: false, fighting: true }), 'turn-error');
  assert.equal(why({ delivered: false, fighting: true }), 'narration-changed');
  assert.equal(why({ fighting: true, combatResultId: 'r2', deathOrOver: true }), 'combat-started');
  assert.equal(why({ combatResultId: 'r2', deathOrOver: true }), 'combat-result');
  assert.equal(why({ deathOrOver: true, choiceId: 'c2' }), 'death');
  assert.equal(why({ choiceId: 'c2', pendingStored: true }), 'level-choice');
  assert.equal(why({ pendingStored: true, online: false }), 'pending');
});

test('mergeDraft: a fila vem primeiro; campo vazio ou só espaços fica só com a fila', async () => {
  const { mergeDraft } = await load();
  assert.equal(mergeDraft('olho o céu', ''), 'olho o céu');
  assert.equal(mergeDraft('olho o céu', '   \n '), 'olho o céu');
  assert.equal(mergeDraft('olho o céu', 'e escuto'), 'olho o céu\ne escuto');
});

test('returnNote traz o motivo e a flag fica desligada por padrão e só liga com true', async () => {
  const { returnNote, actionQueueEnabled, setActionQueueEnabled } = await load();
  assert.equal(returnNote('offline'), 'A ação na fila não foi enviada: sem conexão. O texto voltou ao campo.');
  assert.equal(actionQueueEnabled(), false);
  for (const v of [1, 'true', 'on', undefined, null]) { setActionQueueEnabled(v); assert.equal(actionQueueEnabled(), false); }
  setActionQueueEnabled(true);
  assert.equal(actionQueueEnabled(), true);
});
