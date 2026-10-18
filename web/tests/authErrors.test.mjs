import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load(name) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(`../src/${name}.ts`, import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const err = (status, code, extra = {}) => Object.assign(new Error(code), { status, code, ...extra });

test('auth errors never surface raw backend codes', async () => {
  const { authErrorMessage } = await load('lib/authErrors');
  const codes = ['credentials_invalid', 'email_not_confirmed', 'captcha_invalid', 'captcha_required',
    'csrf_invalid', 'origin_denied', 'captcha_unavailable', 'signup_failed', 'session_invalid',
    'validation_error', 'auth_rate_limit', 'whatever_new_code'];
  for (const flow of ['login', 'signup', 'email']) {
    for (const code of codes) {
      const message = authErrorMessage(err(code === 'auth_rate_limit' ? 429 : 401, code), flow);
      assert.ok(message.length > 10);
      assert.doesNotMatch(message, /[a-z]+_[a-z_]+/, `${flow}/${code} leaked a code: ${message}`);
    }
  }
});

test('login messages explain the actionable cases', async () => {
  const { authErrorMessage } = await load('lib/authErrors');
  assert.match(authErrorMessage(err(401, 'credentials_invalid'), 'login'), /senha incorretos/);
  assert.match(authErrorMessage(err(401, 'email_not_confirmed'), 'login'), /Confirme seu e-mail/);
  assert.match(authErrorMessage(err(403, 'captcha_invalid'), 'login'), /anti-robô/);
  assert.match(authErrorMessage(err(429, 'auth_rate_limit', { retryAfterSeconds: 600 }), 'email'), /10 min/);
  assert.match(authErrorMessage(new TypeError('Failed to fetch'), 'login'), /Tente novamente/);
});
