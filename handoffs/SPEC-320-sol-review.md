# SPEC-320 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Sol (Opus, revisor independente; não escreveu o código) · **Data:** 2026-10-25 · **Commit revisado:** `f957fe13`

## Escopo

Branch `spec-320` (`git diff main...spec-320`, 1 commit, 23 arquivos, só `web/` + cabeçalho da spec).
Revisei contra a SPEC-320 (R1–R13, §3 e desvios) e o contrato SSE da SPEC-316 §3.1:
`App.tsx` (máquina do turno, `retryTurn`, `narrative_shown`, `replace`), `api.ts`/`http.ts`,
`turnWait.ts`, `useTurnClock.ts`, `useTypewriter.ts`, `revealHtml.ts`, `StoryLog.tsx`, `Banner.tsx`,
`TurnStatus.tsx`, `ChatSurface.tsx`, `PlayScreen.tsx`, `Workspace.tsx`, `OnboardingHint.tsx`,
`effects.registry.ts`, `styles.css`, `e2e/effects.spec.ts`, `e2e/turn-wait.spec.ts` e os testes unitários
novos/alterados. Fora do escopo: Playwright, build e screenshots (são do coordenador), backend.

O que está certo: o input fica travado até o `state` nos dois modos (`busy` só cai no `finally`).
`replace` vai para `onReplace` e troca o texto inteiro (`replaceStreamText`); nunca é anexado.
`narrative_shown` mantém o texto com "não salvo", preserva o pending e não cai no POST automático.
O retry depois da falha reaproveita o mesmo `operation_id` e o mesmo payload (`preparePending` devolve
o existente). O "Tentar de novo" com turno em voo consulta `getOperation` e não re-POSTa. O typewriter
é determinístico, tem teto de 2,5 s, dá para pular, respeita `useEffectsEnabled()` e o `mdLite` é
memoizado por texto. O banner de erro persiste, o ✕ tem ≥ 44 px e, na tela de jogo, fica no fluxo
abaixo da topbar. O `onDone` é estável e o timer é chaveado por `state`. O botão perdeu o `aria-label` e
o nome acessível passou a ser o texto visível. A capitular só aparece com `data-opening`. A edição em
`web/e2e/effects.spec.ts` é legítima: o arquivo não está em `evals/protected-paths.txt` (só
`web/e2e/contracts` está) e nenhum contrato protegido assere "Enviando…" ou `.thinking`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `web/src/App.tsx:585`, `:621` (com `:656-661`) | Corrida criada pelo novo `retryTurn`. Quando o "Tentar de novo" recupera um turno `completed` com o SSE ainda aberto, ele incrementa `turnToken` e libera `busy`. Se o jogador envia a próxima ação, um **novo** pending é gravado. Quando o fluxo antigo resolve, ele chama `clearPending(user, gid)` **antes** do `if (!active()) return`, e a chave é só dono+jogo, então apaga o pending do turno novo. O mesmo vale para o `clearPending` do POST de fallback (`:621`) se a invalidação cair durante o POST. Efeito: o turno novo perde a identidade durável (recarregar no meio não retoma) e, se ele falhar com `narrative_shown`, o "Tentar de novo" vira botão morto (`retryTurn` sai em `!pending`, `:649`). | Só limpar se o pending gravado ainda for desta operação: `clearPendingIf(user, gid, operation.operation_id)`, ou `loadPending(...)?.operation_id === operation.operation_id` antes de `clearPending`. Opcional: `AbortController` no `sendActionStream` antigo ao recuperar. Teste unitário/e2e: recuperar via retry → enviar ação nova → soltar o stream antigo → o pending novo continua lá. |
| P1-2 | P1 | `web/e2e/turn-wait.spec.ts` (ausente); `web/e2e/effects.spec.ts:111`; spec §5 itens 3 e 9 | Os caminhos com a SPEC-316 `on` não têm nenhum teste da fiação no `App`. Ficaram sem cobertura: o selo "registrando…" entre `narrative done:true` e `state` com o envio travado; `replace` substituindo o texto (e não anexando); erro com `narrative_shown` → "não salvo" + retry com o mesmo `action_id` e **um** POST/stream a mais, nunca dois. O rótulo "Aguardando o narrador" depois do ack e o nome "Lutar" em combate também não são verificados: a fixture segura a resposta inteira, então nunca há ack, e o regex `/^(Agir\|Aguardando o narrador)$/` passa só com "Agir". Só a função pura `nextStage` está testada. Como a medição da 316 em staging espera esta spec, esses caminhos são exatamente o que vai ligar. | Uma fixture SSE estilo 316 em `fixtures.ts` (`accepted` → chunks `done:false` → `done:true` → pausa → `phase archivist` → `replace` opcional → `state`) e um modo de erro `{narrative_shown:true}`. Em `turn-wait.spec.ts`: o selo aparece e o botão continua `disabled` até o `state`; o `replace` deixa só o texto final; o erro deixa "não salvo" e o retry manda o mesmo `action_id` (contar requests). Mais um caso com ack (enviar um byte e segurar o resto) assertando "Aguardando o narrador", e um caso de combate com `getByRole('button', {name:'Lutar'})`. |
| P2-1 | P2 | `web/src/hooks/useTypewriter.ts:59-64` | `idx` é lido de dentro de um updater de `setDisplayedText`, que o React não garante executar de forma síncrona. O código antigo tolerava isso porque o primeiro tick vem depois do render; o código novo usa `idx` **na hora** para escolher `perTick` e o teto (`idx > 0 ? LAG : maxMs`). Sem execução ansiosa, o texto que cresce é revelado sobre o comprimento inteiro em 2,5 s, e o R7 ("≤ ~1 s atrás") deixa de valer quando chegarem tokens reais (SPEC-319). | Guardar o comprimento exibido num `useRef` (`shownLen.current`), atualizado a cada tick e no `finish`, e calcular `idx`/`perTick` a partir dele. |
| P2-2 | P2 | `web/src/App.tsx:652-665` | Com o turno em voo, qualquer status diferente de `completed` vira "O turno ainda está em andamento… continue esperando". `unknown` (perfil legacy sempre, `api.py:4198`) e `failed` não significam isso. Não há saída para um stream pendurado. | Separar as mensagens: `running` → "continue esperando"; `failed`/`unknown` → explicar e oferecer "Descartar ação pendente" (ou abortar o stream e cair no fluxo de pending existente, que já faz o POST com o mesmo `action_id`). Nunca um envio novo. |
| P2-3 | P2 | `web/src/App.tsx:63`, `:251`, `:671-677` | O estado `turn` (`failed-after-narration`, `error`) só zera no logout e no próximo envio. Depois de `discardPending()` ou de trocar de save ou de jogo novo, o compositor continua mostrando "não salvo — Tentar de novo", e o retry sai calado (sem pending) ou age sobre o pending de **outro** jogo. | Chamar `resetTurn()` em `discardPending`, `handleContinueSave` e `handleNew`. O selo `unsaved` da entrada pode ficar até o próximo turno. |
| P2-4 | P2 | `web/src/App.tsx:661` | `setBusy(false)` roda antes de `await loadHistory(...)`. Uma ação enviada nesse intervalo tem o eco e a entrada de stream sobrescritos pelo `setLog` do histórico. | Liberar `busy` depois de `loadHistory` (ou ignorar o `setLog` do histórico se outro turno começou). |
| P2-5 | P2 | `web/src/workspace/TurnStatus.tsx:43`, `:46`, `:51` | Gestão de foco: os botões "Continuar esperando" e "Tentar de novo" se desmontam no clique (`kept`, `resetTurn`, troca de estágio) e o foco cai no `body`. | Devolver o foco ao input do compositor (callback ou `ref` vindo do `Composer`) quando a ação some. |
| P2-6 | P2 | `web/src/workspace/TurnStatus.tsx:27`, `:56` + `web/src/components/Banner.tsx` | Leitor de tela: (a) `aria-atomic="true"` sobre o livro-razão inteiro relê todas as fases a cada evento (cerca de 5 anúncios por turno, cada vez mais longos); (b) o erro do turno é anunciado duas vezes, pelo `role="alert"` do banner e pelo `turn-status__error` na região `status`; (c) os botões ficam dentro da região viva. Os dois `role="status"` do compositor (turno e `voice-status`) já existiam e são aceitáveis. | Uma `<span>` visualmente oculta, `aria-live`, só com a fase atual e a tranquilização; o livro-razão e os botões ficam fora da região viva; `turn-status__error` com `aria-hidden` (ou fora da região), já que o banner anuncia. |
| P2-7 | P2 | `web/src/App.tsx:594-601` | `narrativeShown` vem antes do `status < 500`/`shouldClearPending`. Uma recusa definitiva (400/404/422) que chegue depois da narração preserva um pending que nunca vai passar. | Aplicar `shouldClearPending` também nesse ramo (manter o texto "não salvo", mas descartar o pending e esconder o retry). |
| P2-8 | P2 | `web/e2e/turn-wait.spec.ts` | Cobertura parcial do plano: falta `Espaço`/`Esc` com o foco em `.story` (só há o clique); falta o `info` sumir em 9 s; falta `assertA11y` (axe) na tela de jogo durante a espera; falta contar o POST `/game/action` no teste do retry (hoje só conta streams). | Acrescentar os quatro casos. |
| P2-9 | P2 | `web/src/hooks/useTypewriter.ts:56-80` | Com `replace` (texto final diferente), `text.startsWith(prev)` é falso e a narração inteira, já exibida, é redigitada do zero por até 2,5 s. | Em troca que não é prefixo de um texto já revelado, revelar direto (ou animar só a partir do prefixo comum). |
| P2-10 | P2 | `web/src/workspace/ChatSurface.tsx:128` + `styles.css:630` | A `.turn-status` vazia (idle, sem erro) continua no fluxo da coluna flex e soma `gap` de 0,4 rem ao compositor o tempo todo. | Não renderizar o conteúdo quando vazio (a região viva pode continuar montada, mas com `display: contents` ou sem gap), ou ajustar o gap. |

