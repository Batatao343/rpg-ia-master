# SPEC-215 — Conhecimento por NPC e propagação limitada de notícias

> **Status:** `done` (código + testes + smokes entregues; revisão Astra APPROVED_WITH_FOLLOWUPS; dataset `npc_knowledge` autorado; Project Index regenerado pelo coordenador no land)
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-16
> **Depende de:** SPEC-202 `done` (interlocutor), SPEC-206 `done` (taxonomia), SPEC-214 `done` (cache de cena — recomendado), SPEC-223 `done` (mesmos `agents/npc.py`/`event_processor`; prova de eventos), SPEC-230 `done` (ciclo de vida do NPC) (ordem final 2026-10-15)
> **Desbloqueia:** nada obrigatório (ordem final 2026-10-15)
> **Origem:** pacote `proximas-specs/pacote-prompts-rpg-beta-2026-10-15/`, prompt 12 (parte b). Contexto histórico apenas: `historico-nao-executar/HISTORICO_SPEC-176*` (não executar).
> **EXECUTOR_MODEL:** `Sol` (≡ Opus, ver `docs/planos/equivalencia-modelos-claude.md`)
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — dataset novo `npc_knowledge` (testemunha/distância/mensageiro/mentira/save/spoiler) + oráculos de vazamento e de teleporte; autoria em tarefa separada, antes da implementação, sem que o executor edite evaluator/expected.
> **Prioridade:** P2 (após o beta desktop). [R] `DECISOES_PRODUTO.md` coloca "consistência profunda de memórias/segredos" em P3; o coordenador desta onda fixou P2 — ver §8 D0.
> **Nota de schema (cadeia final 2026-10-15):** ordem dos bumps de `SCHEMA_VERSION` (hoje 8): SPEC-228 primeiro (R9 recusa save de versão mais nova; sem bump) → [SPEC-227 só se D-C = migração; default sem bump] → SPEC-202 → SPEC-203 → SPEC-207 → SPEC-213 → SPEC-215. Nenhuma outra spec 199–236 altera o schema de save (SPEC-228 R7 `needs_replan` e SPEC-231 `scene_allies` usam default/campo existente, sem bump). Cada spec usa o próximo `SCHEMA_VERSION` livre no HEAD ao implementar e encadeia sua migração após a anterior; onde o texto disser "v8→v9", leia "vN→vN+1".

---

## 1. Contexto & Objetivo

