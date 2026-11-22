# SPEC-420 — latencia-cliente-sem-getoperation

> **Status:** `in-progress` (aprovada pelo dono em 13/11; código pousado em 22/11; revisão Sonnet APPROVED; falta o smoke §6, que depende de deploy no staging)
> **Criada:** 2026-11-13 · **Atualizada:** 2026-11-13
> **Depende de:** nenhuma (SPEC-316, SPEC-320 e SPEC-383 já `done`; o contrato de retomada delas fica intacto)
> **Desbloqueia:** nada diretamente; item L1a de `docs/auditorias/latencia-turno-2026-11-12.md` (linha 241 da fila)
> **Risco:** `médio` (cliente web; toca a retomada da SPEC-320 e a idempotência do turno por `operation_id`, sem mudar o servidor). Revisor Sonnet obrigatório; se o coordenador tratar a retomada como "estado", sobe para `alto` e `spec-reviewer`.
> **Requer:** staging (smoke §6 depois do deploy; sem chave nova e sem LLM além dos turnos do smoke)
> **Domínios de revisão:** concorrência (retry e fluxos invalidados por `turnToken`; os itens do guia são de `asyncio` e quase todos "não se aplica", ver §3 Concorrência)
> **Evidência:** e2e Playwright que conta requisições a `/game/{game}/operations/{op}` (sem `/cost`): envio novo = 0 (hoje 1, falha antes); retomada de pending = 1 (passa antes e depois). E2e de eco com a consulta pendurada: o eco aparece (hoje nunca aparece, falha antes).

---

## 1. Contexto & Objetivo

Todo turno do cliente web espera `await api.getOperation(gid, operation.operation_id)` (`web/src/App.tsx:487`) antes do POST e antes do eco da ação do jogador (`App.tsx:510`). Quando não havia pending, o `operation_id` acabou de ser gerado com `crypto.randomUUID()` dentro de `preparePending` (`web/src/pendingOperation.ts:35`), então o servidor não tem como conhecê-lo e a consulta sempre volta "desconhecida". A auditoria de latência registrou isso como C2 (`docs/auditorias/latencia-turno-2026-11-12.md:130`) e propôs a L1a (`:133-134`). A medição no staging (n=120) dá **0,35 s por turno fora do servidor e 0,24 s dentro dele** (`docs/auditorias/latencia-turno-medicao-2026-11-13.md:48`; item 7 da fila em `:80`).

As jogadas de carta e as ações básicas de combate passam pela mesma função: `web/src/workspace/tabs/CombateTab.tsx:173-210,283,335` chama `onAction`, que é `handleAction` (`App.tsx:916`). A mudança vale para elas sem código extra (confirmado no source; a auditoria cita `web/src/combat/targeting.ts:106`, que só monta o texto da carta). Entra nesta spec com teste próprio (R9).

Objetivo: quando a operação foi **criada nesta chamada**, o cliente pula a consulta e mostra o eco antes de qualquer rede. Quando já existia uma operação pendente (retry, "Consultar / retomar", reload, retomada do app), o fluxo fica exatamente como hoje: a consulta vem antes do eco de propósito, porque o ramo "concluído" restaura sem eco (`App.tsx:488-498`) e o ramo de retry remove o eco órfão (`App.tsx:500-507`).

Decisão do dono (13/11): aprovou a L1a. Não aprovou fila de ação nem liberar o campo antes do `state` (SPEC-316 D2, `specs/SPEC-316-latencia-narracao-antes-do-arquivista.md:221`; SPEC-320 R13): o campo continua travado até o `state`.

## 2. Requisitos

