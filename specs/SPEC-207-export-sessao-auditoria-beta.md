# SPEC-207 — Export de sessão para auditoria beta (pacote sob demanda)

> **Status:** `done` (revisão Astra APPROVED_WITH_FIXES 2026-10-16)
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** SPEC-200 `done` (timings por `action_id`), SPEC-206 `done` (taxonomia de conhecimento), SPEC-228 `done` (export fiel ao save) · reaproveita SPEC-190 `done` (prova de auth recente) e SPEC-182 `done` (`app.usage_events`) (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-212 (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 08; referência `referencias/AUDITOR_PROMPT_MODELO.md`
> **EXECUTOR_MODEL:** `Sol` (≡ Opus, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` — o pacote produz insumo para propostas de eval do auditor; nenhum eval novo é fixado aqui
> **Nota de schema (cadeia final 2026-10-15):** ordem dos bumps de `SCHEMA_VERSION` (hoje 8): SPEC-228 primeiro (R9 recusa save de versão mais nova; sem bump) → [SPEC-227 só se D-C = migração; default sem bump] → SPEC-202 → SPEC-203 → SPEC-207 → SPEC-213 → SPEC-215. Nenhuma outra spec 199–236 altera o schema de save (SPEC-228 R7 `needs_replan` e SPEC-231 `scene_allies` usam default/campo existente, sem bump). Cada spec usa o próximo `SCHEMA_VERSION` livre no HEAD ao implementar e encadeia sua migração após a anterior; onde o texto disser "v8→v9", leia "vN→vN+1".

---

## 1. Contexto & Objetivo

[D] Decisão fechada do produto (DECISOES_PRODUTO.md § Auditoria beta): capturar fluxos e causas e
**exportar sessões sob demanda** como pasta/ZIP autossuficiente que o dono abre no próprio coding agent
(Codex/Claude) com créditos próprios. Nada de auditor automático pago, nada de replay humano como produto.

[F] Hoje existem exportações parciais, nenhuma serve à auditoria de sessão:
- `GET /game/chronicle/export` (`api.py:3710`, `export_chronicle`) — `.txt` da crônica por capítulo.
  Nos perfis DB o middleware `_session_boundary` (`api.py:92`) exige identidade em `/game*` e
  `persistence.load_game_state` (`persistence.py:684`) carrega via `store.get(principal, uuid)` —
  **não vaza entre donos** (o achado [H] da análise fica refutado). No perfil `legacy` não há login
  por design (loopback).
- `GET /game/saves` (`api.py:3621`) — lista owner-scoped (`persistence.list_saves`, `persistence.py:302`).
- `GET /account/export` (`api.py:500`) → `PostgresAccountLifecycle.export`
  (`infrastructure/account_lifecycle.py:28`) — dump bruto das `PRIVATE_TABLES` + financeiras, com
  `_require_recent` (`api.py:489`, cookie `rpg_recent` ligado ao access cookie). Inclui `owner_id` cru
  e todo o `state` — adequado a LGPD/portabilidade, **inadequado** para entregar a um agente externo.
- `services/game_transfer.export_game` / `verify_export` (`services/game_transfer.py:104/140`) e
  `scripts/export_game_data.py` — bundle portável `valoria-game-export-v1` (state, checkpoint,
  `app.game_events`, `app.runtime_catalog`) com hashes; ferramenta de operador (`--owner` explícito).
- `playtest/telemetry.py` (`turn_to_record`, l.757) — schema rico por turno (rota, nós, latência por
  nó, combate, eventos aplicados/rejeitados, erro), mas só para runs sintéticos do harness.

[F] O que existe por turno em produção: `app.turns` (sequence, epoch, `route`, `input_sha256`,
versões antes/depois, `latency_ms`, `llm_cost_usd`); `app.usage_events` (custo por tentativa);
`app.game_events` (eventos canônicos por turno); `state['presentation_history']`
(`services/presentation_history.py`, linhas player/narrator com `turn`/`epoch`/`type`). **Não
existe**: snapshot/delta de estado por turno, registro do contexto visto pelo NPC/narrador, nem
classificação de visibilidade do que foi narrado. `context_builder.assemble_pack` já gera ids estáveis
por conteúdo (`lore_content_<sha256[:24]>`, `memory_content_<sha256[:24]>`) e filtra por
`visibility` — base para referências de contexto sem copiar texto.

Objetivo: um endpoint owner-only que monte, sob demanda, um ZIP determinístico com transcrito,
deltas, visibilidade de conhecimento, erros, timings e custo por turno, pronto para o prompt de
auditor, com redaction de PII obrigatória e sem custo de provider.

## 2. Requisitos

- **R1** — `POST /game/{game_id}/audit-export` (perfis DB) gera o ZIP e devolve-o como download
  (`Content-Disposition: attachment`, `Cache-Control: no-store`). Exige principal autenticado **e**
  prova recente (`_require_recent`, mesmo contrato da SPEC-190); sem prova → 403
  `recent_session_required`. CSRF validado pelo middleware existente (é POST).
- **R2** — Isolamento: `game_id` de outro dono → 404 indistinguível de inexistente; toda consulta SQL
  filtra `owner_id = principal.user_id` (nenhum owner vindo do cliente). Conta em exclusão
  (`app.account_deletions`) → 401 `account_deleted`.
- **R3** — Conteúdo do ZIP (nomes fixos): `manifest.json`, `sessions/<epoch>.jsonl`,
  `state/initial_snapshot.json`, `state/final_snapshot.json`, `state/deltas.jsonl`,
  `knowledge_visibility.jsonl`, `errors.jsonl`, `timings.jsonl`, `AUDITOR_PROMPT.md`,
  `README_SCHEMA.md`. Schemas na seção 3.
- **R4** — `manifest.json` contém: `format: "valoria-audit-export-v1"`, `game_ref` (pseudônimo HMAC do
  `game_id`, via `observability.telemetry.pseudonym`), `build_sha`, `save_schema_version`,
  `export_schema_version`, `generated_at` (UTC), faixa de turnos/epochs incluída, flags de truncagem,
  versões de prompt/rota quando disponíveis, e `sha256` de cada arquivo do ZIP.
- **R5** — Cada linha de `sessions/*.jsonl` (um turno) contém: `turn_ref`, `epoch`, `sequence`,
  `action_ref` (pseudônimo do `action_id`), `player_text`, `route`, `speaker`
  (`narrator`|`npc:<id canônico>`|`system`), `narration`, `event_ids` (de `app.game_events`),
  `delta_ref`, `timing_ref`, `cost_usd` (soma de `usage_events` do `operation_id`), `error_refs`.
  Ordem = `sequence` crescente; deterministico para o mesmo estado.
- **R6** — `knowledge_visibility.jsonl` registra por turno, usando a taxonomia da SPEC-206, quais
  itens de conhecimento referidos no contexto/narração eram `public` (visíveis ao jogador) vs
  privados (`hidden`/`secret`/conhecimento só do engine), com o `source_id` do context pack — para o
  auditor checar vazamento e “conhecimento telepático”.
- **R7** — Contexto visto pelo NPC/narrador é persistido **como referências**, não cópias: por turno,
  lista de `source_id` + `visibility` + `section` do `ContextPack` usado, em ring buffer limitado no
  estado (default 200 turnos; seção 8). Sem esse registro (turnos antigos), o campo sai `null` com
  `context_refs_unavailable: true` — nunca reconstruído por inferência.
- **R8** — Redaction obrigatória (aplicada antes de serializar, falha fechada): nunca exportar e-mail,
  IP, user-agent, `owner_id`/`user_id`/ids de conta, `operation_id` crus, cookies/tokens, chaves de
  API, signed URLs, áudio ou transcrição bruta de voz, dados de pagamento/wallet. Texto do jogador
  passa por um scrubber de e-mail/telefone/URL com token → `[REDACTED:<tipo>]`. Um teste varre o ZIP
  inteiro por regex de PII e pelos valores reais do fixture (email, uuids do owner) e falha se achar.
- **R9** — Segredos do engine (`hidden`/`secret`, segredos de NPC, beats/clímax privados) entram
  **somente** no export do próprio dono e **somente** marcados: arquivo/campo separado com rótulo
  literal `"privado — referência de auditoria"` (seção 8, D4). Nunca entram em `narration`/`player_text`
  reformulados nem em campos sem rótulo.
- **R10** — Limites: no máximo `RPG_AUDIT_EXPORT_MAX_TURNS` (default 500) turnos mais recentes e ZIP
  ≤ `RPG_AUDIT_EXPORT_MAX_BYTES` (default 25 MiB); excedeu → trunca pelos turnos mais antigos e marca
  `manifest.truncated=true` com motivo. Rate limit: 3 exports/10 min por dono (bucket existente de
  rate limit), excedido → 429.
- **R11** — Geração síncrona em memória e streaming da resposta; **nada é retido server-side**. Se a
  implementação precisar de blob temporário (fallback para jogos grandes), objeto em
  `users/<owner>/audit-exports/` com expiração ≤ 24h e limpeza pelo cron de operações; o
  `account_lifecycle.begin` já apaga prefixo `users/<owner>/`.
- **R12** — Zero chamada de LLM/embedding/provider pago durante o export (verificável por
  `set_llm_telemetry_hook` e ausência de `usage_events` novos com o `operation_id` do export).
- **R13** — `AUDITOR_PROMPT.md` é derivado de `AUDITOR_PROMPT_MODELO.md` (pacote), versionado no repo
  em `docs/auditoria/AUDITOR_PROMPT.md`, e especifica a saída `report.md` + `findings.jsonl` com
  `severity, category, session_ref, turn_ref, expected, observed, evidence_refs, hypothesis,
  confidence, eval_proposal`, mais seções de agrupamento de bugs relacionados (`cluster_id`) e de
  falsos positivos descartados com motivo; instrui a não promover suspeita a bug sem evidência e a não usar judge
  onde há oráculo determinístico. `README_SCHEMA.md` documenta cada arquivo/campo.
- **R14** — Perfil `legacy`: endpoint responde 404 `audit_export_unavailable_in_legacy` (sem login não
  há prova de dono); o harness de playtest continua usando `playtest/telemetry.py`. Export offline de
  operador fica coberto por `scripts/export_game_audit.py` (owner explícito, mesmo builder, mesma
  redaction) para runs locais de fixture.
- **R15** — UI: botão “Exportar sessão para auditoria” na área de conta/saves da campanha, que dispara
  a re-autenticação (fluxo `POST /auth/reauth` existente, `api.py:468`) quando falta prova recente; texto curto
  explicando o conteúdo e que segredos do mundo vêm marcados. Sem tela de replay.
- **R16** — Consentimento: o texto legal correspondente é entregue como **handoff** para a SPEC-197
  (`handoffs/SPEC-207-legal-consent-handoff.md`), sem editar a SPEC-197 nem `docs/spec197/legal/*`.

### Fora de escopo

- Auditor automático (noturno ou por evento), chamada de qualquer modelo para analisar o pacote.
- UI de replay humano, visualização de turnos no app.
- Exportar sessões de outro dono, de admin ou agregado multi-conta.
- Áudio, imagens geradas (só `asset_id` + hash, se referido), dados de wallet/pagamento.
- Streaming real de tokens, instrumentação de timing (é da SPEC-200; aqui só é lida).
- Novos evals/datasets; edição de `evals/`; alteração do texto legal publicado.
- Persistir texto integral de prompts/respostas brutos do LLM (só referências; ver seção 8 D-b).

## 3. Design técnico

**Arquivos novos**
- `services/audit_export.py` — builder puro: `build_audit_bundle(source: AuditSource, *, limits:
  AuditLimits, build_sha: str) -> AuditBundle`; `write_zip(bundle) -> bytes` (ordem de entradas e
  `ZipInfo.date_time` fixos → bytes determinísticos para mesmo input); `verify_audit_zip(data: bytes)
  -> list[str]` (hashes do manifest, arquivos obrigatórios, scan de PII).
- `services/audit_redaction.py` — `redact_record(obj, *, owner_values: set[str]) -> obj` (allowlist de
  chaves por arquivo; chave fora da allowlist é descartada, não copiada), `scrub_text(text) -> str`.
  Reusa `observability.telemetry.pseudonym`; **não** reusa `redact` diretamente, pois `_SENSITIVE_KEYS`
  apaga `action`/`narrative`/`state`, que aqui são o conteúdo desejado.
- `infrastructure/audit_source.py` — `PostgresAuditSource(pool, principal, game_id)`: lê `app.games`
  (via `PostgresGameStore.get`), `app.turns`, `app.usage_events` (agregado por `operation_id`),
  `app.game_events`, sempre com `owner_id = principal.user_id`; e o estado (presentation_history,
  ring buffer de contexto, deltas).
- `scripts/export_game_audit.py` — CLI de operador espelhando `scripts/export_game_data.py`.
- `docs/auditoria/AUDITOR_PROMPT.md`, `docs/auditoria/README_SCHEMA.md` — embutidos no ZIP.
- `tests/test_audit_export.py`, `tests/test_audit_redaction.py`,
  `tests/integration/test_audit_export_postgres.py` (marcado como os demais testes PG locais).

**Arquivos alterados**
- `api.py` — rota `POST /game/{game_id}/audit-export` (R1/R2/R10/R14).
- `services/context_builder.py` — `build_context_pack` devolve/expõe `context_refs: list[{source_id,
  section, visibility}]` (sem texto). [H] o `ContextPack` já carrega `ScoredFact.source_id` e
  `visibility`; basta projetar.
- Nós que constroem contexto (storyteller, npc_actor, combat narração) — anexam `context_refs` ao
  registro do turno via helper único `services/audit_trace.record_turn_trace(state, ...)`.
- `persistence.py` — novo campo `audit_trace` (lista, ring buffer); migração `_migrate_v8_to_v9`
  (default `[]`), round-trip save/load; `serialize` corta em N.
- `web/src/...` (tela de saves/conta) — botão R15.

**Schemas (TypedDict em `state.py`)**
```python
class AuditTurnTrace(TypedDict):
    turn: int; epoch: int; action_ref: str      # pseudônimo do action_id
    speaker: str                                 # narrator | npc:<id> | system
    context_refs: list[dict]                     # {source_id, section, visibility}
    delta: dict                                  # diff estrutural mínimo, ver abaixo
    errors: list[dict]                           # {code, node, recovered: bool}
    timing: dict | None                          # subconjunto SPEC-200, ver abaixo
```

**Fonte dos timings (correção de revisão).** [F] A SPEC-200 grava TTFMC/TTLT/fases **só** na
linha de log `rpg.turn` (sua §Fora de escopo exclui persistência em Postgres); logs não são
legíveis pelo builder. Por isso `record_turn_trace` copia, no momento da finalização canônica, o
snapshot da `TurnTimeline` da SPEC-200 para `AuditTurnTrace.timing` com exatamente estes nomes:
`transport`, `execution_mode`, `ack_server_ms`, `ttfmc_server_ms`, `ttlt_server_ms`, `phase_ms`
(as 6 fases de `TurnPhase`), `lock_wait_ms`, `llm_attempts`, `llm_fallbacks`,
`llm_failed_attempts`, `providers_used`, `cost_basis`, `input_size`. Como o trace é gravado dentro
do commit, `phase_ms.persistence` e a marca `state` ainda não fecharam: saem `null` com
`timing_partial: true`. `app.turns.latency_ms` (total do servidor) completa a linha. Latência de
cliente (`client_latency`, SPEC-200 R10) é só log e **não** é exportada (`client_timing:
"not_exported"`). Sem SPEC-200 implementada, `timing: null`.

**Linha de `timings.jsonl`**
```json
{"turn_ref":"t:42","action_ref":"a:…","latency_ms":8123,"timing_partial":true,
 "timing":{"transport":"stream","execution_mode":"sequential","ack_server_ms":41,
  "ttfmc_server_ms":2310,"ttlt_server_ms":7900,
  "phase_ms":{"router":300,"context":120,"narrator":6900,"archivist":610,"persistence":null,"other":90},
  "lock_wait_ms":3,"llm_attempts":3,"llm_fallbacks":0,"llm_failed_attempts":0,
  "providers_used":["deepseek"],"cost_basis":"provider_usage","input_size":"short"},
 "client_timing":"not_exported"}
```

**Linha de `errors.jsonl`**
```json
{"turn_ref":"t:42","node":"npc_actor","code":"structured_output_invalid",
 "recovered":true,"fallback":"provider_next","error_class":"ValidationError"}
```
`code` é enum fechado documentado em `README_SCHEMA.md` (sem mensagem de exceção crua, que pode
conter texto/PII); fonte: `AuditTurnTrace.errors` + `app.turns` com status de falha.
`delta` = diff de chaves escalares e listas por id para `player` (vitalidade, entropia, carga, ouro,
xp, nível, inventário por id/qty, cartas), `world` (local, relógio, clima, danger), `combat`
(active/round/inimigos por id+vitalidade), `npcs` (in_scene/relação por id), `quests` (status). Sem
cópia do estado inteiro; snapshots inteiros só `initial`/`final` (redigidos).

**Linha de `knowledge_visibility.jsonl`**
```json
{"turn_ref":"t:42","speaker":"npc:npc_magda","items":[
 {"source_id":"memory_content_9f…","visibility":"public",
  "knowledge_kind":"report","certainty":"reported","source_kind":"npc_claim"},
 {"source_id":"lore_content_1a…","visibility":"hidden",
  "knowledge_kind":null,"certainty":null,"source_kind":null,
  "private_label":"privado — referência de auditoria"}],
 "player_revealed_secret_ids":["pacto_valerius"]}
```
Nomes e valores **idênticos** ao `KnowledgeStamp` da SPEC-206 (§3.2b): `knowledge_kind ∈ fact|report|
rumor|suspicion|perception`, `certainty ∈ confirmed|reported|speculative`, `source_kind` =
`MemoryProvenance`. Item privado (não visível ao jogador por SPEC-206 R4) leva os três campos `null`
mais `private_label` — o export nunca inventa um rótulo de certeza para o que o jogador não vê.
`player_revealed_secret_ids` vem de `memory_provenance.accepted_secret_ids(state)` (critério estrito
da SPEC-206 R5), **não** de `player.known_secrets` (campo lido mas nunca escrito em produção) nem de
`revealed_corpus` (permissivo, aceita prosa). A divergência entre `revealed_corpus` e o critério
estrito é justamente um sinal útil ao auditor: quando houver, registrar `reveal_criteria_diverge: true`.

**Contrato de UI** — botão na lista de saves/área da campanha; estados: idle → (sem prova recente)
modal de senha → gerando (spinner, ≤ 10 s alvo) → download; 403/404/429 → mensagem curta. Nenhuma
mudança na shell/abas.

**State ownership** — `audit_trace` é escrito apenas pelo helper `record_turn_trace`, chamado na
finalização canônica do turno (mesmo ponto que `record_history`), dentro do commit do turno; nunca
pelo archivist em segundo plano. Leitura só pelo builder.

**Degradação/fallback** — falha de leitura de `usage_events`/`turns` → arquivo correspondente com
`unavailable: true` e motivo, export continua; falha no scanner de PII → 500 `audit_export_redaction_failed`
e nada é enviado (fail-closed). Turnos anteriores à migração: `context_refs`/`delta` nulos e marcados.

## 4. Plano passo a passo (TDD)

### Etapa 1 — Redaction (fail-closed)
1. **Testes** (`tests/test_audit_redaction.py`): `test_scrub_email_phone_url` substitui por
   `[REDACTED:*]`; `test_owner_values_never_survive` (uuid do owner, e-mail do fixture em qualquer
   profundidade) ; `test_unknown_key_dropped` (allowlist); `test_audio_and_tokens_dropped`.
2. **Implementação:** `services/audit_redaction.py`.

### Etapa 2 — Trace por turno + migração
1. **Testes** (`tests/test_audit_export.py`): `test_trace_ring_buffer_caps_at_limit`;
   `test_context_refs_have_no_text` (só ids/visibility/section);
   `test_save_v8_loads_with_empty_audit_trace` (save v8 real de fixture → v9, round-trip);
   `test_trace_written_once_per_action_id` (replay idempotente não duplica);
   `test_trace_timing_uses_spec200_field_names` (com `TurnTimeline` fake; sem SPEC-200 → `null`);
   `test_knowledge_visibility_values_match_spec206` (enum fechado; privado → `null` + rótulo);
   `test_revealed_ids_use_accepted_secret_ids` (prosa/`known_secrets` não contam).
2. **Implementação:** `audit_trace.record_turn_trace`, `context_refs` no context_builder, migração.

### Etapa 3 — Builder e ZIP determinístico
1. **Testes:** `test_zip_has_required_files`; `test_manifest_hashes_match`;
   `test_same_input_same_bytes`; `test_sessions_ordered_by_sequence`;
   `test_private_items_only_with_label`; `test_truncation_marks_manifest`;
   `test_zip_pii_scan_clean` (varre todas as entradas); `test_no_llm_called` (hook de telemetria vazio).
2. **Implementação:** `services/audit_export.py`, `docs/auditoria/*`.

### Etapa 4 — Fonte Postgres + endpoint
1. **Testes** (`tests/integration/test_audit_export_postgres.py`, Supabase local):
   `test_owner_can_export_own_game`; `test_cross_account_404` (B pede game de A → 404, corpo igual ao de
   uuid inexistente); `test_requires_recent_proof_403`; `test_deleted_account_401`;
   `test_rate_limit_429`; `test_cost_sums_usage_events`; `test_legacy_profile_404` (offline).
2. **Implementação:** `infrastructure/audit_source.py`, rota em `api.py`, CLI.

### Etapa 5 — UI e handoff legal
1. **Testes:** teste Node/Playwright do fluxo botão → reauth → download (API mock).
2. **Implementação:** botão; `handoffs/SPEC-207-legal-consent-handoff.md`.
3. **Verificação final:** `uv run pytest` verde; `npm run build`; `uv run ruff check`.

## 5. Critérios de aceite

- [x] ZIP contém os 10 artefatos de R3 e `verify_audit_zip` retorna `[]`.
- [x] Teste cross-account (Postgres local) prova 404 para game alheio, sem diferença de corpo/status.
- [x] Sem prova recente → 403; com prova → 200 e download.
- [x] Scan de PII do ZIP: zero e-mail, IP, uuid de owner, token, signed URL, áudio.
- [x] Itens privados aparecem só com o rótulo literal e só no export do dono.
- [x] Mesmo estado → mesmos bytes; limites de turnos/bytes respeitados e sinalizados.
- [x] Zero `usage_events` e zero invoke de LLM gerados pelo export.
- [x] Save v8 carrega e faz round-trip com `audit_trace` (campo aditivo, default `[]`; **sem bump** — regra da onda).
- [x] `knowledge_visibility.jsonl` usa só valores da taxonomia SPEC-206; itens privados com campos `null` + rótulo; reveal via `accepted_secret_ids`.
- [x] `timings.jsonl` com os nomes de campo da SPEC-200 (R5/R17) ou `timing: null` marcado; `errors.jsonl` sem mensagem de exceção crua.
- [x] `AUDITOR_PROMPT.md` + `README_SCHEMA.md` presentes e coerentes com os campos reais.
- [x] Handoff legal escrito; SPEC-197 e `docs/spec197/legal/*` intocados (diff vazio).
- [x] `uv run pytest` verde (suíte completa offline); build web verde.
- [x] Revisão Astra independente APPROVED (with fixes — `handoffs/SPEC-207-ASTRA-independent-review.md`).

## 6. Smoke

Offline (padrão): `uv run python -m playtest run --profile normal --turns 10` (MockLLM; o harness grava em `saves_playtest/` no perfil `legacy` — o smoke DB exige criar a campanha pela API local com Supabase e MockLLM, ou importar o save via `services/game_transfer`) → abrir a
campanha resultante no perfil local Supabase, exportar via endpoint com prova recente, rodar
`verify_audit_zip`, inspecionar 3 turnos (speaker, delta, visibility). Smoke de 2 usuários no padrão
de `scripts/staging/two_user_smoke.py` (A exporta o próprio; B tenta o de A → 404), primeiro local,
depois em staging se autorizado (sem provider pago: os turnos usam MockLLM ou jogo já existente).
Provider real: **não necessário**. Opcional: entregar um ZIP real a um coding agent com o
`AUDITOR_PROMPT.md` para validar legibilidade — fora do custo do produto, decisão do dono.

## 7. Riscos & compatibilidade

- **Saves:** nova chave `audit_trace` → schema v9 com migração default vazia; saves v8 continuam
  carregando; turnos antigos sem trace ficam marcados `unavailable`.
- **Tamanho de save:** ring buffer só com ids (estimativa [H] ~0,5–2 KB/turno → ≤ 400 KB a 200 turnos);
  medir no teste de cap e ajustar N.
- **Privacidade:** risco principal é vazamento de PII digitada pelo jogador no texto livre; mitigado
  por scrubber + aviso na UI + consentimento (handoff). Segredos do engine expostos ao próprio dono
  podem estragar a experiência dele — mitigado por rótulo e aviso explícito antes do download.
- **Cross-account:** reutiliza `store.get(principal, …)` e filtros `owner_id`; RLS já cobre as tabelas.
- **Concorrência:** export lê `app.turns`/estado sem lock de turno; pode capturar o estado entre
  turnos — aceitável, `manifest` registra `state_version` lido.
- **Latência do hot path:** `record_turn_trace` é O(tamanho do delta), sem I/O extra além do save já
  existente; sem nova chamada LLM.
- **MockLLM/FallbackLLM:** export não usa LLM; nenhum structured output novo.
- **Merge:** toca `api.py`/frontend também editados pela SPEC-197 em curso — isolar em rota/arquivo novos.

## 8. Pontos de decisão do dono

- **D4 (fechada como default recomendado da onda):** export só do próprio dono, prova recente,
  redaction obrigatória, gerado sob demanda e não retido > 24h; consentimento via handoff para a
  SPEC-197; contexto do NPC como referências/hashes em ring buffer. Inclui segredos do engine só
  rotulados. **Default:** adotar como descrito.
- **D-a — Segredos no export do dono:** incluir rotulados (default, permite auditar vazamento) **ou**
  excluir e exportar só `source_id`+visibility. Default: incluir rotulados, com aviso de spoiler.
- **D-b — Prompt/resposta bruta do LLM:** não persistir (default; só refs + narração final) **ou**
  ring buffer curto opt-in de prompts completos para testers convidados. Default: não persistir.
- **D-c — Tamanho do ring buffer:** default 200 turnos; limites de export 500 turnos / 25 MiB.

## 9. Evidência requerida

- Saída de `uv run pytest` (suíte completa) e dos testes de integração Postgres locais.
- Um ZIP de fixture (MockLLM) com `verify_audit_zip == []` e o relatório do scan de PII, em
  `docs/spec207/evidence/` (ZIP sem dado real).
- JSON do smoke de dois usuários (status por chamada, sem ids crus).
- Diff provando que `specs/SPEC-197-*`, `docs/spec197/legal/*` e `evals/` não foram alterados.
- Parecer Astra em `handoffs/SPEC-207-ASTRA-independent-review.md`.

## 10. Registro de execução (2026-10-16)

**Defaults do dono adotados (seção 8):** D4 como descrito; D-a = incluir segredos rotulados
(`final_snapshot.private_reference` + itens não públicos com `private_label`, aviso de spoiler na UI);
D-b = não persistir prompt/resposta bruta; D-c = ring buffer 200 (`RPG_AUDIT_TRACE_MAX`), export 500
turnos / 25 MiB.

**Desvios:**
- Sem bump de `SCHEMA_VERSION` (regra da onda: o eval protegido fixa 8). `audit_trace` é campo
  ADITIVO com default `[]` em `_raw_to_state` e corte idempotente no save; teste de round-trip com save v8.
- Teste Postgres em `tests/test_audit_export_local.py` (padrão `*_local.py`, marcador `infra_local`),
  não em `tests/integration/`.
- `AUDITOR_PROMPT.md`/`README_SCHEMA.md` canônicos em `docs/auditoria/`; cópia byte-idêntica em
  `data/auditoria/` para o runtime (a `.vercelignore` exclui `docs/`), garantida por teste.
- `state/initial_snapshot.json` = projeção final com os deltas dos turnos exportados revertidos
  (não há snapshot inicial persistido); mudanças fora de turno não entram.
- `errors.jsonl`: `node` de falha LLM sai `null` (a tentativa só conhece o tier, gravado em `tier`);
  `error_class` só em `turn_failed` (nome de classe validado). `cost_basis` copia `cost_usd_basis` da SPEC-200.
- Teste de UI em Node (`web/tests/auditExport.test.mjs`, fluxo puro com API mock), não Playwright.

**Revisão Astra:** APPROVED_WITH_FIXES (scrubber ampliado, trace compactado — ring de 200 turnos reais ≈ 208 KB ≤ 400 KB, refs agrupadas + delta de `source_ids` entre turnos —, game_id sensível). Smoke em staging não executado (opcional);
smoke de 2 usuários executado contra o Supabase local. Evidência: `docs/spec207/README.md`.
