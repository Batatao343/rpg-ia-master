# Pacote de auditoria `valoria-audit-export-v1` — esquema (SPEC-207)

Pacote gerado sob demanda pelo dono da campanha. Determinístico: o mesmo estado gera os
mesmos bytes (exceto `generated_at`). Nenhum dado de conta: sem e-mail, IP, user-agent,
ids de conta/`operation_id` crus, cookies, tokens, chaves, URLs assinadas, áudio ou
transcrição de voz, wallet/pagamento. Texto livre passa por scrubber
(`[REDACTED:email|phone|url|token|api_key|uuid|ip|owner]`). Nenhum prompt ou resposta bruta do
LLM é exportado (só referências por `source_id` e a narração final mostrada ao jogador).

Convenções: `turn_ref = "t:<epoch>:<turn>"`; `action_ref` = pseudônimo HMAC do `action_id`
(igual ao `action_ref` da linha de log `rpg.turn`); `delta_ref = "d:<epoch>:<turn>"`;
`timing_ref = "tm:<epoch>:<turn>"`; `error_ref = "e:<epoch>:<turn>:<i>"` (ou `e:op:<ref>`).
`null` significa **não registrado** — nunca inferido.

## `manifest.json`
`format`, `game_ref` (pseudônimo HMAC do game_id), `build_sha`, `save_schema_version`,
`export_schema_version`, `generated_at` (UTC), `range` (`first_turn_ref`, `last_turn_ref`,
`epochs`), `turn_count`, `truncated` + `truncation_reason` (`max_turns`|`max_bytes`),
`state_version` (versão do save lida), `private_label`, `taxonomy_version` (SPEC-206),
`trace_limit` (tamanho do ring buffer), `client_timing` (`not_exported`), `unavailable`
(fonte → motivo), `session_files`, `files` (sha256 de cada arquivo, exceto o manifest).

## `sessions/<epoch>.jsonl` — um turno por linha
`turn_ref`, `epoch`, `sequence` (ordem do servidor; `null` sem banco), `action_ref`,
`player_text` (scrubbed), `route`, `speaker` (`narrator` | `npc:<id canônico>` | `system`),
`narration` (texto mostrado ao jogador), `event_ids` (eventos canônicos do turno),
`delta_ref`, `timing_ref`, `cost_usd` (soma de `usage_events` da operação; string decimal),
`error_refs`, `trace_available`, `context_refs_unavailable`. Ordem = `sequence` crescente.

## `state/initial_snapshot.json` e `state/final_snapshot.json`
`kind`, `turn`, `epoch`, `state_version`, `derivation`, `projection` — projeção FECHADA do
estado: `player.{vitalidade,max_vitalidade,entropy,max_entropy,abyss_charge,gold,xp,level}`,
`player.inventory` (id→qtd), `player.known_cards`, `player.prepared_cards`,
`world.{location_id,day,period,weather,danger_level}`, `combat.{active,round}`,
`combat.enemies` (id→vitalidade), `npcs` (id→{in_scene, relationship}), `quests` (id→status).
O inicial é derivado da projeção final com os deltas dos turnos exportados revertidos
(`derivation: final_projection_with_turn_deltas_reversed`); mudanças fora de turno
(equipar, subir de nível) não entram nos deltas.
`final_snapshot.private_reference` (rótulo `"privado — referência de auditoria"`):
`arc_title`, `climax`, `current_step`, `beats[{description,status}]`,
`unrevealed_secret_ids` — segredos do engine, presentes **só** no export do próprio dono.

## `state/deltas.jsonl`
`delta_ref`, `turn_ref`, `delta`: caminho → `{before, after}` sobre a projeção acima
(mapas por id viram `npcs.<id>`, `quests.<id>`, `player.inventory.<id>`, `combat.enemies.<id>`).

## `knowledge_visibility.jsonl`
`turn_ref`, `speaker`, `items` (lista), `player_revealed_secret_ids`, `reveal_criteria_diverge`
(ou `items: null` + `context_refs_unavailable: true`). Cada item: `source_id` (id estável do
ContextPack: `lore_content_<sha>`, `memory_content_<sha>`, event_id, edge id…), `section`,
`visibility` (`public` | `hidden` | `secret` | `engine` = contexto só do planejador),
`purpose` (`story`|`npc`|`combat_narration`|`planning`), `npc_id`, e os valores SPEC-206:
`knowledge_kind` ∈ `fact|report|rumor|suspicion|perception`, `certainty` ∈
`confirmed|reported|speculative`, `source_kind` ∈ `canonical_event|player_observation|
npc_claim|inference|legacy_unverified`. Item público sem classificação SPEC-206 (lore,
relações, entidades) leva os três `null`. Item **não público** leva os três `null` +
`private_label`. `player_revealed_secret_ids` usa o critério estrito
(`memory_provenance.accepted_secret_ids`: só `secret_revealed` aceito);
`reveal_criteria_diverge: true` quando o corpus permissivo (`revealed_corpus`) discorda.

## `mechanics` (em `sessions/<epoch>.jsonl`, só turnos com conflito)
`{steps, truncated}`: até 64 passos `{kind, actor_ref, target_ref, dice, kept, modifier,
dc_or_defense, result, amount, card_id, reason}` (refs = ids de catálogo ou `player`).

## `errors.jsonl`
`error_ref`, `turn_ref`, `action_ref`, `node`, `tier`, `code`, `recovered`, `fallback`
(`provider_next`|`none`|`rejected`), `error_class` (só nome de classe para `turn_failed`).
`code` é enum fechado: `llm_invoke_error`, `structured_output_invalid`, `llm_stream_error`,
`llm_circuit_open`, `llm_build_error`, `llm_other_error`, `event_rejected`,
`narrative_rejected`, `memory_rejected`, `turn_failed`. Nunca mensagem de exceção crua.
Linha `{"unavailable": true, "reason": …}` quando a fonte de turnos falhou.

## `timings.jsonl`
`turn_ref`, `action_ref`, `latency_ms` (total do servidor, `app.turns`), `timing_partial`,
`client_timing: "not_exported"`, `timing` = snapshot da TurnTimeline SPEC-200 com os nomes
dela: `transport`, `execution_mode`, `ack_server_ms`, `ttfmc_server_ms`, `ttlt_server_ms`,
`phase_ms` (`router`, `context`, `narrator`, `archivist`, `persistence`, `other`),
`lock_wait_ms`, `llm_attempts`, `llm_fallbacks`, `llm_failed_attempts`, `providers_used`,
`cost_basis`, `input_size`. O snapshot é gravado dentro do commit: `phase_ms.persistence` e as
marcas ainda não fechadas (`ttfmc/ttlt`, entregues depois no stream) saem `null` com
`timing_partial: true`. `timing: null` = turno sem trilha.

## `AUDITOR_PROMPT.md`
Instruções do auditor e o formato de saída (`report.md` + `findings.jsonl`).