- **R1 — origem da operação, sem heurística de tempo.** `web/src/pendingOperation.ts` exporta `preparePendingWithOrigin(owner, game, input, options): Promise<{ operation: PendingOperation; created: boolean }>`. `created === true` se e somente se `loadPending(owner, game)` devolveu `null` na leitura síncrona do início da chamada (`pendingOperation.ts:27`) e o `operation_id` foi gerado por `crypto.randomUUID()` dentro dela (`:35`). `created === false` quando a chamada devolveu o pending existente (`:28`). `created` **não** é gravado no `localStorage` (o formato `version: 1` de `:3-9` não muda). `preparePending` mantém a assinatura e devolve `(await preparePendingWithOrigin(...)).operation`.
- **R2 — envio novo sem consulta.** Em `handleAction`, com `created === true`: nenhuma chamada a `api.getOperation`; o cliente roda a mesma limpeza local de hoje (`pendingVisual.current = null` e remoção da narração `unsaved` com seu eco, `App.tsx:500-507`), empurra o eco e só então chama `api.sendActionStream`. Entre o Enter e o `POST /game/action/stream` não há requisição a `/game/{game}/operations/{op}`.
- **R3 — eco antes de qualquer rede no envio novo.** Com `created === true`, o eco do jogador entra no log antes da primeira requisição de rede do turno (o único passo assíncrono anterior é o `crypto.subtle.digest` local de `pendingOperation.ts:34`).
- **R4 — pending existente: fluxo idêntico.** Com `created === false`: `api.getOperation` é chamado uma vez antes do eco, como hoje; `completed` restaura estado e histórico sem eco (`App.tsx:488-498`); `running` lança o mesmo erro (`:499`); qualquer outro status segue para limpeza, eco e envio (`:500-510`). Mesma ordem, mesmas mensagens.
- **R5 — eco não confirmado sai no erro sem narração.** Se o fluxo cai no `catch` externo (`App.tsx:581`) ainda ativo (`active()`), sem narração mostrada (não é `HttpError` com `narrativeShown`) e o pending desta operação continua gravado (`loadPending(user, gid)?.operation_id === operation.operation_id`), o eco que **este** fluxo empurrou é removido do log pelo seu `id`. Recusa definitiva (pending descartado por `shouldClearPending`) mantém o eco como hoje. Motivo: sem isso, "offline no envio" passa a deixar um eco que o "Consultar / retomar" duplica (hoje a consulta falhava antes do eco; o retomar empurra eco novo em `:510` e a limpeza de `:502-507` só remove entradas `unsaved`). Vale para os dois caminhos (R2 e R4); ver D1.
- **R6 — no máximo um eco por envio.** Envio que falha sem narração seguido de "Consultar / retomar" (`App.tsx:794`) termina com exatamente um eco do texto e uma narração.
- **R7 — mesmo `operation_id` em todo reenvio.** O `action_id` de `sendActionStream` e do fallback `sendAction` (`App.tsx:486,535,574`) é sempre `operation.operation_id`; retry, "Tentar de novo" e retomada reusam o id do pending gravado.
- **R8 — consultas de retomada intactas.** `resumeSession` (`App.tsx:144`), abertura de save com pending (`web/src/hooks/useSaves.ts:110`) e `retryTurnInner` com turno em voo (`App.tsx:616`) continuam chamando `api.getOperation` exatamente como hoje. Esta spec não edita essas funções.
- **R9 — cartas e ações de combate.** Jogar uma carta sem pending prévio também faz 0 consultas a `/operations/{op}` (consequência de R2, provada por teste próprio).
- **R10 — tamanho.** `web/src/App.tsx` tem 950 linhas e o gate (`scripts/dev/size_budget.py:31`, limite 1.000) cobre `web/src/*.tsx`. A mudança não passa de +15 linhas líquidas em `App.tsx`; lógica nova que não couber vai para `pendingOperation.ts`.

### Fora de escopo