Hoje todo NPC que fala é **onisciente sobre o mundo dinâmico e sobre a experiência do jogador**.
[F] `agents/npc.py:428` chama `build_context_pack(state, …, purpose="npc", npc_id=…)`; em
`services/context_builder.py:209-247` (`collect_dynamic_facts`) o pack injeta, sem filtro por
holder: as últimas 100 entradas de `event_log` (inclusive `npc_killed` ocorrido em qualquer
região, template em `context_builder.py:64`), `world_projection.revealed_facts`, o status vivo/morto
de todas as entidades da projection; e em `context_builder.py:512-533` o `narrative_summary` do
jogador, as últimas 20 `memory_facts` da sessão (ledger do jogador) e a memória privada do NPC.
[F] O prompt reforça a onisciência: `agents/npc.py:494` — "O estado atual acima é a verdade de AGORA."
O único freio é textual: `agents/npc.py:501` ("Um camponês comum NÃO conhece os planos de cultos
distantes") e as regras de atuação 1–2 (`agents/npc.py:507-511`), que dependem da LLM obedecer.

[F] Não existe modelo de conhecimento por NPC: `grep observed_by|told_to|believed_by` em
`services/`, `agents/`, `state.py`, `api.py`, `main.py` = 0 ocorrências. Não existe propagação
de notícia no tempo/espaço. O que existe e será **reaproveitado, não duplicado**:

- [F] Verdade do mundo: `GameEvent` (`state.py:350`) em `event_log` append-only + `WorldProjection`
  (`state.py:401`), produzidos por `services/event_processor.py` após `services/world_validators.py`.
- [F] Autoridade de relatos: `services/memory_provenance.py` — `MemoryProvenance`
  (`canonical_event|player_observation|npc_claim|inference|legacy_unverified`), confiança derivada
  em `_CONFIDENCE_BY_PROVENANCE` (l.33) e nunca controlada pela LLM (`_derive_authority`, l.87).
- [F] Memória privada do NPC: `rag.add_npc_memory` (l.1128) / `rag.query_npc_memory` (l.1266),
  namespace `game_id+npc_id`; escrita `npc_claim` em `agents/npc.py:571-591`; retry em
  `services/memory_retry.py` (`pending_npc_memory`, teto 50); ledger espelhado (SPEC-114).
- [F] Segredos: `services/secret_signatures.py` (`revealed_corpus` l.45, `find_unrevealed` l.71),
  `player.known_secrets`, `memory_provenance.find_strict_unrevealed` (l.170), visibilidade
  `hidden/secret` no RAG e no `ContextBudget.max_visibility`.
- [F] Presença/local: `services/npc_layers.py` — `npcs_in_scene` (l.91), `npcs_for_context` (l.115),
  `home_location_id`, sorteio seeded por `sha256(npc_id|game_id)` (l.47).
- [F] Tempo/espaço: `world_utils.advance_clock` (l.45, 5 períodos/dia), `travel_cost` (l.132,
  `travel_times` do `data/world_map.json`). O relógio só avança dentro de `world_utils`
  (`advance_clock` chamado em l.170/175/188 por `apply_travel` e l.261 por `apply_rest`); esses são
  invocados pelo storyteller (viagem l.~330, descanso l.~365) **e também** pela fuga de combate
  (`agents/combat.py`, `apply_travel` na fuga, SPEC-038). Por isso o ponto autoritativo de entrega é
  o `turn_finalizer` (§3.1), não o storyteller.
- [F] Visão do jogador: `services/discovery.player_codex` (l.219), `npc_layers.visible_npc_view`
  (l.194) — nenhum dos dois expõe estado privado de NPC; SPEC-206 define a taxonomia pública.

**Objetivo:** dar a cada NPC um conhecimento **derivado** do ledger existente — quem observou, a
quem foi contado, quem acredita — com propagação determinística, limitada e atrasada pela
geografia, e fazer o `npc_actor` só receber no contexto o que aquele NPC sabe ou acredita.
Mecânica 100% Python; a LLM continua só atuando.

## 2. Requisitos

- **R1 — Relações, não verdade nova.** `world_truth` é exclusivamente o `GameEvent` canônico /
  `WorldProjection`. `observed_by`, `told_to`, `believed_by` são **relações** sobre um *assunto*
  (`event_id` canônico ou `memory_id` de `MemoryFact`). Nenhuma relação altera `event_log`,
  projection, `provenance` ou `confidence` de `MemoryFact`. `unknown` = ausência de relação.
- **R2 — Testemunha.** Ao aplicar evento canônico elegível (§3.3) no local L, todo NPC presente em
  L no turno (`npcs_in_scene` + party ativa presente) recebe `observed_by` + `believed_by`
  (`channel="witness"`, `hops=0`). NPC fora de L não recebe nada.
- **R3 — Sem teleporte.** Um NPC cuja localização é L2 ≠ L só passa a saber do assunto quando uma
  entrega chega a L2 com `due_clock ≥ acquired_clock + distância(L, L2)` (Dijkstra sobre
  `travel_times`, mesmo semântico de `travel_cost`; interior = 0) **+ atraso de mensageiro** (§3.4).
  Carregar save, recriar NPC, trocar de interlocutor ou reiniciar o processo não antecipa entrega.
- **R4 — Propagação limitada e seeded.** Cada entrega é decidida por
  `sha256(game_id|subject_id|from_loc|to_loc|hop)` contra probabilidade por tipo/impacto;
  máximo `MAX_HOPS=2` (testemunha → mensageiro → cidade distante), raio máximo por tipo, teto
  global de links e de fila. Mesmo save + mesma sequência de ações = mesmas entregas (replay).
- **R5 — Mentira/rumor nunca vira fato.** Assunto `npc_claim`/`inference`/rumor de `WorldPulse` pode
  ser `told_to`/`believed_by`, mas nunca promove `confidence`, nunca cria `GameEvent`, nunca entra em
  `revealed_facts` e sempre chega ao prompt rotulado `[BOATO]`/`[OUVIU DIZER]`. Um NPC pode
  *acreditar* numa mentira; isso fica na relação do NPC, não no mundo.
- **R6 — Gate no contexto do `npc_actor`.** Com o flag em `on`, `build_context_pack(purpose="npc")`
  inclui de `event_log`/`entities`/`revealed_facts`/`memory_facts` **somente** assuntos com relação
  para aquele `npc_id`, mais a memória privada do NPC e o lore público. O status "morto" de uma
  entidade só aparece se o NPC sabe da morte. O texto `npc.py:494` passa a falar do que o
  personagem sabe.
- **R7 — Segredo.** Assunto com assinatura `hidden/secret` não revelada (`find_strict_unrevealed`)
  nunca é propagado, e nunca entra no contexto, exceto para o holder com relação `observed_by`
  direta; mesmo assim jamais chega ao jogador fora do fluxo `secret_revealed` existente (SPEC-024).
- **R8 — Jogador vê só projeção pública.** `knowledge_links` e a fila nunca são serializados por
  `/game/state`, codex, SSE, tooltip, arte ou export público; o jogador só percebe o que o NPC
  *disse* (vira `player_observation`/`npc_claim` pelo caminho atual) e o que a SPEC-206 classificar.
- **R9 — Jogador conta ao NPC.** (`BELIEF_MIN_RELATIONSHIP = 6` [BALANCEAR], escala 0–10 do campo
  `relationship` existente, default 5 — [F] `agents/npc.py:95,360`; mesmo limiar de amizade usado
  por `party.scene_allies` (`SCENE_ALLY_MIN_REL = 6`, [F] `party.py:33`), SPEC-055.) Se a fala do jogador ao NPC menciona (alias canônico, SPEC-149) uma
  entidade cujo assunto o **jogador** conhece, gera `told_to(source="player")`; `believed_by`
  só se `relationship ≥ BELIEF_MIN_RELATIONSHIP` (determinístico). Fala do jogador não vira fato.
- **R10 — NPC gerado depois.** NPC criado em L herda como `told_to(channel="local_rumor")` apenas o
  que já foi entregue a L (`location_heard`) antes da sua criação; nunca o que ainda está na fila.
- **R11 — Custo de contexto limitado.** No máximo `NPC_KNOWLEDGE_CONTEXT_MAX=8` fatos de
  conhecimento por prompt, dentro do `token_budget` atual (3500) — sem aumentar o budget nem
  chamadas LLM. Zero chamadas LLM novas na propagação.
- **R12 — Cronologia.** Relações são ordenadas por `acquired_clock`; o NPC nunca "sabe antes" de ter
  sabido; relação/identidade/pronomes do NPC preservados (SPEC-149) através de save/load.
- **R13 — Migração sem retroatividade.** Save sem `knowledge_links` (schema ≤ 8) carrega com ledger
  vazio e flag `legacy_knowledge=true`: o NPC sabe apenas o que já está em sua memória privada
  (FAISS/pgvector `npc_id`) e em `npc.memory`; nenhum evento passado é distribuído
  retroativamente. Eventos novos seguem R2–R4.
- **R14 — Rollout reversível.** `RPG_NPC_KNOWLEDGE=off|shadow|on`, default `off`. `shadow` registra
  links e mede (log `rpg.npc_knowledge`: fatos filtrados vs. o pack atual) sem alterar o prompt;
  `on` aplica o gate. `off` = comportamento byte a byte atual do contexto.

### Fora de escopo

- Lore autoral e segredos de NPC em `data/codex/` (SPEC-024): continuam pelo RAG com visibilidade.
- Mostrar ao jogador "o que o NPC sabe" (UI de dossiê) — consumidor futuro via SPEC-206/211.
- Simulação social completa (NPC↔NPC conversando off-screen, fofoca emergente por LLM).
- Conhecimento de facções (`faction_intel` continua do jogador; não muda).
- Memória de criaturas/bestiário (`services/discovery.py`, `bestiary_knowledge`).
- Tabela SQL nova no perfil hosted: o ledger vive no snapshot do save, como `memory_facts`.
- Otimização de latência (SPEC-200/214).

## 3. Design técnico

### 3.1 Arquivos

- **Novo `services/npc_knowledge.py`** — owner único do ledger: tipos, `record_witnesses`,
  `record_player_told`, `schedule_propagation`, `deliver_due`, `known_subject_ids`,
  `inherit_local`, `normalize_knowledge`, `npc_knowledge_block`. Puro, sem LLM, sem I/O.
- **Novo `services/world_distance.py`** — `travel_periods(from_id, to_id) -> int | None`, Dijkstra
  cacheado sobre `data/world_map.json` reutilizando a regra de `world_utils.travel_cost`.
- **`state.py`** — `KnowledgeLink`, `KnowledgeDelivery`, campos `knowledge_links`,
  `knowledge_queue`, `location_heard`, `legacy_knowledge` em `GameState`.
- **`services/event_processor.py`** — após aplicar evento elegível, chama `record_witnesses` e
  `schedule_propagation` (mesma transação lógica do turno; não em worker).
- **`agents/turn_finalizer.py`** — chama `deliver_due(state, clock_index)` **uma vez por turno**
  (idempotente por `delivery_id`), depois de qualquer avanço de relógio do turno (viagem, descanso,
  fuga de combate). É o único ponto de entrega; storyteller/combat não chamam `deliver_due`
  (evita dupla entrega e cobre a fuga). `clock_index = day*5 + PERIODS.index(period)`.
- **`agents/npc.py`** — `record_player_told` antes do invoke; `inherit_local` em `generate_new_npc`;
  texto da l.494 trocado; passa `npc_id` e flag ao pack.
- **`services/context_builder.py`** — `collect_dynamic_facts(..., knowledge_filter: set[str]|None)`;
  para `purpose="npc"` com flag `on`, filtra `event_log`/`entities`/`revealed_facts` por assunto e
  exclui `memory_facts`/`narrative_summary` do jogador (§8 D2); bloco `npc_knowledge_block` limitado.
- **`persistence.py`** — `SCHEMA_VERSION` 8→9, `_migrate_v8_to_v9` (R13), normalização no save/load.
- **`api.py`** — teste de não-serialização (nenhum código de exposição novo).
- **`playtest/invariants.py`** — invariantes `knowledge.teleport` e `knowledge.rumor_promoted` (error).

### 3.1b Mapeamento dos termos do prompt 12 para o que existe (sem ontologia paralela)

| Termo do prompt 12 | Representação nesta spec | Owner existente reaproveitado |
|---|---|---|
| `world_truth` | `GameEvent` em `event_log` + `WorldProjection` (sem campo novo) | `services/event_processor.py` |
| `observed_by` | `KnowledgeLink.relation="observed_by"` (`channel="witness"`) | novo ledger (só relação) |
| `told_to` | `KnowledgeLink.relation="told_to"` | novo ledger |
| `believed_by` | `KnowledgeLink.relation="believed_by"` | novo ledger |
| `rumor` | assunto `memory_fact` com `provenance ∈ {npc_claim, inference}` ou `told_to` sem `believed_by`; rótulo `[BOATO]` | `services/memory_provenance.py` |
| `unknown` | ausência de link para o holder | — |
| `secret_visibility` | `visibility hidden/secret` + `find_strict_unrevealed` / `secret_signatures.find_unrevealed` | `services/secret_signatures.py`, `memory_provenance.py` |

**Alinhamento com a SPEC-206 (taxonomia visível ao jogador).** O ledger desta spec é **privado**
(R8) e não produz `KnowledgeKind`. Se um consumidor futuro (dossiê SPEC-211) quiser mostrar "o
que o NPC parece saber", deve projetar via SPEC-206 usando só o que o NPC **disse ao jogador** (já
`npc_claim` → `knowledge_kind=report|rumor`, `certainty=reported`), nunca lendo `knowledge_links`.
Nenhum valor novo de `KnowledgeKind`/`MemoryConfidence` é criado aqui.

