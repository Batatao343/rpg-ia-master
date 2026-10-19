# SPEC-284 — frontend-lint-typecheck-bloqueantes

> **Status:** `done`
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Aprovação:** dono, 19/10/2026 ("autorizou tudo que não exige ação externa dele").
> **Depende de:** workspace #10 (ESLint introduzido não bloqueante) · SPEC-244 (beacon de erro do cliente)
> **Desbloqueia:** gates de frontend sem `continue-on-error`

---

## 1. Contexto & Objetivo

O CI rodava `typecheck:e2e` e `eslint` com `continue-on-error` (4 erros de tsc e 93 achados de
ESLint em 2026-10-19), então regressões de tipagem/a11y/hooks passavam. O objetivo é zerar os
achados com correção real, tornar os dois passos bloqueantes e fechar o follow-up da SPEC-244
(teste de dedupe do beacon de erro).

## 2. Requisitos

- **R1** — `npm run typecheck:e2e` e `npm run lint` (web/) saem com 0 erros e 0 avisos.
- **R2** — Sem desligar regras em massa: `eslint-disable-next-line` só pontual, sempre com `-- motivo`.
- **R3** — `.github/workflows/validate.yml`: os dois passos deixam de ser `continue-on-error`.
- **R4** — Playwright: um erro forçado no cliente gera exatamente 1 `POST /telemetry/client-error`
  (repetições da mesma assinatura dentro da janela de dedupe não geram novo POST).

### Fora de escopo
Reescrever os efeitos de carregamento para derived state/Suspense; `web/e2e/contracts` (protegido).

## 3. Design técnico (o que mudou)

- **tsc e2e:** `.at(-1)` → `.slice(-1)[0]` (lib alvo), `entropy ?? 0`, import `React` não usado.
- **`no-explicit-any`:** tipado de verdade em `androidPlay.ts`, `wav.ts`, `critical-journeys.spec.ts`;
  nos dois arquivos do oráculo vertical (`vertical-journey.spec.ts`, `vertical-support.ts`; payloads
  JSON dinâmicos do servidor real) há um disable de arquivo com motivo.
- **a11y real:** `<label>` sem controle → `span.field__label`; clique redundante nos cards de raça/classe
  removido (o botão `card__select` já cobre o card inteiro via `::after`); `ArtworkDialog` com listener
  nativo de backdrop e sem `autoFocus` (o `showModal` foca o botão); `ImageQuoteDialog` foca "Cancelar" por
  ref; `role="region"` redundante removido; teclas de seta da Arena passaram para o `role="toolbar"`
  interno. Handlers de teclado delegados / regiões roláveis focáveis / splitter ficam com disable pontual
  motivado (padrões WAI-ARIA).
- **react-hooks:** refs "último valor" passam a ser atualizados em `useEffect` (useTypewriter, voice, Turnstile,
  useModalFocus, Workspace); `visited` do Workspace vira state ajustado no render (sem mutar ref);
  `luDismissed` do PlayScreen deriva de `luDismissedKey === pendingKey` (sem efeito); `Date.now()` em
  `useState` lazy; ordem de `useState`/`setState` em `useVoiceInput`. Efeitos de leitura externa que setam
  estado e deps deliberadas ficam com disable pontual motivado (comportamento preservado).
- **CI:** passos sem `continue-on-error`. **Teste:** `web/e2e/client-error-dedupe.spec.ts`.

## 5. Critérios de aceite

- [x] `npm run build`, `typecheck`, `typecheck:e2e` verdes; `npm run lint` 0
- [x] `npm test` 148/148
- [x] Teste de dedupe do beacon verde
- [x] Playwright chromium completo (flakes de carga reportados no hand-back)
- [x] Suíte Python offline (sem mudança de backend)
