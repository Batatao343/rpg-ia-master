// SPEC-352 R12: regras puras do pedido de retrato pago (confirmação única só se a cotação cabe no preço mostrado).
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

test('cotacao_dentro_do_preco_mostrado_confirma_direto_e_maior_abre_dialogo', async () => {
  const { withinShownPrice } = await load('../src/lib/portraitOrder.ts');
  assert.equal(withinShownPrice('3000', 3), true);   // igual ao mostrado
  assert.equal(withinShownPrice('2500', 3), true);   // menor
  assert.equal(withinShownPrice('3001', 3), false);  // câmbio mudou: 1 milli acima -> diálogo
  assert.equal(withinShownPrice('abc', 3), false);   // lixo nunca confirma
});

test('erros_do_retrato_viram_aviso_curto_sem_cobranca', async () => {
  const { portraitErrorBanner } = await load('../src/lib/portraitOrder.ts');
  for (const code of ['creature_portrait_in_progress', 'creature_portrait_exists']) {
    const b = portraitErrorBanner(409, code, 'x');
    assert.equal(b.kind, 'info');
    assert.match(b.msg, /Outro jogador já está gerando este retrato\. Ele aparece em breve, sem custo\./);
  }
  assert.equal(portraitErrorBanner(402, 'image_insufficient_shards', 'x').msg, 'Estilhas insuficientes.');
  assert.equal(portraitErrorBanner(503, 'image_generation_disabled', 'x').msg, 'Geração de imagem indisponível agora.');
  assert.equal(portraitErrorBanner(500, undefined, 'falhou').msg, 'falhou');
});

test('dialogo_monster_avisa_compartilhamento_e_liberacao', async () => {
  const { ImageQuoteDialog } = await load('../src/components/ImageQuoteDialog.tsx');
  const quote = { quote_id: 'q', type: 'monster', credits_milli: '4000', pricing_version: 'v', expires_at: new Date(Date.now() + 300000).toISOString(), reformulation: false };
  const out = html(h(ImageQuoteDialog, { quote, busy: false, error: '', onConfirm() {}, onCancel() {} }));
  assert.match(out, /Gerar retrato/);
  assert.match(out, /registro compartilhado/);
  assert.match(out, /saldo é liberado/);
  assert.match(out, /Custo máximo: <strong>4 Estilhas/);
});
