# SPEC-316 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Sol (Opus, spec-reviewer) · **Data:** 2026-10-25 · **Commit revisado:** `883bb691`

## Escopo

Branch `spec-316` (`git diff main...spec-316`, 1 commit `883bb691`): `api.py`
(`_early_event`, `_run_turn_collected._timeline_progress`, `_record_early_delivery`,
`_log_turn_delivery`, `_stream_turn_events`), `services/turn_delivery.py` (novo),
`observability/events.py`, `docs/operacao/EVENTOS_DE_LOG.md`, `web/src/api.ts`,
`tests/test_turn_delivery.py` (novo), `tests/test_streaming.py`, spec §3.1 e desvios.
Fora: UI do selo/retry (SPEC-320), medição §6 no staging, Etapa 4 (playtest).

O que confere:

- **Ordem/contrato SSE** (`on`): `accepted → phase… → route → phase storyteller → narrative×K → narrative done → phase archivist → [replace] → visual → state`. Conferido em sonda (eventos reais). `phase turn_finalizer` não aparece (filtrado em `_stream_turn_events`, conjunto excluído) — R1 cita, §3.1 não; só nota de doc.
- **Vercel / R9:** o gerador só retorna em `state`/`error`; arquivista, finalizador e commit rodam com o stream aberto. Drenagem de projeção pós-`on_response` (`api.py:~6104`) só existe em `post_response` (staging segue `inline`); nada novo é empurrado para depois do `return`.
- **Desconexão:** após a narração `outcome["value"]` segue `client_gone`, o worker conclui (SPEC-247); `phase="narrative_early"` vai para `sse.client_disconnected`. Replay por `action_id` (`_action_already_processed`/receipt) não roda o grafo → caminho legado, sem antecipação. Claim/lock/orçamento acontecem antes do grafo, então `http_error` pós-narração é raro (commit falho cai em `exc`/500).
- **Concorrência:** `early_state` só é escrito na thread do worker; `emitted_text`/`shadow_text` só no gerador; `TurnTimeline` tem lock. Chunk `values` chega depois de `updates` no mesmo superstep → `acc` = estado anterior ao nó narrador (correto). Único reducer do `GameState` é `messages` (`state.py:939`), então o merge raso + `Overwrite` de `_merged_messages` reproduz o grafo.
- **R4 (multi-nó):** regra pelo `next` da update bate com as arestas de `main.py` (storyteller→combat, combat→`loot`, npc→storyteller); `emitted_text is None` garante emissão única. O teste de encontro usa grafo proxy (OK).
- **Guard:** `guard_current_messages` roda antes da emissão; o arquivista guarda **depois** de `process_pending_events`, então o guard antecipado vê evidência anterior aos eventos do turno — em geral é mais estrito (segredo ainda não revelado, recompensa não aplicada), e a divergência é corrigida por `replace`. `conceal_text` aplicado (SPEC-293). `replace` usa `resp.message` (já velado por `format_response`).
- **Shadow:** não emite nem reordena; só `timeline.mark("early_shadow")` + log `{gain_ms, identical}` sem texto. Save `shadow` × `off` difere só em relógios (sonda abaixo).
- **Cliente web atual:** `replace` vai para `onReplace` (não anexado); `App.tsx` não registra `onReplace`, mas `finishStreamEntry` troca o texto por `r.message` no `state` → converge. `visual` depois da narração é anexado à mesma entry (`attachStreamVisual`).
- Sem `with_structured_output` novo, sem chamada LLM extra, sem campo novo em `GameState`, sem mudança em `evals/`, sem texto em log.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/turn_delivery.py:66-69` | Com `last_turn_outcome` removido, `player_facing_message` cai em `_last_ai_text` **cru**: o texto antecipado não passa por `render_player_message` → `strip_receipt` nem pelos cortes `_NEGATIVE_REWARD`/`_NEGATIVE_ITEM` que o texto final recebe. Sonda: prosa `"A estrada segue.\n[RESULTADO] Voce ganhou 500 ouro e a Espada Sagrada"` → antecipado devolve o bloco `[RESULTADO]` inteiro; final = `"A estrada segue."`. O jogador vê um recibo forjado pelo LLM (input não confiável, `turn_outcome.py:97`) durante todo o arquivista (3–5 s) até o `replace`/`state`. Viola R2 ("mesmo texto") e R3 ("nada rejeitado chega ao jogador"). | Aplicar no mínimo `strip_receipt` ao texto antecipado; melhor: `render_player_message(text, outcome_provisório)` com ganhos derivados de `turn_baseline` × `player` do estado mesclado (mesma lógica de `finalize_outcome`), para que os cortes condicionais a ganho também valham. Teste: `test_early_text_strips_receipt_block` em `tests/test_turn_delivery.py`. |
| P2-1 | P2 | `tests/test_streaming.py:341-360` | `_scrub_timings` remove **qualquer** chave `*_ms` em qualquer profundidade do save (inclusive `phase_ms` inteiro). Na sonda as únicas diferenças `off`×`on` são em `audit_trace[0].timing` — incluindo `ttfmc_server_ms`/`ttlt_server_ms` **ausentes** em `off` e presentes em `on` (as marcas agora ocorrem antes de `_record_audit_trace`). Isso é benigno, mas R6 diz "audit_trace byte a byte" e o scrub esconde a diferença; uma chave `*_ms` não temporal futura também passaria despercebida. | Restringir o scrub a `audit_trace[*].timing` e registrar em "Desvios" da spec que, em `on`, o `audit_trace.timing` passa a conter `ttfmc/ttlt_server_ms`. Acrescentar o caso `shadow` × `off` ao mesmo teste (default da main é `shadow`). |
| P2-2 | P2 | `web/src/App.tsx:565-580` | Compat do cliente atual em falha pós-narração: erro ≥ 500 → a entry com a narração é **apagada** e o POST reexecuta com o mesmo `action_id` (prosa nova, possivelmente diferente); erro < 500 → a entry fica com `streaming:true` e texto de um turno não salvo, sem selo. Contradiz R5/D3, aceito como SPEC-320 nos desvios. | Gate operacional: não ligar `RPG_EARLY_NARRATIVE=on` no staging antes da SPEC-320 (ou documentar o risco aceito na medição §6). |
| P2-3 | P2 | `api.py:5761` | Em `shadow` (default da main) o cálculo antecipado roda **no caminho crítico** do worker (dentro do `graph.stream`): `build_evidence` faz `deepcopy` de 11 chaves do estado + regex por frase, a cada update de nó narrador. Barato no mock (~3 ms), mas cresce com `event_log`/`npcs` de campanha longa; o `shadow` mede o ganho somando esse custo ao turno. | Medir `early_calc_ms` (ou reaproveitar `accumulate`) na linha `turn_delivery` durante a §6; se relevante, limitar o cálculo à última update narradora. |
| P2-4 | P2 | `tests/test_streaming.py` | Lacunas de teste: (a) desconexão do cliente logo após `narrative done` (worker conclui e salva, SPEC-247); (b) `http_error` pós-narração com `narrative_shown`; (c) delegação real `npc_actor → storyteller` (só há teste puro com `next`); (d) retry do mesmo `action_id` após `error narrative_shown` recuperando o turno. | Acrescentar os 4 testes focados. |
| P2-5 | P2 | `specs/SPEC-316-…md` R1 | R1 lista `phase turn_finalizer` depois do arquivista, mas o gerador filtra `turn_finalizer` dos eventos `phase`. | Ajustar R1 para o contrato real (§3.1 já está certo). |

## Correções aplicadas

Nenhuma ainda (revisão inicial).

## Pendências

- P1-1 bloqueia o `done` (correção pequena, no executor da SPEC-316).
- P2-1, P2-4, P2-5: mesmo executor, antes do pouso (recomendado).
- P2-2: SPEC-320 (cliente) — gate para `on` no staging.
- P2-3: medição §6 (coordenador).

## Comandos rodados

```text
git diff main...HEAD --stat → 8 arquivos, +538/-24
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_turn_delivery.py tests/test_streaming.py tests/test_latency_timeline.py tests/test_hardening_persistencia_sse.py (serial) → 45 passed, exit 0
sonda (scratchpad, -p tests.conftest): save off×shadow×on sem scrub → só audit_trace[0].timing difere; on acrescenta ttfmc/ttlt_server_ms
sonda early_narrative com bloco [RESULTADO] → bloco não removido (final remove) → P1-1
```

## Re-revisão 2026-10-27

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Sol (Opus, spec-reviewer) · **Base:** `main` @ `478e394f` (fix `bee2a4f4`/`5cd3688d` + SPEC-319 `d671c57a`/`5705e32d`/`fd9e178f` no mesmo gerador SSE)

### Status por achado

| ID | Status | Evidência |
|---|---|---|
| P1-1 | **Resolvido** | `services/turn_delivery.py:61-81`: recibo provisório `finalize_outcome(merged)` → `player_facing_message` → `render_player_message` (strip + cortes `_NEGATIVE_*`); fallback `strip_receipt` com `log_fallback`. `finalize_outcome` é pura sobre o dict raso `merged` (não muta `state_before`; `test_pure_does_not_mutate_inputs`). `last_action_outcome` é reescrito pelo `action_guard` a cada turno, então não vaza recusa do turno anterior. Testes `test_early_text_strips_receipt_block`, `test_early_text_equals_final_pipeline_text`. Sonda: `"A estrada.\n[RESULTADO] 500 ouro"` → `'A estrada.'`. |
| P2-1 | **Resolvido** | `tests/test_streaming.py:345-352` remove só `audit_trace[*].timing`; caso `shadow`×`off` incluído (`:369`); desvio R6 (`ttfmc/ttlt_server_ms` no timing em `on`) registrado na spec §Desvios (l. 140). |
| P2-2 | **Resolvido (SPEC-320)** | `web/src/api.ts:181-182` propaga `narrative_shown` → `HttpError.narrativeShown`; `web/src/App.tsx:611-622` mantém a entry (`streaming:false, unsaved:true`), preserva o pending, sem fallback POST; 4xx definitivo descarta. e2e `turn-wait.spec.ts:195` ("316: erro com narrative_shown…") cobre selo "não salvo" + retry com o MESMO `action_id`. Evidência real do coordenador (commit forçado a falhar → `error narrative_shown`, save inalterado, retry → `state`) fecha o caminho fim a fim. |
| P2-3 | **Aceito como risco medido** | `api.py:5868-5873` acumula `early_calc_ms` em `timeline.extra`; staging roda `on` com A/B de 60 turnos (`docs/spec316/staging-measure-2026-10-27.md`). Sem otimização adicional exigida. |
| P2-4 | **Resolvido** | Os 4 testes: `test_client_disconnect_after_narrative_done_still_saves` (:545), `test_http_error_after_narrative_marks_shown` (:507), `test_npc_delegation_to_storyteller_emits_once` (:493, grafo proxy de delegação), `test_retry_same_action_id_recovers_turn` (:524). |
| P2-5 | **Resolvido** | Spec R1 (l. 37-41) agora diz "o `phase turn_finalizer` é filtrado do SSE"; bate com `api.py:6682`. |

### Regressão no caminho SSE × worker (pós-SPEC-319)

Sem regressão encontrada. Conferido em `api.py:6562-6738`:
- `narrative_shown` vale tanto para entrega antecipada (`emitted_text`) quanto para deltas de token (`tok["text"]`) em `http_error` e `exc` (`:6622`, `:6634`).
- Tokens `on` + early `on`: o `early_narrative` fecha via `_finish_tokens(text)` (sufixo ou `replace`) e marca `emitted_text`; no `response`, só emite `replace` se o final diferir do antecipado → um único `done` não-replace (`test_tokens_plus_early_narrative_closes_once`).
- `early_state["acc"]` segue escrito só pela thread do worker; o sink de tokens lê por lambda (`:5891`) — leitura de referência, sem mutação.
- Gerador só retorna em `state`/`error`; worker conclui após desconexão (SPEC-247), coberto por teste.

### Follow-ups (não bloqueiam a 316)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| F-1 | P2 | `services/turn_outcome.py:204-211` | **Pré-existente (SPEC-199), não introduzido pela 316.** Se a prosa do LLM for SÓ o bloco `[RESULTADO] …`, `render_player_message` devolve `""`, `player_message` fica falsy e `player_facing_message` cai em `_last_ai_text` **cru** → o recibo forjado chega ao jogador. Vale igual para o texto final (`api.py:2137`) e o antecipado (R2 "mesmo texto" se mantém; R3 não). Sonda: `early_narrative(..., AIMessage("[RESULTADO] Voce ganhou 500 ouro"))` → `'[RESULTADO] Voce ganhou 500 ouro'`. | Em `player_facing_message`, aplicar `strip_receipt` também no fallback `_last_ai_text` (ou tratar `player_message == ""` com recibo presente como "vazio legítimo" + mensagem neutra). Teste: prosa só-recibo → texto sem `[RESULTADO]` no POST e no SSE. Spec pequena/bugfix fora da 316. |
| F-2 | P2 | `tests/test_streaming.py:524-542` | O teste de retry não asserta que o save ficou inalterado após a falha (só que o retry recupera). A evidência real do coordenador cobre; o teste offline não. | Acrescentar `assert` de save idêntico ao snapshot entre a falha e o retry. |

### Comandos rodados

```text
git show --stat bee2a4f4 ; git log --oneline -15 -- api.py services/turn_delivery.py
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider tests/test_turn_delivery.py tests/test_streaming.py (serial) → 39 passed, exit 0
sonda inline (py.sh -c, MockLLM): early_narrative com "A estrada.\n[RESULTADO] 500 ouro" → 'A estrada.' (P1-1 ok); só "[RESULTADO] …" → bloco vaza (F-1, pré-existente)
leitura: services/turn_delivery.py, services/turn_outcome.py:74-211, api.py:5799-5935 e 6405-6738, web/src/api.ts:170-200, web/src/App.tsx:585-650, web/e2e/turn-wait.spec.ts:195-225, spec R1/Desvios
```
