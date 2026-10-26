# SPEC-318 — Latência: trabalho pós-narração fora do nó narrador e gate do arquivista

> **Status:** `in-progress` (implementada 25/10; falta revisão independente Sol + medição no staging; aprovada pelo dono 25/10: "boa, aprovo" — decisões nos padrões recomendados em negrito)
> **Criada:** 2026-10-25 · **Atualizada:** 2026-10-25
> **Depende de:** SPEC-316 (`done` — a narração só é entregue cedo se o NÓ narrador terminar cedo); insumos `done`: SPEC-028 (traits seeded), SPEC-213 (projeções), SPEC-302/304/309 (motor de mundo e percepção)
> **Desbloqueia:** SPEC-319 (ganho de TTFMC só é pleno com o nó narrador enxuto)
> **Origem:** investigação de latência 2026-10-25 (oportunidades #5 e #6)
> **EXECUTOR_MODEL:** `Sol` (topologia do grafo, continuidade de NPC, memória) · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false` — `memory_context.jsonl` e demais datasets só são executados em `compare`

---

## 1. Contexto & Objetivo

Com a SPEC-316 a narração sai quando a **update do nó** chega ao gerador. Mas o nó narrador ainda faz,
depois de ter a prosa pronta, trabalho que só o turno seguinte consome:

- **NPC novo dentro do storyteller:** por nome em `introduced_npcs`, `_with_new_npc` (`storyteller.py:570-637`,
  `:1907-1920`) roda librarian CLASSIFY (se há candidato fuzzy) + `query_rag` (embedding + FAISS) + FAST
  `NPCSchema` (`npc.py:464-541`), em série: **+2 a +5 s** nos turnos que apresentam alguém.
- **`add_npc_memory` síncrono** no `npc_actor` após a resposta (`npc.py:1311-1336`): embedding + load/save do FAISS
  (legacy) ≈ 0,5–1 s.
- **`narrate_day` (FAST) antes do narrador** quando o dia vira em viagem/descanso (`storyteller.py:830-837`,
  `:1410`): duas chamadas FAST em série (+3 a +4 s nesses turnos), só para gerar o `world_note` que entra no
  prompt.
- **Replan SMART do `campaign_manager` na frente do router** a cada 15 turnos, troca de região ou beats
  esgotados (`campaign_manager.py:56,78-106,186`), com 2ª chamada SMART se um beat sair em inglês (`:249-253`):
  +3 a +6 s. O narrador só usa `beats[current_step]` como "Objetivo Atual" (`storyteller.py:1489-1500`).
- **Arquivista SMART em 70–80 % dos turnos** (`docs/spec213/staging-measure-2026-10-18.md`, l.24):
  `archive_due` é setado em toda conversa de NPC (`npc.py:1443`, `:1015`, `:1034`), todo loot (`loot.py:269/294/391`),
  toda viagem/descanso/beat e qualquer evento pendente (`storyteller.py:2064,2082`). Com a 316 ele sai do
  TTFMC, mas segura o `state`, custa US$ e, na Vercel, alonga o turno que o jogador rápido manda em seguida.
  Falha de structured output faz uma 2ª chamada SMART em texto puro (`archivist.py:103-130`, `:918`).

Objetivo: o nó narrador devolve a update assim que a prosa está guardada; fichas, memória, plano e
digest do mundo são produzidos **depois da entrega** (ainda dentro do stream, 316 R9) ou no turno seguinte,
sem mudar o que o jogador lê nem a mecânica.

## 2. Requisitos

- **R1 — Ficha de NPC em duas fases.** Ao introduzir um NPC, o storyteller cria **na hora** um stub
  determinístico (nome, papel inferido pelo regex/role do texto, traits seeded via `services/npc_layers`,
  `in_scene=True`, `sheet_status="stub"`) e devolve a update. A ficha completa (librarian + RAG + FAST
  `NPCSchema`) roda na **fase pós-entrega** do mesmo turno (nó `enrich`, R6) e preenche `sheet_status="full"`;
  se falhar, o stub permanece e o turno seguinte tenta de novo (máx. 3). `npc_actor` conversa com stub (prompt
  usa o que existe) — nunca "Ninguém responde" por ficha pendente.
- **R2 — Memória de NPC fora do nó.** `add_npc_memory` do `npc_actor` vira `pending_npc_memory` (campo já
  existe, `archivist.py:243-260`) consumido pelo arquivista; o retry por `turn%3` já cobre falha. Nenhum
  embedding dentro do `npc_actor`.
- **R3 — Digest do dia sem chamada extra.** Quando o dia vira, o storyteller **não** chama `narrate_day`; os
  itens percebidos (`world_perception`, SPEC-309) entram no prompt do narrador como bloco factual
  (`<MUNDO_PERCEBIDO>` já existe), e o narrador os tece na própria narração. `narrate_day` continua
  disponível para o `world_simulator` legado (`RPG_WORLD_ENGINE=off`). Flag `RPG_DAY_DIGEST=llm|inline`,
  default **`inline`**.
- **R4 — Replan após a entrega.** `campaign_manager` sai da frente do router; o nó `enrich` (R6) chama
  `_should_replan` e, se verdadeiro, gera o plano **para o próximo turno**. Exceções que seguem inline antes
  do router: primeiro turno sem plano e `needs_replan` com `campaign_plan is None`. A 2ª chamada "beat em
  inglês" vira FAST com o mesmo prompt de correção.
- **R5 — Gate do arquivista mais estreito.** `_should_archive` com política `RPG_ARCHIVE_POLICY=legacy|lean`:
  em `lean`, conversa de NPC só dispara se `memory_fact_policy` marcou fato memorável ou se o NPC saiu de cena;
  loot só em item único/compra ≥ 50 ouro; viagem só com troca de região; sempre em `conflict_summary`, evento
  do mundo aplicado e a cada 10 turnos (`_ARCHIVE_EVERY`). Fallback plain-text (`:103-130`) usa tier FAST.
  Default **`legacy`**; `lean` em `shadow` loga `archivist.lean_shadow {would_skip: bool}`.
- **R6 — Nó `enrich` no grafo.** Novo nó entre o narrador e o `archivist`: `storyteller|combat|npc|loot →
  enrich → archivist → turn_finalizer`. Ele hospeda R1 (ficha completa) e R4 (replan). Falha em `enrich`
  nunca derruba o turno (log + estado anterior). Em `combat_simulation` é no-op.
- **R7 — Paridade de conteúdo.** Com todas as flags no valor legado (`RPG_DAY_DIGEST=llm`,
  `RPG_ARCHIVE_POLICY=legacy`, `RPG_NPC_TWO_PHASE=off`, `RPG_REPLAN_AFTER=off`) o estado final é byte a byte
  igual ao HEAD para o mesmo seed/MockLLM (exceto a presença do nó `enrich` como no-op).
- **R8 — Telemetria.** `rpg.turn` ganha `enrich_ms`, `npc_sheets_deferred`, `replan_deferred`,
  `archive_skipped_by_policy`. Playtest: `node_latency_ms.enrich` no relatório.

### Fora de escopo

- Worker/job para a ficha completa (fica no stream do mesmo turno ou no próximo). Mudar prompts do narrador
  além do bloco factual (R3). Qualquer mudança de evaluator/dataset. Streaming de tokens (319).

## 3. Design técnico

- **Novo** `agents/enrich.py`: `enrich_node(state) -> dict` — ordem: fichas pendentes (`npcs[*].sheet_status ==
  "stub"`, até 2 por turno), depois replan. Usa `generate_new_npc` e `campaign_manager._plan` já existentes.
- **Alterado** `main.py`: `workflow.add_node("enrich", ...)`; arestas `storyteller/npc_actor/combat_agent/loot_agent
  → enrich` (mantendo as condicionais atuais de encontro/vitória/delegação, agora apontando a `enrich` em vez
  de `archivist`), `enrich → archivist`. `campaign_manager` permanece no grafo, mas `turn_prepare →
  campaign_manager` só quando `_needs_inline_plan(state)` (R4), senão `turn_prepare → dm_router`.
- **Alterado** `agents/storyteller.py:570-637,1907-1920`: `_stub_new_npc(name, text, state) -> dict`
  (determinístico, usa `npc_layers.seeded_traits`); `_with_new_npc` passa a ser chamado por `enrich`.
- **Alterado** `agents/npc.py:1311-1336`: substituir `add_npc_memory(...)` por acumular em
  `pending_npc_memory` (lista de `{npc_id, text, turn}`); `archivist._persist_memory_records` já drena.
- **Alterado** `agents/storyteller.py:830-837,1410`: `_narrate_world` só com `RPG_DAY_DIGEST=llm`; em `inline`
  o bloco `<MUNDO_PERCEBIDO>` recebe os itens do dia com a instrução "teça estes fatos na narração, sem listar".
- **Alterado** `agents/archivist.py:243-260`: `_should_archive(state, turn, policy=archive_policy())`;
  `_extract_summary_plain` com `tier=FAST`.
- **Schema (`state.py`, aditivo):** `npcs[*]["sheet_status"]: Literal["stub","full"]` (default `full` no load);
  `pending_npc_memory: list[dict]` (já existe como campo transitório — confirmar e tipar); `campaign_plan`
  inalterado.
- **Flags:** `RPG_NPC_TWO_PHASE=off|on` (default **`on`** — stub é determinístico e a ficha chega no mesmo turno),
  `RPG_REPLAN_AFTER=off|on` (default **`on`**), `RPG_DAY_DIGEST=llm|inline` (default **`inline`**),
  `RPG_ARCHIVE_POLICY=legacy|lean` (default **`legacy`**, com `RPG_ARCHIVE_POLICY_SHADOW=1` para medir).

## 4. Plano passo a passo

### Etapa 1 — Nó `enrich` e paridade
1. **Testes** (`tests/test_enrich_node.py`): `test_graph_has_enrich_between_narrator_and_archivist` (ordem dos
   updates do `app.stream`); `test_enrich_failure_does_not_break_turn`; `test_legacy_flags_byte_identical`
   (R7: estado final igual ao HEAD com flags legadas, 3 turnos × 3 rotas).
2. **Implementação:** `agents/enrich.py`, `main.py`.

### Etapa 2 — NPC em duas fases (R1, R2)
1. **Testes** (`tests/test_npc_two_phase.py`): `test_storyteller_update_has_stub_and_no_fast_npc_call`
   (contador MockLLM por tier); `test_enrich_completes_sheet_same_turn`; `test_npc_actor_talks_to_stub`;
   `test_stub_retry_max_three`; `test_npc_memory_pending_not_embedded_in_node` (contador de embeddings = 0);
   `test_archivist_drains_pending_npc_memory`. Invariantes de playtest: `npc.sheet_stub_streak ≥ 3` = `warning`.
2. **Implementação:** `_stub_new_npc`, `enrich`, `npc.py`.

### Etapa 3 — Digest inline e replan após a entrega (R3, R4)
1. **Testes** (`tests/test_day_digest_inline.py`): `test_day_turn_makes_single_fast_call`;
   `test_perceived_items_in_prompt_block`; `test_llm_mode_keeps_narrate_day`.
   `tests/test_replan_after_delivery.py`: `test_first_turn_plans_inline`; `test_interval_replan_runs_in_enrich`
   (router update chega antes de qualquer SMART); `test_next_turn_uses_new_plan`; `test_english_beat_retry_is_fast_tier`.
2. **Implementação:** storyteller, `main.py` condicional, `campaign_manager`.

### Etapa 4 — Gate do arquivista (R5)
1. **Testes** (`tests/test_archivist_policy.py`): `test_lean_skips_small_talk`; `test_lean_keeps_conflict_summary`;
   `test_lean_keeps_every_10_turns`; `test_shadow_logs_would_skip`; `test_plain_fallback_uses_fast`.
2. **Implementação:** `archivist.py`. **Verificação de qualidade:** `python -m evals --root . run --dataset
   datasets/regression/memory_context.jsonl --run-id spec318-lean` + `compare` com baseline (sem editar dataset).

## 5. Critérios de aceite

- [x] R1–R8 cobertos; testes do escopo verdes (suíte completa = coordenador); `test_legacy_flags_byte_identical` passa.
- [x] Playtest offline 16 perfis × 30 turnos (MockLLM): zero erro, zero violação (err/warn).
- [ ] Staging §6: turnos com NPC novo p50 −2 s; turnos de viagem com dia virado −3 s; `state` p50 −0,8 s;
  chamadas SMART/turno de 0,75 → ≤ 0,45 em `lean` (shadow conta), com `evals compare` sem piora nos hard gates.
- [x] Guard de FallbackLLM nas chamadas movidas para `enrich` (ficha `id == "fallback"` conta como falha; o replan herda o guard do planner).
- [x] Saves antigos carregam (`sheet_status` ausente = ficha completa; nunca pendente).
- [ ] Revisão independente (Sol) da topologia e da continuidade de NPC.

## 6. Smoke test com LLM real

Staging, DeepSeek, teto **US$ 0,15**: `projection_measure.py --label spec318 --turns 15 --think 8` ×2 com um
roteiro que inclui 3 apresentações de NPC, 2 viagens com virada de dia e 1 troca de região (replan), com
`RPG_ARCHIVE_POLICY_SHADOW=1`. Conferir: ficha completa presente no `GET /game/state` ao fim do turno; NPC
stub responde coerente no turno seguinte; plano novo aparece no turno após a troca de região;
`archive_skipped_by_policy` ≥ 30 %. Browser: 3 turnos, narração chega antes da ficha ("o escriba registra…").

## 7. Riscos & compatibilidade

- **Continuidade do NPC:** o stub pode divergir da ficha completa (classe, facção). Mitigação: a ficha completa
  recebe o stub como contexto e não pode contradizer nome/papel/traits; `librarian` continua deduplicando.
- **Plano com 1 turno de atraso:** o narrador do turno da troca de região usa o beat antigo (ou nenhum). Aceito
  (D2); o primeiro turno segue inline.
- **Digest inline:** o narrador pode omitir itens do dia. Regra de ouro (SPEC-308) intacta — só itens já
  percebidos entram; marcos/`perceived_ids` continuam gravados pelo caminho determinístico, não pelo LLM.
- **Gate `lean`:** menos resumos ⇒ `narrative_summary` mais velho em diálogos triviais. Por isso `legacy`
  default e `shadow` antes; `compare` em `memory_context.jsonl` é gate de promoção (dataset não editado).
- **Vercel:** todo o `enrich` roda dentro do stream (316 R9); nada fica para depois do `return`.
- **MockLLM/FallbackLLM:** `enrich` é só orquestração; guards existentes migram junto. Mecânica inalterada.

## 8. Decisões do dono

- **D1 — NPC em duas fases:** **`on` por default** (stub determinístico, ficha no mesmo turno).
- **D2 — Replan após a entrega:** **`on` por default**, com exceção inline no 1º turno
  (alternativa: só a cada 15 turnos e inline na troca de região — rejeitada: a troca de região é justamente o caso lento).
- **D3 — Digest do dia:** **`inline` no prompt do narrador** (alternativa: paralelizar `narrate_day` com o pack —
  mantém a chamada e o custo).
- **D4 — Política do arquivista:** **`legacy` + shadow na main; `lean` no staging após `compare` sem piora**.

## 9. Histórico de mudanças

- **2026-10-25 — implementação (executor).** Desvios e decisões de desenho em relação ao texto acima:
  - **Marca `archive_low`** (campo transitório de `GameState`, não persistido): os emissores (conversa de NPC sem
    consequência, loot barato, viagem na mesma região) marcam o turno como de baixo valor e `_should_archive`
    `lean` a lê; só vale no próprio turno e **só é escrita quando `lean`/shadow está ligado** (paridade R7).
    A política não tem como saber o "motivo" do `archive_due` de outro modo; o plano falava em
    `memory_fact_policy`, que o `npc_actor` põe em toda conversa.
  - **Fila de memória de NPC** (`pending_npc_memory`): com `RPG_NPC_TWO_PHASE=on` o `npc_actor` só enfileira;
    entrada nova (sem `attempts`) é gravada pelo arquivista no mesmo turno, falha ganha `attempts` e espera a
    janela de retry (turno % 3). Em `lean` a drenagem roda mesmo quando o SMART é pulado
    (`_drain_npc_memory`, extraída de `_archive_node`).
  - **Digest inline (R3):** em vez do bloco `<MUNDO_PERCEBIDO>` (que traz só estado local/crises), os fatos do
    dia entram como nota `[ECOS DO MUNDO]` em *Eventos do turno* (`FATO:`/`BOATO:` de template, boato só como
    boato). Sem chamada FAST; `memory_fact_policy`/marcos seguem pelo caminho determinístico.
  - **Replan (R4):** `campaign_manager` fica no grafo; `turn_prepare` só passa por ele sem plano. O `enrich`
    replaneja com a mesma regra (`_should_replan`) e não replaneja em combate ativo nem com `game_over`/morte
    pendente; a correção "beat em inglês" usa FAST.
  - **Ficha em duas fases (R1):** o stub reaproveita a cauda de `_with_new_npc` (relação inicial, vínculo de
    local, traits seeded); a completa mantém nome, papel (se inferido), id e todo o estado dinâmico do stub.
    Falha = `id == "fallback"` ou nenhuma entrada nova; `sheet_attempts` ≤ 3 e o invariante de playtest
    `npc.sheet_stub_streak` avisa quando desiste. O NPC do elenco do pool (sem LLM) nasce completo.
  - **Flags no staging:** as 5 flags entram em `OPTIONAL_FLAGS`/`WORLD_FLAGS` de `scripts/staging/vercel_env.py`
    com validação de valores por flag (`WORLD_FLAG_VALUES`).
  - **Não feito aqui:** medição em staging (§6) e `evals compare` de `memory_context.jsonl` (exigem a corrida
    `lean`; nenhum dataset/expected foi tocado). `EVAL_AUTHORING_REQUIRED` continua `false`.
- **2026-10-25 — correções da revisão (handoffs/SPEC-318-sol-review.md).**
  - P1-1: o papel do stub só sai de aposto ao nome, em palavra inteira ("o guarda Marta", "Marta, a
    estalajadeira"); do contrário `Desconhecido`. O papel provisório **não é mais travado**: a ficha completa
    pode corrigi-lo (só nome e estado dinâmico do stub são preservados).
  - P1-2: `_with_new_npc` devolve `outcome_out` (`merged_into`/`blocked`/`failed`). Ficha que resolve para NPC
    já existente funde o stub no canônico (memória, interações, `in_scene`, `pending_npc_memory` e
    `active_npc_name` remapeados); NPC morto/bloqueado remove o stub (legado); só falha real conta tentativa.
  - P1-3: a nota inline do digest tem versão para o jogador (`_digest_player_text`: fatos de template, boato como
    "Dizem por aí: …") usada por `_player_facing_note`/fallbacks; a instrução nunca chega ao jogador.
  - P2: a fusão preserva `_NPC_DYNAMIC_FIELDS` (vitalidade/ferimentos...) e adota o `id` da ficha completa
    (remapeando a fila); FAST do reforço de idioma do planner e do fallback plain do arquivista só valem com
    `RPG_REPLAN_AFTER=on` / `RPG_ARCHIVE_POLICY=lean` (legado = mesmo tier); `RPG_NPC_TWO_PHASE`/`RPG_REPLAN_AFTER`
    aceitam só `on|off` no `vercel_env`; digest limitado a `DAY_FACTS_MAX` linhas; a primeira escrita diferida
    registra a promoção como `npc_claim_direct_write`; teste R7 ganhou cenários de viagem/descanso.
  - Documentado (D2): num turno de reparo bloqueado pelo `action_guard` com `needs_replan`, o replan agora
    acontece depois da narração do turno seguinte, não antes.
