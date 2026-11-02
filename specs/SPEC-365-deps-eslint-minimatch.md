# SPEC-365 — deps-eslint-minimatch

> **Status:** `done` (aprovada pelo dono em bloco, "manda bala", 2026-11-02; revisão independente pendente)
> **Criada:** 2026-11-02 · **Atualizada:** 2026-11-02
> **Depende de:** SPEC-225, SPEC-276 (job `npm-audit-full`)
> **Desbloqueia:** CI `npm-audit-full` verde

## 1. Contexto & Objetivo

`npm audit --audit-level=moderate` em `web/` acusava 15 moderate: GHSA-3g3m-2fjr-6pw4
(glob 3.0.0–14.0.1) e GHSA-g3hv-75wg-m249 (minimatch <11.0.1), via eslint@9, @eslint/*,
eslint-plugin-jsx-a11y (minimatch@3), typescript-estree (minimatch@10) e @capacitor/cli→rimraf→glob@13.
Objetivo: audit = 0 sem afrouxar o gate (sem allowlist/ignore/nível menor) e sem migrar TypeScript (PR #42).

## 2. Requisitos

- **R1** — `npm audit --audit-level=moderate` = 0 em `web/`.
- **R2** — lint mantém todas as regras (arquivo de prova com erros: mesmos achados de antes + label/componente sem crash).
- **R3** — typecheck, `npm test`, `npm run build`, `npx cap --version` verdes.

### Fora de escopo
Migrar para eslint 10 (usa minimatch ^10.2.6, ainda vulnerável) ou TypeScript 7.

## 3. Design técnico

- Opção (a) descartada: eslint 10.14 depende de minimatch ^10.2.6 (vulnerável); jsx-a11y 6.10.2 é a última e usa minimatch ^3.
- `web/package.json` `overrides`: `minimatch: ^11.0.1`, `glob: ^14.0.2`.
- minimatch 11 exporta `{ minimatch, Minimatch }` (não é mais função): eslint/@eslint/*/typescript-estree usam só
  `.Minimatch`/`{ minimatch }` (compatíveis), mas `eslint-plugin-jsx-a11y` faz `require("minimatch")(a, b)` e
  quebraria (TypeError) em `label-has-associated-control`. `web/eslint.config.js` torna o export callable (shim via
  `require.cache`) antes de `await import("eslint-plugin-jsx-a11y")`. (Tentativa de shim por `overrides` aninhado com `file:` falhou no npm: vazou para outros pacotes.)

## 4. Plano
1. overrides + lockfile; 2. shim no `eslint.config.js`; 3. verificação abaixo.

## 5. Critérios de aceite

- [x] `npm ci` limpo; `npm audit --audit-level=moderate` = 0
- [x] lint exit 0; arquivo de prova: 7 erros (6 originais + label-has-associated-control), sem crash
- [x] typecheck, `npm test` (290/290), `npm run build`, `npx cap --version` (8.5.3)

## 6. Smoke test com LLM real
N/A (somente tooling de front).

## 7. Riscos & compatibilidade
- Shim depende de `jsx-a11y` resolver o mesmo `minimatch` hoistado em `web/node_modules`; remover quando jsx-a11y suportar minimatch ≥ 11.
- Override de `glob ^14` em rimraf@6 (só `npx cap`/CLI), verificado com `cap --version`.
