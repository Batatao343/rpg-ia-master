// SPEC-197 R3: renders web/legal/*.md (RASCUNHO) into static pages at build time.
// Output: dist/<slug>/index.html -- no inline script, same theme (links the built app stylesheet).
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

export const PAGES = [
  { slug: 'privacidade', file: 'privacy-policy.md', label: 'Privacidade' },
  { slug: 'termos', file: 'terms.md', label: 'Termos' },
  { slug: 'reembolso', file: 'refund-policy.md', label: 'Reembolso' },
  { slug: 'suporte', file: 'support.md', label: 'Suporte' },
  { slug: 'creditos', file: 'credits.md', label: 'Créditos' },
];

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
function inline(raw) {
  const codes = [];
  let s = esc(raw).replace(/`([^`]+)`/g, (_m, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>');
  return s.replace(/\u0000(\d+)\u0000/g, (_m, i) => `<code>${codes[Number(i)]}</code>`);
}

const ITEM = /^\s*(?:(\d+)\.|[-*])\s+(.*)$/;

/** Minimal Markdown subset used by the legal drafts: #/##/###, > quote, 1. lists, - lists, tables, paragraphs. */
export function renderMarkdown(md) {
  const lines = md.replace(/\r\n/g, '\n').split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const h = /^(#{1,3})\s+(.*)$/.exec(line);
    if (h) { out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); i++; continue; }
    if (line.startsWith('>')) {
      const buf = [];
      while (i < lines.length && lines[i].startsWith('>')) buf.push(lines[i++].replace(/^>\s?/, ''));
      out.push(`<blockquote class="legal__draft">${inline(buf.join(' '))}</blockquote>`);
      continue;
    }
    if (line.startsWith('|')) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith('|')) rows.push(lines[i++]);
      const cells = (r) => r.replace(/^\||\|$/g, '').split('|').map((c) => inline(c.trim()));
      const body = rows.filter((r) => !/^\|[\s:|-]+\|?$/.test(r));
      const [head, ...rest] = body;
      out.push(`<div class="legal__table"><table><thead><tr>${cells(head).map((c) => `<th>${c}</th>`).join('')}</tr></thead><tbody>${
        rest.map((r) => `<tr>${cells(r).map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
      continue;
    }
    const li = ITEM.exec(line);
    if (li) {
      const ordered = Boolean(li[1]);
      const items = [];
      while (i < lines.length) {
        const m = ITEM.exec(lines[i]);
        if (m) { items.push(m[2]); i++; }
        else if (/^\s{2,}\S/.test(lines[i]) && items.length) { items[items.length - 1] += ' ' + lines[i].trim(); i++; }
        else break;
      }
      const tag = ordered ? 'ol' : 'ul';
      out.push(`<${tag}>${items.map((t) => `<li>${inline(t)}</li>`).join('')}</${tag}>`);
      continue;
    }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,3}\s|>|\||\s*(\d+\.|[-*])\s)/.test(lines[i])) buf.push(lines[i++]);
    out.push(`<p>${inline(buf.join(' '))}</p>`);
  }
  return out.join('\n');
}

/** Optional front-matter block with `status: draft|final`; anything but `final` is treated as draft. */
export function parseFrontMatter(md) {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(md);
  if (!m) return { status: 'draft', body: md };
  const st = /^status:\s*(\w+)/m.exec(m[1]);
  return { status: st && st[1].toLowerCase() === 'final' ? 'final' : 'draft', body: md.slice(m[0].length) };
}

export function renderPage({ label, slug }, bodyHtml, cssHref, status = 'draft') {
  const nav = PAGES.map((p) => `<a href="/${p.slug}/"${p.slug === slug ? ' aria-current="page"' : ''}>${p.label}</a>`).join('');
  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta name="robots" content="noindex" />
<title>${esc(label)} - Crônicas</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
${cssHref ? `<link rel="stylesheet" href="${cssHref}" />` : ''}
</head>
<body>
<main class="legal" data-legal-page="${slug}">
${status === 'final' ? '' : '<p class="legal__banner" role="note"><strong>RASCUNHO</strong> - texto em revisão pelo titular; não vale como documento jurídico final.</p>'}
<nav class="legal__nav" aria-label="Documentos legais">${nav}<a href="/">Voltar ao jogo</a></nav>
${bodyHtml}
</main>
</body>
</html>
`;
}

export function buildLegal({ dist, legalDir }) {
  const assets = join(dist, 'assets');
  const css = existsSync(assets) ? readdirSync(assets).find((f) => f.endsWith('.css')) : undefined;
  const written = [];
  for (const page of PAGES) {
    const { status, body } = parseFrontMatter(readFileSync(join(legalDir, page.file), 'utf8'));
    const html = renderPage(page, renderMarkdown(body), css ? `/assets/${css}` : '', status);
    mkdirSync(join(dist, page.slug), { recursive: true });
    writeFileSync(join(dist, page.slug, 'index.html'), html);
    written.push(page.slug);
  }
  return written;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const here = dirname(fileURLToPath(import.meta.url));
  const written = buildLegal({ dist: join(here, '..', 'dist'), legalDir: join(here, '..', 'legal') });
  console.log('legal pages:', written.join(', '));
}