### 3.2 Schemas (`state.py`)

```python
class KnowledgeLink(TypedDict, total=False):
    link_id: str            # sha256(holder|subject|relation|acquired_clock)[:16]
    holder_id: str          # "npc:<npc_id canônico>" | "loc:<location_id>"
    subject_kind: Literal["event", "memory_fact"]
    subject_id: str         # GameEvent.event_id | MemoryFact.memory_id
    relation: Literal["observed_by", "told_to", "believed_by"]
    source: str             # "world" | "player" | "npc:<id>" | "loc:<id>"
    channel: Literal["witness", "messenger", "local_rumor", "player"]
    hops: int               # 0 testemunha; ≤ MAX_HOPS
    acquired_clock: int     # day*5 + period_index (advance_clock)
    acquired_turn: int

class KnowledgeDelivery(TypedDict, total=False):
    delivery_id: str
    subject_kind: str; subject_id: str
    from_location_id: str; to_location_id: str
    hop: int; due_clock: int; created_turn: int
```

`GameState`: `knowledge_links: List[KnowledgeLink]` (teto `MAX_KNOWLEDGE_LINKS=2000`, despejo dos
links `loc:` mais antigos primeiro, nunca `observed_by`), `knowledge_queue: List[KnowledgeDelivery]`
(teto 200, FIFO por `due_clock`), `location_heard: Dict[str, List[str]]` (subject ids por local,
teto 100/local), `legacy_knowledge: bool`.

