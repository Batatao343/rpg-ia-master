// SPEC-322 R5/R6/R7/R10-R12: lint de CSS em node (stylelint-equivalente, sem dependência nova).
// Falha em: hex/rgb() literal, var(--x) indefinida, raio literal, duplicata de .combat-card/.tab/pulse,
// `transition: width`, z-index numérico alto fora de :root.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src", import.meta.url));
const walk = (d, ext, out = []) => {
  for (const n of readdirSync(d)) {
    const p = `${d}/${n}`;
    if (statSync(p).isDirectory()) walk(p, ext, out);
    else if (ext.some((e) => p.endsWith(e))) out.push(p);
  }
  return out;
};
const allCss = walk(SRC, [".css"]);
const cssFiles = allCss.filter((f) => !f.endsWith("fonts.css"));
const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
const lines = (f) => strip(readFileSync(f, "utf8")).split("\n");
const rel = (f) => f.slice(SRC.length + 1);

test("R5: zero hex/rgb()/hsl() literal em CSS (cor só por token oklch)", () => {
  const bad = [];
  for (const f of allCss) {
    lines(f).forEach((l0, i) => {
      const l = l0.replace(/url\((["']?)data:[^)]*\)/g, "url()"); // remove só o payload data: embutido
      if (/#[0-9a-fA-F]{3,8}\b/.test(l) || /\b(rgba?|hsla?)\(/.test(l)) bad.push(`${rel(f)}:${i + 1}`);
    });
  }
  assert.deepEqual(bad, []);
});

test("R5: toda var(--x) tem definição (CSS ou JS) ou fallback", () => {
  const defined = new Set();
  for (const f of cssFiles) for (const m of strip(readFileSync(f, "utf8")).matchAll(/(--[a-z0-9-]+)\s*:/g)) defined.add(m[1]);
  for (const f of walk(SRC, [".ts", ".tsx"])) {
    const s = readFileSync(f, "utf8");
    for (const m of s.matchAll(/["'`](--[a-z0-9-]+)["'`]/g)) defined.add(m[1]);
    for (const m of s.matchAll(/(--[a-z0-9-]+)\s*:/g)) defined.add(m[1]);
  }
  const bad = [];
  for (const f of cssFiles) {
    lines(f).forEach((l, i) => {
      for (const m of l.matchAll(/var\((--[a-z0-9-]+)\s*([,)])/g)) {
        if (!defined.has(m[1]) && m[2] === ")") bad.push(`${rel(f)}:${i + 1} ${m[1]}`);
      }
    });
  }
  assert.deepEqual(bad, []);
});

test("R7: border-radius só por token (ou 0 / 50% / inherit)", () => {
  const tok = String.raw`(?:0|var\(--r-(?:sharp|sm|md|pill)\))`;
  const ok = new RegExp(String.raw`^(?:50%|inherit|none|${tok}(?:\s+${tok}){0,3})$`);
  const bad = [];
  for (const f of cssFiles) {
    lines(f).forEach((l, i) => {
      for (const m of l.matchAll(/(?:border-(?:(?:top|bottom)-(?:left|right)-)?|border-(?:start|end)-(?:start|end)-)radius:\s*([^;}]+)/g)) {
        if (!ok.test(m[1].trim().replace(/\s*!important$/, ""))) bad.push(`${rel(f)}:${i + 1} ${m[1].trim()}`);
      }
    });
  }
  assert.deepEqual(bad, []);
});

test("R7: pílula (--r-pill) só em tags de status, barras e indicadores", () => {
  // lista curta e explícita; ampliar exige decisão de design
  const allowed = /(chip|badge|seal|\btag|status|bar\b|bar__|track|fill|dot|scrollbar|thumb|tchip|abyss|flag|disp|deadline|traitchip|knowledge|locked|reveal-new|data-selected|dossier-flag|outcome-chip|spark)/i;
  const deny = /(placechip|actionchip|codex-cat|\.btn|iconbtn|\.seg\b|button|select|filter|offer|step|\.tab\b|cancel|copy|\.init\b)/;
  const bad = [];
  for (const f of cssFiles) {
    const src = strip(readFileSync(f, "utf8"));
    for (const m of src.matchAll(/([^{}]+)\{([^{}]*border-radius:\s*var\(--r-pill\)[^{}]*)\}/g)) {
      if (!allowed.test(m[1]) || deny.test(m[1])) bad.push(`${rel(f)}: ${m[1].trim().split("\n").pop().slice(0, 70)}`);
    }
  }
  assert.deepEqual(bad, []);
});

test("R10: um único .combat-card, um único .tab, um único keyframe de pulso", () => {
  const all = cssFiles.map((f) => strip(readFileSync(f, "utf8"))).join("\n");
  const count = (re) => (all.match(re) || []).length;
  assert.equal(count(/^\.combat-card\s*\{/gm), 1, ".combat-card {");
  assert.equal(count(/^\.tab\s*\{/gm), 1, ".tab {");
  assert.equal(count(/@keyframes\s+(prologue-pulse|pulse)\b/g), 1, "keyframe de pulso");
});

test("R11: sem `transition: width` (barras usam scaleX)", () => {
  const bad = [];
  for (const f of cssFiles) lines(f).forEach((l, i) => /transition:[^;]*\bwidth\b/.test(l) && bad.push(`${rel(f)}:${i + 1}`));
  assert.deepEqual(bad, []);
});

test("R11: sem overshoot (--ease-spring-soft removido)", () => {
  for (const f of cssFiles) assert.ok(!/ease-spring-soft/.test(readFileSync(f, "utf8")), rel(f));
});

test("R12: z-index > 2 só por token --z-*", () => {
  const bad = [];
  for (const f of cssFiles) {
    lines(f).forEach((l, i) => {
      if (/^\s*--z-/.test(l) || /^\s*:root/.test(l)) return;
      for (const m of l.matchAll(/z-index:\s*(-?\d+)/g)) if (Math.abs(Number(m[1])) > 2) bad.push(`${rel(f)}:${i + 1} ${m[1]}`);
    });
  }
  assert.deepEqual(bad, []);
});

test("R5: cor literal oklch() fora de :root não cresce (catraca; migrar para tokens)", () => {
  const MAX = 57; // medido em 2026-10-26; só pode DIMINUIR
  let n = 0;
  for (const f of cssFiles) {
    let inRoot = false;
    lines(f).forEach((l) => {
      if (/^:root\b/.test(l)) inRoot = true;
      if (inRoot) { if (/^}/.test(l)) inRoot = false; return; }
      if (/^\s*--/.test(l)) return;
      n += (l.match(/oklch\(/g) || []).length;
    });
  }
  assert.ok(n <= MAX, `oklch() literais fora de :root: ${n} > ${MAX}`);
});
