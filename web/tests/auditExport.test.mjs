import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

const { outputFiles } = await build({
  entryPoints: [fileURLToPath(new URL('../src/lib/auditExport.ts', import.meta.url))],
  bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent',
});
const mod = await import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}`);

const blob = { size: 3 };
const httpError = (status, code) => Object.assign(new Error(code), { status, code });

test('with recent proof downloads without asking the password', async () => {
  let asked = 0;
  const result = await mod.exportWithReauth('g1', {
    exportGame: async (id) => { assert.equal(id, 'g1'); return blob; },
    reauthenticate: async () => { throw new Error('must not reauth'); },
    askPassword: async () => { asked++; return 'x'; },
  });
  assert.deepEqual(result, { status: 'ok', blob });
  assert.equal(asked, 0);
});

test('button -> 403 -> reauth -> retried download', async () => {
  const calls = [];
  let attempts = 0;
  const result = await mod.exportWithReauth('g1', {
    exportGame: async () => {
      calls.push('export');
      if (attempts++ === 0) throw httpError(403, 'recent_session_required');
      return blob;
    },
    reauthenticate: async (pw) => { calls.push(`reauth:${pw}`); },
    askPassword: async () => { calls.push('ask'); return 'segredo'; },
  });
  assert.equal(result.status, 'ok');
  assert.deepEqual(calls, ['export', 'ask', 'reauth:segredo', 'export']);
});

test('cancelled password never downloads', async () => {
  const result = await mod.exportWithReauth('g1', {
    exportGame: async () => { throw httpError(403, 'recent_session_required'); },
    reauthenticate: async () => { throw new Error('no'); },
    askPassword: async () => null,
  });
  assert.deepEqual(result, { status: 'cancelled' });
});

test('wrong password and 404/429 become short messages', async () => {
  const wrong = await mod.exportWithReauth('g1', {
    exportGame: async () => { throw httpError(403, 'recent_session_required'); },
    reauthenticate: async () => { throw httpError(401, 'invalid'); },
    askPassword: async () => 'bad',
  });
  assert.equal(wrong.status, 'error');
  for (const [status, needle] of [[404, 'indisponível'], [429, 'Aguarde']]) {
    const r = await mod.exportWithReauth('g1', {
      exportGame: async () => { throw httpError(status, 'x'); },
      reauthenticate: async () => {}, askPassword: async () => 'p',
    });
    assert.equal(r.status, 'error');
    assert.equal(r.httpStatus, status);
    assert.match(r.message, new RegExp(needle));
  }
  assert.match(mod.AUDIT_EXPORT_NOTICE, /privado — referência de auditoria/);
});