### 3.3 Assuntos elegíveis e parâmetros (constantes Python, `[BALANCEAR]`)

| Assunto | p entrega por hop | raio máx. (períodos) | hops |
|---|---|---|---|
| `npc_killed` | 0.8 | 15 | 2 |
| `location_control_changed` | 0.9 | 20 | 2 |
| `route_blocked`/`route_cleared` | 0.7 | 10 | 1 |
| `quest_completed` | 0.5 | 5 | 1 |
| `memory_fact` `npc_claim`/`inference` (rumor) | 0.35 | 5 | 1 |
| `secret_revealed` / qualquer assinatura hidden/secret não revelada | 0 | 0 | 0 |

Atraso de mensageiro: `+1 + (seed % 3)` períodos por hop. Destinos de um hop: locais com NPC
registrado ou com `location_heard` possível, até 4 destinos por hop, ordenados por distância.

### 3.4 Assinaturas

```python
def record_witnesses(state: dict, event: GameEvent, location_id: str, clock: int) -> list[KnowledgeLink]
def record_player_told(state: dict, npc_id: str, player_text: str, clock: int) -> list[KnowledgeLink]
def schedule_propagation(state: dict, subject_kind: str, subject_id: str,
                         from_location_id: str, clock: int, hop: int = 1) -> list[KnowledgeDelivery]
def deliver_due(state: dict, clock: int) -> dict   # parcial: knowledge_links/queue/location_heard
def inherit_local(state: dict, npc_id: str, location_id: str, clock: int) -> list[KnowledgeLink]
def known_subject_ids(state: dict, npc_id: str) -> dict[str, set[str]]  # {"believed","heard"}
def npc_knowledge_block(state: dict, npc_id: str, limit: int = 8) -> str
def normalize_knowledge(raw: dict) -> dict          # tolerante a save adulterado
def travel_periods(from_id: str, to_id: str) -> int | None
```

