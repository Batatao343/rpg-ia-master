# SPEC-316 — Latência: narração entregue antes do arquivista e do commit (stream aberto)

> **Status:** `done` (aprovada 25/10; pousada 25/10; `on` no staging; A/B 27/10 em `docs/spec316/staging-measure-2026-10-27.md`; re-revisão Sol 27/10 APPROVED_WITH_FOLLOWUPS)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-27
> **Depende de:** SPEC-036 (`done`, SSE), SPEC-200 (`done`, marcas ttfmc/ttlt), SPEC-213 (`done`, projeções), SPEC-247 (`done`, worker SSE sobrevive à desconexão)
> **Desbloqueia:** SPEC-318 (trabalho fora do caminho crítico), SPEC-319 (streaming de tokens e cauda)
> **Origem:** investigação de latência 2026-10-25 (relatório do coordenador, oportunidade #1)
> **EXECUTOR_MODEL:** `Sol` (concorrência SSE × worker, semântica de recibo) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` (nenhum evaluator/dataset protegido muda)

---

## 1. Contexto & Objetivo

O jogador vê a narração em **11,1 s p50 / 25,5 s p95** no staging (DeepSeek, SSE, n=30,
[medição](../docs/spec213/staging-measure-2026-10-18.md)). Desses, o narrador FAST responde em 4,1 s p50; o
resto é trabalho que **não produz texto**: fase `archivist` 3,35 s p50 / 4,8 s p95 (SMART + memória),
`turn_finalizer`, fase PERSISTENCE e commit (≈0,3–0,8 s). Playtests reais de 23–24/10 confirmam
(`archivist` p50 4,2–4,8 s em `playtest_runs/20261024-232054-228681/report.md:45`).

O SSE da SPEC-036 é **pseudo-streaming**: `_stream_turn_events` só emite `narrative` quando `_execute_action`
devolve a `GameResponse` (`api.py:6416-6429`), e `_execute_action` só chama `on_response` depois de `_run_turn`
terminar o grafo inteiro e o commit (`api.py:6062-6076`, `:5746-5788`; `main.py:154-155`). Logo
TTFMC = TTLT ≈ 11 s.

A SPEC-213 tentou tirar o arquivista do caminho com `post_response`, mas o trabalho rodava **depois do stream
fechar**: na Vercel a instância congela ao fim da resposta, a chamada SMART para no meio e vira `lock_wait`
de 3 s no turno seguinte (ganho visível −1,7 %; p95 +2,9 s; medição §"Por quê"). Esta spec faz o oposto:
**emite a narração assim que o nó narrador termina e mantém o stream aberto** enquanto arquivista,
finalizador e commit rodam; o evento `state` continua fechando o turno. A função serverless não congela
porque a resposta HTTP ainda não terminou. Modo `inline` do arquivista permanece — nada vira job.

Alvo: TTFMC p50 ≤ 7 s (−35 %) sem mudar estado final, save ou `GameResponse` (byte a byte).

## 2. Requisitos

- **R1 — Entrega antecipada no SSE.** Em `/game/action/stream`, os eventos `narrative` saem quando o
  chunk `updates` do nó narrador (`storyteller`, `npc_actor`, `combat_agent`, `loot_agent`) chega ao
  gerador, antes dos eventos `phase` de `archivist`/`turn_finalizer`. Ordem garantida:
  `accepted → phase/route… → narrative(chunks) → narrative(done) → phase archivist → [narrative replace] →
  visual → state` (o `phase turn_finalizer` é filtrado do SSE). `POST /game/action` não muda.
- **R2 — Texto idêntico.** O texto emitido antecipadamente é `player_facing_message({**state, **update})`
  (`services/turn_outcome.py:204`) aplicado ao estado acumulado após a update do nó. Ao final, se
  `resp.message` diferir do texto já emitido (guard alterou a prosa), o servidor emite
  `narrative {"chunk": <texto final>, "done": true, "replace": true}` e o cliente substitui o texto.
- **R3 — Guard antes da exibição.** `guard_current_messages` roda sobre a update do nó narrador ANTES de emitir
  (função pura; hoje em `archivist.py:320` e `turn_finalizer.py:12`). O arquivista e o finalizador continuam
  rodando o guard (idempotente); o texto exibido é o guardado. Nenhum texto rejeitado pelo guard chega ao
  jogador.
- **R4 — Turnos com mais de um nó narrando.** Encontro `storyteller → combat_agent`, vitória
  `combat_agent → loot_agent` e delegação `npc_actor → storyteller` emitem a narração **uma vez só**, a partir da
  última update que altera `player_facing_message`; updates intermediárias com `SystemMessage`
  (`storyteller.py:1309`) não emitem. Regra: emitir quando `next` da update não aponta para outro nó narrador.
- **R5 — Falha depois da narração.** Se o worker falhar após `narrative(done)` (archivist, commit, lock), o
  evento `error` leva `"narrative_shown": true`. O cliente mantém o texto no log com selo "não salvo" e
  oferece "tentar de novo" reenviando o **mesmo `action_id`** (replay por `action_id` já existe,
  `api.py:6044`, `:6285-6288`). Nenhum texto é apagado da tela pelo servidor.
- **R6 — Estado final byte a byte.** Com a flag `on` ou `off`, `GameResponse`, save e `audit_trace`
  são idênticos ao HEAD para o mesmo seed/MockLLM (só a ordem dos eventos SSE muda).
- **R7 — Marcas.** `ttfmc`/`ttlt` passam a ser marcadas no primeiro/último chunk antecipado
  (`api.py:6423-6428`); `state` continua no evento final. `turn_delivery` ganha `early_narrative: bool`
  e `early_gain_ms` = `state_ms − ttlt_ms` (tempo que o jogador ganhou).
- **R8 — Kill switch.** `RPG_EARLY_NARRATIVE=off|shadow|on`. `off` = comportamento atual. `shadow` =
  calcula o texto antecipado e `early_gain_ms`, loga `sse.early_narrative_shadow {gain_ms, identical}` e
  **não** emite cedo. `on` = R1–R7. Default **`shadow`** até a medição §6; staging vai a `on` após a medição.
- **R9 — Vercel.** O gerador SSE só retorna depois do evento `state` ou `error` (já é assim); nenhum
  trabalho do turno fica para depois do `return` do gerador (diferença essencial da SPEC-213 modo A).
- **R10 — Cliente.** `web/src/App.tsx` (`onChunk`, ≈L554) mantém `busy=true` até `state`; mostra o selo
  "o escriba registra…" ao lado do texto entre `narrative(done)` e `state`; aceita `visual` depois da narração
  (hoje vem antes, `api.py:6419`) e `replace: true`. Fallback POST inalterado.

### Fora de escopo

- Streaming de tokens do LLM (SPEC-319). Tirar NPC novo/replan/`narrate_day` do nó narrador (SPEC-318).
- Mudar o modo de projeção (`RPG_PROJECTION_MODE` segue `inline`). Qualquer worker/job novo.
- Alterar prompts, mecânica, evaluators ou datasets.

## 3. Design técnico

- **Novo** `services/turn_delivery.py` (puro, sem I/O):
  - `NARRATING_NODES = {"storyteller", "combat_agent", "npc_actor", "loot_agent"}`
  - `early_narrative(state_before: dict, update: dict) -> str | None` — aplica `guard_current_messages`
    sobre `{**state_before, **update}` (respeitando `Overwrite` de `messages`), devolve
    `player_facing_message(...)` ou `None` se a update não narra (R4: `update.get("next") in NARRATING_NODES`
    ⇒ `None`; última mensagem não `AIMessage` ⇒ `None`).
  - `early_mode() -> Literal["off","shadow","on"]` (lê `RPG_EARLY_NARRATIVE`, default `shadow`).
  - `narrative_chunks(text: str, size: int = 80) -> list[str]`.
- **Alterado** `api.py`:
  - `_run_turn_collected._timeline_progress` (`:5728-5740`): mantém um `accumulated` (estado corrente a
    partir dos chunks `values`) e, para chunk `updates` de nó narrador, chama `early_narrative` e repassa ao
    `progress` um chunk sintético `("early_narrative", {"text": str, "node": str})`.
  - `_stream_turn_events` (`:6406-6433`): trata `early_narrative` → emite chunks (`ttfmc`/`ttlt`), guarda
    `emitted_text`; no `response`, se `emitted_text is None` segue o caminho atual; senão compara com
    `resp.message` (R2) e emite `visual` + `state`. `shadow` só loga.
  - `_worker` (`:6313-6369`): `except` depois da narração emitida → payload do `error` com
    `narrative_shown: true` (R5).
- **Alterado** `observability/latency.py`: campos `early_narrative`, `early_gain_ms` na linha `turn_delivery`.
- **Alterado** `web/src/api.ts` (`handleEvent`, ≈L170): `narrative.replace`, `visual` após narração;
  `web/src/App.tsx`: selo "ainda salvando", erro com `narrative_shown`, retry com mesmo `action_id`.
- **Sem schema novo de estado.** Nenhum campo em `GameState`; saves inalterados.

### 3.1 Contrato SSE para o cliente (SPEC-320 implementa contra isto)

Sequência com `RPG_EARLY_NARRATIVE=on` (`off`/`shadow` = ordem legada da SPEC-036, sem `replace`):

```text
accepted {game_id}
phase {node, status:"done"}  ×N   (campaign_manager, dm_router, ...)
route {route}
phase {node:"storyteller"|"combat_agent"|"npc_actor"|"loot_agent"}
narrative {chunk, done:false}  ×K      <- texto final já guardado (≤ 80 chars/chunk)
narrative {chunk:"", done:true}        <- "estágio": narração entregue, turno ainda NÃO salvo
phase {node:"archivist"}               <- o escriba registra… (até o evento state)
[narrative {chunk:<texto final>, done:true, replace:true}]   <- só se o texto final difere
visual {…}                              <- agora DEPOIS da narração (antes vinha antes)
state {GameResponse}                    <- turno commitado; libera o input
```

- Narração é emitida **uma vez** por turno (o 1º nó narrador terminal); updates posteriores não emitem.
- Selo "o escriba registra…": visível entre `narrative done:true` (sem `replace`) e `state`.
- `replace:true` traz o texto **inteiro** que substitui o exibido; nunca deve ser anexado ao anterior.
  Cliente antigo que ignora `done` em `narrative` e troca o texto no `state` continua correto.
- `error` após narração leva `narrative_shown:true` (além de `detail/code/error_code/request_id`):
  manter o texto com selo "não salvo" e oferecer retry com o **mesmo** `action_id`.
- `error` sem `narrative_shown` = nada foi mostrado; fluxo atual (fallback POST).
- `web/src/api.ts` já roteia `replace` para `handlers.onReplace` (e **não** para `onChunk`).

### Desvios da implementação (25/10)

- `early_narrative(state_before, update, node="")` ganhou `node` (um nó narrador não se auto-suprime
  pelo próprio `next`); `next="loot"` (router) é tratado como `loot_agent`.
- O texto antecipado descarta `last_turn_outcome` do estado (é o recibo do turno **anterior**), usa um
  recibo provisório (`finalize_outcome` sobre o estado parcial → `render_player_message`: `[RESULTADO]` forjado
  e cortes de ganho/item valem antes do arquivista; revisão P1-1) e aplica
  o mesmo véu de exibição do `format_response` (SPEC-293, `conceal_text`).
- `early_narrative`/`early_gain_ms` saem na linha `turn_delivery` (montada em `api._log_turn_delivery`,
  não em `observability/latency.py`). `early_gain_ms` em `shadow` é hipotético (`state` − texto pronto).
- Evento novo de log: `sse.early_narrative_shadow {gain_ms, identical}`; falha do cálculo =
  `sse.fallback early_narrative_failed` (o turno segue pelo caminho legado).
- R6: em `on` o `audit_trace[*].timing` ganha `ttfmc_server_ms`/`ttlt_server_ms` (as marcas existem antes de
  gravar a trilha); é a única diferença de save (o teste compara `off`/`shadow`/`on` removendo só `timing`).
- Custo do cálculo antecipado no caminho crítico (inclui `deepcopy` de `build_evidence`): medido em
  `timeline.extra["early_calc_ms"]` (campo do log `rpg.turn`); conferir na §6 e, se relevante, limitar à
  última update narradora. Só roda no stream (POST não calcula).
- Cliente: só `api.ts` (`onReplace`). Selo, `narrative_shown` e retry na UI ficam na SPEC-320 (o fluxo
  atual já cai no POST com o mesmo `action_id` em erro ≥ 500). Etapa 4 (playtest) não rodada: o runner
  usa `app.invoke`, que este código não toca.

## 4. Plano passo a passo

### Etapa 1 — Função pura de entrega
1. **Testes** (`tests/test_turn_delivery.py`): `test_story_update_yields_guarded_text` (update com
   `AIMessage` → texto = `player_facing_message`); `test_system_message_update_yields_none`
   (`COMBAT START` → `None`); `test_update_routing_to_another_narrator_yields_none` (`next="combat_agent"`);
   `test_guard_rejection_changes_text` (mensagem com NPC morto é limpa pelo guard e o texto devolvido é o
   guardado); `test_mode_default_is_shadow`.
2. **Implementação:** `services/turn_delivery.py`.

### Etapa 2 — SSE antecipado atrás da flag
1. **Testes** (`tests/test_streaming.py`, estender): `test_early_narrative_before_archivist_phase` (`on`:
   índice do 1º `narrative` < índice de `phase archivist`); `test_shadow_mode_keeps_order_and_logs`;
   `test_off_mode_byte_identical_to_head`; `test_final_state_identical_on_vs_off` (R6: mesmo seed MockLLM,
   compara `state` JSON e save); `test_replace_event_when_guard_changes_text`;
   `test_encounter_turn_emits_narrative_once` (storyteller→combat); `test_error_after_narrative_marks_shown`
   (monkeypatch `_commit_turn` levantando → `error.narrative_shown is True`, texto não removido do stream).
2. **Implementação:** `api.py` conforme §3; `latency.py` campos novos.
3. **Verificação:** `uv run pytest tests/test_turn_delivery.py tests/test_streaming.py tests/test_latency_timeline.py tests/test_hardening_persistencia_sse.py -n 2`.

### Etapa 3 — Cliente
1. **Testes** (`web/src/__tests__/stream.test.ts` ou equivalente Node): `replace: true` substitui texto;
   `visual` após `narrative` anexa ao mesmo entry; `error` com `narrative_shown` mantém entry + selo; retry
   reenvia o mesmo `action_id`. Playwright: 1 jornada "narração aparece antes do selo sumir".
2. **Implementação:** `api.ts`, `App.tsx`, `StoryLog.tsx` (selo).

### Etapa 4 — Playtest e medição offline
1. `uv run python -m playtest run --all --turns 30` com `RPG_EARLY_NARRATIVE=on` (runner usa `app.invoke`; só
   confirma paridade de estado); harness da SPEC-200 (`tests/test_latency_baseline_offline.py`) com latência
   injetada: `ttfmc` cai pelo valor injetado no archivist.

## 5. Critérios de aceite

- [x] R1–R10 cobertos pelos testes nomeados; `uv run pytest` verde (suíte completa offline, 1×, no pouso).
- [x] `test_final_state_identical_on_vs_off` prova R6 (save + `GameResponse` iguais).
- [x] Medição §6 no staging (27/10, 30+30 turnos: TTFMC p50 2,6 s; p95 11,2 × 25,1 s; `state` p50 10,1 × 10,9 s — melhor, não pior; `lock_wait` p50 55–58 ms): **TTFMC p50 ≤ 7 s** (de 11,1 s) e p95 não pior que o baseline em mais de 10 %;
  `state` p50 dentro de ±5 % do baseline (nada foi empurrado para o turno seguinte: `lock_wait` p50 < 150 ms).
- [x] Zero `narrative_shown` em 30 turnos sem falha induzida (29/29 `ok`); falha induzida 27/10 com DeepSeek real, local (commit forçado a falhar → `error` com `narrative_shown`, save inalterado, retry com o mesmo `action_id` → `state`) + e2e do selo/retry no cliente; 1 falha induzida mostra o selo e o retry recupera.
- [x] Nenhum `with_structured_output` novo. Saves antigos carregam (nenhum campo novo).
- [x] Revisão independente (Sol) do caminho SSE × worker (`handoffs/SPEC-316-sol-review.md`, re-revisão 27/10).

## 6. Smoke test com LLM real

Staging Vercel, DeepSeek, mesmo protocolo da SPEC-213: `scripts/staging/projection_measure.py --label
early_{off,on} --turns 15 --think 8` (2 sessões por modo, 30 turnos/modo; o script já coleta `accepted`,
1º chunk, `done`, `state` e `lock_wait_ms`). **Gate de rollout (revisão P2-2):** não ligar `RPG_EARLY_NARRATIVE=on` no staging antes da SPEC-320 (o
cliente atual apaga a entrada e refaz via POST em erro ≥ 500 após a narração) ou registrar o risco aceito
na medição. Teto **US$ 0,15** (≈60 turnos × ~US$ 0,002). Registrar em
`docs/spec316/staging-measure-<data>.md` com a tabela p50/p95 de `ttfmc`, `ttlt`, `state`, `lock_wait`,
`early_gain_ms`. Conferir no browser (Chromium 1440): texto aparece com o selo "o escriba registra…", selo
some no `state`, input libera só no `state`.

## 7. Riscos & compatibilidade

- **Por que isto funciona na Vercel e a SPEC-213 não:** o modo A drenava após o `return` do gerador (stream
  fechado ⇒ instância congelada). Aqui todo o trabalho acontece **dentro** do stream; o cliente só perde
  tempo de leitura, não o turno. Se o cliente desconectar após a narração, o worker conclui o save (SPEC-247).
- **Texto mostrado e turno falho (R5):** o jogador vê prosa de um turno que não existe no save. Mitigação:
  selo "não salvo" + retry com o mesmo `action_id`; replay devolve a resposta commitada, se houver.
- **Guard:** o texto só sai depois de `guard_current_messages` (R3); `validate_narrative` do resumo/crônica
  continua no arquivista (não afeta a prosa exibida). Regra de ouro (SPEC-308) intacta: o filtro é no
  contexto, antes do LLM.
- **Mecânica** determinística inalterada; nenhum número vem do LLM por este caminho.
- **MockLLM/FallbackLLM:** sem chamada nova; `FallbackLLM` devolvendo `AIMessage` de erro passa pelo mesmo
  guard e sai como hoje.
- **Latência/custo:** zero chamadas extras; `visual` passa a chegar depois da narração (cliente ajustado).
- **Compat de cliente antigo:** cliente que ignora `replace`/`narrative_shown` continua funcionando (eventos
  conhecidos, só reordenados); `off` restaura byte a byte.

## 8. Decisões do dono

- **D1 — Default da flag:** **`shadow` na main; `on` no staging após §6**; `on` na main só com a medição anexa.
- **D2 — UX após narração:** **selo discreto "o escriba registra…" junto ao texto; input bloqueado até `state`**
  (alternativa: liberar input na narração — rejeitada, pois o próximo turno esperaria o lock e a mensagem do
  jogador entraria antes do save).
- **D3 — Falha pós-narração:** **manter o texto com selo "não salvo" + botão "tentar de novo" (mesmo `action_id`)**
  (alternativa: apagar o texto — rejeitada: pior percepção e perde o que o LLM já produziu).
- **D4 — Guard alterou o texto:** **substituir silenciosamente (`replace: true`)** sem aviso ao jogador
  (alternativa: mostrar aviso — rejeitada, caso raro e confuso).

## Histórico de mudanças

- 25/10 — aprovada pelo dono ("boa, aprovo"), padrões recomendados.
- 25/10 — implementada (`883bb691`); revisão Sol CHANGES_REQUIRED (P1-1 recibo cru no texto antecipado; P2-1..5) → corrigida em `bee2a4f4`.
- 25/10 — pousada na main com `RPG_EARLY_NARRATIVE` no default `shadow` (zero mudança para o jogador; mede `early_gain_ms`/`early_calc_ms`). Suíte completa verde. `done` só depois da medição §6 com `on` no staging, que por P2-2 espera a SPEC-320 (cliente com selo/"não salvo"/retry).
- 25/10 — **medição §6 no staging** (`1c0e7d12`, `RPG_EARLY_NARRATIVE=on`, DeepSeek, `projection_measure.py --turns 15 --think 8`, 2 sessões, `checks.all_ok=true`): primeira narração p50 **8,2 s / 6,8 s** vs `state` p50 10,9 s / 10,7 s na mesma sessão (ganho −2,6 a −3,8 s; baseline SPEC-213 11,1 s). Meta R§6 ≤ 7 s p50 batida em 1 de 2 sessões (média ~7,5 s) → **não marca `done` ainda**; remedir após a SPEC-318. p95 35–44 s dominado por cold start (ack p95 28–39 s) → SPEC-319 (hedge) e bundle (SPEC-317 R11/R12). Artefatos: `scratchpad/m316_on_{1,2}.json` da sessão do coordenador.
- 26/10 — remedição no staging `e9b5f000` (316 on + 317 shadow + 318 + 319 shadow), 2 sessões × 15 turnos: primeira narração p50 **7,5 s / 6,7 s**, p95 26,8 / 21,5 s (antes 35–44 s); `state` p50 13,3 / 9,5 s; checks all_ok. Meta ≤ 7 s p50 batida em 1 de 2 sessões; cauda caiu ~40 %.
- **2026-10-26 (noite, staging `9775ea1`, `RPG_EARLY_NARRATIVE=on` + `RPG_TOKEN_STREAM=on`):** 55 turnos reais
  (`projection_measure` 3×15 + smokes): `turn_delivery` 53 `ok` com narração antecipada, 2 `ok` replay; **0 erro com
  `narrative_shown`**. 1ª narração no cliente p50 3,1–4,4 s (meta ≤ 7 s ✔; era 11,1 s). p95 8,8–11,7 s nas sessões sem
  cold start; nas com instância nova do Vercel o `ack` chega a 19–63 s (fora desta spec, ver SPEC-317 §6.3).
  Falta: 1 falha induzida no staging (selo + retry com o mesmo `action_id`).
- 27/10 — A/B OFF×ON intercalado 2× no staging (60 turnos, [docs/spec316/staging-measure-2026-10-27.md](../docs/spec316/staging-measure-2026-10-27.md)). 1ª narração p50 8,2–11,4 s → 2,6 s;
  p95 15,5–26,1 s → 9,8–11,8 s (melhor, não pior). **Estado final (input liberado) sem ganho**: p50 8,2–11,4 ×
  9,8–11,4 s, p95 15,5–26,1 × 17,0–17,1 s (empate no ruído). 29/29 entregas antecipadas `ok`, 0 `narrative_shown`.
  Segue `in-progress`: falta 1 falha induzida no staging (selo + retry).
- 27/10 — Falha induzida: local com DeepSeek real (o staging não tem gancho de falha); servidor ok e e2e do cliente
  (`turn-wait.spec.ts` "316: erro com narrative_shown") verde. Re-revisão Sol das correções de `bee2a4f4`:
  APPROVED_WITH_FOLLOWUPS — F-1 (pré-existente, SPEC-199: resposta só com `[RESULTADO]` chega crua; `strip_receipt`
  no fallback de `player_facing_message`, bugfix separado) e F-2 (assert de save inalterado no teste offline do
  retry). → **`done`**.
