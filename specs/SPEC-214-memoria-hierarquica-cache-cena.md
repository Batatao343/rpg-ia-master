# SPEC-214 — Memória hierárquica: snapshot da cena ativa (L1), contexto do interlocutor/local (L2) e histórico sob demanda (L3)

> **Status:** `done` — **decisão `NO_GO` por medição** (dono, 2026-10-18). Medições: A/B offline de três braços turn_total p50 **−1,2 %** e context p50 0 % (o arquivista invalida o cache quase todo turno) ⇒ R13 não atendida; com provider real o contexto é só **3,94 %** do TTLT p50 (teto de ganho ~0,4 s de ~10,5 s). O código fica no branch `spec-214` (`5fe7a3c`, flag `RPG_SCENE_CACHE` default `off`), **não mergeado** na main; dataset de invalidação e revisão Astra deixam de ser necessários (sem promoção). Hipótese (a) da SPEC-217 descartada. Ver `docs/spec214/README.md`.
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-18
> **Execução (2026-10-17):** dono autorizou executar esta onda; entrada pelo **Gate R1 `GO` com provider real**
> ([gate-real-2026-10-17](../docs/spec214/gate-real-2026-10-17.md): context p95 762 ms ≥ 400 ms, share 3,94 %).
> Implementado atrás de `RPG_SCENE_CACHE` (default `off`, byte a byte ao HEAD). A/B offline de três braços
> **não atende R13** ⇒ decisão `off` (não promovido). Faltam: dataset de invalidação (EVAL_AUTHORING_REQUIRED,
> [handoff](../handoffs/SPEC-214-eval-authoring.md)) e revisão Astra. Defaults §8: P1–P4 (todos o default).
> Evidência: [docs/spec214/README.md](../docs/spec214/README.md).
> **Desvios/precisões:** memória nova invalida só slots com sessão/NPC (slot só de lore sobrevive, leitura de R3);
> fonte degradada não é cacheada; `turn_replay`/`rollback` via `note_turn_start` no início do turno; A/B usa
> `--embed-ms` (latência injetada por embedding, ≈ p50 real) porque offline o embedding não existe.
> **Gate R1:** gate não atingido em 2026-10-16; reavaliar com baseline real. `NO_GO` no baseline offline
> (`--mode scaled --scale 1.0`, seed 214): context p50/p95 = 9/36 ms (`typical`) e 5/12 ms (`slow-tail`),
> `context_share` 0,14 % / 0,08 % do TTLT p50. Default P1 aplicado. Nenhum código de produto escrito;
> limitação: offline não inclui embedding HTTP real. Evidência: [docs/spec214/gate.md](../docs/spec214/gate.md).
> **Gate R1 com provider real (staging, 2026-10-17): `GO` pela regra** — DeepSeek + Jina, 20 turnos SSE:
> context p50/p95 = 414/762 ms, TTLT p50/p95 = 10 487/14 774 ms, `context_share` 3,94 % (< 10 %) mas
> `p95(context)` ≥ 400 ms ⇒ a condição de `NO_GO` não vale. Teto de ganho ~4 % do TTLT; amostra n = 20.
> (Nota de 2026-10-17: a decisão do dono veio depois — ver **Execução** acima.) Evidência: [docs/spec214/gate-real-2026-10-17.md](../docs/spec214/gate-real-2026-10-17.md).
> **Depende de:** SPEC-200 `done` (baseline/gate), SPEC-213 `done` (cursor das projeções — recomendado), SPEC-234 `done` (ledger/resumo que não congela) · SPEC-005, SPEC-085, SPEC-146, SPEC-147, SPEC-149 e SPEC-170 `done` (insumos/régua, não reabertos) (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-215, SPEC-217 (ordem final 2026-10-15)
> **Origem:** pacote `docs/historico/proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 11
> **EXECUTOR_MODEL:** `Sol` (≡ Opus, ver docs/planos/equivalencia-modelos-claude.md) — cross-domain: estado canônico, invalidação, concorrência de turno, save/restore
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — semântica de invalidação, vazamento de segredo e critério de promoção contra a régua SPEC-170
> **EVAL_AUTHORING_REQUIRED:** `true` — fixtures determinísticas de invalidação/staleness do snapshot (troca de local, interlocutor, quest, combate, rollback, revisão de turno, morte) num dataset NOVO, autoradas em tarefa separada; a régua `evals/datasets/regression/memory_context.jsonl` e `evals/evaluators/memory.py` não são editadas

Rótulos: **[F]** fato observado no source do HEAD `6b94f66` · **[D]** decisão de produto fechada · **[H]** hipótese técnica · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[D]** `DECISOES_PRODUTO.md` § Memória e latência: a visão "cache/RAM/HD" é **hipótese arquitetural a testar**, não arquitetura decidida: pequeno estado ativo da cena; contexto relevante de interlocutor/local; história longa no archivist/RAG. Fatos canônicos persistem imediatamente. Jev não entra automaticamente (SPEC-180 `NO_GO`). O prompt 11 proíbe adotar três bancos distintos por metáfora e exige gate: sem ganho medido de TTFT/TTLT/custo (na SPEC-200: TTFMC/TTLT, `ttfmc_server_ms`/`ttlt_server_ms`; TTFT ≡ TTFMC só enquanto `pseudo_streaming=true`) com zero regressão crítica de identidade/segredo/causalidade, não promover.

**[F]** Hoje todo turno reconstrói o contexto do zero em `services/context_builder.py::build_context_pack(state, query, purpose, token_budget=3500, game_id=None, npc_id=None)` (L430): `collect_dynamic_facts` (L181) pontua fatos dinâmicos com `score_fact` (L124); `services/context_sources.py` faz **um** embedding da query (`embed_context_query`, L49) e busca lore/sessão/NPC em paralelo (`acquire_context_sources`, L104) com `RPG_CONTEXT_MAX_CONCURRENCY` limitado a 1..3 (L477); depois monta memória (resumo `compact_summary` com `NARRATIVE_SUMMARY_MAX_CHARS = 1200` em `services/memory_summary.py` L10, últimos 20 `active_memory_facts`, sessão, NPC), passando cada parte por `validate_narrative(..., channel='context')` e `find_strict_unrevealed` (L493–L499), e chama `assemble_pack` → `_assemble` (L255) com `ContextBudget(max_tokens=3500)` e quotas `current_state 0.25 / active_location 0.20 / relations 0.15 / entities 0.15 / lore 0.15 / session_memory 0.10` (L79–L89), `max_visibility="public"`.

**[F]** Callsites de produção: `agents/storyteller.py` L534 (`purpose="story"`), `agents/npc.py` L428 (`purpose="npc"`, `npc_id`), `agents/combat.py` L282 e L942, `agents/campaign_manager.py` L118 (`purpose="planning"`). `PURPOSES = ("story","npc","combat_narration","planning")` (L48). Não existe snapshot de cena persistente ou reutilizado entre turnos.

**[F]** Memória longa: FAISS por sessão em `rag.py` (`query_session_memory` L731, `prepare_shared_query_vector` L746, `query_global_by_vector` L793) e, nos perfis Postgres, `infrastructure/pgvector_memory.py::PgVectorMemoryStore` (`query` L156, `discard_after(game_id, timeline_epoch, commit_version)` L196 — documentos carregam `timeline_epoch` e `commit_version`). Proveniência/confiança em `services/memory_provenance.py` (`MemoryFactRecord` L52, `find_strict_unrevealed` L170, `MAX_MEMORY_FACTS = 500`). Relógios de continuidade em `services/continuity.py` (`session_action_count`, `timeline_epoch`, `last_checkpoint_turn`, `death_history`); checkpoints em `services/checkpoints.py` (`CHECKPOINT_EVERY = 10`, `resolve_death_choice` L106). Save em `persistence.py` com `SCHEMA_VERSION = 8`.

**[F]** A régua SPEC-170 (`done`) mede Recall@1/3/5, MRR, `context_recall_at_5`, `context_forbidden_leak_rate` e `context_token_budget_violation` (`evals/metrics-registry.yaml`). O adapter `context_grounding` (`evals/core/adapters.py` ~L455) chama `assemble_pack`/`active_memory_facts` diretamente com fatos de fixture — **não** exercita `build_context_pack` inteiro nem estado entre turnos. Logo, a régua atual não detecta snapshot obsoleto: daí `EVAL_AUTHORING_REQUIRED`.

**[H]** O ganho pode ser pequeno: se a fase `narrator` (LLM) dominar o turno, cachear contexto rende pouco. Por isso esta spec é **condicional**: a Etapa 0 decide com o baseline da SPEC-200 se vale implementar.

**Objetivo.** Especificar (a) um gate de entrada quantitativo; (b) um `SceneSnapshot` L1 derivado e recomputável, nunca fonte de verdade; (c) contexto L2 do interlocutor/local reaproveitável com invalidação explícita; (d) L3 = caminho atual (RAG/archivist) sob demanda; (e) orçamento de tokens por camada; (f) fallback integral para o builder atual; (g) A/B offline pareado e critério de promoção. Default de produção continua o builder atual até promoção explícita.

## 2. Requisitos

- **R1 — Gate de entrada.** Antes de qualquer código de produto, um relatório `docs/spec214/gate.md` lê o baseline da SPEC-200 (`latency_runs/<run_id>/summary.json`, `--mode virtual`, perfis `typical` e `slow-tail`; campos `journeys.<J>.phases.context.{p50,p95,share}` e `journeys.<J>.total`, mais `phase_ms.context` por registro) e registra `context_share = p50(context)/p50(total)`. Terminologia da SPEC-200: TTFMC/TTLT (`ttfmc_server_ms`/`ttlt_server_ms`); com pseudo-streaming, TTFMC ≈ duração do turno, então ganho de contexto aparece igualmente em TTFMC e TTLT. Se `context_share < 0.10` **e** `p95(context) < 400 ms` no perfil `typical` [R: limiar default, ver §8 P1], a spec é encerrada como `NO_GO` documentado (status `done` com decisão, sem implementação). Caso contrário, prossegue.
- **R2 — Snapshot L1 puro.** `services/scene_snapshot.py::build_scene_snapshot(state) -> SceneSnapshot` é função pura (sem I/O, sem LLM, sem embedding) derivada só do estado canônico: `location_id`/`current_location`, NPCs presentes (`npcs_for_context`), interlocutor (`active_npc_name`) **e a relação do jogador com ele** (valor canônico do NPC), combate (`combat.active`, round, inimigos vivos com id/nome/Vitalidade), **ameaças** (`world.danger_level` + inimigos vivos), **eventos recentes da cena** (ids/tipos dos últimos N=5 `event_log` com `location_id` atual, renderizados pelo template já existente), objetivo público (mesma fonte da view pública da SPEC-115, nunca beats privados), **segredos acessíveis** (apenas ids revelados ao jogador: `player.known_secrets`/`revealed_facts`; nunca texto `hidden/secret` não revelado), relógio/período, clima/luz. (Prompt 11 exige local, atores, memória do interlocutor, relação, objetivo, ameaças, eventos recentes e segredos acessíveis; a memória do interlocutor é L2.) Mesma entrada ⇒ snapshot byte-idêntico (serialização canônica).
- **R3 — Chave de versão.** `SceneSnapshot.key` é um hash estável sobre: `game_id`, `timeline_epoch`, `location_id`, interlocutor, `combat.active`+round, id da quest ativa, `continuity.last_checkpoint_turn`, `len(death_history)`, **versão de memória** (`len(memory_facts)` + último `memory_id` do ledger + contador de writes de memória privada do interlocutor; se SPEC-213 `done`, `projection_state.memory.projected_version`) e **hash do conjunto revelado** (`known_secrets`/`revealed_facts`). Não inclui `world.turn_count` (mudaria todo turno e zeraria o hit de L2; e volta no rollback). Memória escrita no turno N invalida o bloco de sessão/NPC do L2 no turno N+1 (teste `test_new_memory_fact_invalidates_l2_session_block`). Qualquer mudança em um desses campos produz chave diferente.
- **R4 — Nunca fonte de verdade.** Nenhum agente lê dado mecânico do snapshot; o snapshot só alimenta **texto de contexto**. Removê-lo do estado/cache e reconstruir dá o mesmo resultado (teste de recomputação).
- **R5 — Invalidação explícita.** O cache L1/L2 é invalidado (entrada descartada, não "atualizada") por: troca de local, troca de interlocutor, criação/conclusão/mudança de quest ativa, início/fim/troca de round de combate, restore de checkpoint/rollback (`timeline_epoch` muda), revisão/replay de turno (`action_id` reprocessado), morte/`death_pending`, e `secret_revealed` aceito (o conjunto revelado muda o que pode entrar). Cada causa tem teste próprio.
- **R6 — L2 por interlocutor/local.** `ContextTier2` guarda, por chave `(snapshot_key, purpose, npc_id)`, os blocos de lore/sessão/NPC **já validados** (pós `validate_narrative` e `find_strict_unrevealed`) e suas `evidence_ids`. Hit de L2 pula `embed_context_query`/`acquire_context_sources`; a query do turno ainda entra em `score_fact` para os fatos dinâmicos (L1 nunca reaproveita ranking dependente da fala).
- **R7 — L3 sob demanda.** Miss ou sinal de "assunto novo" (termos da query sem interseção com o L2 cacheado, regra determinística em Python, sem LLM) cai no caminho atual integral (RAG lore+sessão+NPC). Hipótese (a) da SPEC-217 é exatamente esta decisão `scene_cache | deep_rag`; aqui ela é Python.
- **R8 — Orçamento por camada.** `ContextBudget` ganha quotas por camada configuráveis com total ≤ `token_budget` (default 3500): L1 ≤ 600 tokens, L2 ≤ 1900, L3 ≤ 1000 [R, §8 P2]. Sobra de uma camada não estoura o total. `context_token_budget_violation` permanece 0.
- **R9 — Segredos.** Nenhuma camada inclui texto com assinatura `hidden/secret` não revelada; o filtro roda **na escrita** do cache e **de novo na leitura** (o conjunto revelado pode ter mudado — e R5 invalida). `max_visibility="public"` inalterado.
- **R10 — Fallback.** Qualquer exceção, chave ausente, versão de schema do snapshot desconhecida ou flag desligada ⇒ `build_context_pack` atual, sem erro visível ao jogador; contador `rpg_context_cache_fallback_total{reason}`.
- **R11 — Flag e modos.** `RPG_SCENE_CACHE=off|shadow|l1_only|on`, default `off`. `l1_only` (só para A/B/eval, nunca default) = snapshot L1 renderizado + caminho atual integral de L2/L3 sem cache — é o braço "snapshot de cena" exigido pelo prompt 11; `on` = híbrido L1+L2 cacheado+L3 sob demanda. `shadow` calcula as duas versões, entrega a do builder atual e registra divergência (conjunto de `evidence_ids`, tokens) sem texto do jogador. `on` só após promoção (R13).
- **R12 — Telemetria.** Fase `context` da SPEC-200 continua medida; acrescenta-se aditivamente em `rpg.turn`: `context_cache` (`off|hit_l1|hit_l2|miss|fallback`), `context_layers_tokens` `{l1,l2,l3}`, `context_invalidation_reason`. Sem `game_id` cru nem texto.
- **R13 — Promoção.** Comparação de **três braços** pareados: `off` (builder/RAG atual), `l1_only` (snapshot) e `on` (híbrido). `on` só com: (i) A/B offline pareado (mesmas jornadas/seed da SPEC-200, MockLLM com latência injetada) mostrando redução de `p50(context)` ≥ 30% e de `p50(turn_total)` ≥ 5% [R, §8 P3], ou custo de embeddings/turno reduzido ≥ 30%; (ii) zero regressão na régua SPEC-170 (Recall@1/3/5, MRR, `context_recall_at_5`, leak = 0, budget = 0) rodada contra o comportamento `on`; (iii) 100% verde no dataset novo de invalidação (EVAL_AUTHORING_REQUIRED); (iv) zero violação `error` de identidade/segredo/causalidade nos invariantes de playtest num smoke offline curto. Falhou qualquer um ⇒ fica `off`/`shadow`.
- **R14 — Concorrência.** Cache é por processo, indexado por `game_id`, protegido por lock; turnos do mesmo jogo já são serializados (SPEC-086/111). Em perfis multi-instância o cache é só best-effort local; correção não depende de hit.

### Fora de escopo

- Jev ou qualquer classificador LLM para decidir L1/L2/L3 (SPEC-217).
- Mover o archivist/projeções para segundo plano (SPEC-213); `validate_narrative` segue síncrona (D5).
- Streaming real de tokens, mudanças de prompt/narrador, novos tiers de LLM.
- Cache compartilhado entre instâncias (Redis etc.) ou nova tabela Postgres.
- Conhecimento por NPC/propagação de rumores (SPEC-215) — L2 usa a memória privada de NPC que já existe.
- Editar `evals/` protegido; campanhas 100/200 turnos; provider real por padrão.

## 3. Design técnico

**Arquivos novos**
- `services/scene_snapshot.py` — `SceneSnapshot` (dataclass frozen), `SNAPSHOT_SCHEMA = 1`, `build_scene_snapshot(state) -> SceneSnapshot`, `snapshot_key(state) -> str`, `render_l1(snapshot, max_tokens) -> str`.
- `services/context_cache.py` — `ContextCache` (LRU por processo, `maxsize` por env `RPG_SCENE_CACHE_MAX_GAMES`, default 64), `get_l2(key)`, `put_l2(key, entry)`, `invalidate(game_id, reason)`, `invalidation_reason(prev_key_parts, cur_key_parts) -> Optional[str]`.
- `docs/spec214/gate.md` (Etapa 0) e `docs/spec214/README.md` (A/B e decisão).
- `tests/test_scene_snapshot.py`, `tests/test_context_cache.py`, `tests/test_context_layers_ab.py`.

**Arquivos alterados**
- `services/context_builder.py` — `build_context_pack` ganha despacho interno por `RPG_SCENE_CACHE` (assinatura pública **inalterada**; callsites intocados). `ContextBudget` ganha `layer_quota: Dict[str,int]` opcional (default `None` ⇒ comportamento atual byte a byte). `ContextPack` ganha campos opcionais `cache_status: str = "off"`, `layer_tokens: Dict[str,int] = {}`.
- `api.py::_log_turn` — campos aditivos de R12 (lidos de um ContextVar de turno já existente no padrão da SPEC-200).
- `observability/metrics.py` — `rpg_context_cache_total{status}`, `rpg_context_cache_fallback_total{reason}`.

**Schema**
```python
@dataclass(frozen=True)
class SceneSnapshot:
    schema: int                    # SNAPSHOT_SCHEMA
    key: str                       # sha256 hex de key_parts canônicos
    key_parts: tuple               # (game_id, epoch, location_id, npc_id, combat_active, round, quest_id, ckpt_turn, deaths, memory_version, revealed_hash)
    location: str
    present_npcs: tuple[str, ...]  # ordenado
    interlocutor: str | None
    interlocutor_relation: int | None
    threats: tuple                 # (danger_level, n_enemies_alive)
    recent_events: tuple[str, ...] # event_ids da cena, ≤5
    revealed_secret_ids: tuple[str, ...]
    combat: tuple | None           # (round, ((enemy_id, name, vit, max_vit), ...))
    public_objective: str | None
    clock: str                     # "dia N, período"
    weather_light: str
```
`L2Entry = {lore_block, session_block, npc_block, evidence_ids, revealed_set_hash, created_turn}`.

**Contrato de montagem (modo `on`)**: `facts = collect_dynamic_facts(...)` (sempre recomputado) + `render_l1(snapshot)` como seção `current_state` + L2 hit (ou L3 = `acquire_context_sources` atual) → `_assemble` com quotas por camada. Ordem de prioridade preservada: estado vivo antes de lore (SPEC-005).

**State ownership.** [F→D desta spec] Nenhum campo novo em `GameState` nem no save; `SCHEMA_VERSION` permanece 8. O snapshot é efêmero; dono = `services/context_cache.py` do processo. Fonte de verdade continua `GameState` + event_log/projection + ledger de memória (SPEC-085) + FAISS/pgvector.

**Degradação.** Cache vazio após reinício/deploy = miss ⇒ caminho atual. Sem embeddings disponíveis ⇒ comportamento atual (degradação já existente do RAG).

**UI.** Nenhuma mudança visível. Contrato de UI inalterado.

## 4. Plano passo a passo (TDD)

### Etapa 0 — Gate (sem código de produto)
1. Ler `docs/spec200/README.md`/`latency_runs/<run_id>/summary.json`; preencher `docs/spec214/gate.md` com `context_share`, p50/p95 por jornada, custo de embedding/turno (`usage_events`, SPEC-182).
2. Decisão `GO`/`NO_GO` por R1. `NO_GO` ⇒ atualizar spec para `done` com a decisão; parar.

### Etapa 1 — Handoff de eval (tarefa separada, outro executor)
1. Preparar `handoffs/SPEC-214-eval-authoring.md`: dataset novo `evals/datasets/regression/scene_cache_invalidation.jsonl` com ≥ 1 caso por causa de R5 + caso "segredo revelado no meio" + caso "rollback descarta memória pós-epoch"; adapter novo que chama `build_context_pack` em sequência de estados. Autor ≠ implementador; registry/lock atualizados por ele.

### Etapa 2 — Snapshot L1
1. **Testes** (`tests/test_scene_snapshot.py`): `test_snapshot_deterministic`; `test_snapshot_includes_relation_threats_recent_events`; `test_snapshot_secrets_only_revealed_ids`; `test_snapshot_has_no_private_beats` (beats/clímax privados ausentes); `test_key_changes_on_each_invalidation_field` (parametrizado por campo de R3); `test_recompute_equals_cached` (R4); `test_render_l1_respects_token_cap`.
2. **Implementação:** `services/scene_snapshot.py`.

### Etapa 3 — Cache L2 e invalidação
1. **Testes** (`tests/test_context_cache.py`): `test_invalidate_on_location_change`, `..._interlocutor_change`, `..._quest_change`, `..._combat_start_end_round`, `..._checkpoint_restore_epoch`, `..._turn_replay`, `..._death_pending`, `..._secret_revealed`, `test_new_memory_fact_invalidates_l2_session_block`; `test_secret_filtered_on_write_and_read`; `test_lru_bound`; `test_thread_safe_put_get`.
2. **Implementação:** `services/context_cache.py`.

### Etapa 4 — Integração com flag
1. **Testes**: `test_off_is_byte_identical_to_current` (mesmo `ContextPack` que HEAD para estados de fixture); `test_shadow_returns_current_and_logs_divergence`; `test_on_hit_skips_embedding` (contador de `embed_context_query` = 0 no hit); `test_fallback_on_exception` (R10); `test_layer_quota_never_exceeds_total` (R8); `test_rpg_turn_additive_fields` (R12, sem texto/`game_id`).
2. **Implementação:** despacho em `build_context_pack`, quotas em `ContextBudget`, telemetria.
3. **Verificação:** `uv run pytest tests/test_scene_snapshot.py tests/test_context_cache.py tests/test_context_builder*.py` e depois suíte completa.

### Etapa 5 — A/B offline pareado
1. `tests/test_context_layers_ab.py` + execução de `scripts/latency_baseline.py` (SPEC-200, `--mode virtual`) com `RPG_SCENE_CACHE=off`, `l1_only` e `on`, mesmas jornadas/seed/perfis; `compare` exige fingerprint compatível (o valor da flag entra no fingerprint/`records.jsonl` para não misturar braços).
2. Rodar régua SPEC-170 e dataset de invalidação com `on`; smoke playtest offline curto (R13 iv).
3. Registrar em `docs/spec214/README.md`. Decidir `on`/`shadow`/`off` pela regra pré-declarada de R13.

## 5. Critérios de aceite

- [x] `docs/spec214/gate.md` com decisão `GO`/`NO_GO` fundamentada no baseline SPEC-200. (`NO_GO` 2026-10-16, offline; `GO` 2026-10-17 com provider real em `gate-real-2026-10-17.md`)
- [x] (se GO) Snapshot puro, determinístico, sem beats privados; recomputação idêntica. (`tests/test_scene_snapshot.py`)
- [x] (se GO) Cada causa de invalidação de R5 tem teste verde; segredo filtrado na escrita e na leitura. (`tests/test_context_cache.py`)
- [x] (se GO) `RPG_SCENE_CACHE=off` produz `ContextPack` idêntico ao HEAD (teste de paridade; golden do HEAD `8823bb0`).
- [ ] (se GO) Régua SPEC-170 sem regressão com `on`; dataset de invalidação 100% verde; `context_forbidden_leak_rate = 0`, `context_token_budget_violation = 0`. (Régua: igual a `off`, leak 0, budget 0 — mas o adapter não exercita a flag. **Falta** o dataset de invalidação: handoff.)
- [x] (se GO) A/B offline pareado de três braços (`off`/`l1_only`/`on`) registrado; promoção só se R13 for atendido, senão default permanece `off`. (R13 não atendido: −1,2 % turn_total, 0 % context p50 ⇒ `off`.)
- [x] Nenhum campo novo em save; saves `SCHEMA_VERSION = 8` carregam sem migração.
- [x] `uv run pytest` verde (suíte completa offline: 3685 passed, 227 skipped); Ruff verde nos arquivos tocados.
- [x] Nenhum `with_structured_output` novo (se surgir, guard de FallbackLLM obrigatório).

## 6. Smoke

**Offline (obrigatório):**
1. `uv run python scripts/latency_baseline.py run --journeys all --reps 30 --seed 214 --profile typical --mode virtual` com `RPG_SCENE_CACHE=off`, `l1_only` e `on` (repetir com `slow-tail`); `report`/`compare`. Com n < 20 o relatório da SPEC-200 marca "p95 indicativo" — por isso `--reps 30`.
2. `uv run python -m evals --root . run --dataset datasets/regression/memory_context.jsonl --run-id spec214-on` com `RPG_SCENE_CACHE=on`; idem para o dataset de invalidação.
3. `uv run python -m playtest run --profile normal --turns 30 --seed 214` (MockLLM) com `on`: zero violação `error`, cache hits > 0 e invalidações registradas em troca de local/combate/morte.

**Provider real (opt-in, nunca default):** só com autorização expressa do dono, perfil `deepseek-paid`, 1 campanha × 20 turnos por braço (`off`/`on`), teto **US$ 0,10 e 120 requests no total**; mede `phase_ms.context`, custo de embedding e TTLT. Sem autorização, a promoção usa só a evidência offline e o relatório declara isso.

## 7. Riscos & compatibilidade

- **Saves:** sem mudança de schema; nada persistido. Risco zero de migração. [D desta spec]
- **Snapshot obsoleto (risco principal) [H]:** campo canônico relevante fora da chave ⇒ contexto velho. Mitigação: L1 só é *render* do estado atual (recomputado a cada turno; o "cache" real é L2), chave conservadora, `shadow` antes de `on`, dataset de invalidação.
- **Vazamento de segredo:** revelação muda conjunto permitido; mitigado por R5 (`secret_revealed` invalida) + R9 (filtro na leitura).
- **Ganho irrisório [H]:** se o LLM domina, R1 encerra cedo com `NO_GO` — resultado válido.
- **Multi-instância (Vercel/serverless):** hits raros entre instâncias; correção preservada porque miss = caminho atual.
- **MockLLM:** contexto não é structured output; MockLLM não mascara mapeamento aqui, mas não mede qualidade de prosa — A/B offline mede latência/recuperação, não narrativa.
- **Custo de manutenção [R]:** cada campo canônico novo que afete contexto precisa ser avaliado contra a chave de R3; checklist no `docs/spec214/README.md` e teste parametrizado de R3 tornam o esquecimento visível. Se o custo de manter a chave superar o ganho medido, preferir `off`.
- **Interação:** SPEC-213 pode mudar quando o summary/ledger é atualizado; se `done`, a chave usa o cursor dela, senão `turn_count`. SPEC-217 consome R7 como alvo.

## 8. Pontos de decisão do dono

- **P1 — Limiar do gate R1.** Default recomendado: `context_share < 10%` e `p95(context) < 400 ms` ⇒ `NO_GO`. Alternativa: exigir também custo de embedding < X% do custo do turno.
- **P2 — Quotas por camada.** Default L1 600 / L2 1900 / L3 1000 dentro de 3500. Alternativa: manter as quotas por seção atuais e só cachear (quotas por camada ficam informativas).
- **P3 — Critério de promoção.** Default: −30% `p50(context)` e −5% `p50(turn_total)` **ou** −30% custo de embedding, com zero regressão. Alternativa mais estrita: exigir também smoke real opt-in.
- **P4 — Smoke real.** Default: não executar; promoção baseada em evidência offline. Se autorizar, teto da §6.

## 9. Evidência requerida

- `docs/spec214/gate.md` (números do baseline SPEC-200, decisão).
- `docs/spec214/README.md`: tabela A/B `off` vs `on` (p50/p95 de `context` e `turn_total` por jornada, hits/misses/fallbacks, tokens por camada, chamadas de embedding/turno), run IDs e hashes da régua SPEC-170 e do dataset de invalidação, resumo do playtest offline, decisão final `on|shadow|off`.
- Handoff de eval `handoffs/SPEC-214-eval-authoring.md` e parecer independente Astra em `handoffs/SPEC-214-ASTRA-review.md`.
- Saída de `uv run pytest` (contagem) e Ruff.
