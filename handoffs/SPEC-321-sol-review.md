# SPEC-321 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED` (1 P1 trivial; o resto são P2/follow-ups)
> **Revisor:** Opus / papel Sol (spec-reviewer) · **Data:** 2026-10-25 · **Commit revisado:** `95e56c7d`

## Escopo

Branch `spec-321`, `git diff main...spec-321` (1 commit, 39 arquivos, só `web/` + a spec). Lidos:
`App.tsx`, `PlayMenu.tsx` (novo), `PlayScreen.tsx`, `Workspace.tsx`, `ChatSurface.tsx`, `StoryLog.tsx`,
`SceneArtwork.tsx`, `CharacterTab.tsx`, `ContextSurface.tsx`, `composerKeys.ts`, `useComposerHeight.ts`,
`useIsCompact.ts`, `useModalFocus.ts`, `mobileSurface.ts`, `styles.css`, `workspace.css`, `index.html`,
`capacitor.config.ts`, `styles.xml` (Android), os e2e alterados/novos e os testes unitários. Também conferi
a máquina de estados da SPEC-320 (`turnWait.ts`, `handleAction`/`retryTurn`/`handleNew`/`discardPending`)
e o backend de `art_offers` (`api.py`). Fora do escopo: Playwright e build não rodados (RAM); smoke real
(§6) não feito.

Por foco:
1. **Cabeça única e menu.** OK. Em mobile o `header.topbar` não renderiza; `.ws-mhead` tem 52 px +
   safe-area-top com local, superfície, stats, chip de nível e "⋯". `PlayMenu` usa `useModalFocus`
   (foco inicial, Tab preso, Esc, devolução do foco ao gatilho), `aria-haspopup="dialog"` e `aria-modal`,
   e traz Conta (com saldo), Nova jornada/Reiniciar, Sair e a marca Laboratório. Em ≥ 900 px os controles
   continuam inline. `useIsCompact` e `useViewportWidth` usam o mesmo breakpoint (`innerWidth < 900`),
   então nunca somem os dois conjuntos ao mesmo tempo. Nenhuma ação se perdeu: "Ficha" vira a aba
   Personagem da tabbar e o combate tem a tabbar e "Ir para o combate".
2. **Confirmação de "Nova jornada".** OK. `confirmLeave = !!pending || narrated || failed-after-narration`
   (`App.tsx:885`). O botão continua desabilitado com `busy`, e `narrated` só existe com `busy=true`, então
   esse termo nunca conta; é inofensivo. A confirmação cobre ação pendente e falha depois da narração.
   `handleNew` não apaga o pending do `localStorage`, então reabrir a jornada oferece "Consultar /
   retomar": nenhum turno se perde (ver P2-2 sobre o texto).
3. **Ofertas de imagem.** OK no fluxo pago: o chip e "Cotar retrato" só chamam `openImageQuote`
   (cotação), e a compra continua exigindo o `ImageQuoteDialog` com "Confirmar". Ficam desabilitados com
   `busy || imageBusy`. Regressão de gate em P2-1.
4. **Compositor.** OK. `shouldSubmitOnKey` cobre Shift/Alt/Ctrl/Meta, `isComposing` e `keyCode 229`; o
   `submit` respeita `busy`/`blocked`; `enterKeyHint="send"`; a voz continua via `setInput`, e a altura é
   recalculada em `[input]`. O fallback de foco do `useModalFocus` passou de `input[...]` para
   `[aria-label="Sua ação"]`. Ressalva sobre Android em P2-3.
5. **Ancoragem.** OK. `--composer-h` vem de `ResizeObserver` no form; o `TurnStatus` está dentro dele,
   então a linha "Tentar de novo" é contada. `--tabbar-h` só existe em < 900 px. Escala de z-index:
   `--z-toast: 45` < banner < overlay. `viewport-fit=cover` + `theme-color #080c10`; `env()` aplicado em
   `.ws-mhead` (top/left/right), `.mtabbar` (bottom/left/right) e `.playmenu` (bottom). StatusBar DARK
   no Capacitor + `statusBarColor` no tema Android: o desvio está documentado.
6. **Unificação com a SPEC-320.** OK. Em `failed-after-narration` a barra pendente só oferece
   "Descartar", e o retry fica na linha de status. Depois de recarregar, `stage=idle` e "Consultar /
   retomar" volta. Não há beco sem saída: numa superfície fora da Crônica, no mobile, basta voltar a ela.
7. **e2e.** `web/e2e/contracts` não existe nesta árvore (está listado em `evals/protected-paths.txt:13`);
   nada protegido foi tocado e `evals/` está intacto. O helper `openFicha` está correto. Um spec antigo
   quebra (P1-1).
8. **Arte de cena.** OK. Na arte, `flex-shrink: 0` + `.story { flex-basis: 0 }`; ao recolher, a faixa
   fica em 72 px por troca de classe, sem animar altura, então funciona com reduced-motion. "Ampliar" some
   quando recolhida, e um toggle de 44 px cobre a faixa. Com altura ≤ 420 px a arte continua oculta (M03).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `web/e2e/voice-input.spec.ts:145` | `getByRole("button", { name: "Nova", exact: true })`. O botão agora se chama "Nova jornada" (`PlayScreen.tsx`, topbar desktop), então o passo `unmount` do teste SPEC-187 não acha o botão e estoura o tempo. Este spec ficou fora do diff e do comando de verificação da §4. | Trocar por `{ name: "Nova jornada" }`. Sem pending, `confirmLeave=false` e `handleNew` desmonta direto, como antes. Rodar `npm run test:e2e -- voice-input image-quote`. Em `image-quote.spec.ts:137`, `name: "Nova"` sem `exact` ainda casa por substring; deixar explícito também. |