Todas retornam dicts parciais/novas listas (convenção de nó), nunca mutam o estado recebido.

### 3.5 Contrato de contexto (prompt NPC)

Com `on`, o bloco `<O_QUE_VOCE_SABE>` substitui o efeito onisciente: linhas
`[VIU] …` (observed_by), `[OUVIU DE <fonte>] …` (told_to+believed_by) e
`[BOATO, não confirmado] …` (told_to sem belief, ou assunto rumor). Assunto sem relação não
aparece. Regras do prompt: "Se não está aqui nem na sua memória, você não sabe."

### 3.6 State ownership e degradação

- Owner de escrita: só `services/npc_knowledge.py` (chamado por event_processor/storyteller/npc).
- Falha interna (exceção) no ledger: loga `rpg.npc_knowledge` e o turno segue; com `on`, o gate
  **falha fechado** (contexto do NPC sem fatos dinâmicos, só memória privada + lore público), nunca
  aberto para o pack onisciente.
- MockLLM/FallbackLLM: sem efeito (sem structured output novo). Nenhum `with_structured_output` novo.
- Perfil hosted: ledger dentro do snapshot JSON do jogo; sem migration SQL.

### 3.7 Contrato de UI

Nenhuma UI nova. Garantia negativa: nenhum campo `knowledge_*`/`location_heard` em resposta da API,
SSE, codex, tooltip ou prompt de arte. Export de auditoria (SPEC-207) pode anexar o ledger apenas no
artefato do dono, se aquela spec o aceitar via handoff — esta spec não o exige.

