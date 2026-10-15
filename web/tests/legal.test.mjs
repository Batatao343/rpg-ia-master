import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PAGES, renderMarkdown, buildLegal } from '../scripts/legal.mjs';

test('markdown subset: headings, lists, tables, escaping', () => {
  const html = renderMarkdown('# T\n\n> **RASCUNHO** x\n\n1. **a** `<b>`\n   cont\n2. c\n\n| A | B |\n|---|---|\n| 1 | <script> |\n\n- x\n');
  assert.match(html, /<h1>T<\/h1>/);
  assert.match(html, /legal__draft/);
  assert.match(html, /<ol><li><strong>a<\/strong> <code>&lt;b&gt;<\/code> cont<\/li><li>c<\/li><\/ol>/);
  assert.match(html, /<th>A<\/th>/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /<ul><li>x<\/li><\/ul>/);
});

test('builds the four static pages: RASCUNHO banner, no inline script, cross links', () => {
  const dist = mkdtempSync(join(tmpdir(), 'legal-'));
  mkdirSync(join(dist, 'assets'));
  writeFileSync(join(dist, 'assets', 'index-abc.css'), 'body{}');
  const legalDir = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'docs', 'spec197', 'legal');
  assert.deepEqual(buildLegal({ dist, legalDir }), ['privacidade', 'termos', 'reembolso', 'suporte']);
  for (const p of PAGES) {
    const html = readFileSync(join(dist, p.slug, 'index.html'), 'utf8');
    assert.match(html, /RASCUNHO/);
    assert.match(html, /\/assets\/index-abc\.css/);
    assert.doesNotMatch(html, /<script|onclick=|javascript:/i);
    for (const q of PAGES) assert.ok(html.includes(`href="/${q.slug}/"`));
  }
});
