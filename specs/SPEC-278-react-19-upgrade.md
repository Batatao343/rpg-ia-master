# SPEC-278 — react-19-upgrade

> **Status:** `approved` (decisão do dono, 19/10: o teto de 5 % de bundle da SPEC-276 NÃO vale para o React 19; o crescimento é aceito)
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Depende de:** SPEC-276 (`done`, Etapa 4 bloqueada pela R4)
> **Desbloqueia:** PRs Dependabot #40/#41 ficam obsoletos (fechar)

---

## 1. Contexto & Objetivo

A SPEC-276 (§8, Etapa 4) bloqueou o React 19 porque o bundle crescia +15,7 % bruto / +12,1 % gzip, acima do teto de 5 %. O dono decidiu em 19/10 que esse teto não se aplica ao React 19 (o `react-dom` 19 é ~79 kB maior minificado e não há corte razoável). Esta spec executa a atualização isolada: `react` + `react-dom` 19 juntos, com `@types/react` e `@types/react-dom`.

## 2. Requisitos

- **R1** — `react` e `react-dom` em 19.3.1 (mesma versão), tipos 19.3.0.
- **R2** — Nenhuma API removida do React 19 em uso (`defaultProps` em função, `propTypes`, string refs, `ReactDOM.render`, `findDOMNode`, `react-dom/test-utils`); `forwardRef` segue suportado e fica.
- **R3** — `npm run build`, `npm run typecheck` (0 erros), `npm test`, `npm audit` (0) verdes; Playwright Chromium completo sem regressão contra a `main`.
- **R4** — Bundle antes/depois registrado (§8). Sem teto de crescimento, por decisão do dono.

### Fora de escopo
TypeScript 7 (bloqueado na 276), code splitting, migração de `forwardRef` para ref-como-prop.

## 3. Design técnico

- `web/package.json`/`package-lock.json`: react/react-dom 19.3.1; @types 19.3.0.
- `web/src/workspace/useModalFocus.ts`: `ref: RefObject<HTMLElement | null>` (em 19, `useRef<T>(null)` devolve `RefObject<T | null>`).
- `motion` ^12.42 já é compatível com React 19 (peer `^18 || ^19`); sem mudança.

## 4. Plano

1. `npm i react@19.3.1 react-dom@19.3.1` e `npm i -D @types/react@19.3.0 @types/react-dom@19.3.0`.
2. Corrigir os 3 erros de tipo (modais) pela assinatura de `useModalFocus`.
3. Verificar build/typecheck/test/audit/lint/Playwright.

## 5. Critérios de aceite

- [x] `npm run build` verde
- [x] `npm run typecheck` 0 erros; `typecheck:e2e` 4 (= SPEC-276, sem piora); `lint` 93 (= main)
- [x] `npm test` 147/147
- [x] `npm audit` 0
- [x] Playwright Chromium completo sem regressão (§8)
- [ ] `uv run pytest` completo (§8)
- [ ] Revisão independente Opus em `handoffs/SPEC-278-review.md`

## 6. Smoke
Sem LLM: só toolchain do cliente; o smoke é o Playwright contra o build.

## 7. Riscos & compatibilidade
- Saves/API inalterados (só `web/`).
- Rollback: `git revert` + `npm ci`.

## 8. Execução (registro)

Bundle (soma de `.js`/`.css` em `web/dist/assets`, bruto / gzip -9), baseline = `main` `f8deeba`:

| | bruto | gzip |
|---|---|---|
| React 18.3 | 622 832 B | 181 057 B |
| React 19.3.1 | 702 005 B (+12,7 %) | 203 668 B (+12,5 %) |

Crescimento aceito pelo dono. Única mudança de código: `useModalFocus`. Nenhuma API removida em uso.

Playwright `CI=1 --project=chromium`: 181 passed, 35 skipped (opt-in), 1 failed (`account-lifecycle` "export requires reauth...", polling por tempo sob carga). O arquivo isolado passa 9/9 tanto no React 18 (`main`) quanto no React 19 -> flake de timing sob carga, não regressão.
