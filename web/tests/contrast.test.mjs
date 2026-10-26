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