- Servidor (rotas, idempotência, `/operations/{op}`): nenhum arquivo Python muda.
- Fila de ação (L1b) e qualquer liberação do campo antes do `state` (SPEC-316 D2, SPEC-320 R13).
- Code splitting e os demais itens C* da auditoria.
- Mover a marca `latency.submit()` (`App.tsx:516`) para o Enter: a telemetria do cliente (`TurnLatencyTracker`) já começa depois da consulta e por isso não mostra este ganho; medir isso é outro trabalho.
- Eco em recusa definitiva 4xx (`App.tsx:553,557-566`): fica como está.
- Extração de `handleAction` para hook (SPEC-392, `draft`). Se a 392 pousar antes, a mudança vai para o hook equivalente com o mesmo contrato.
- `resumeSession` e `useSaves`: só leitura nesta spec (R8).

### Invariantes

- **I1** — Idempotência: para um mesmo pending, todo POST do turno carrega o mesmo `action_id` (testes: `web/e2e/turn-retry.spec.ts:84` "reenvia o MESMO action_id", `web/e2e/turn-wait.spec.ts:195`, novo `envio novo: 0 consultas e mesmo operation_id`, novo `pending existente consulta uma vez`).
- **I2** — Nenhum caminho com pending existente perde a consulta: retomar = 1 consulta (novo `pending existente consulta uma vez`), reload com pending consulta e restaura (`web/e2e/critical-journeys.spec.ts:237` F14), retry com turno em voo consulta (`turn-retry.spec.ts:63,84,108`).
- **I3** — Sem eco duplicado nem eco órfão: falha sem narração deixa 0 ecos e o retomar deixa 1 (novo `eco único após falha e retomada`); turno concluído no servidor restaura sem eco (F14, `critical-journeys.spec.ts:247`).
- **I4** — Recusa definitiva descarta o pending e libera o compositor como hoje (`turn-retry.spec.ts:149`, `web/e2e/pending-discard.spec.ts:53`).
- **I5** — `preparePending` mantém o contrato (`web/tests/pending.test.mjs` existente sem alteração e verde).
- **I6** — Marcas de latência por turno continuam com um `action_id` só (`web/e2e/latency.spec.ts:36`).

## 3. Design técnico

**Arquivos alterados**

- `web/src/pendingOperation.ts`
  - Nova `export async function preparePendingWithOrigin(owner: string, game: string, input: string, options: Record<string, unknown>): Promise<{ operation: PendingOperation; created: boolean }>` com o corpo atual de `preparePending` (`:25-40`): `existing` → `{ operation: existing, created: false }`; senão `{ operation: row, created: true }`.
  - `preparePending` vira wrapper de uma linha (contrato e testes atuais intactos).
- `web/src/App.tsx` (`handleAction`, `:469-599`)
  - Troca `preparePending` por `preparePendingWithOrigin` e desestrutura `{ operation, created }`.
  - O bloco `getOperation` + ramos `completed`/`running` (`:487-499`) só roda quando `!created`. A limpeza local (`:500-507`) e o eco (`:510`) rodam nos dois casos, na mesma ordem.
  - `pushLog` (`:307-309`) passa a devolver o `id` da entrada (compatível: os outros chamadores ignoram o retorno). O eco guarda `echoId`.
  - No `catch` externo (`:581`), antes do banner: se `active()`, `echoId !== null`, o erro não é `HttpError` com `narrativeShown` e `loadPending(user, gid)?.operation_id === operation.operation_id`, remove a entrada `echoId` (`setLog(prev => prev.filter(e => e.id !== echoId))`). `operation` e `echoId` ficam declarados antes do `try` para o `catch` enxergar.
- `web/tests/pending.test.mjs`: casos novos de `preparePendingWithOrigin` (os existentes não mudam).
- `web/e2e/turn-retry.spec.ts` (ou arquivo novo `web/e2e/turn-preflight.spec.ts`, se o executor preferir isolar): os testes novos da Etapa 2.

**Sem arquivo novo de produto, sem schema, sem mudança de formato no `localStorage`.**

