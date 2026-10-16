# SPEC-226 — Contabilidade de recompensas: XP por abate, quests, beats, achados e eventos derivados

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · SPEC-142 interacoes-progresso-elegibilidade, SPEC-057 loot-exploracao e SPEC-010 fase-4.1-progressao `done` são corrigidas, não reabertas (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-199, SPEC-212, SPEC-223; baseline de XP do balanceamento (ordem final 2026-10-15)
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-03-01/02-01, 03-02, 01-01, 01-08, 06-05, 06-06/03-12, 03-10/02-18, 06-13, 06-03, 01-11 (`achados/01,02,03,06-*.md`)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — altera a progressão do jogador (XP/nível) e o ledger de eventos
> **EVAL_AUTHORING_REQUIRED:** `false` — o corpus de state/rules (SPEC-168) pode ganhar casos de regressão em handoff separado (§9), mas a cobertura principal é unitária

---

## 1. Contexto & Objetivo

O princípio "mecânica é Python" vale para XP, mas a auditoria reproduziu (scripts re-executados pelo orquestrador)
que a contabilidade de recompensas NÃO é idempotente em quatro caminhos e que um caminho perde recompensa:

- [F] **XP de abate por rodada** — `agents/combat.py:905` `dead = [e for e in enemies if e.get("dead") or status=="morto"]`
  pega TODOS os mortos do estado; `:984` devolve `enemies` com os mortos enquanto o combate continua; `:925-929`
  `grant_xp(xp_for_kills(dead))` roda de novo a cada rodada; `disc.record_kills` (bestiário `defeated`) e `_kill_events`
  (`npc_killed`, `:1005`) idem. Repro: Goblin 1 morto + Goblin 2 vivo, 3 rodadas → `xp 50 / 100 / 150`, `defeated 1/2/3`.
  Um Chefe morto numa luta longa renderia +1000 XP por rodada.
- [F] **Quest concluída 2× no mesmo lote** — `services/event_processor.py:277-287`: `quests_completed += 1` incondicional
  (o ouro usa `delivered`, idempotente), e `working["quests"]` não é atualizado no loop (o validador vê a quest
  ainda `active`). Repro: 2 propostas `quest_completed` para `q1` → `xp 400, gold 20`.
- [F] **Beat + achado no mesmo turno** — `agents/storyteller.py:811` `base_p = rested_player or state.player` ignora
  `discovery_player`; `:859` `updates["player"] = leveled_player` sobrescreve o jogador com o loot do baú/achado.
  Repro em `pm_profundezas`: sem beat `gold 40 + 2 itens`; com beat `gold 0, inventário []`, `looted_locations` marcado
  e claim de único emitido → baú consumido sem entrega.
- [F] **Planejador falho reabre XP de beat** — `agents/campaign_manager.py:178-181, 207-224`: `AIMessage` em vez de
  `CampaignPlanModel` → plano genérico de 3 beats com `current_step=0`, cada beat genérico concluído paga
  `XP_PER_BEAT` (150) de novo; já o caminho "beats em inglês" mantém o plano anterior (inconsistente).
- [F] **Achado ambiental farmável** — `agents/storyteller.py:337` `if first_visit or dest.get("treasure")` +
  `services/exploration.py:104-116`: nos 2 nós com baú curado, toda revisita com o baú já saqueado rola
  `roll_discovery` (86/200 chegadas geram loot).
- [F] **Quest "duas ações distintas" por pontuação** — `services/quest_log.py:176-211` fingerprint = `casefold` do
  texto cru: "Investigo a pista" + "Investigo a pista." → `completion_ready` (XP 200 + 20 ouro).
- [F] **Tier de XP/orçamento por `type` legado** — `progression.xp_for_kills` (`:37-43`) e `encounter_budget.tier_cost`
  (`:16-18`) leem `type` (Minion/Elite/BOSS); `Standard` (12), "Monstrosidade (Gigante)" (chefe) e "Humanoid (Human)"
  (nomeado) pagam/custam como Minion. A fonte canônica v4 é `categoria` (lacaio/padrao/elite/chefe/nomeado).
- [F] **Reputação N× por turno** — `agents/storyteller.py:782-792`: cada `faction_impact` aplica `apply_reputation`
  antes da validação; o validador rejeita o 2º `reputation_changed` do mesmo alvo/turno → estado moveu 2×, log 1×.
- [F] **Eventos derivados com `turn=0`** — `services/rule_engine.py:239-248` `_new_event` fixa `"turn": 0`;
  `event_processor` anexa sem carimbar → crônica/recência/dedupe erradas para cascatas.
- [F] **Guard `reward_delta`** — `services/narrative_evidence.py:88-93` compara cada frase "recebeu N" com o delta
  líquido do turno (ganho 50 − gasto 30 → frase "recebeu 50" rejeitada).

Objetivo: toda recompensa (XP, ouro, item, abate, reputação) é concedida **exatamente uma vez por fato gerador**,
derivada de transição de estado observável (vivo→morto nesta rodada; quest active→completed; beat pending→done;
primeira visita), com ledger coerente (turno correto, 1 evento por mudança).

## 2. Requisitos

- **R1** — [R] XP de abate, `record_kills` e `npc_killed` só consideram inimigos que transitaram para morto NESTA
  rodada: `newly_dead = [e for e in enemies if is_dead(e) and e["id"] not in dead_before]` com `dead_before` tirado
  de `state["enemies"]` na entrada do nó, E marcador idempotente `e["xp_awarded"]=True` (defesa para reforço/replay).
  Teste de reprodução: 3 rodadas com 1 cadáver → `xp 50, 50, 50` (não cumulativo), `defeated == 1`, 1 `npc_killed`.
- **R2** — [R] `event_processor`: `quests_completed` só incrementa quando `complete_quest_with_reward` efetivamente
  transiciona (`delivered_flag`/estado anterior `active`); `working["quests"] = quests` atualizado no loop para o
  validador rejeitar a 2ª proposta como "já concluída". Teste: 2 propostas → `xp 200, gold 20`, 1 evento no log.
- **R3** — [R] `storyteller`: o XP de beat é aplicado sobre o jogador JÁ atualizado (`rested_player` →
  `discovery_player` → `state.player`, nessa precedência) e `updates["player"]` resulta de uma única composição.
  Teste de reprodução: viagem a `pm_profundezas` + beat concluído → `gold 40`, 2 itens, `xp +150`, `looted_locations` marcado.
- **R4** — [R] `campaign_manager`: se já existe plano com beats e o planejador devolve inválido (`AIMessage`/None/
  schema), mantém o plano anterior e `needs_replan=True` (mesmo contrato do caminho "inglês"); o template genérico só
  entra quando NÃO há plano. Teste: plano válido + provider esgotado → plano inalterado, `current_step` inalterado.
- **R5** — [R] `discover_on_arrival(..., first_visit: bool)`: o passo 2 (`roll_discovery`) só roda em `first_visit`;
  o baú curado continua independente (one-shot por `looted_locations`). Teste: 200 revisitas com baú saqueado → 0 achados.
- **R6** — [R] Fingerprint de progresso de quest normalizado (NFKD sem acento, sem pontuação, tokens ≥ 4 chars
  ordenados) e "distinta" exige similaridade Jaccard < 0,6 com todas as anteriores. Teste: "Investigo a pista" ×
  "Investigo a pista." → 1 ação; "Investigo a pista" × "Pergunto ao guarda sobre o sumiço" → 2.
- **R7** — [R] `xp_for_kills` e `encounter_budget.tier_cost` derivam de `categoria` canônica
  (`combat_mechanics.normalize_categoria`: lacaio 50/2, padrao 100/3, elite 200/5, chefe 1000/12, nomeado 1000/12),
  com fallback por `type` só para fichas sem `categoria`. Teste: tabela sobre `data/bestiary.json` sem `Standard`→minion.
- **R8** — [R] `faction_impacts` deduplicados por `faction_id` antes de `apply_reputation` (último vence) e a
  reputação só muda se o evento `reputation_changed` for aceito (aplicar DEPOIS da validação). Teste: 2 impactos para
  a mesma fação → delta 1×, 1 evento.
- **R9** — [R] `rule_engine._new_event(..., turn=parent_turn)` e `event_processor` carimba `turn` em todo derivado.
  Teste: `npc_killed` no turno 42 → derivado `location_control_changed` com `turn == 42`.
- **R10** — [R] Guard `reward_delta` compara a frase com o GANHO BRUTO do turno (soma dos eventos/recibos positivos:
  loot, venda, quest, beat), não com o delta líquido. Teste: ganho 50 + gasto 30, frase "recebeu 50" → aceita.
- **R11** — [R] `last_turn_outcome.xp_delta` (SPEC-144/199) reflete R1–R4 sem ajuste adicional (teste de integração
  pelo grafo com MockLLM: combate 2 rodadas → `xp_delta` igual ao XP dos abates novos).

### Fora de escopo

- Tirar números da prosa / chip de `turn_outcome` (SPEC-199).
- Valores de XP (tabela), curva de nível, `XP_PER_BEAT`/`XP_PER_QUEST` — mantidos.
- Venda/inventário (spec `SPEC-227`), combate (specs `SPEC-231`/`SPEC-232`).

## 3. Design técnico

### Arquivos alterados

- `agents/combat.py:895-935, 984, 1005` — `dead_before`/`newly_dead` + `xp_awarded` (R1).
- `services/event_processor.py:277-330` — transição real + `working["quests"]` (R2); carimbo de `turn` (R9).
- `agents/storyteller.py:337, 782-812, 857-860` — composição única do jogador (R3), `first_visit` (R5), dedupe de
  fações pós-validação (R8).
- `agents/campaign_manager.py:178-224` — fallback só sem plano (R4).
- `services/exploration.py:104-116` — parâmetro `first_visit` (R5).
- `services/quest_log.py:176-211` — `normalize_fingerprint` + Jaccard (R6).
- `progression.py:37-43`, `encounter_budget.py:16-18`, `combat_mechanics.py` — `normalize_categoria` (R7).
- `services/rule_engine.py:239-248` — `turn` (R9). `services/narrative_evidence.py:88-93` — ganho bruto (R10).

### Assinaturas

```python
def xp_for_kills(dead_enemies: list[dict]) -> int            # por categoria canônica
def normalize_categoria(sheet: dict) -> str                   # lacaio|padrao|elite|chefe|nomeado
def discover_on_arrival(state, dest, *, first_visit: bool, rng=None) -> tuple[dict, list]
def normalize_fingerprint(action: str) -> frozenset[str]
```

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)
`tests/test_bug_contabilidade_recompensas.py`: `test_kill_xp_once_across_rounds` (R1),
`test_quest_completed_twice_in_batch_pays_once` (R2), `test_beat_xp_keeps_discovery_loot` (R3),
`test_planner_failure_keeps_plan` (R4), `test_revisit_looted_treasure_no_discovery` (R5),
`test_quest_fingerprint_punctuation` (R6), `test_xp_tier_by_categoria` (R7), `test_faction_impact_dedupe` (R8),
`test_rule_engine_derived_turn` (R9), `test_reward_delta_gross` (R10).
### Etapa 1 — combate + event_processor + rule_engine (R1, R2, R9)
### Etapa 2 — storyteller + exploration + campaign_manager + quest_log (R3–R6, R8)
### Etapa 3 — tiers por categoria (R7) + guard (R10) + integração (R11)
### Etapa 4 — regressão `uv run pytest`; playtest offline `combate`/`quester`/`explorador` 50 turnos: `xp` por turno
nunca > XP máximo possível de um turno; `defeated` ≤ abates.

