// SPEC-322 R1-R4: conversor OKLCH -> sRGB e verificador de contraste WCAG dos tokens de cor.
// Uso: `node scripts/contrast.mjs` (exit 1 se algum par exigido falhar). Importado por tests/contrast.test.mjs.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const here = (rel) => fileURLToPath(new URL(rel, import.meta.url));

/** Lê `--nome: valor;` de :root em tokens.css + styles.css (styles.css vence). */
export function readTokens() {
  const out = {};
  for (const f of ["../src/design/tokens.css", "../src/styles.css"]) {
    const css = readFileSync(here(f), "utf8");
    for (const m of css.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  }
  return out;
}

/** oklch(L C H [/ a]) -> [r,g,b] lineares 0..1 (sem clamp de gamut além do necessário). */
export function oklchToLinear(L, C, Hdeg) {
  const h = (Hdeg * Math.PI) / 180;
  const a = C * Math.cos(h), b = C * Math.sin(h);
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.291485548 * b;
  const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
  const rgb = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  return rgb.map((v) => Math.min(1, Math.max(0, v)));
}

export function parseOklch(value) {
  const m = value.match(/^oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/);
  if (!m) throw new Error(`nao e oklch(): ${value}`);
  const alpha = value.match(/\/\s*([\d.]+%?)\s*\)/);
  if (alpha) {
    const a = alpha[1].endsWith("%") ? parseFloat(alpha[1]) / 100 : Number(alpha[1]);
    if (a < 1) throw new Error(`token translucido nao serve de cor de texto/fundo opaco: ${value}`);
  }
  return oklchToLinear(Number(m[1]), Number(m[2]), Number(m[3]));
}

export function luminance(lin) {
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

export function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

export function tokenRatio(tokens, fg, bg) {
  const get = (n) => {
    if (!(n in tokens)) throw new Error(`token ${n} ausente`);
    return parseOklch(tokens[n]);
  };
  return ratio(get(fg), get(bg));
}

const SURFACES = ["--surface", "--surface-2", "--bg-deep", "--bg"];
const FIELD_BGS = ["--bg-deep", "--surface", "--surface-2", "--bg"];
/** Pares exigidos: [fg, bg[], minimo]. Texto >= 4,5 (1.4.3); bordas de campo >= 3 (1.4.11). */
export const REQUIRED = [
  ...["--ink", "--muted", "--faint", "--danger-text", "--abyss-text", "--accent"].map((fg) => [fg, SURFACES, 4.5]),
  ["--field-border", FIELD_BGS, 3.0],
  // botões preenchidos
  ["--on-danger", ["--danger"], 4.5],
  ["--on-accent", ["--accent", "--accent-strong"], 4.5],
];

export function check(tokens = readTokens()) {
  const rows = [];
  for (const [fg, bgs, min] of REQUIRED) {
    for (const bg of bgs) {
      const r = tokenRatio(tokens, fg, bg);
      rows.push({ fg, bg, min, ratio: r, ok: r >= min });
    }
  }
  return rows;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const rows = check();
  for (const r of rows) console.log(`${r.ok ? "ok  " : "FAIL"} ${r.fg} / ${r.bg}: ${r.ratio.toFixed(2)} (>= ${r.min})`);
  process.exit(rows.every((r) => r.ok) ? 0 : 1);
}