**Contagem de consultas nos testes:** `backend.requests` (`web/e2e/fixtures.ts:98,297`) filtrado por `/^\/game\/[^/]+\/operations\/[^/]+$/` (o `/cost` de `refreshTurnCost`, `App.tsx:460`, tem um segmento a mais e fica fora). Atenção: o stream do fake registra a operação **antes** de abortar com `failNextTurn` (`fixtures.ts:372-374`), então uma consulta real depois disso volta `completed` (`fixtures.ts:351-355`); testes que precisam do ramo "desconhecida" roteiam a consulta como `missing`, como em `turn-retry.spec.ts:119-123`.

### Concorrência

Sem thread nem `asyncio`; o que existe é corrida de fluxos de UI invalidados por `turnToken`/`session`/`gameId` (`App.tsx:473-474`).

| Evento | Estado no momento | Resultado esperado | Teste |
|---|---|---|---|
| Duplo Enter no envio novo | 1º fluxo já ligou `busy` (`:475`) | 2ª chamada sai em `:471`; um único stream | novo `envio novo: 0 consultas…` (assertar 1 stream) |
| "Tentar de novo" com stream pendurado (status `unknown`) | pending gravado, eco do 1º fluxo no log | F-3 remove o eco por texto (`:634-638`); `retryBypass` reenvia com `created === false` → 1 consulta + mesmo `action_id`; um eco no fim | `turn-retry.spec.ts:84` (acrescentar eco = 1) |
| Duplo clique em "Consultar / retomar" | consulta lenta em voo | um envio só (`busy`/`retrying`) | `turn-retry.spec.ts:108` |
| Falha de rede no envio novo (stream e fallback POST) | eco empurrado, pending gravado | eco removido (R5), banner "Ação não confirmada", pending fica | novo `eco único após falha e retomada` |
| Fluxo antigo termina depois de um turno novo | `active()` falso | não remove eco nem pending de ninguém (guarda `active()`, `clearPendingIfOwn`) | `pending.test.mjs:77`, `turn-retry.spec.ts:32`, F15 |
| Outra aba grava pending entre o `loadPending` e o `set` de `preparePending` | duas operações novas, ids distintos | igual a hoje: nenhuma das duas era conhecida do servidor, a consulta não mudaria nada; o servidor serializa pelo jogo | N/A (comportamento anterior preservado) |

Itens de `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` § concorrência: todos tratam de `await to_thread`/cancelamento Python e não se aplicam, exceto "espera em teste sempre com teto" (usar `expect.poll`/`toBeVisible` com o timeout do Playwright; `waitForTimeout` nunca é o oráculo).

## 4. Plano passo a passo

### Etapa 0 — caracterização (antes de editar produto)

1. Ler `docs/guias/CASOS_QUE_O_REVISOR_PEDE.md` § concorrência e registrar no hand-back o que não se aplica.
2. Escrever os testes das Etapas 1 e 2 e rodar contra o código atual. Esperado **antes**: `preparePendingWithOrigin` inexistente (unit falha); "envio novo = 0 consultas" falha com 1; "eco com consulta pendurada" falha (eco não aparece); "eco único após falha e retomada" falha (1 eco depois da falha, 2 depois da retomada; se der outro número, parar e registrar a hipótese, porque a R5 depende disso); "pending existente consulta uma vez" passa. Colar as contagens no hand-back.

### Etapa 1 — origem da operação (unit)

1. **Testes** (`web/tests/pending.test.mjs`, casos novos):
   - `preparePendingWithOrigin creates once then reuses`: 1ª chamada `created === true`; 2ª (outro texto) `created === false`, mesmo `operation_id`, `payload.input_text` original.
   - `created again after clearPending`: depois de `clearPending`, `created === true` com id novo.
   - `blocked storage still reports origin`: com `localStorage` que lança, 1ª `created === true` e `volatile === true`; 2ª `created === false` com o mesmo id (fallback em memória, `web/src/safeStorage.ts:2-3,20`).
   - `created is not persisted`: o JSON gravado não tem a chave `created`.
