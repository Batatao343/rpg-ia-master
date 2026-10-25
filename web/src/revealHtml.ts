// SPEC-320 R8: o markdown (mdLite) roda uma vez por texto; a revelação do typewriter só
// corta o HTML já parseado por nº de caracteres visíveis (tags não contam, entidade = 1).

const VOID_TAGS = new Set(["br", "hr", "img"]);

/** Texto visível de um HTML de mdLite (tags removidas, entidades decodificadas). */
export function htmlToPlain(html: string): string {
  return html.replace(/<[^>]*>/g, "")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}

/** Corta `html` em `visible` caracteres visíveis, fechando as tags abertas. */
export function revealHtml(html: string, visible: number): string {
  if (visible <= 0) return "";
  let out = "";
  let count = 0;
  const open: string[] = [];
  let i = 0;
  while (i < html.length && count < visible) {
    const ch = html[i];
    if (ch === "<") {
      const end = html.indexOf(">", i);
      if (end < 0) break;
      const tag = html.slice(i, end + 1);
      out += tag;
      const m = /^<(\/)?([a-zA-Z0-9]+)/.exec(tag);
      if (m && !VOID_TAGS.has(m[2].toLowerCase())) {
        if (m[1]) open.pop(); else if (!tag.endsWith("/>")) open.push(m[2]);
      }
      i = end + 1;
    } else if (ch === "&") {
      const end = html.indexOf(";", i);
      const ent = end > 0 && end - i <= 5 ? html.slice(i, end + 1) : ch;
      out += ent; i += ent.length; count += 1;
    } else {
      out += ch; i += 1; count += 1;
    }
  }
  while (open.length) out += `</${open.pop()}>`;
  return out;
}