Sem regressão vista em entrada por voz (botão "Voz" e `voice-status` intactos; o texto do onboarding bate
com o rótulo), nos chips/aba Combate nem nas ofertas de arte (só o banner "Imagem confirmada" mudou para
`info`). Os e2e existentes com `getByRole("button", {name: "Agir"})` durante o turno
(`critical-journeys.spec.ts:558`, `mobile-single-pane.spec.ts:162`) continuam passando só porque a fixture
nunca dá ack. Com um backend que dê ack, o nome vira "Aguardando o narrador" e esses locators falham. Se
P1-2 introduzir ack na fixture padrão, ajuste esses testes (não são caminhos protegidos).

## Correções aplicadas

Nenhuma ainda (revisão sobre `f957fe13`).

## Pendências

- P1-1 e P1-2 antes do pouso. P2-1, P2-2 e P2-3 de preferência junto, porque tocam os mesmos trechos.
- P2-4 a P2-10 podem virar follow-up da própria 320 ou entrar na SPEC-321 (que reaproveita a linha de status).

## Comandos rodados

```text
git diff main...HEAD --stat (worktree rpg-spec-320) → 23 arquivos, +776/-125
cd web && npm test → 166 pass, 0 fail
cd web && npx tsc --noEmit -p . → sem erros
cd web && npx eslint <11 arquivos alterados em src/> → sem achados
Playwright/build: não rodados (coordenador)
```