2. **Implementação:** `preparePendingWithOrigin` + wrapper (§3).
3. **Verificação:** `cd web && npm test` (todos os `tests/*.test.mjs`, os existentes sem mudança).

### Etapa 2 — `handleAction` (e2e)

1. **Testes** (Playwright, fixture `DeterministicBackend`):
   - `envio novo: 0 consultas e mesmo operation_id`: abre o jogo, envia texto com `backend.delayStream()`; durante o voo, o `operation_id` do pending no `localStorage` = `action_id` do stream; solta; espera a narração; consultas `/operations/{op}` = 0; 1 stream.
   - `eco antes de qualquer rede`: `page.route` da consulta sem responder (pendurada) + `backend.delayStream()`; envia; o eco (`article.msg--player` com o texto, locator de `web/e2e/livro.spec.ts:16`) fica visível e há 1 stream; solta o stream; 1 narração.
   - `carta sem pending: 0 consultas`: no cenário de combate de `critical-journeys.spec.ts` (helper `combatActions`, `:600`), joga uma carta; consultas = 0; 1 ação enviada.
   - `pending existente consulta uma vez`: `failNextTurn`; envia; "Ação não confirmada"; anota a contagem; consulta roteada como `missing`; clica "Consultar / retomar ação pendente"; consultas a mais = 1 e o `action_id` do reenvio = o do envio que falhou.
   - `eco único após falha e retomada`: `failNextTurn`; envia; depois do banner, eco do texto = 0 e pending gravado; retoma (consulta roteada `missing`); eco = 1 e narração = 1.
   - Reforço: em `turn-retry.spec.ts:84`, acrescentar no fim a asserção eco do texto = 1.
2. **Implementação:** §3 em `App.tsx`.
3. **Verificação:** `cd web && npm run typecheck && npm run lint && npm test`; e2e do escopo com `--workers=2`: `e2e/turn-retry.spec.ts e2e/turn-wait.spec.ts e2e/pending-discard.spec.ts e2e/critical-journeys.spec.ts e2e/latency.spec.ts e2e/effects.spec.ts e2e/mobile-single-pane.spec.ts` (mais o arquivo novo, se houver). `bash scripts/dev/py.sh scripts/dev/size_budget.py` verde. Nada de suíte completa no executor.

### Etapa 3 — pouso

1. Coordenador: `npm run build`, `npm run test:e2e` completo 1× e suíte Python completa 1× (nenhum `.py` alterado; não deve mudar nada).
2. Revisão Sonnet (ou `spec-reviewer`, se o risco subir), com foco em R4, R5 e R8.

## 5. Critérios de aceite

- [x] Envio de texto e jogada de carta sem pending: 0 requisições a `/game/{game}/operations/{op}` (e2e).
- [x] Com a consulta pendurada, o eco do envio novo aparece (e2e).
- [x] Pending existente ("Consultar / retomar", "Tentar de novo", reload F14): a mesma consulta de hoje (e2e).
- [x] Mesmo `action_id` em todo reenvio de um pending (e2e existentes + novos).
- [x] Falha sem narração: 0 ecos; retomada: 1 eco e 1 narração (e2e).
- [x] `web/tests/pending.test.mjs` existente sem edição e verde; casos novos verdes.
- [x] `npm run typecheck`, `npm run lint`, `npm test`, e2e do escopo e `size_budget.py` verdes; `App.tsx` ≤ 965 linhas.
- [ ] `uv run pytest` verde (suíte completa offline, no pouso).
- [x] Guard de FallbackLLM: não se aplica (sem `with_structured_output` novo).
- [x] Saves antigos continuam carregando: não há mudança de save; pending `version: 1` antigo no `localStorage` continua lido (formato inalterado, R1).
- [ ] Smoke §6 registrado.

## 6. Smoke test real

