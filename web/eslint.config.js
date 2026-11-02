// ESLint flat config (workspace #10). Bloqueante no CI (SPEC-284): zero achados.
import js from "@eslint/js";
import globals from "globals";
import { createRequire } from "node:module";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

// SPEC-365: minimatch>=11 (sem os advisories) exporta `{ minimatch, Minimatch }`; o
// eslint-plugin-jsx-a11y@6 ainda chama `require("minimatch")(nome, padrao)` (API do v3).
// Torna o export callable ANTES de carregar o plugin (import dinamico abaixo).
const require = createRequire(import.meta.url);
const mm = require("minimatch");
if (typeof mm !== "function") {
  require.cache[require.resolve("minimatch")].exports = Object.assign(
    (p, pattern, options) => mm.minimatch(p, pattern, options),
    mm,
  );
}
const { default: jsxA11y } = await import("eslint-plugin-jsx-a11y");

export default tseslint.config(
  { ignores: ["dist", "android", "node_modules", "test-results", "playwright-report", "public"] },
  {
    files: ["src/**/*.{ts,tsx}", "e2e/**/*.ts", "tests/**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { ecmaVersion: 2022, globals: { ...globals.browser, ...globals.node } },
    plugins: { "react-hooks": reactHooks, "jsx-a11y": jsxA11y },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.recommended.rules,
    },
  },
);
