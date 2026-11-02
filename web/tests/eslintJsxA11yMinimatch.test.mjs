// SPEC-365: prova que o shim do minimatch>=11 em eslint.config.js mantem as regras do
// jsx-a11y que chamam `require("minimatch")(...)` funcionando (sem TypeError).
import test from "node:test";
import assert from "node:assert/strict";
import { ESLint } from "eslint";
import { fileURLToPath } from "node:url";

const cwd = fileURLToPath(new URL("..", import.meta.url));

test("jsx-a11y label/control rules rodam sem crash e acusam os erros esperados", async () => {
  const eslint = new ESLint({
    cwd,
    overrideConfig: [
      {
        files: ["src/**/*.tsx"],
        rules: {
          "jsx-a11y/label-has-associated-control": "error",
          "jsx-a11y/control-has-associated-label": ["error", { controlComponents: ["Custom*"] }],
        },
      },
    ],
  });
  const code = [
    "export function P() {",
    "  return (",
    "    <div>",
    "      <label><Foo /></label>",
    "      <button><Foo /></button>",
    "      <button><CustomIcon /></button>",
    "    </div>",
    "  );",
    "}",
    "",
  ].join("\n");
  const [res] = await eslint.lintText(code, { filePath: "src/zz_fixture.tsx" });
  const ids = res.messages.map((m) => m.ruleId);
  assert.ok(!res.messages.some((m) => m.fatal), JSON.stringify(res.messages));
  assert.ok(ids.includes("jsx-a11y/label-has-associated-control"), ids.join());
  // so o <button> com CustomIcon (casa "Custom*" via minimatch) acusa; o com <Foo /> passa.
  const ctl = res.messages.filter((m) => m.ruleId === "jsx-a11y/control-has-associated-label");
  assert.equal(ctl.length, 1, ids.join());
  assert.equal(ctl[0].line, 6);
});