## 4. Plano passo a passo (TDD)

0. **Handoff de eval (tarefa separada, pré-requisito):** autoria do dataset `npc_knowledge` e dos
   oráculos `knowledge_teleport` / `knowledge_leak` em `evals/`, travados pela governança
   (SPEC-165). O executor desta spec não edita evaluator/expected.
1. **Distância** — `tests/test_world_distance.py`: `test_adjacent_equals_travel_cost`,
   `test_interior_zero`, `test_unreachable_none`, `test_symmetric_fallback`. Implementar.
2. **Schema + migração** — `tests/test_npc_knowledge_migration.py`: save v8 real de fixture carrega
   com ledger vazio e `legacy_knowledge=True`; round-trip v9 preserva links byte a byte; save
   adulterado (tipos errados, relação desconhecida, teto excedido) normaliza sem crash. Implementar.
3. **Testemunha** — `tests/test_npc_knowledge.py::test_witness_knows_death` (NPC em cena recebe
   observed+believed), `test_distant_npc_unknown`, `test_party_present_witness`,
   `test_waiting_party_member_not_witness`.
4. **Propagação** — `test_messenger_delivers_after_distance` (entrega só com `clock ≥ due`),
   `test_no_delivery_before_due_after_save_load` (teleporte por reload),
   `test_seeded_replay_identical`, `test_max_hops_two`, `test_queue_and_link_caps`,
   `test_npc_created_later_inherits_only_delivered`.
5. **Rumor/mentira** — `test_npc_claim_never_promoted` (provenance/confidence inalterados, nenhum
   `GameEvent`, nada em `revealed_facts`), `test_lie_believed_stays_in_relation`,
   `test_player_told_belief_threshold`, `test_player_text_not_fact`.
6. **Segredo** — `test_secret_not_propagated`, `test_secret_absent_from_other_npc_context`.
7. **Gate de contexto** — `tests/test_context_npc_gate.py`: com `on`, pack de NPC distante não
   contém o nome do morto nem "morto"; testemunha contém `[VIU]`; `off` gera pack idêntico ao atual
   (snapshot); `shadow` idêntico ao `off` + log; limite de 8 fatos; budget 3500 respeitado;
   falha interna → fail-closed.
