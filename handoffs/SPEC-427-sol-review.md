# SPEC-427 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Claude Opus (spec-reviewer, papel sol) · **Data:** 2026-11-23 · **Commit revisado:** `80d33758`

## Re-revisão (2026-11-23, `422f92cf..80d33758`)

Commits revisados: `cc7c466d` (trava síncrona + P2-1, P2-2, P3), `11a94bfb` (spec: I2 e tabela de concorrência),
`80d33758` (testes "a trava sempre solta"). A branch não foi rebaseada por mim; a `main` está em `25562940` (SPEC-428),
e o rebase fica com o coordenador no pouso.

O produto está correto nos dois sentidos pedidos: (A) não achei caminho para dois turnos em voo e (B) não achei
caminho em que a trava fique presa. Sobra um buraco de teste: a liberação forçada no retry `completed` é
necessária, mas nenhum teste a cobre. Removê-la deixa o jogador sem conseguir enviar de novo, inclusive com a
flag `off` (produção), e a suíte continua verde. Pela regra do pedido ("teste que passa com o produto quebrado
é P1"), isso fica como P1.

### Achados da re-revisão

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R2-P1-1 | P1 | `web/src/App.tsx:641`, `web/e2e/action-queue.spec.ts` (bloco "trava solta") | **A mutação L4 sobrevive** (`unlockTurn()` do retry `completed` trocado por nada): 6/6 testes de trava verdes, unit verde. O e2e "trava solta: 'Tentar de novo'" só passa pelo ramo `unknown`: o fixture responde `missing` para a operação (`fixtures.ts:357`), o reenvio com bypass reescreve a trava e o `finally` novo a solta. No ramo `completed`, com o stream antigo pendurado, só esse `unlockTurn()` solta a trava; sem ele, `turnLocked()` fica `true` para sempre e `handleAction` e o compositor recusam calados. **Provado** com um e2e temporário: verde no produto; com L4, vermelho (`waitSseReqs(2)` nunca chega a 2). Como a trava vale também com a flag `off`, essa regressão travaria todos os jogadores. | Pôr no `action-queue.spec.ts` (ou no `turn-retry.spec.ts`, como arquivo novo de caso, sem mudar asserção existente) o teste abaixo: `backend.operations.set(<action_id do 1º stream>, …)` antes de "Tentar de novo" → botão volta habilitado, 1 stream só (completed não reenvia), e depois Enter "olho o céu" → 2º stream com esse texto. Núcleo em "Comandos rodados (re-revisão)". |
| R2-P3-1 | P3 | `web/src/turnLock.ts:10` | A mutação L5 (`unlockTurn(token)` ignorando o token) só é pega pelo unit `turnLock.test.mjs`; nenhum e2e tem um fluxo antigo que termina depois de um mais novo travar. Tolerável, porque o unit testa o próprio contrato. | Opcional: e2e com retry `unknown` em que o stream abandonado fecha depois do reenvio, afirmando que um Enter no meio do turno novo não sai. |

### Respostas aos pontos

1. **P1-1 fechado.** O e2e de corrida agora está no arquivo ("I2 corrida…", nas duas viewports). Resultado: 2 streams, `["olho ao redor","sigo pela rua"]`, o texto da fila volta ao campo com a nota "outro envio saiu antes" e 0 envios da fila. Com a flag `off`, dois submits no commit dão 1 stream. A mutação L1 (sem `lockTurn`) derruba 2 testes.
   - **Outras entradas de envio:** todas passam por `onAction` = `handleAction`, que checa `turnLocked()` (`App.tsx:474`): mapa (`MapTab.tsx:66,200`), combate e cartas (`CombateTab.tsx:176-405`), atalhos de lugar (`ChatSurface.tsx:82,88`), barra de pendente e retry `!busy`.
   - Sugestões e voz só preenchem o campo (`onPick` → `setInput`; voz → `setInput`).
   - Não há outra chamada a `sendActionStream`/`sendAction` (`App.tsx:525,583`).
   - O único bypass é o retry `unknown` (`App.tsx:653-657`). Ele roda depois de `turnToken++`; a trava é então do fluxo abandonado, e o reenvio a reescreve com o token novo. Não há fila nesse estágio (`waiting`).
2. **Trava presa (B).** Para cada caso: a trava solta, e um envio novo funciona.
   - (a) O `App` não desmonta no meio de um turno: logout, troca de partida e conta ficam bloqueados com `busy` (`PlayMenu.tsx:28-38`, `useSaves.ts:95`).
   - (b) StrictMode e remontagem: `lockTurn` não está em efeito, só em `handleAction`.
   - (c) e (d): `lockTurn` fica na linha antes do `try`; entre os dois só há `let`, e toda saída passa pelo `finally`, que chama `unlockTurn(token)`. L2 derruba 5 testes.
   - (e) Stream pendurado sem fim: como hoje, `busy` também fica preso. "Tentar de novo" `unknown` reescreve a trava (coberto); `completed` usa a liberação forçada (**sem teste: R2-P1-1**).
   - (f) Reload: o módulo recomeça com `holder = 0`.
   - (g) O token protege: o `finally` antigo não solta a trava nova (unit; ver R2-P3-1).
   - (h) As liberações sem token não soltam um turno legítimo mais novo. `auth-expired` invalida tudo (`session++`). No `completed`, `busy` continua `true` durante os `await`, então nenhum turno novo consegue travar antes do `unlockTurn()`. L3 derruba o e2e de `auth-expired`.
3. **Estado global em teste.** Não vaza. Os units importam o módulo de novo a cada `load()` (data URL com `Math.random()`, `turnLock.test.mjs:10`), e cada e2e roda numa página nova, com contexto JS próprio.
4. **Flag `off`.** Com a flag desligada, Enter depois do `state` envia normalmente (`turn-wait` e `critical-journeys`). Dois Enters no commit dão 1 stream (e2e). Rótulos e estados de botão não mudaram (`a11y-label-in-name` verde).
   - O `git diff 422f92cf..HEAD -- web/e2e` só toca `action-queue.spec.ts`, arquivo novo desta spec. Nenhum arquivo que já existia na `main` foi editado nesta rodada.
   - Rodados, um arquivo por vez, `--workers=1`, todos verdes e sem precisar repetir nenhum:
     - `voice-input` 11
     - `mobile-single-pane` 16 (mobile-320 e mobile-390)
     - `a11y-label-in-name` 5
     - `turn-wait` 20
     - `turn-retry` 7
     - `turn-preflight` 4
     - `pending-discard` 5
     - `critical-journeys -g "F14|F15|F20"` 3
     - `effects` 48 (+3 skipped)
5. **P2-1, P2-2 e P3-1..3.**
   - P2-1: `clearNote` agora limpa `liveNote`, e um efeito em `base.seq` limpa a nota quando não há fila. O e2e "a região viva do turno seguinte não repete…" passa, e o meu teste da rodada 1 era a mesma checagem.
   - P2-2: a nota aparece no ramo `deckLocked` (`ChatSurface.tsx:216-219`), com e2e usando `armDeck` (pilhas) nas duas viewports.
   - P3-1: o unit `closed({busy:true}) → wait` foi adicionado.
   - P3-2: `choiceId` agora junta a lista inteira, com e2e.
   - P3-3: o texto foi aceito na tabela R10.
6. **Mutações** (todas restauradas; `git status` limpo, só o handoff modificado):

   | mutação | resultado |
   |---|---|
   | L1 sem `lockTurn` | 2 e2e vermelhos |
   | L2 `finally` sem `unlockTurn` | 5 e2e vermelhos |
   | L3 `auth-expired` sem unlock | 1 e2e vermelho |
   | **L4 retry `completed` sem unlock** | **sobrevive** (6/6 verdes): R2-P1-1. Com o e2e temporário, vermelho |
   | L5 unlock ignorando o token | e2e verde, unit 1 falha (R2-P3-1) |
   | M1 sem `delivered` | 3 e2e, 3 unit |
   | M3b sem `drop` antes do envio (só a linha do efeito) | 1 e2e |
   | M4 combate envia | 2 e2e, 2 unit |
   | M5 `replace` envia | 1 e2e |
   | M6 fila aceita em `waiting` | 1 e2e, 1 unit |
   | M7 `Boolean(...)` | 4 e2e |

7. **Spec e gates.**
   - O I2 novo e a linha nova da tabela de concorrência descrevem o código. Só a frase "e2e 'trava solta' … retry" cobre o ramo `unknown`, não o `completed` (R2-P1-1).
   - `npm test` 328/328; `typecheck`, `typecheck:e2e` e `lint` com rc 0.
   - `App.tsx` com 965 linhas (+4 desde a `main`, dentro do R15 ≤ 969), e `test_size_budget` verde.
   - `baseline_growth --base main`: nenhum baseline cresceu.
   - `action-queue.spec.ts` inteiro: 72/72 verdes, sem repetição.

## Evidência verificada

Re-revisão em `80d33758`. Web, feito à mão (o `red_green.sh` só cobre Python; a tabela Python da rodada 1 continua valendo, porque o servidor não mudou nesta rodada):

| verificação | resultado |
|---|---|
| `action-queue.spec.ts` (72 testes, 2 viewports) | 72 passed |
| e2e de corrida da rodada 1 (agora "I2 corrida…") | 2 streams `["olho ao redor","sigo pela rua"]`, fila devolvida |
| e2e temporário: retry `completed` com o stream pendurado + envio novo | verde no produto; **vermelho com L4** |
| L1 / L2 / L3 | vermelhos (2 / 5 / 1) |
| L4 | **sobrevive** na suíte da branch |
| L5 | só o unit pega |
| M1, M3b, M4, M5, M6, M7 | todos vermelhos |
| voice-input, mobile-single-pane, a11y-label-in-name, turn-wait, turn-retry, turn-preflight, pending-discard, critical F14/F15/F20, effects | todos verdes (11, 16, 5, 20, 7, 4, 5, 3, 48+3 skip) |
| npm test / typecheck / typecheck:e2e / lint | 328/328 · 0 · 0 · 0 |
| pt.sh test_size_budget, test_flag_registry, test_latency_client_endpoint | 37 passed |
| baseline_growth --base main | nenhum baseline cresceu |

### Comandos rodados (re-revisão)

```text
playwright action-queue.spec.ts --workers=1 --project=chromium → 72 passed
mut2.sh (L1–L5, M1, M3b, M4–M7; cada uma restaurada com git checkout --) → tabela acima
e2e temporário zz-review-lock.spec.ts: produto → 1 passed; com L4 → 1 failed (waitSseReqs 2)
e2e_files.sh (9 arquivos, --workers=1, um por vez) → todos verdes
npm test → 328/328 · typecheck 0 · typecheck:e2e 0 · lint 0
pt.sh tests/test_size_budget.py tests/test_flag_registry.py tests/test_latency_client_endpoint.py → 37 passed
py.sh scripts/dev/baseline_growth.py --base main → nenhum baseline cresceu
```

Núcleo do teste que falta (R2-P1-1):

```ts
await page.clock.install();
await composer(page).fill("olho ao redor"); await composer(page).press("Enter");
await waitSseReqs(page, 1);
await push(page, ": ack\n\n" + ev("phase", { node: "campaign_manager", status: "done" }));
const opId = String((await sseReqs(page))[0].action_id);
const st = backend.states.get("game-a")!;
backend.operations.set(opId, { signature: "x", response: { ...st, message: "Concluído no servidor." }, gameId: "game-a", ownerId: backend.userId } as never);
await page.clock.fastForward(25_000);
await page.locator(".ws-composer .turn-status").getByRole("button", { name: "Tentar de novo" }).click();
await expect(page.locator('[data-effect="chat.pending"]')).toBeEnabled();
expect(await sseReqs(page)).toHaveLength(1);          // completed: não reenvia
await composer(page).fill("olho o céu"); await composer(page).press("Enter");
await waitSseReqs(page, 2);                           // com L4 nunca chega
expect((await sseReqs(page))[1].input_text).toBe("olho o céu");
```

---

# Rodada 1 (commit `99aa5a4c`)

## Escopo

Branch `spec-427`, `git diff main...HEAD`. A merge-base `8e6cb2f4` é a `main` atual, então não há defasagem:
`b93e94ac` (flag, `/auth/config`, preset), `fdea732f` (fila no cliente), `975ff367` e `99aa5a4c` (e2e).
Li o diff inteiro de `web/src`, `web/e2e`, `routes/auth.py`, `services/latency_flags.py`,
`config/flags.yaml`, `scripts/staging/*` e dos testes Python. A spec foi lida por seção (R1–R16, I1–I7, §3, §4).
Ficaram de fora: o smoke §6 (staging), a suíte completa e o `test:e2e` completo.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `web/src/hooks/useQueuedAction.ts:354-368`, `web/src/App.tsx:473`, `web/src/workspace/ChatSurface.tsx:192-205` | **Dois turnos em voo (viola I2).** O autoenvio roda num efeito passivo. O render do `state` é de lane default, então um envio manual (Enter com texto no campo, sugestão, atalho de mapa) passa pelo guarda `busy` do closure, que ainda vale `false`, em duas janelas: entre o commit (`busy=false` no DOM) e a execução do efeito, e de novo entre o efeito e o re-render do `setBusy(true)` que ele dispara. O `pending` não protege, porque `preparePendingWithOrigin` só grava depois do `await crypto.subtle.digest` (`pendingOperation.ts:40-44`). **Reproduzido** num e2e temporário: o jogador enfileira "olho o céu", digita "sigo pela rua" e aperta Enter no commit do `state` (via `MutationObserver` + `form.requestSubmit()`). Resultado: `__sseReqs` = `["olho ao redor","sigo pela rua","olho o céu"]`, 3 streams e 2 turnos cobrados em voo; o fluxo mais antigo perde o `turnToken` e a narração dele é ignorada. Sem fila não existe envio fora de evento discreto, então essa janela é nova. É a corrida "substitui o texto no mesmo instante" (item 3 do pedido). | Trava síncrona no `App`: `const turnInFlight = useRef(false)`. Em `handleAction`: `if (((busy \|\| turnInFlight.current) && !bypass) \|\| …) return; turnInFlight.current = true;`. Zerar no `finally` (quando `active()`) e nos pontos que já fazem `setBusy(false)` do turno: `retryTurnInner` (`completed`, e `unknown` antes do reenvio), `rpg:auth-expired`, e `discardPending` se aplicável. Cabe em ≤ +6 linhas (o `App.tsx` está em 962, +1). Regressão: o e2e de corrida (núcleo em "Comandos rodados") entra em `action-queue.spec.ts`, afirmando `__sseReqs` ≤ 2 e que o texto recusado não se perde (vai ao rascunho ou fica na fila). Corrigir só no compositor não cobre sugestões nem mapa. Atualizar o I2 na spec: o guarda é a ref, não o `busy` do closure. |
| P2-1 | P2 | `web/src/hooks/useQueuedAction.ts:335-338,397` | **Anúncio de devolução preso na região viva.** `giveBack` grava `liveNote` e nada o limpa: `clearNote` só zera `note`, e `drop` só roda quando há fila nova. Com `aria-atomic`, o texto vivo dos turnos seguintes vira "O mestre consulta os arcanos… A ação na fila não foi enviada: a narração mudou. O texto voltou ao campo." e depois "registrando… A ação na fila não foi enviada…". O leitor de tela relê isso a cada fase, até a próxima fila. Reproduzido por e2e temporário (devolução por `reset`, depois Enter manual; saída acima). Vale também para "Ação tirada da fila…" e para a nota de montagem (R11). Viola SPEC-320 R1 e R14 (região viva só com a fase atual ou um aviso). | `clearNote = () => { setNote(null); setLiveNote(null); }` (já é chamado no submit e na edição do campo). E2e: depois de uma devolução, enviar um turno e afirmar que a região viva em `waiting` e em `narrated` não contém "não foi enviada". |
| P2-2 | P2 | `web/src/workspace/ChatSurface.tsx:212-214,646` | **Caso a sem nota visível no combate de cartas.** A nota (`queue.note`) mora no ramo `!deckLocked`. Com `combat.pilhas` (cartas `on` no staging), o compositor vira "Na luta, você age pelas cartas…" e a devolução só é anunciada ao leitor de tela. O e2e do caso a usa `armCombat` sem `pilhas` (`fixtures.ts:138-155`), então não cobre a configuração do staging. Nada é enviado (é seguro), mas o R10 pede nota visível. | Renderizar a nota também no ramo `deckLocked` (ex.: `<p className="composer-hint">` depois de `composer-locked`) e adicionar um e2e do caso a com `pilhas` no estado final. |
| P3-1 | P3 | `web/tests/queuedAction.test.mjs:30-38` | Duas mutações sobrevivem: tirar `if (s.busy) return wait` (`queuedAction.ts:476`) e tirar o guarda `sentSeq` (`useQueuedAction.ts:365`) deixam unit e e2e verdes. Hoje são equivalentes (o `stage !== "idle"` e o `drop` antes do envio já cobrem), mas essa defesa em profundidade não tem teste. | Unit: `decideQueued(queued, closed({ busy: true }))` com stage `idle` → `wait`. |
| P3-2 | P3 | `web/src/queuedAction.ts:456,485` | O caso d compara só `pending_choices[0].id`: uma escolha nova anexada atrás de outra já pendente não devolve a fila. | Comparar a lista de ids (`map(c => c.id).join()`). |
| P3-3 | P3 | `web/src/queuedAction.ts:480` | O caso j por `resetTurn` (retry `completed`) cai em `!delivered` e anuncia "a narração mudou", não "o turno foi retomado" (tabela R10). Hoje é inalcançável (ver o ponto 2 abaixo); só afeta o texto. | Aceitar e registrar, ou ajustar a tabela. |

## Respostas aos pontos do coordenador

1. **I1/I2.** A ordem real dos eventos, toda síncrona depois do `await` (mesmo batch):
   - `clearOwnPending` (`App.tsx:542`);
   - `setPending(null)` (545);
   - `delivered` (546);
   - `setData`/`finishStreamEntry` (547-548);
   - no `finally`, `setBusy(false)` e volta a `idle` preservando `delivered` (606-608).

   O efeito decide no render com `busy=false`, `stage=idle` e os dados novos. `live.current` é atualizado num efeito declarado antes (`useQueuedAction.ts:328`), então `onAction` é o `handleAction` do render atual. StrictMode: o e2e roda no Vite dev (StrictMode, `main.tsx:17`) e conta 2 streams no fim; o `drop` antes do envio e o `sentSeq` impedem um segundo envio pelo próprio efeito. **Mas o I2 falha contra um envio manual concorrente** (P1-1).
2. **Casos a–m.** Têm e2e que falha se a fila enviar (mutações M1, M4 e M5 ficam vermelhas): a, b, c (×2), d, e, f, g (×2), h, i, k, l, I7 e reload.
   - **j:** inalcançável pela UI, confirmado, e o desvio é aceito.
     - A fila só existe em `narrated` (`queuedAction.ts:463`).
     - "Tentar de novo" só aparece em `waiting` com tier `retry` ou em `failed-after-narration` (`TurnStatus.tsx:33,59,66`).
     - `narrated` não volta a `waiting` sem `submit` (`turnWait.ts:52-58`).
     - `resumeSession` sai cedo com `busy` (`App.tsx:141`).
     - Abrir save, menu ou conta é bloqueado com `busy` (`useSaves.ts:95`, `PlayMenu.tsx:28-38`).
   - **l:** trocar de partida pelo menu é inalcançável com `busy` pelo mesmo motivo; a versão por sessão expirada é a alcançável.
   - **m:** reload e I7 cobertos.
   - Não há unit de React para "não envia duas vezes". É aceitável, dado o e2e em StrictMode, mas ver P3-1.
3. **Corridas.**
   - Tirar da fila no instante do `state`: 0 ou 1 envio (o handler e o efeito leem a mesma ref).
   - Substituir no mesmo instante, antes do commit: o efeito lê a ref e manda o texto novo; 1 envio.
   - `replace` a caminho: `replaced` é marcado antes do `state` (os eventos chegam em ordem no mesmo stream).
   - Rede caindo: casos h e k.
   - `turnToken` invalidado: `!active()` retorna antes de `delivered`.
   - **Envio manual no commit: 2 turnos em voo (P1-1).**
4. **Idempotência e retomada.** O `action_id` é novo e igual ao pending, com 0 consultas a `/operations` (e2e verde). Uma falha do autoenvio é uma falha comum de `handleAction`. `preparePendingWithOrigin`, `resumeSession` e `retryTurnInner` não têm diff.
5. **Flag.**
   - `/auth/config` só leva a chave com `on`/`" ON "`; com `"1"`, `"true"`, `"yes"` e `""` ela fica ausente (pytest).
   - O cliente liga só com `=== true`; a mutação M7 (`Boolean(...)`) derruba 4 e2e.
   - Flag off: `turn-wait.spec.ts` 20/20 verde. O diff de `turn-wait.spec.ts` é só a remoção dos helpers, idênticos em `sseControl.ts`, e o `fixtures.ts` só ganhou `actionQueue` (default `false` = resposta igual à de hoje).
   - Nenhum caminho de `evals/protected-paths.txt` foi tocado (lista atual, que inclui `web/e2e/contracts`).
6. **Estados especiais.** Cobertos: combate (a; ver P2-2 para cartas), morte/game_over (c), nível (d; ver P3-2), não salvo (f), fallback POST (h) e `waiting` (e2e). Cartas, combate e voz: a fila só sai do compositor, o compositor some com `deckLocked` e a voz fica desabilitada com `busy`.
7. **A11y e mobile.** O anúncio sai na região viva única (e2e). "Tirar da fila" funciona por Tab+Enter e por clique, tem ≥ 44 px, e o axe passa nas duas viewports. O ajuste do 390 (`#composer` em vez do papel) só troca o seletor, porque no combate o compositor fica fora da superfície; o teste continua afirmando valor, nota, anúncio e 0 envios, então não esconde bug de devolução. Anúncio preso: P2-1.
8. **Mutações.** Cada uma foi restaurada com `git checkout --` e o `git status` ficou limpo no fim. Resultados na tabela de Evidência.
9. **Vermelho antes.** Com o `web/src` da merge-base, o e2e principal falha (`toBeEnabled` → `disabled`). Restaurado com `git checkout HEAD -- web/src`.
10. **Gates.** Todos verdes (lista abaixo). `App.tsx` passou de 961 para 962 linhas (+1).

## Evidência da rodada 1 (commit `99aa5a4c`)

`bash scripts/dev/red_green.sh 427` (só Python):

```text
| teste | main | branch | veredito |
|---|---|---|---|
| tests/test_latency_client_endpoint.py::test_auth_config_action_queue_absent_by_default | verde | verde | FAIL: nao prova a mudanca |
| tests/test_latency_client_endpoint.py::test_auth_config_action_queue_near_valid_values_stay_off | verde | verde | FAIL: nao prova a mudanca |
| tests/test_latency_client_endpoint.py::test_auth_config_action_queue_on | vermelho | verde | OK |
| tests/test_spec192_vercel_env.py::test_action_queue_is_sent_from_the_staging_preset_only | vermelho | verde | OK |
red_green: 2/4 OK
```

Os dois "verde na main" são controles de ausência da chave (na `main` ela nunca aparece), então são
esperados. O pouso deve rodar com `--allow-green` para esses dois nodeids.

Web (feito à mão, porque o red_green não cobre e2e):

| verificação | resultado |
|---|---|
| e2e principal com o `web/src` da merge-base | vermelho (`toBeEnabled`: disabled) |
| `action-queue.spec.ts` na branch (54 testes, 2 viewports) | 53 verdes + 1 timeout de navegação no 1º (Vite frio); repetido isolado: verde |
| `turn-wait.spec.ts` (flag off) | 20/20 |
| M1 sem `delivered` | e2e g/h vermelhos (3), unit com 3 falhas |
| M2 sem `busy → wait` | **sobrevive** (equivalente; P3-1) |
| M3 sem `sentSeq` | **sobrevive** (equivalente; P3-1) |
| M3b sem `drop` antes do envio | e2e vermelho |
| M4 combate envia | e2e a vermelho, unit com 2 falhas |
| M5 `replace` não marca `replaced` | e2e g vermelho |
| M6 fila aceita em `waiting` | e2e vermelho, unit com 1 falha |
| M7 `Boolean(config.action_queue)` | 4 e2e vermelhos |
| corrida: Enter manual no commit do `state` (temporário) | **3 streams: P1-1** |
| região viva depois de uma devolução (temporário) | **nota presa: P2-1** |

## Correções aplicadas

Nenhuma (o revisor não edita código).

## Pendências

P1-1, P2-1 e P2-2 bloqueiam o pouso; os P3 podem virar follow-up. Foi acrescentada uma linha em
`docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` § concorrência.

## Comandos rodados

```text
bash scripts/dev/red_green.sh 427 → 2/4 OK (2 controles de ausência verdes na main, esperado)
npm test → 327/327 · npm run typecheck → 0 · npm run typecheck:e2e → 0 · npm run lint → 0
pt.sh test_flag_registry test_spec192_vercel_env test_latency_client_endpoint test_ruff_counts test_clock_asserts test_size_budget → 83 passed
py.sh scripts/dev/baseline_growth.py --base main → nenhum baseline cresceu
py.sh scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função nova com nome repetido
playwright action-queue.spec.ts --workers=1 --project=chromium → 53 passed + 1 timeout, repetido verde
playwright turn-wait.spec.ts --workers=1 → 20 passed
git checkout 8e6cb2f4 -- web/src; e2e principal → vermelho; git checkout HEAD -- web/src
mutações M1–M7 (script do revisor) → tabela acima; git status limpo
e2e temporário zz-review-race.spec.ts → SSE ["olho ao redor","sigo pela rua","olho o céu"]
e2e temporário zz-review-live.spec.ts → live "registrando… A ação na fila não foi enviada: a narração mudou…"
```

Núcleo do teste de corrida (P1-1), para virar regressão:

```ts
await composer(page).fill("sigo pela rua"); // a fila já tem "olho o céu"
const state = ev("state", await finalState(page, "A névoa sobe."));
await page.evaluate(() => {
  const btn = document.querySelector('[data-effect="chat.pending"]')!; let fired = false;
  new MutationObserver(() => { if (fired || btn.textContent?.trim() !== "Agir") return; fired = true;
    (document.querySelector("form.ws-composer") as HTMLFormElement).requestSubmit(); })
    .observe(btn, { subtree: true, childList: true, characterData: true, attributes: true });
});
await push(page, state); await closeSse(page);
// esperado: ≤ 2 em __sseReqs; hoje são 3
```