## 5. Critérios de aceite

- [x] 10 testes vermelhos → verdes; `tests/test_audit_reward_contracts.py`, `test_fase33.py`, `test_fase27.py`,
      `test_matriz_a_contratos.py`, `test_pre_matrix_contracts.py`, `test_beats_visibilidade.py` verdes ou diff justificado.
- [x] `uv run pytest` verde; playtest offline com run_id e grep de XP por turno.
- [x] Saves antigos carregam (sem mudança de schema; `xp_awarded` é campo opcional no inimigo).
- [x] Guard de FallbackLLM: `campaign_manager` já tem isinstance (R4 muda só o fallback).

## 6. Smoke test com LLM real

1. Combate com 2 inimigos, matar 1 e lutar 2 rodadas → HUD XP sobe 1× pelo abate.
2. Concluir quest e repetir "concluo a missão" → XP não repete.
3. Viajar para as Profundezas com beat prestes a concluir → ouro/itens do baú + XP do beat.

## 7. Riscos & compatibilidade

- Perfis do playtest que contavam com XP inflado sobem mais devagar: remedir `first_death_turn`/nível (sinalizar no README).
- R4 pode deixar o jogo sem replan por 15 turnos se o provider seguir falhando — mitigado por `needs_replan`
  persistido (spec `SPEC-228` R7).
