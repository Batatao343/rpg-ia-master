# SPEC-396 — revisão (independent-review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** spec-reviewer (Opus/Sonnet 5.5, independente) · **Data:** 2026-11-05 · **Commit revisado:** `36b8b542` (base `0461d6cb`)

## Escopo

`0461d6cb..HEAD` (282df03b red, 36b8b542 fix): 8 componentes web, `styles.css`, e2e novo, 4 testes editados, bump axe/typescript-eslint/vite. Fora: backend, evals protegidos (nenhum tocado).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | web/src/styles.css:1231 | `.sr-inline { font-size:0 }` entra na árvore de acessibilidade no Chromium (provado pelo e2e: nomes com sufixo), mas é o padrão com histórico de risco: WebKit/VoiceOver e algumas versões do TalkBack/JAWS podem ignorar ou não anunciar texto de tamanho zero; não há teste em AT real (a spec previa o smoke §6.2, ainda não feito). Também é copiado/pesquisado (Ctrl+F) e some do texto de tradutor. | Manter, mas registrar como follow-up o smoke com VoiceOver/TalkBack antes do release. Alternativa concreta se falhar: `.sr-inline{display:inline-block;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);vertical-align:top}` (sem `position:absolute`), ou, para os poucos casos de prefixo/sufixo curtos, `aria-label` no botão SOMENTE onde o texto visível é prefixo do nome (axe passa quando o nome começa com o texto visível) — o que cobre CardHand/Hand/DeckCard sem texto oculto. |
| P2-2 | P2 | web/src/components/combat/PlayQueue.tsx:70 | O nome da fila perdeu o sufixo `. Abrir/Fechar opções`. Estado continua em `aria-expanded`, então é aceitável, mas contradiz "nomes preservados". | Documentar na spec como mudança consciente (aria-expanded cobre). |
| P3-1 | P3 | web/src/components/combat/Hand.tsx:97 | Nome do descarte passou de `Descartar X por N de Fôlego` para `Descartar (N Fôlego): X` — mudança de fraseado (declarada). Aceitável. | Nenhuma. |
| P3-2 | P3 | web/src/components/PlayScreen.tsx:117 | `Encerrar sessão` (texto visível, antes `Sair`) mais longo na topbar. Não verifiquei 320 px: o e2e novo roda em 1440 e 390; a topbar desktop não está no menu ⋯ abaixo de 390? Os specs de overflow a 320 em `critical-journeys.spec.ts` (linhas 272/422/683) não foram rodados por mim. | Rodar `critical-journeys.spec.ts` nos viewports 320 antes do pouso (`--workers=2 -g 320`) ou conferir `wrap` da `.topbar`. |
| P3-3 | P3 | specs/SPEC-396-*.md | Dúvida 2 (`sr-only` dentro do botão) marcada "não medida". O problema do espaço do Playwright com `.sr-only` é plausível (elemento `position:absolute` é blockificado, e o cálculo de nome do Playwright/Chromium insere espaço em volta de não-inline), mas não foi provado. | Opcional: provar com 1 teste, já que muda a decisão P2-1. |

## Respostas às perguntas do coordenador

1. `font-size:0`: funciona em Chromium/NVDA/JAWS(Chrome) em geral; risco real e não medido em VoiceOver/TalkBack (P2-1). O problema de espaço do `.sr-only` é real em Playwright (display não-inline => espaço) e também no cálculo de nome do Chromium; não é invenção do teste.
2. Nomes conferidos componente a componente no diff: CardHand, Hand, TargetChip, DeckCard, SupportCode, PlayMenu, PlayScreen preservam o nome; PlayQueue perde `. Abrir/Fechar opções` (P2-2); Descartar muda fraseado (P3-1). `aria-hidden` está só em filhos, nunca no elemento focável. Em TargetChip, sem `aim` nada vira `aria-hidden` (chip não-botão intacto).
3. Asserts editados: seguiram o markup, sem enfraquecer. `toHaveAttribute("aria-label")` -> `toHaveAccessibleName` é, na prática, mais forte (mede o nome real). Os `.mjs` trocaram `aria-label=` por `doesNotMatch aria-label` + match do markup exato com `sr-inline`; o teste novo de DeckCard valida os ids do `aria-describedby`. Regex do `deck-components` ganhou `(<span class="sr-inline">...)?` opcional: levemente mais frouxo, aceitável porque o e2e cobre o nome real.
4. Bump: `package.json` mudou só `@axe-core/playwright` ^4.14.0, `typescript-eslint` ^8.72.1, `vite` ^8.3.5; `overrides` (xcode/uuid, glob, minimatch) intactos. O lockfile tem também bumps transitivos esperados (axe-core 4.10.3->4.14.0, rolldown/oxc 1.2.14->1.2.16, 0.154->0.156, postcss 8.5.32) vindos do vite; coerente com o bump, sem pacotes novos. `tests/test_eval_frontend.py` atualizado ao pin.
5. 320 px: não verificado (P3-2).

## Correções aplicadas

Nenhuma (revisor não edita código).

## Pendências

- P2-1: smoke §6.2 com leitor de tela (VoiceOver iOS/TalkBack) antes de release; dono: coordenador/dono.
- P3-2: rodar specs de overflow a 320 px no pouso.

## Comandos rodados

```text
cd web && npm test → 315 pass, 0 fail
npx tsc --noEmit; npm run lint → sem erros
npx playwright test e2e/a11y-label-in-name.spec.ts e2e/effects.spec.ts --workers=2 → 97 passed, 10 skipped (0 falha)
```