| P2-1 | P2 | `web/src/workspace/ChatSurface.tsx:103`, `web/src/components/StoryLog.tsx:67` | Regressão de gate. A barra antiga escondia as ofertas de cena/NPC com `combat_simulation.enabled` ou `game_over`. O chip novo usa `data.art_offers` sem esse gate, e o backend não filtra (`api.py:2072`; até 32 ofertas persistem). No memorial e no laboratório aparecem "Cotar cena épica/NPC" clicáveis. A cotação ainda exige confirmação, então não há cobrança acidental. | Passar `offers` só quando `!data.combat_simulation?.enabled && !data.game_over`, igual ao `artPanel`. |
| P2-2 | P2 | `web/src/components/PlayMenu.tsx:79` | O texto diz "a ação pendente será abandonada", mas `handleNew` só zera o estado em memória (`setPending(null)`): o pending continua no `localStorage` e volta como "Consultar / retomar" ao reabrir a jornada. Esse comportamento é o mais seguro (nenhum turno se perde); a cópia é que está errada. | Trocar por algo como "A ação pendente fica guardada nesta jornada; você pode retomá-la ao voltar." Não apagar o pending. |
| P2-3 | P2 | `web/src/workspace/composerKeys.ts:16` | No Android (Gboard, autocorreção pt-BR) a última palavra costuma estar em composição. O Enter chega como `229`/`isComposing`, não envia e insere um `\n`, que faz o textarea crescer; só o 2º Enter envia (o `trim` limpa o texto). Não é perda de dado, mas fica contra o `enterKeyHint="send"`. Só aparece em aparelho real, e o MockLLM/Playwright não pega. | No smoke §6.5, testar num Android real. Se confirmar, tratar `beforeinput` com `inputType === "insertLineBreak"` em `pointer: coarse` (cancelar e enviar depois do `compositionend`), ou aceitar e registrar. |
| P2-4 | P2 | `web/src/workspace/ChatSurface.tsx:47,53` | `scrolled` não é reiniciado ao mudar de local (só `entry` e `override` são por `sceneKey`). Depois que o jogador rola uma vez, a arte de todo local novo já chega recolhida, contra "depois do 1º beat num mesmo local". | Reiniciar `scrolled` junto com `entry` quando `sceneKey` muda (o mesmo `if` do render). |
| P2-5 | P2 | `web/src/components/StoryLog.tsx:95,109,113` | Os chips de oferta ficam dentro do `role="log" aria-live="polite"`: cada oferta nova é lida pelo leitor de tela como narração ("Cotar cena épica"). | Envolver a linha em `aria-live="off"` ou renderizá-la fora do `.log`, mantendo a posição visual. |
| P2-6 | P2 | `web/e2e/critical-journeys.spec.ts:279`, `web/e2e/mobile-single-pane.spec.ts` (M08) | No mobile, o teste agora só afirma que "Encerrar sessão" sumiu da tela. M08 abre o menu mas só checa "Nova jornada". Nada prova que Conta e Sair existem e funcionam no menu ⋯. | Em M08 (ou no ramo `compact`), abrir o menu e afirmar "Conta · … Estilhas" e "Encerrar sessão" (com auth). |
| P2-7 | P2 | `web/src/workspace.css` (`.ws-mhead .ws-stat--fight { display:none }`), `PlayScreen.tsx` | No mobile a cabeça perdeu "⚔ Combate" e o round. Restam o véu, a tabbar e "Ir para o combate", então não há perda funcional, só de leitura rápida. | Opcional (SPEC-322): um glifo de combate na cabeça. |

Notas sem ação: o termo `narrated` em `confirmLeave` nunca dispara (o botão fica desabilitado com
`busy`); dá para tirar ou comentar. Um rascunho multilinha restaurado com o compositor oculto
(`display:none` mede 0) mostra uma linha até a próxima edição; o `min-height` evita o colapso.

## Correções aplicadas

(nenhuma ainda; o executor preenche por commit)

## Pendências

- P1-1 antes do pouso (correção de uma linha).
- P2-1 e P2-2: recomendo corrigir na mesma branch, são baratos.
- P2-3: validar no smoke §6.5 (Android real); se confirmar, follow-up na SPEC-198 ou na 322.
- P2-4 a P2-7: follow-ups aceitáveis (SPEC-322 / próxima revisão de UX mobile).
- Critério de aceite em aberto: `npm test` + e2e do escopo + `uv run pytest` verdes (o coordenador roda
  no pouso, incluindo `voice-input`).

## Comandos rodados

```text
git diff main...HEAD --stat                      → 39 arquivos, +855/−231, só web/ + spec
npm test (web/)                                  → 175 pass, 0 fail
npx tsc --noEmit -p . (web/)                     → sem erros
npx tsc --noEmit -p tsconfig.e2e.json (web/)     → sem erros (o P1-1 é em runtime: nome do botão)
```