8. **Não-exposição** — `tests/test_api_npc_knowledge_private.py`: `/game/state`, codex, SSE e
   `visible_npc_view` sem chaves `knowledge_*`.
8b. **Entrega no finalizer** — `test_flee_travel_triggers_delivery` (fuga de combate que avança o
   relógio entrega notícias vencidas no mesmo turno), `test_deliver_due_idempotent_twice_same_turn`.
9. **Cronologia/identidade** — `test_links_ordered_by_clock`, `test_identity_alias_holder_merge`
   (aliases SPEC-149 resolvem para um holder).
10. **Invariantes do playtest** — `knowledge.teleport`, `knowledge.rumor_promoted` + teste unitário.
11. **Fiação** em event_processor/storyteller/npc/context_builder; `uv run pytest` verde.

## 5. Critérios de aceite

- [x] R1–R14 cobertos pelos testes nomeados em §4, todos verdes.
- [x] Dataset `npc_knowledge` (tarefa separada, 39 casos, `docs/spec215/README.md`) passa com `on`: zero teleporte, zero vazamento,
      zero rumor promovido; `off` documentado como baseline (falha esperada nos casos de teleporte).
      → handoff em `handoffs/SPEC-215-eval-authoring.md` (evals/ protegido); oráculos já em pytest.
- [x] `RPG_NPC_KNOWLEDGE=off` produz contexto de NPC idêntico ao HEAD (teste de snapshot).
- [x] Save v8 carrega; round-trip verde (sem bump: v8 aditivo, ver §10); nenhuma distribuição retroativa.
- [x] Nenhuma chamada LLM nova; nenhum `with_structured_output` novo.
- [x] Smoke offline 14 perfis × 30 turnos (`--all`) com `on`: zero erro, zero violação `error`.
- [x] `uv run pytest` verde (suíte completa offline); Ruff verde; Project Index regenerado.
      → pytest e Ruff verdes; Project Index fica com o coordenador.
- [x] Revisão independente Astra APPROVED (APPROVED_WITH_FOLLOWUPS — `handoffs/SPEC-215-ASTRA-independent-review.md`).

## 6. Smoke

**Offline (obrigatório):** `uv run python -m playtest run --all --turns 30` com
`RPG_NPC_KNOWLEDGE=on` e depois `shadow`; `uv run python -m playtest report <run_id>`; registrar
links criados, entregas, filtrados por prompt e violações. Cenário dirigido offline: matar NPC em
L, conversar com NPC em cidade a ≥3 períodos antes e depois do `due_clock`.

**Real (opt-in, somente com autorização):** 1 campanha dirigida curta (≤ 15 turnos, ≤ 60 requests,
teto US$ 0,10) em `deepseek-paid`: verificar que o NPC distante diz não saber e, após viagem/descanso
suficientes, cita o fato como notícia; e que nenhum segredo vaza. Sem long-run.

## 7. Riscos & compatibilidade

- **Saves:** schema 8→9 aditivo; legado sem relações = conhecimento só pela memória privada
  (R13). Checkpoints (`services/checkpoints.py`) carregam o ledger junto do save — restaurar
  checkpoint volta o conhecimento ao ponto do checkpoint (coerente com rollback de mundo).
- **Regressão de continuidade:** remover `narrative_summary`/`memory_facts` do jogador do prompt de
  NPC pode deixar NPC "esquecido" do que viveu com o jogador; mitigado pela memória privada do NPC
  (`query_npc_memory`) e por `shadow` medindo a perda antes do `on` (§8 D2).
- **NPC de party:** viaja com o jogador; ganha `observed_by` por presença, não pela narração.
- **Custo:** zero LLM; Dijkstra cacheado; fila ≤200; teto de 8 fatos não aumenta tokens.
- **Determinismo:** depende de `game_id` estável e de `clock`; replay coberto por teste.
- **Halveth:** [F] não há NPC "Halveth" no source versionado; o nome só aparece em artefatos
  runtime gitignored (`data/runtime/bestiary_runtime.json`, criatura `enemy_corvo_de_halveth`) e
  num save local. A exigência do prompt 12 (identidade/pronomes/cronologia da Halveth) vira caso
  genérico de fixture em §4 passo 9 e no dataset; se o dono indicar o save de origem, o autor do
  eval pode derivar dele uma fixture sanitizada.