- R7 muda custo de orçamento de encontro para 14 criaturas: revalidar `clamp_encounter` em `tests/test_encounter_budget*.py`.

## 8. Pontos de decisão do dono

- **D-A (XP de abate com reforços):** default por transição + `xp_awarded`; alternativa: XP só no fim do conflito
  via `ConflictSummary.mortos` (mais simples, muda a cadência do HUD).
- **D-B (Jaccard 0,6):** limiar sugerido; alternativa mais simples: exigir turnos não consecutivos.

## 8b. Decisoes aplicadas e desvios (execucao 2026-10-16)

- **D-A**: default (transicao vivo->morto + `xp_awarded`) implementado; mortos presentes no estado de entrada nunca rendem.
- **D-B**: Jaccard 0,6 (`FINGERPRINT_JACCARD`).
- **R8**: dedupe por `faction_id` (ultimo vence) ANTES de aplicar; e (revisao Sol) `event_processor._revert_reputation` desfaz o delta exato aplicado pelo storyteller quando o `reputation_changed` e REJEITADO por qualquer motivo (ex.: faccao derrotada). Aceito = nada a desfazer, sem aplicar 2x. Estado e log nunca divergem.
- **R10**: o guard aceita o liquido, liquido+gasto (`turn_baseline[<gold|xp>_spent]`) ou qualquer ganho individual (`turn_baseline[<gold|xp>_gains]`). Ledger alimentado por um helper unico `services/turn_outcome.record_gain(baseline, kind, amount)` (ganho >0, gasto <0; sem baseline = no-op) nos pontos reais: combate (XP de abate), storyteller (baú/achado ouro, armadilha XP, beat XP), event_processor (quest XP+ouro), loot (saque ouro, venda ganho, compra/craft gasto).
- **R2**: a repro exige propostas com `target_id` distintos (mesmo alvo/turno ja era rejeitado por dedupe).
- **R7**: `type` e so fallback; ficha sem `categoria` e desconhecida continua lacaio. Fichas de combate recebem `categoria` via `ensure_combat_sheet`.
- **R4 (revisao Sol)**: o plano anterior so e mantido se for da MESMA regiao (`_same_region`); de outra regiao cai no template ancorado no local atual (evita transplante de ganchos, P1 sessao 38).
- **Follow-up (D-A, nao trivial)**: reforco que reaproveite o id de um cadaver (`{base}_{N}`) nao renderia XP. `conflict_scene.fire_reinforcement` nao tem callsite de producao hoje; quem ligar reforcos deve gerar id de instancia unico por conflito.
- Smoke real (secao 6) nao executado (sem provider real); cobertura offline via MockLLM.

## 9. Evidencia requerida

- `uv run pytest` completo; testes antes/depois; run_ids do playtest com grep de XP por turno.
- `docs/<spec>/README.md` com os scripts `test_r4.py`, `r1.py`, `repro1.py` transcritos e revisão `Sol` independente.
- Handoff opcional: casos de regressão para o corpus state/rules (SPEC-168) — autoria separada.
