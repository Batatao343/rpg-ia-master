// SPEC-322 Etapa 1: contraste WCAG dos tokens de texto e de borda de campo.
import { test } from "node:test";
import assert from "node:assert/strict";
import { check, readTokens, tokenRatio } from "../scripts/contrast.mjs";

test("sanidade do conversor: branco/preto = 21:1", () => {
  const t = { "--w": "oklch(1 0 0)", "--k": "oklch(0 0 0)" };
  assert.ok(Math.abs(tokenRatio(t, "--w", "--k") - 21) < 0.2);
});

test("R1-R4: pares texto/fundo >= 4,5 e borda de campo >= 3", () => {
  const fails = check().filter((r) => !r.ok).map((r) => `${r.fg}/${r.bg}=${r.ratio.toFixed(2)}<${r.min}`);
  assert.deepEqual(fails, []);
});

test("R2: --danger nao e cor de texto (so --danger-text)", async () => {
  const { readFileSync, readdirSync, statSync } = await import("node:fs");
  const { fileURLToPath } = await import("node:url");
  const files = [];
  const walk = (d) => { for (const n of readdirSync(d)) { const p = `${d}/${n}`; statSync(p).isDirectory() ? walk(p) : p.endsWith(".css") && files.push(p); } };
  walk(fileURLToPath(new URL("../src", import.meta.url)));
  const bad = [];
  for (const f of files) {
    readFileSync(f, "utf8").split("\n").forEach((line, i) => {
      if (/(^|[;{\s])color:\s*var\(--danger(-bright)?\)/.test(line)) bad.push(`${f.split("src")[1]}:${i + 1}`);
    });
  }
  assert.deepEqual(bad, []);
});

test("tokens novos existem", () => {
  const t = readTokens();
  for (const n of ["--danger-text", "--field-border", "--abyss", "--abyss-dim", "--abyss-line", "--abyss-text",
    "--r-sharp", "--r-sm", "--r-md", "--r-pill"]) assert.ok(n in t, n);
});

test("SPEC-345 9b: botao desabilitado sem opacity e com contraste >= 4,5", async () => {
  const { readFileSync } = await import("node:fs");
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  const rule = css.match(/\.btn:disabled, \.btn--primary:disabled, \.btn--danger:disabled \{([^}]*)\}/);
  assert.ok(rule, "regra unificada de botao desabilitado");
  assert.match(rule[1], /opacity:\s*1\b/);
  assert.match(rule[1], /background:\s*var\(--bg-deep\)/);
  assert.match(rule[1], /color:\s*var\(--muted\)/);
  const t = readTokens();
  assert.ok(tokenRatio(t, "--muted", "--bg-deep") >= 4.5, "muted sobre bg-deep");
  assert.doesNotMatch(css, /\.btn(--\w+)?:disabled\s*\{[^}]*opacity:\s*0?\.\d/);
});

test("SPEC-345 P3-1: nenhum estado desabilitado usa opacity < 1 (exceto a face da carta, que tem motivo escrito)", async () => {
  const { readFileSync } = await import("node:fs");
  const bad = [];
  for (const f of ["../src/styles.css", "../src/workspace.css"]) {
    readFileSync(new URL(f, import.meta.url), "utf8").split("\n").forEach((line, i) => {
      if (/(:disabled|\[aria-disabled)/.test(line) && /opacity:\s*0?\.\d/.test(line) && !/\.combat-card/.test(line)) bad.push(`${f}:${i + 1}`);
    });
  }
  assert.deepEqual(bad, []);
  const t = readTokens();
  assert.ok(tokenRatio(t, "--muted", "--bg-deep") >= 4.5);
});