- **Interlocutor (SPEC-202):** pergunta ao narrador sobre um NPC não usa o gate do NPC; o narrador
  continua no contexto do jogador.

## 8. Pontos de decisão do dono

- **D0 — Prioridade.** P2 (coordenador) vs. P3 (`DECISOES_PRODUTO.md`). Default [R]: P2 após beta,
  sem bloquear SPEC-212.
- **D1 — Rollout.** Default [R]: `off` → `shadow` por uma rodada offline → `on` após dataset verde e
  review; promoção a default exige aprovação explícita.
- **D2 — Resumo do jogador no prompt do NPC.** Default [R]: excluir `narrative_summary` e
  `memory_facts` do jogador com `on`, manter memória privada do NPC; alternativa: manter o resumo
  só para NPCs de party ativa.
- **D3 — Parâmetros de §3.3.** Default [R]: valores da tabela como `[BALANCEAR]`, ajustados por
  medição `shadow`, não por intuição.

## 9. Evidência requerida

- Saída completa de `uv run pytest` (contagem passed/skipped/deselected, exit 0).
- Run IDs do smoke offline `on` e `shadow` + report com contagem de links/entregas/filtrados.
- Resultado do dataset `npc_knowledge` (off vs on), hashes travados pela governança.
- Diff de prompt NPC antes/depois para um caso testemunha e um caso distante (sanitizado).
- Teste round-trip com save v8 de fixture real.
- Parecer Astra independente em `handoffs/SPEC-215-ASTRA-independent-review.md`.
- Smoke real apenas se autorizado, com chamadas/custo registrados.

## 10. Execução (2026-10-16)

Evidência: [`docs/spec215/README.md`](../docs/spec215/README.md).

**Defaults de decisão usados (§8):** D0 = P2; D1 = flag default `off`, promoção exige
aprovação; D2 = excluir `narrative_summary`/`memory_facts`/memória de sessão do
jogador com `on` (memória privada do NPC fica); D3 = valores da tabela §3.3.

**Desvios:**
- **SPEC-214 `NO_GO`** (`docs/spec214/gate.md`): não há cache de cena. A 214 era
  "recomendada"; esta spec não depende dela.
- **Sem bump de `SCHEMA_VERSION`** (regra da onda: o caso protegido
  `state.persistence.migration-idempotent` fixa 8). `knowledge_links`,
  `knowledge_queue`, `location_heard`, `legacy_knowledge` são aditivos; save sem as
  chaves → ledger vazio + `legacy_knowledge=true`. Onde a spec diz "v8→v9", leia
  "v8 aditivo".
- **Testemunha/agendamento no `turn_finalizer`**, não no `event_processor`: eventos do
  turno são `event.turn == world.turn_count` (garante R13 sem cursor) e a entrega
  segue no mesmo ponto. Idempotente por `link_id`/`delivery_id`.
- **R7 mais estrito:** conteúdo com assinatura não revelada nunca entra no prompt de
  NPC algum (nem do observador direto); o link existe, o texto não.
- Campos extras opcionais em `KnowledgeLink` (`location_id`, `origin_location_id`,
  `origin_clock`) e `KnowledgeDelivery` (`subject_type`, `origin_*`) para o
  invariante de teleporte e o raio a partir da origem.
- Destinos por hop: locais com NPC registrado primeiro, depois os demais, por distância.

**Concluído:** Project Index regenerado pelo coordenador no land (commit de reindex logo após o merge). O dataset
`npc_knowledge` foi autorado (39 casos; publicar exige aprovação do environment `eval-governance`).
