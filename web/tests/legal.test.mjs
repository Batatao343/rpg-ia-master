import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PAGES, renderMarkdown, buildLegal, parseFrontMatter, renderPage } from '../scripts/legal.mjs';

test('markdown subset: headings, lists, tables, escaping', () => {
  const html = renderMarkdown('# T\n\n> **RASCUNHO** x\n\n1. **a** `<b>`\n   cont\n2. c\n\n| A | B |\n|---|---|\n| 1 | <script> |\n\n- x\n');
  assert.match(html, /<h1>T<\/h1>/);
  assert.match(html, /legal__draft/);
  assert.match(html, /<ol><li><strong>a<\/strong> <code>&lt;b&gt;<\/code> cont<\/li><li>c<\/li><\/ol>/);
  assert.match(html, /<th>A<\/th>/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /<ul><li>x<\/li><\/ul>/);
});

test('builds the static pages: published (no RASCUNHO), no placeholder, owner data, no inline script, cross links', () => {
  const dist = mkdtempSync(join(tmpdir(), 'legal-'));
  mkdirSync(join(dist, 'assets'));
  writeFileSync(join(dist, 'assets', 'index-abc.css'), 'body{}');
  const legalDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'legal');
  assert.deepEqual(buildLegal({ dist, legalDir }), ['privacidade', 'termos', 'reembolso', 'suporte', 'creditos']);
  for (const p of PAGES) {
    const html = readFileSync(join(dist, p.slug, 'index.html'), 'utf8');
    assert.doesNotMatch(html, /RASCUNHO/);
    assert.doesNotMatch(html, /&lt;[^&\n]{1,80}?&gt;/);
    assert.match(html, /Última atualização: \d{2}\/\d{2}\/2026/);
    assert.match(html, /\/assets\/index-abc\.css/);
    assert.doesNotMatch(html, /<script|onclick=|javascript:/i);
    for (const q of PAGES) assert.ok(html.includes(`href="/${q.slug}/"`));
  }
});

test('front-matter status drives the RASCUNHO banner (draft default)', () => {
  assert.equal(parseFrontMatter('# x').status, 'draft');
  assert.equal(parseFrontMatter('---\nstatus: draft\n---\n# x').status, 'draft');
  const fin = parseFrontMatter('---\nstatus: final\n---\n# x');
  assert.equal(fin.status, 'final');
  assert.equal(fin.body, '# x');
  assert.match(renderPage(PAGES[0], '', '', 'draft'), /RASCUNHO/);
  assert.doesNotMatch(renderPage(PAGES[0], '', '', 'final'), /RASCUNHO/);
});
