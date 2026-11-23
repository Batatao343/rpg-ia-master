# SPEC-427 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Claude Opus (spec-reviewer, papel sol) · **Data:** 2026-11-23 · **Commit revisado:** `99aa5a4c`

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

## Evidência verificada

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
