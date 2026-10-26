# SPEC-319 — Latência: streaming de tokens do `narrative` e hedge na cauda do narrador

> **Status:** `in-progress` (aprovada 25/10; implementada + revisão Sol 2 rodadas (APPROVED_WITH_FOLLOWUPS, F-1/F-2 feitos); pousada na main 26/10 com `RPG_TOKEN_STREAM=shadow` e hedge 0; falta medição §6 no staging)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-25
> **Depende de:** SPEC-316 (`done` — canal de narração antecipada no SSE e UX de "ainda salvando"); recomendado SPEC-318 (`done`) para o ganho pleno; insumos `done`: SPEC-032 (RoutedLLM), SPEC-236 (`stream_interrupted`), SPEC-250 (fallbacks silenciosos)
> **Desbloqueia:** —
> **Origem:** investigação de latência 2026-10-25 (oportunidades #2 e #8)
> **EXECUTOR_MODEL:** `Sol` (parser incremental, concorrência de providers, guards) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Depois da SPEC-316 o jogador ainda espera o narrador FAST **inteiro** (4,1 s p50 / 16,4 s p95 no staging,
`docs/spec213/staging-measure-2026-10-18.md`) antes de ver a primeira palavra. A SPEC-036 descartou streaming
de tokens porque a narração nasce dentro de `with_structured_output(StoryUpdate)` e "parcial de JSON não é
confiável entre 6 providers". Dois fatos mudam a conta:

- `narrative` é o **primeiro campo** de `StoryUpdate` (`agents/storyteller.py:96`); com `function_calling`
  (injetado para todo provider OpenAI-compat em `RoutedLLM._apply`, `llm_setup.py:690`) os deltas de argumentos
  da tool call começam em `{"narrative": "…`. Extrair essa string incrementalmente é um parser pequeno e
  determinístico; o Pydantic completo valida no fim como hoje.
- `RoutedLLM.stream` já existe com fallback por provider e `stream_interrupted` (`llm_setup.py:1065-1190`) e
  **nenhum agente o usa**.

Cauda: o narrador p95 é 16 s com timeout DeepSeek de 12 s (`llm_setup.py:456-460`) seguido de fallback Groq
**em série** — o p95 do jogador chega a 25 s. Um hedge (2º candidato disparado em paralelo quando o 1º não
emitiu o primeiro token em N ms) troca custo raro por cauda curta.

Alvo: TTFMC p50 de ~7 s (pós-316) para **≤ 3 s** (router + contexto + TTFT do provider); TTLT inalterado;
p95 do `done` −30 %. Só para o provider primário OpenAI-compat; os demais caem no pseudo-streaming da 316.

## 2. Requisitos

- **R1 — Extrator incremental puro.** `services/partial_narrative.py::NarrativeExtractor` recebe deltas de
  texto da tool call (ou do conteúdo JSON) e devolve o trecho novo de `narrative` já **desescapado**
  (`\"`, `\\`, `\n`, `\uXXXX`, pares surrogate), parando no fechamento da string. Deltas que cortam no meio de
  uma sequência de escape não emitem até completar. Chave ausente/ordem diferente ⇒ não emite nada (fallback 316).
- **R2 — Streaming no narrador.** `storyteller_node`, `npc_actor_node`, narração do `combat_node` e do
  `loot_node` usam `RoutedLLM.stream` quando `RPG_TOKEN_STREAM=on`, o candidato ativo está em
  `_OPENAI_COMPAT_PROVIDERS` e há um `narrative_sink` ligado (contextvar da API). Cada trecho vai ao sink; ao
  fim, os chunks são juntados e passam pelo mesmo `with_structured_output`-equivalente (parse do JSON completo
  em `StoryUpdate`, com guard `isinstance`). Sem sink (CLI, playtest, POST) ⇒ `invoke` como hoje.
- **R3 — Texto final manda.** Após o parse, `player_facing_message` do estado resultante é comparado ao texto
  streamado (pós-guard, 316 R3). Diferença ⇒ evento `narrative {replace: true}` (316 R2). Guard rejeitou ⇒
  `replace` com o texto guardado. O texto parcial nunca entra em `messages`/save.
- **R4 — Falha no meio do stream.** `stream_interrupted`/`stream_error` ⇒ `RoutedLLM` já cai para o próximo
  candidato; o sink recebe `reset` e o cliente limpa o parcial (evento `narrative {chunk:"", reset:true}`).
  Esgotados os candidatos ⇒ `AIMessage` de erro como hoje (guard de FallbackLLM obrigatório).
- **R5 — Hedge na cauda.** `RPG_LLM_HEDGE_MS=<int>` (0 = off, default **0**). Só no tier FAST com stream
  ativo: se o 1º candidato não emitiu nenhum delta após N ms, dispara o 2º em paralelo; o primeiro a emitir
  delta vence, o outro é abandonado (a request HTTP termina sozinha — SPEC-143 §2.6; o custo conta em
  `usage_events` com `outcome="hedge_lost"`). Máximo 1 hedge por chamada; telemetria `hedged`, `hedge_won`.
- **R6 — Marcas e métricas.** `ttfmc` = 1º delta não vazio; novo `rpg_turn_first_token_seconds`;
  `turn_delivery.pseudo_streaming=false` quando houve token real. SPEC-200 `TTFT ≡ TTFMC` deixa de valer e
  o `README` da 200 ganha nota.
- **R7 — Cliente.** `useTypewriter` segue os tokens: sem atraso artificial enquanto chegam deltas; ao receber
  `done` revela o resto com o ritmo atual; `reset` limpa o entry; `replace` substitui.
- **R8 — Kill switch.** `RPG_TOKEN_STREAM=off|shadow|on`. `shadow` = faz o stream, **não** envia deltas, loga
  `ttft_shadow_ms` e `identical_to_final`. Default **`shadow`** até §6; staging `on` após medição.
- **R9 — Paridade.** Com `off`, byte a byte ao HEAD. Com `on` e MockLLM, `MockLLM.stream` (a adicionar, gera
  deltas a partir do mesmo texto) produz o mesmo estado final que `invoke`.

### Fora de escopo

- Streaming de outros campos ou de outros tiers (CLASSIFY/SMART). Streaming no POST clássico/CLI.
- Providers não OpenAI-compat (Anthropic/Gemini) — ficam no pseudo-streaming.
- Mudar schema de `StoryUpdate`/`NPCResponse` (a ordem dos campos é pré-condição: teste R10 trava isso).
- **R10 (invariante, não feature):** teste que falha se `narrative` deixar de ser o 1º campo dos schemas de narração.

## 3. Design técnico

- **Novo** `services/partial_narrative.py`: `class NarrativeExtractor: feed(delta: str) -> str` (trecho novo
  desescapado ou `""`), `done: bool`, `found: bool`; `KEY = "narrative"`. Estados: `seek_key → seek_quote →
  in_string(escape_buf) → closed`. Sem regex em texto acumulado (O(n)).
- **Novo** `services/narrative_sink.py`: contextvar `_SINK`; `bind(sink) -> Token`, `emit(text)`, `reset()`,
  `active() -> bool`. A API liga o sink ao `progress` do turno (chunk sintético `("narrative_delta", {...})`),
  consumido pelo `_stream_turn_events` da 316.
- **Alterado** `llm_setup.py`: `RoutedLLM.stream_structured(messages, schema) -> schema | AIMessage` — itera
  `stream`, acumula `tool_call_chunks[].args` (ou `content` quando o provider devolve JSON no conteúdo), chama
  o extractor, no fim `schema.model_validate_json(args)`; aplica R5 quando `RPG_LLM_HEDGE_MS>0` (thread do 2º
  candidato + `queue.Queue` de deltas; vence o primeiro delta). Telemetria por tentativa como `invoke`.
- **Alterado** `agents/storyteller.py:1688-1692`, `agents/npc.py:1251`, `agents/combat.py:978`, `agents/loot.py:117`:
  `_narrate(llm, schema, msgs)` helper escolhe `stream_structured` vs `with_structured_output(...).invoke`.
- **Alterado** `mock_llm.py`: `stream` que fatia a resposta estruturada em deltas JSON (3–12 chars) para testes.
- **Alterado** `api.py` (`_stream_turn_events`): trata `narrative_delta`/`reset`; `web/src/api.ts`, `useTypewriter.ts`.
- **Flags:** `RPG_TOKEN_STREAM`, `RPG_LLM_HEDGE_MS`. Sem campo novo em `GameState`.

## 4. Plano passo a passo

### Etapa 1 — Extrator (R1, R10)
1. **Testes** (`tests/test_partial_narrative.py`): `test_plain_string`; `test_escapes_split_across_deltas`
   (`\"` e `ç` cortados); `test_surrogate_pair`; `test_stops_at_closing_quote_and_ignores_rest`;
   `test_missing_key_emits_nothing`; `test_key_not_first_emits_nothing`; `test_one_char_deltas_equal_whole`
   (propriedade: concatenação dos trechos == campo parseado pelo `json.loads` para 50 fixtures PT-BR com acentos);
   `tests/test_schema_order.py::test_narrative_is_first_field` para `StoryUpdate`, `NPCResponse` e schemas de combate/loot.
2. **Implementação:** `services/partial_narrative.py`.

### Etapa 2 — `stream_structured` e MockLLM (R2, R4, R9)
1. **Testes** (`tests/test_stream_structured.py`): `test_mock_stream_equals_invoke_state` (R9);
   `test_interrupted_stream_falls_back_and_resets_sink`; `test_no_sink_uses_invoke`;
   `test_non_openai_compat_uses_invoke`; `test_fallbackllm_returns_aimessage_guarded`.
2. **Implementação:** `llm_setup.py`, `mock_llm.py`, helper `_narrate` nos 4 agentes.

### Etapa 3 — SSE e cliente (R3, R6, R7, R8)
1. **Testes** (`tests/test_streaming.py`, estender): `test_token_deltas_arrive_before_node_phase`;
   `test_replace_when_guard_changes_streamed_text`; `test_shadow_logs_ttft_without_deltas`;
   `test_off_byte_identical`; `tests/test_latency_timeline.py`: `pseudo_streaming=false` + `first_token`.
   Node: `useTypewriter` com deltas (sem atraso), `reset`, `replace`.
2. **Implementação:** `api.py`, `narrative_sink.py`, `api.ts`, `useTypewriter.ts`.

### Etapa 4 — Hedge (R5)
1. **Testes** (`tests/test_llm_hedge.py`, provider fake com latência injetada): `test_hedge_not_started_when_first_token_in_time`;
   `test_hedge_started_after_threshold_and_second_wins`; `test_first_wins_even_if_slow_after_first_token`;
   `test_hedge_telemetry_outcomes`; `test_hedge_off_by_default`.
2. **Implementação:** `RoutedLLM.stream_structured` (ramo hedge).

## 5. Critérios de aceite

- [x] R1–R10 cobertos no escopo (testes novos + streaming/latência/roteamento); R9 paridade MockLLM provada (`test_mock_stream_equals_invoke_state`, `test_final_state_identical_across_token_modes`). Suíte completa: coordenador, no pouso.
- [ ] Staging §6 (26/10, `9775ea1`: TTFMC servidor p50 2,65 s ✔; `replace` 0/35 ✔; TTLT vs baseline pós-316 ainda sem comparação limpa): **TTFMC p50 ≤ 3 s**; TTLT p50 dentro de ±5 % do baseline pós-316; `replace` em < 5 % dos turnos.
- [ ] Hedge (ligado 26/10; 0 disparos em 15 turnos — a cauda vem depois do 1º delta, o gatilho não pega; critério NÃO atingido): `done` p95 −30 % com custo extra ≤ 10 % (`hedge_lost` contabilizado).
- [x] Guard de FallbackLLM em `stream_structured` e nos agentes (`narrate_structured` devolve `AIMessage`; o `isinstance` do nó segue).
- [x] Nenhum campo novo no save; `off` byte a byte ao HEAD (`test_off_byte_identical`).
- [ ] Revisão independente (Sol): parser, concorrência do hedge, contextvar entre thread SSE e worker.

## 6. Smoke test com LLM real

Staging, DeepSeek (Groq como 2º), teto **US$ 0,25**:
1. `RPG_TOKEN_STREAM=shadow`, 15 turnos: `ttft_shadow_ms` p50 e `would_replace` < 5 % (log `sse.token_stream_shadow`); no `on`, `sse.token_replace` traz o motivo.
2. `RPG_TOKEN_STREAM=on`, `projection_measure.py --label tokens_on --turns 15 --think 8` ×2: tabela p50/p95 de
   `ttfmc`, `ttlt`, `state`, taxa de `replace`/`reset`.
3. `RPG_LLM_HEDGE_MS=6000`, 15 turnos: `hedged`, `hedge_won`, custo por turno vs baseline.
4. Browser (Chromium 1440 + mobile 390): texto aparece palavra a palavra; `reset` em fallback induzido
   (`RPG_ROUTES` com 1º candidato inválido) limpa e recomeça sem duplicar.

## 7. Riscos & compatibilidade

- **Texto parcial que o guard rejeitaria:** o jogador pode ver por 1–3 s uma frase que será substituída
  (`replace`). Taxa esperada baixa (guards reagem a NPC morto/segredo, que o filtro de contexto já evita —
  regra de ouro). `shadow` mede `identical_to_final` antes de ligar.
- **Providers divergentes:** deltas via `tool_call_chunks` (DeepSeek/Groq/OpenAI) ou `content` JSON; qualquer
  formato não reconhecido ⇒ sem deltas, fallback 316 — nunca erro de turno.
- **Hedge dobra custo na cauda** e pode acionar rate limit do 2º provider; por isso `0` default e teto por
  chamada. A request perdedora não é cancelável (SPEC-143 §2.6).
- **Mecânica:** nada muda — o stream só antecipa a exibição da string `narrative`; eventos/impactos
  continuam vindo do `StoryUpdate` completo e validado em Python.
- **MockLLM/FallbackLLM:** `MockLLM.stream` novo; `FallbackLLM` sem `stream` ⇒ `invoke` (AIMessage de erro,
  guard obrigatório). Sem chave ⇒ comportamento atual.
- **Observabilidade:** `TTFT ≡ TTFMC` (SPEC-200) deixa de ser verdade; dashboards/alertas que assumem
  `pseudo_streaming=true` precisam do campo novo.

## 8. Decisões do dono

- **D1 — Default do stream:** **`shadow` na main; `on` no staging após §6 com `would_replace` < 5 %** (critério corrigido na revisão: `identical_to_final` é igualdade estrita e sobe falso-negativo quando o final só estende o texto; `would_replace = not final.startswith(streamado)` usa a mesma regra do `on`).
  **Rollout:** ligar `RPG_TOKEN_STREAM=on` no staging **só com `RPG_EARLY_NARRATIVE=on`** — sem isso o `replace` só chega no `state` e o texto divergente fica na tela o turno inteiro.
- **D2 — Hedge:** **desligado por default (`0`); ligar no staging em `6000 ms` só para o tier FAST**
  (alternativa: 4000 ms — mais cauda cortada, mais custo; rejeitada até ver a distribuição do TTFT real).
- **D3 — Texto parcial rejeitado pelo guard:** **substituir silenciosamente (`replace`)**, igual à 316 D4.
- **D4 — Escopo de providers:** **só OpenAI-compat (DeepSeek/Groq/MiniMax/Qwen)**; Anthropic/Gemini ficam no
  pseudo-streaming (alternativa: implementar parsers por provider — custo alto para candidatos de fallback).

---

## Histórico de mudanças

- **2026-10-25 · implementação (Sonnet/Opus executor).** Desvios e decisões de execução, todos dentro das
  decisões D1–D4 do dono:
  1. `narrate_structured`/`narrate_text` (em `services/narrative_sink.py`) são o helper `_narrate` dos agentes.
     **Combate e loot narram em texto plano** (`llm.invoke`, não structured): usam `RoutedLLM.stream_text`
     (sem extrator JSON). Storyteller usa `stream_structured` (campo `narrative`); NPC usa `key="dialogue"`
     (1º campo de `NPCResponse`) com `prefix='"'`, pois a mensagem final abre com aspas. O teste R10 trava
     `narrative` (3 variantes de `StoryUpdate`) e `dialogue` (`NPCResponse`) como 1º campo.
  2. `stream_structured(input, schema, *, on_delta, on_reset, key)` **não reaplica `_transforms`**: faz
     `bind_tools([schema], tool_choice=<nome>)` direto no client e valida o JSON acumulado com
     `schema.model_validate_json` (mesma validação Pydantic do invoke). JSON inválido ⇒ `invalid_structured`
     e próximo candidato (sem regeneração semântica no mesmo provider, ao contrário do `invoke`).
     Candidato não-OpenAI-compat ⇒ sub-`RoutedLLM` de 1 candidato com `invoke` estruturado (D4).
  3. **Guard do texto parcial** (`StreamGuard`): só texto limpo vai ao sink — remove `[RESULTADO] …`, aplica
     o véu SPEC-293 (`conceal_text`) segurando uma janela do tamanho do maior nome oculto e a palavra
     parcial/`[` aberto. Prose guard, evidência e regra de ouro só existem no texto FINAL ⇒ divergência vira
     `replace`; quando o final apenas **estende** o já exibido a API manda só o sufixo (sem `replace`).
  4. SSE: chunks reais saem com `"live": true`; fallback de provider ⇒ `narrative {chunk:"", reset:true}`.
     O cliente só acompanha o cursor (sem atraso) em entradas `live`; pseudo-streaming segue animado.
     `shadow` também streama no LLM mas a API descarta os deltas e loga `sse.token_stream_shadow`
     (`ttft_shadow_ms`, `identical_to_final` — não é sempre `true`: o anti-repetição de abertura prefixa o final).
  5. Hedge: `RPG_LLM_HEDGE_MS`, só tier FAST e `stream_structured`; 1º delta (ou conclusão válida) vence;
     perdedor registrado como `hedge_lost` (contado como "recebido" em `usage_metering`; ignorado em
     `audit_trace.turn_errors`). Teto de custo: no máximo ~10 % das chamadas hedgeadas (`HEDGE_MAX_RATIO`,
     contador por processo, +1 de folga). Log `llm.hedge` (`hedged`, `hedge_won`).
  6. `playtest/latency_llm.py` ganhou `stream_structured`/`stream_text` (mesma latência injetada), senão o
     baseline offline perdia a fase do narrador. Métrica nova `rpg_turn_first_token_seconds`; `rpg.turn` e
     `turn_delivery` ganham `first_token_server_ms` e `pseudo_streaming=false` com token real.
  7. Flags novas em `scripts/staging/vercel_env.py` (`RPG_TOKEN_STREAM`, `RPG_LLM_HEDGE_MS`; valores de hedge
     restritos a 0/3000/4000/6000/8000). Nota para o README da SPEC-200: com token real, TTFT ≠ TTFMC.
- **2026-10-25 · correções da revisão (`handoffs/SPEC-319-sol-review.md`, CHANGES_REQUIRED).**
  P1-1/P2-1: narração mediada (`interlocutor_reason ∈ MEDIATION_REASONS`) e `rumor_nothing` **não streamam**
  (`narrate_structured(..., stream=False)`): os guards de segredo/achado falso só existem no texto final.
  P1-2: prefixo do NPC agora `**Nome:** "`; teste SSE `test_npc_route_tokens_do_not_replace`.
  P2-3: `StreamGuard` aplica `sanitize_player_facing` (preâmbulo meta, espaços/pontuação), segura os
  primeiros 120 chars e corta antes do espaço. P2-4: log `sse.token_replace` (`reason`, tamanhos, prefixo comum).
  P2-5: `would_replace` no shadow (critério D1). P2-2: `hedge_lost` só para quem não terminou.
  P2-6: `hedge_lost` não conta como falha/fallback em `llm_failures`, `llm_failed_attempts`, `llm_by_tier`.
  P2-7: teto do hedge é **melhor-esforço por instância**: só hedgeia após `HEDGE_MIN_CALLS=10` chamadas e
  `hedges+1 ≤ 10 % × chamadas`; conferir `hedged`/turnos no smoke 3 (instâncias frias do Vercel têm poucas chamadas).
  P2-8: stream aplica a instrução de `_input_for_provider` e, se o JSON streamado for inválido, recorre ao
  `invoke` estruturado do mesmo candidato (regeneração semântica) antes de passar ao próximo.
  P2-9: `reset` não chama `onDone`. P2-10: wrapper do playtest com `hasattr`.
- **2026-10-25 · re-revisão (APPROVED_WITH_FOLLOWUPS).** F-1: JSON streamado inválido não chama mais o
  `invoke` dentro da tentativa; devolve `_StreamRetry` e o coordenador manda `reset` (e `guard.reset()`)
  ANTES do `_invoke_single` — a cauda retida do parcial inválido nunca é emitida (R4). `reset` do route agora
  sempre chama `on_reset` (o sink ignora se nada saiu). F-2: `StreamGuard(normalize=...)`: NPC e
  combate/loot usam só `sanitize_meta_preamble`; storyteller mantém `sanitize_player_facing`.

- 26/10 — shadow no staging: `would_replace` 2/15 (13 %) no round 1 e 5/11 (45 %) no round 2, ttft_shadow p50 ~2,6 s. **Acima da meta D1 (< 5 %) → `RPG_TOKEN_STREAM` segue `shadow`**; follow-up: investigar a causa das trocas pelo `reason` de `sse.token_replace`/would_replace (prefixo anti-repetição, guard de prosa) antes de ligar.
- **2026-10-26 · follow-up D1 (would_replace 13 %/45 % no shadow).** Causas (replay de 34 narrações do
  storyteller + 8 de NPC, `tests/test_spec319_shadow_replay.py`; antes do fix 13/34 do storyteller divergiam):
  (1) **abertura repetida** (`vary_repeated_opening`) só no final: 10/34 (principal causa; o NPC põe a
  transição ANTES da aspa, então o prefixo `**Nome:** "` sempre divergia nesses turnos);
  (2) **saldo de ouro** (`reconcile_player_gold_claims`) só no final: 3/34 (+ risco de padrão partido entre
  deltas); (3) NPC com aspas externas no `dialogue`. Não achados no replay (sem texto nos logs de staging):
  `_NEGATIVE_REWARD/_NEGATIVE_ITEM` em turno com ganho e `species_drift`/resumo canônico no combate (guards de
  conteúdo, mantidos), e loot com `loot_obtido`, cuja prosa livre é sempre descartada (`narrate_text(stream=False)`).
  Correção sem enfraquecer guard: `StreamGuard(finalize=…, hold_extra, min_words)` aplica em fluxo as MESMAS
  funções do final (ouro → abertura; NPC: aspas + transição + rótulo), segura o início até 8 palavras (a
  abertura de 6 palavras decide a transição) e 72 chars no fim. `vary_repeated_opening` agora faz o digest só
  sobre a abertura (6 palavras), para stream e final escolherem a mesma transição. Após o fix: 0/34 e 0/8.
  Telemetria: `sse.token_stream_shadow` ganhou `reason` (`none|start|tail|shorter`, `replace_reason`).
  Critério para ligar: confirmar `would_replace` < 5 % no staging com o novo `reason`.
- **2026-10-26 (§6.1 no staging, `c024b7f`):** shadow com o fix de prefixo, 24 turnos DeepSeek + smoke e2e:
  `would_replace` 1/25 (4 %, `reason=start`) < 5 % → critério D1 cumprido; 1ª narração p50 5,6 s / p95 14,3 s,
  0 erros. Ligado `RPG_TOKEN_STREAM=on` no preset do staging (`RPG_EARLY_NARRATIVE=on` já estava). Próximo: §6.2–6.4.
- **2026-10-26 (§6.2, `bf8392a`, `RPG_TOKEN_STREAM=on`):** `projection_measure` 15 turnos ×2, DeepSeek, 0 erros, checks ok.
  Sessão 2: `first_chunk` p50 2,9 s / p95 11,3 s; `done` p50 5,6 s / p95 14,2 s; `state` p50 9,0 s / p95 20,2 s.
  Sessão 1: 6/15 turnos com `ack` (1º byte SSE) de 19–39 s, fora das fases do servidor (narrador 3–5 s,
  `lock_wait` ~100 ms) → espera de infra/Vercel, não do stream; sem ela o `first_chunk − ack` fica em 2–7 s.
  `sse.token_replace` em produção: 3 em ~35 turnos (~9 %; 2 `tail`, 1 `start`), acima do alvo de 5 % do shadow
  → follow-up: o `tail` mostra texto streamado MAIOR que o final (1505 vs 1391 chars), sinal de corte no final
  que o hold de 72 chars não cobre. Ligado `RPG_LLM_HEDGE_MS=6000` (D2, só FAST) para o §6.3.
- **2026-10-26 (§6.3, `55a81bf`, hedge 6000 FAST):** 15 turnos, checks ok, 0 erros. **0 hedges disparados**: o 1º
  delta chega em ~2 s (< 6000 ms) e a cauda do FAST (9–10 s em 4/21 chamadas) vem DEPOIS do 1º token, então o
  gatilho "sem delta em N ms" não pega; custo/turno inalterado (~US$ 0,0033). `first_chunk` p50 4,2 s; `done` p50 6,3 s.
  `sse.token_replace` 4 (2 `start`, 2 `tail`). 3/15 turnos com `ack` de 19–59 s: `sse.started` chega no servidor só
  depois (servidor responde em ~60 ms) → fila/cold start do Vercel antes da função, fora do escopo desta spec e
  hoje o maior fator da p95. Pendente: §6.4 (browser palavra a palavra + `reset` em fallback induzido) e o
  follow-up do `tail`.
- **2026-10-26 · follow-up `tail` (`sse.token_replace` ~9 % no staging, stream MAIOR que o final).** Causa: o texto
  final passa por guards de CONTEUDO que cortam frases no MEIO e so decidem no fim do turno — (1) guard de evidencia
  (`narrative_evidence.guard_current_messages`, frase a frase: morte falsa, local, posse, recompensa, segredo) aplicado
  em `early_narrative`; (2) cortes de recibo de `render_player_message` (`_NEGATIVE_REWARD/_NEGATIVE_ITEM`);
  (3) `remove_rejected_claims` quando `items_gained` traz item desconhecido/unico (um caso `tail` coincidiu com
  `unknown_item`). Nenhum rodava no stream. Correcao sem afrouxar guard (opcao b, por frase, nao por no):
  `StreamGuard(risk=…)` so mostra ao vivo as frases COMPLETAS anteriores a primeira frase que o guard pode cortar (e
  segura a frase ainda aberta); o resto chega como sufixo do final (sem `replace`). `narrative_evidence.stream_risk_checker`
  reaproveita `_reason` + os regex de recibo; so o narrador da cena (`hold_acquisition=True`) tambem segura frases
  "Voce recebe/pega/encontra…" (item que o motor pode rejeitar); o estado de evidencia do storyteller e o do turno
  (mundo/jogador apos viagem, descanso, achado). Custo: o stream para antes dessas frases e a cauda sai de uma vez.
  Testes: `tests/test_spec319_shadow_replay.py` (`unknown_item`, `false_death_claim`, `acquire_without_item` + unitarios
  do `risk`; os dois primeiros falham sem o fix). Residuais nao cobertos (decididos so no fim): `proposed_events`
  invalido (narrativa inteira vira fallback) e `species_drift` no combate — `reason=start`; seguem `replace` silencioso (D3).
- **2026-10-26 · follow-ups da revisão do `tail` (`handoffs/SPEC-319-sol-independent-review.md`).**
  P1-1 (granularidade): com `risk` presente (todo narrador com estado) o stream sai **frase a frase**, não palavra a
  palavra — a frase aberta é sempre segurada, então o 1º delta espera a 1ª frase completa (após `HOLD_CHARS`); e um
  `_ACQUIRE` casando cedo ("Você encontra…") segura o resto do turno até o final (que chega como sufixo). Isso afeta
  §6.4 e o critério TTFMC p50 ≤ 3 s: **remedir no §6.2** (`ttfmc` com `on`) antes de fechar o critério; se cair, avaliar
  checker de prefixo monotônico para a frase aberta. P2-1: falha ao montar/rodar o checker agora é **fail-closed**
  (segura tudo; o final entrega); `None` só sem estado. P2-2: o checker é montado de forma preguiçosa na 1ª frase
  completa (o deepcopy do estado fica fora do caminho do 1º token). P2-3: resíduos que ainda terminam em `replace`
  silencioso (D3): `remove_rejected_claims` corta qualquer frase com o NOME do item rejeitado (mesmo sem verbo de
  aquisição) e, com ouro/moeda, o parágrafo inteiro (inclusive frases já mostradas); `_ACQUIRE` é amplo
  (`encontra/acha/descobre`) e também segura frases sem item (custo de P1-1). P2-4: log `sse.stream_risk_hold`
  (`rule`, `sentence_index`, `chars_shown`; nunca o texto), 1× por narração. P2-5: se o véu mudar a segmentação em
  frases, o corte cai em 0 (fail-closed) — teste com rótulo contendo ". ".
- **2026-10-26 (§6.2 remedido após o fix do `tail`, `9775ea1`):** 2×15 turnos + smoke, checks ok, 0 erros.
  `sse.token_replace` **0 em 35 turnos** (antes ~9 %); `sse.stream_risk_hold` 2× (`acquisition`). TTFMC no servidor
  p50 2,65 s (n 28); cliente `first_chunk` p50 3,1 s / 4,4 s; `done` p50 6,1 / 7,0 s; `state` p50 10,6 / 8,8 s.
  Sessão 1 ainda com 4/15 `ack` > 5 s (espera do Vercel antes da função — mesma classe de antes).