Staging depois do deploy, conta logada, DeepSeek; só os turnos do roteiro (cerca de 4 turnos, centavos). Navegador com DevTools → Network, filtro `operations`.

1. Enviar 2 ações de texto. Conferir: nenhuma linha `GET /game/<id>/operations/<uuid>` antes do `POST /game/action/stream` (a linha `.../cost` depois do turno é esperada); o eco aparece no instante do Enter.
2. Entrar num combate e jogar 1 carta: idem item 1.
3. DevTools → Offline, enviar 1 ação: banner "Ação não confirmada", nenhum eco do texto, barra de ação pendente visível. Voltar online, "Consultar / retomar ação pendente": **1** `GET .../operations/<uuid>` com o mesmo uuid do `POST` que falhou; 1 eco, 1 narração.
4. Recarregar a página com um turno em voo e reabrir o save: 1 consulta na abertura, turno restaurado sem eco duplicado.
5. Opcional: comparar no Network o intervalo Enter → início do `POST /game/action/stream` antes e depois do deploy (esperado cair cerca de 0,35 s, valor da medição L0).

Registrar o resultado (prints do Network dos itens 1, 3 e 4) no handoff da revisão.

## Não rodou e por quê

- **Smoke §6 (staging):** não rodou. O staging está em `d7aa4beb` (10/11) e o próximo deploy depende de o dono aplicar as migrações das SPEC-413/410 (`ESTADO_ATUAL.md` § Bloqueios). Até lá a spec fica `in-progress`.
- **Vermelho → verde (22/11):** na `main`, 4 unit e 3 dos 4 e2e novos falham (1 consulta no envio novo; eco ausente com a consulta pendurada; 1 eco logo após a falha); na branch, todos passam. O 4º e2e (pending existente consulta 1 vez) é controle e passa antes e depois. Handoff: `handoffs/SPEC-420-terra-review.md`.
- Escrita da spec (13/11): nada foi executado pelo autor. As contagens "antes" da Etapa 0 vêm de leitura do source (`App.tsx:487,502-510`, `fixtures.ts:351-355,372-374`); o executor as confirma rodando os testes novos contra o código atual.
- O 0,35 s não é remedido aqui: vem de `docs/auditorias/latencia-turno-medicao-2026-11-13.md:48` (n=120). O item 5 do smoke é opcional.

## 7. Riscos & compatibilidade

- **Saves e pending antigos:** formato do `localStorage` inalterado; um pending gravado por versão anterior é lido como existente (`created === false`) e segue o fluxo com consulta.
- **MockLLM / FallbackLLM:** não se aplica; nenhuma mudança no servidor.
- **Latência:** menos uma ida e volta autenticada por turno e por jogada de carta (0,35 s medidos). Nenhuma requisição nova.
- **Risco principal:** um ramo de retomada perder a consulta e reenviar um turno já concluído. Mitigação: o critério é estrutural (`created` vem de quem gerou o id), as funções de retomada (R8) não são editadas e o servidor continua idempotente por `action_id` (um reenvio indevido com o mesmo id devolve a resposta gravada).
- **Mudança visível:** no erro sem narração o eco some (R5). Hoje, com a consulta antes do eco, "offline no Enter" já terminava sem eco; a R5 mantém esse resultado.

## 8. Decisões do dono

- **D1 — eco depois de falha sem narração.** **Recomendado: remover o eco que o próprio fluxo empurrou** quando o envio falha sem narração e o pending fica (R5); a barra de ação pendente continua oferecendo "Consultar / retomar" e "Descartar". Alternativa: manter o eco e deduplicar por `operation_id` na retomada (exige marcar a entrada do log e mexer também no descarte). A recomendação é a menor mudança e reproduz o resultado de hoje no caso offline; o coordenador pode aprovar pela recomendação.
  - **Decidida em 13/11 pelo coordenador, pela recomendação** (remover o eco, R5). O dono aprovou a spec e a execução em 13/11 ("pode. e execute elas"); veto continua possível.
