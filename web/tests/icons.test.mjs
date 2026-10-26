// SPEC-322 R9: ícones só da família vendored, sem emoji em strings da UI, atribuição CC BY presente.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src", import.meta.url));
const walk = (d, out = []) => { for (const n of readdirSync(d)) { const p = `${d}/${n}`; statSync(p).isDirectory() ? walk(p, out) : /\.tsx?$/.test(p) && out.push(p); } return out; };

test("zero emoji (Extended_Pictographic) em código de UI", () => {
  const bad = [];
  for (const f of walk(SRC)) {
    readFileSync(f, "utf8").split("\n").forEach((l, i) => {
      if (/^\s*(\/\/|\*|\/\*)/.test(l)) return; // comentários
      if (/\p{Extended_Pictographic}/u.test(l.replace(/[☀-➿⌀-⏿⬀-⯿]/g, ""))) bad.push(`${f.slice(SRC.length + 1)}:${i + 1}`);
    });
  }
  assert.deepEqual(bad, []);
});

test("todo ícone game-icons está creditado em NOTICE e na página de créditos", () => {
  const icons = readFileSync(`${SRC}/design/icons.tsx`, "utf8");
  const notice = readFileSync(new URL("../../NOTICE", import.meta.url), "utf8");
  const credits = readFileSync(new URL("../legal/credits.md", import.meta.url), "utf8");
  const gi = [...icons.matchAll(/src: "game-icons\/([a-z-]+)"/g)].map((m) => m[1]);
  assert.ok(gi.length > 0);
  for (const n of gi) assert.ok(notice.includes(n), `NOTICE sem ${n}`);
  assert.match(credits, /CC BY 3\.0/);
  assert.match(credits, /Lorc/);
  assert.match(credits, /MIT/);
});
