# SPEC-324 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-10-26 · **Commit revisado:** `6ab4022d`

## Escopo

Branch `spec-324` (worktree `rpg-spec-324`), `git diff main...HEAD`: 21 arquivos em `web/`
mais a spec. Revisados: `shortcuts.ts`, `ShortcutsSheet.tsx`, `Workspace.tsx`,
`ContextSurface.tsx`, `RovingTablist.tsx`, `ChatSurface.tsx`, `PlayScreen.tsx`, as trocas
de `p`/`h2` para `h3` (Hud, CodexTab, QuestsTab, tabs/*, MapTab), o CSS, os testes novos
(`tests/shortcuts.test.mjs`, `e2e/a11y-headings.spec.ts`) e os e2e adaptados.
Fora do escopo: Playwright e build (não rodados, por instrução), smoke no staging.

Itens conferidos e OK:
- **Um h1 por tela.** O topbar (`!compact`, < 900 px) e a cabeça mobile (`isMobileViewport`,
  < 900 px) usam o mesmo `MOBILE_MAX_VIEWPORT`, então nunca renderizam juntos.
- **h2 por painel.** Fica `sr-only` no desktop, dentro de painéis com `hidden` quando
  inativos. No celular vale o h2 visível da cabeça.
- **Visual dos h3.** `.hud__label` recebe `font-weight: inherit` e mantém a margem
  própria; `.topbar__place` recebe `display: inline; margin: 0`.
- **`matchShortcut`.**
  - Alt sem Ctrl no Windows/Linux, o que rejeita AltGr (= Ctrl+Alt) no ABNT2.
  - Ctrl+Option no macOS; Meta e Shift são rejeitados.
  - Casa por `code` (DigitN), então funciona em AZERTY e ABNT2. Numpad não conflita com Alt-codes.
  - Em campo de texto só Alt+1 dispara; `?` no compositor é texto (unit + e2e).
  - `preventDefault` só quando há match.
- **`aria-keyshortcuts`** com sintaxe válida (`Alt+6`, `Control+Alt+6`, `Alt+ArrowLeft`,
  `Alt+\`). O `title` traz a tecla.
- **Folha "?".** `useModalFocus` prende o foco, Esc fecha e devolve o foco. Com a folha
  aberta, `modalOpen()` bloqueia os outros atalhos.
- **Skip link.** É o 1º filho de `.play`, aparece no foco (`transform` + outline) e leva
  ao compositor no desktop.
- **e2e.** Só `workspace-shell` e `critical-journeys.spec.ts` foram editados, e a troca
  Ctrl→Alt é legítima. `e2e/contracts/`, `critical-journeys.yaml` e `evals/` não foram tocados.
- **SPEC-320..323.** A única mudança no compositor é o `id="composer"`. O `TurnStatus`
  (live region), o menu ⋯ (`useModalFocus`) e a marginália seguem intactos. A folha reusa
  `.playmenu__scrim` (centralizada ≥ 900 px).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `web/src/combat/Arena.tsx:80` (renderizado em `web/src/workspace/tabs/CombateTab.tsx:204`) | Em combate ativo, a aba Combate pula nível: o h2 do painel (sr-only no desktop, ou o h2 da cabeça no celular) é seguido de `<h4>` com o nome da zona, sem nenhum h3 antes. Isso viola R1 ("nenhum nível é pulado") e o critério marcado `[x]` "axe heading-order limpo". O e2e `a11y-headings` só varre a aba sem combate, por isso não pega. | Trocar `h4` por `h3` em `Arena` (com classe e reset de estilo para manter o visual) ou inserir um `h3` "Arena" (`sr-only` se preciso). Estender o e2e com uma fixture em combate (há saves de combate nos e2e de arena) para rodar `assertNoSkips` + axe `heading-order`. |
| P2-1 | P2 | `web/src/workspace/Workspace.tsx:115-118` + `:271` | No celular, com uma superfície ≠ chat, o skip link e o Alt+1 não chegam ao compositor. `focusComposer` faz o dispatch de `close_context` e chama `focus()` na hora, mas o compositor ainda está com `display:none` (`.ws-composer.is-offsurface`), então o `focus()` não tem efeito. Depois o efeito da linha 271 foca o h2 "Crônica". | Adiar o foco para depois do commit (flag + `useEffect`, ou `requestAnimationFrame`) e fazer o efeito da linha 271 respeitar a intenção de focar o compositor. e2e mobile: abrir Personagem, Tab, Enter no skip link, compositor focado. |
| P2-2 | P2 | `web/src/workspace/shortcuts.ts:45` | `split` casa por `code === "Backslash"`. No ABNT2 (público principal) a tecla com a legenda `\` é `IntlBackslash`, e `Backslash` é a tecla `] }`. A folha e o `title` mostram "Alt+\\", mas no pt-BR a tecla real é Alt+]. | Aceitar também `e.key === "\\"` (ou `code === "IntlBackslash"`) e cobrir no unit test. |
| P2-3 | P2 | `web/src/workspace/Workspace.tsx:193-195` | Composição de IME não é ignorada: falta `event.isComposing \|\| event.keyCode === 229`. O risco real é baixo, porque em campo de texto só Alt+1 passa, mas o pedido do coordenador era ignorar IME explicitamente. | Retornar cedo em `onKey` quando `isComposing`. |
| P2-4 | P2 | `web/src/workspace/shortcuts.ts:38-46` | Risco de plataforma a confirmar no smoke. No Linux, Chrome e Firefox usam Alt+1…8 para trocar de aba do navegador, o mesmo tipo de conflito que motivou a spec. No macOS, Ctrl+Option é o modificador do VoiceOver (VO), então usuário de VO pode ter o atalho interceptado. Os dois casos são decisão do dono (D1), não bug. | Incluir Linux (Firefox) e macOS com VoiceOver no smoke §6. Se conflitar, registrar como follow-up (ex.: sequência estilo Gmail como alternativa, prevista em D1). |
| P2-5 | P2 | `web/src/workspace/shortcuts.ts:87` | `ariaShortcut("help")` devolve `"Shift+/"`, que depende do layout (no AZERTY o `?` é Shift+,). Hoje nenhum elemento usa esse valor. | Devolver `"?"` ou remover. Se um botão "Atalhos" for criado, use `aria-keyshortcuts="?"`. |
| P2-6 | P2 | `web/src/workspace/Workspace.tsx:197` | Alt+←/→ continua sendo voltar/avançar do navegador quando o foco está fora de `.play` (ex.: `body` depois de clicar em área não focável), e aí a página sai do jogo. Isso não é regressão: o comportamento já existia e o gate `.play` foi preservado. | Opcional: tratar `document.body` como "dentro" quando a tela de jogo está montada. Registrar como follow-up. |
| P2-7 | P2 | spec §5 / Histórico (5) | O diff de screenshot ≤ 1 % (R2) não foi automatizado e foi trocado por computed style de um h3. Isso aparece como desvio, mas o critério está marcado `[x]`. | Manter o desvio documentado e fazer a comparação visual no smoke §6 antes de `done`. |

Notas sem achado: `CardHand` mantém um `h2` "Sua mão" dentro do painel Combate. Fica
como irmão do h2 do painel, o que é válido para `heading-order` (não pula nível).

## Correções aplicadas

Nenhuma até aqui (o revisor não edita produto).

## Pendências

- P1-1 é obrigatório antes do pouso.
- P2-1 a P2-3: corrigir no mesmo ciclo, se for barato; senão, follow-up na spec.
- P2-4 a P2-7: smoke §6 e follow-ups (dono: coordenador).

## Comandos rodados

```text
git diff main...HEAD --stat                 → 21 arquivos, +429/-86; nada em e2e/contracts nem evals/
cd web && npm test                          → 211 pass, 0 fail
cd web && npx tsc --noEmit                  → exit 0
cd web && npm run lint                      → exit 0; 1 warning pré-existente (src/hooks/useTypewriter.ts:65, fora do diff); 13 pass
```
