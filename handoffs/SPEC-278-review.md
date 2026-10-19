# SPEC-278 — revisão independente (review)

> **Veredito:** `APPROVED`
> **Revisor:** Claude Opus 5.5 (revisor independente) · **Data:** 2026-10-19 · **Commit revisado:** `25453f0`

## Escopo

Branch `spec-278`, `git diff main...spec-278`: `web/package.json`, `web/package-lock.json`,
`web/src/workspace/useModalFocus.ts` e a própria spec. O teto de 5 % de bundle ficou fora
da revisão por decisão do dono (crescimento de +12,7 % bruto / +12,5 % gzip aceito).
O foco foi o comportamento em runtime do React 19, os avisos de console em dev que
derrubariam o guard dos e2e e o flake de `account-lifecycle`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `web/e2e/account-lifecycle.spec.ts:171-196` | Flake que já existia antes (não é regressão). `initialPolls` é lido logo após o 1º poll de checkout, mas o app consulta o pedido de novo a cada 5 s (`AccountScreen.tsx:174`). Na suíte completa, o trecho axe + export + preenchimento pode passar de 5 s antes do início da exclusão. Aí sai um poll legítimo a mais e o teste vê `3 != 2`. Isolado, o arquivo passa. | Follow-up fora desta spec: ler `initialPolls` imediatamente antes de clicar em "Excluir conta" (ou após `deleteStarted`), em vez de logo depois do `goto`. |

Verificações sem achado:

- **APIs removidas (R2):** varredura em `web/src` não achou `defaultProps`, `propTypes`,
  `findDOMNode`, `ReactDOM.render`, `react-dom/test-utils`, `hydrate`, `element.ref`,
  `useRef()` sem argumento nem `<form action>`. O boot já usa `createRoot`.
- **StrictMode do React 19:** o React 19 simula detach/attach de ref callback no mount.
  As 4 ref callbacks (`DossierBrowser`, `ContextSurface`, `RovingTablist`, `MapTab`)
  tratam `null` e usam corpo em bloco, sem retorno implícito que o React 19 tomaria
  por cleanup. O efeito de poll do checkout faz cleanup com abort e `clearTimeout`,
  então o efeito duplo segue seguro, como já era no 18.
- **`useModalFocus`:** a assinatura `RefObject<HTMLElement | null>` está correta para o
  `useRef<T>(null)` do 19. O hook só lê `ref.current` com guarda.
- **`motion` 12.42.0:** o peer é `react ^18 || ^19`. Os e2e de efeitos rodaram verdes
  na suíte completa.
- **Console em dev:** a suíte Chromium completa roda contra o dev server do Vite, que
  repassa o console do cliente. O único aviso visto foi o `console.warn` do motion
  sobre reduced motion, que já existia e não é `error`. Nenhum aviso do React
  (`ref`, `key`, `act`, hydration) e nenhum `console.error` fora das allowlists
  das fixtures.

## Correções aplicadas

Nenhuma no código. Mudanças da revisão: status da spec → `done` e critérios marcados.

## Pendências

- P2-1: endurecer o teste de polling em `account-lifecycle.spec.ts`. Dono: próxima
  spec de higiene de e2e. Não bloqueia: o flake já existia (o ESTADO_ATUAL já
  registrava falhas iguais de `account-lifecycle` na `main`, SPEC-216).

## Comandos rodados

```text
CI=1 npx playwright test e2e/account-lifecycle.spec.ts --project=chromium (3x) → 9/9, 9/9, 9/9
CI=1 npx playwright test --project=chromium → 181 passed, 35 skipped, 1 failed (P2-1, polling de 5 s sob carga)
npm run typecheck → 0 erros
npm test → 147 pass, 0 fail
npm audit → 0 vulnerabilities
npm run build → verde
py.sh -m pytest tests/test_checkout_integrity.py tests/test_eval_frontend.py → 12 passed
```

Observação: a suíte Playwright completa regrava 4 PNGs de `docs/spec209/evidence/`.
Eles foram restaurados com `git checkout` e não entram no commit.
