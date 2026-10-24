import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

async function load() {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/clockLabel.ts', import.meta.url))],
    bundle: true, write: false, format: 'esm', platform: 'neutral', logLevel: 'silent' });
  return import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}#${Math.random()}`);
}

const date = { label: '3º dia de Vorrnak, Sino de Cobre — Ano 112 da Era 7', day_of_month: 3, month: 'Vorrnak',
  month_id: 'vorrnak', weekday: 'Sino de Cobre', year: 112, climate: 'frio' };

test('clockLabel: legado sem data, data de Valoria com data, chip regional', async () => {
  const m = await load();
  assert.equal(m.clockLabel(undefined), 'Dia 1 · Amanhecer');
  assert.equal(m.clockLabel({ day: 4, period: 'Noite' }), 'Dia 4 · Noite');
  assert.equal(m.clockLabel({ day: 4, period: 'Noite', date: null }), 'Dia 4 · Noite');
  assert.equal(m.clockLabel({ day: 4, period: 'Noite', date }), `${date.label} · Noite`);
  assert.equal(m.clockLabel({ day: 4, period: 'Noite', date: { ...date, season_chip: 'Noite Longa' } }),
    `${date.label} · Noite · Noite Longa`);
});
