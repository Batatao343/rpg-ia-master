# SPEC-231 — Combate: fluxo de morte com aliados, categoria de companheiro e persistência de aliados de cena

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · SPEC-068 conflito-07-morte-rendicao-captura, SPEC-055 aliados-em-combate e SPEC-060 checkpoints-morte `done` são corrigidas (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-203, SPEC-212, SPEC-232 (ordem final 2026-10-15)
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-02-02, 02-03, 02-04, 02-07, 02-16 (`achados/02-combate.md`)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — altera quando o jogador morre (`death_pending`) e o comportamento de companheiros
> **EVAL_AUTHORING_REQUIRED:** `false` — motor 100% determinístico; cobertura por testes de orquestração com seed

---

## 1. Contexto & Objetivo

A spec conflito-07 (morte rica) promete: último Crítico → Última Ação → Estado Terminal → até 2 estabilizações
por aliado capaz → só então morte real; companheiros e Nomeados usam o fluxo completo. A auditoria reproduziu
(scripts `combate/r1.py`, `r8.py`, `r11.py`, re-executados pelo orquestrador) que, com aliados em cena, o
protagonista **morre no primeiro Estado Terminal exatamente como se estivesse sozinho**, que companheiros caem
sem fluxo e que aliados transitórios **começam cada rodada com Vitalidade cheia**.

Fatos no HEAD `d6af933`:

- [F] `services/conflict_orchestrator.py:1059-1072` `_stabilizer_for` procura aliados só na PRIMEIRA lista de
  `sides` que contém `down_id`; `sides = {"hero": ["player"], "ally": [...], "enemy": [...]}` (`agents/combat.py:731`)
  → para o player `same_side == ["player"]` → `stabilizer: None` → `player_dead True, cause "sem aliado próximo e
  capaz"`. `_opposing_ids`/`_same_side_ids` tratam `hero+ally` como um lado; esta função não.
- [F] `party.make_companion_from_npc` grava `categoria: "padrao"`; `ensure_combat_sheet` só aplica o ramo
  `companheiro` se o dado já trouxer isso. Resultado (`r11.py`): `sheet categoria: padrao, full_flow: False,
  pursuit nao_persegue` — companheiro morre ao preencher o último Crítico (sem Última Ação/Terminal) e ainda
  recebe `pursuit_policy`, `max_entropy` de inimigo e a carta reativa `bst_defesa_instintiva`.
- [F] `agents/combat.py:719-722,761,976-980,1001-1002`: `allies` é reconstruído a cada rodada a partir do SNAPSHOT
  `combat["scene_allies"]` (criado na rodada 1) e o que se persiste é o snapshot original, não as fichas mutadas.
  `r8.py`: aliado com 2/8 ao fim da rodada 1 começa a rodada 2 com 8/8; aliado morto reaparece lutando.
  `_reflect_scene_allies` só copia a Vitalidade final para o NPC (válida uma rodada).
- [F] `services/death_flow.py:139-140,190-191` seta `last_stand_resolved=True` e incrementa
  `stabilization_attempts`; o único reset está em `services/actor_lifecycle.py:118` (restore de checkpoint).
  Descanso que remove o Crítico (`rest_treat_wounds`) e fim de conflito não limpam. `r1.py`: após sobreviver e
  tratar o Crítico, o 2º quase-morte → `dead True, death_pending False` sem Última Ação nem estabilização.
- [F] `services/conflict_turn.py:328-335` (carta `estabilizar`) seta `scar_pending=True` mas não registra em
  `out["scars_pending"]` (`combat.py:900-903`) → Cicatriz obrigatória (R6 conflito-07) nunca gerada por carta.

Objetivo: o lado do herói (`hero` + `ally`) é um lado para estabilização; companheiros/aliados usam a categoria
`companheiro`; o estado dos aliados transitórios persiste entre rodadas; flags de Última Ação/estabilização
resetam quando o Ferimento Crítico é tratado; a Cicatriz é gerada em todo caminho de reanimação.

## 2. Requisitos

- **R1** — [R] `_stabilizer_for(down_id, actors_by_id, sides)` usa `_same_side_ids` (hero+ally são o mesmo lado;
  enemy é outro) e devolve o aliado vivo, consciente, não-terminal e **mais próximo/engajável** (ordem: party ativa
  → aliado transitório → por Agilidade). Teste de reprodução: player terminal + companheiro vivo em `ally` → hoje
  `None`; depois o companheiro, e `resolve_terminals` executa até 2 tentativas antes de `player_dead`.
- **R2** — [R] Simetria: aliado/companheiro em Estado Terminal pode ser estabilizado pelo player (`hero`) ou por outro
  aliado. Teste: companheiro terminal + player vivo → estabilização tentada.
- **R3** — [R] `make_companion_from_npc` e `party.scene_allies` gravam `categoria="companheiro"`;
  `ensure_combat_sheet(sheet, *, is_ally: bool=False)` força `categoria="companheiro"` para aliados e NÃO aplica
  `pursuit_policy`, `max_entropy` de inimigo nem cartas reativas de bestiário. Teste: `r11.py` → `full_flow True`,
  sem `bst_defesa_instintiva`.
- **R4** — [R] Aliados transitórios persistem entre rodadas: ao fim de cada rodada `combat["scene_allies"]` recebe as
  fichas PÓS-rodada (`[a for a in allies if a.get("transient")]`) e a rodada seguinte parte delas. Aliado com
  `dead`/`status=="morto"` não volta à iniciativa. Teste de reprodução: aliado 2/8 ao fim da rodada 1 → rodada 2
  inicia com 2/8; aliado morto na rodada 2 não age na 3.
- **R5** — [R] `_reflect_scene_allies` continua espelhando no NPC persistente (Vitalidade/morte) — agora a partir
  da ficha acumulada, não da última rodada. Teste: dano em 2 rodadas (3 + 3) → NPC com Vitalidade 2 (8−6).
- **R6** — [R] Reset dos flags: `last_stand_resolved=False` e `stabilization_attempts=0` quando o Ferimento Crítico
  do participante é removido (`rest_treat_wounds`, cura de Crítico por carta/item) e ao encerrar um conflito em que
  o participante sobreviveu sem Crítico cheio. Enquanto o Crítico cheio persiste, os flags permanecem (regra "sem
  imortalidade" mantida). Teste de reprodução: sobrevive → trata Crítico → novo último Crítico → hoje morte
  instantânea; depois Última Ação + Terminal + estabilização de novo.
- **R7** — [R] `stabilization_attempts` conta por EPISÓDIO terminal (zera ao sair do Terminal por qualquer meio),
  de modo que a 1ª tentativa de um novo episódio usa a DC inicial. Teste: dois episódios → DCs iguais na 1ª tentativa.
- **R8** — [R] Carta `estabilizar` (e qualquer reanimação fora de `resolve_terminals`) registra o alvo em
  `out["scars_pending"]` e limpa `last_stand_pending`; a Cicatriz é gerada 1× por episódio (guard FallbackLLM
  existente em `death_flow.generate_scar` mantido). Teste: reanimação por carta → `scars_pending == [alvo]` →
  Cicatriz aplicada 1×.
- **R9** — [R] `death_pending` do jogador continua sendo acionado SÓ após esgotar estabilizações (nenhuma mudança
  na tela de morte). Teste de regressão: sem aliados → comportamento atual byte a byte (`tests/test_death_flow.py`).

### Fora de escopo

- Modificadores de condição/passivas/reações inertes (spec `SPEC-232-combate-modificadores-passivas-reacoes.md`).
- Alvo de carta de cura/purga sem alvo (SPEC-199 R12 + BUG-02-20).
- IA tática do aliado (qual ação escolhe) — `tactical_profile` inalterado.

## 3. Design técnico

### Arquivos alterados

- `services/conflict_orchestrator.py` — `_stabilizer_for` via `_same_side_ids` + ordenação (R1/R2);
  `ensure_combat_sheet(..., is_ally=)` (R3); `resolve_terminals` chama reset de episódio ao reviver (R7).
- `party.py` — `make_companion_from_npc` e `scene_allies` com `categoria="companheiro"` (R3).
- `agents/combat.py` — persistência de `combat["scene_allies"]` pós-rodada (R4) e `_reflect_scene_allies` sobre a
  ficha acumulada (R5); `scars_pending` unificado (R8).
- `services/death_flow.py` — `reset_terminal_episode(participant)` (R6/R7); `check_scar_required` por episódio (R8).
- `world_utils.rest_treat_wounds` + caminhos de cura de Crítico (`conflict_damage.heal_wound`?) — chamam
  `reset_terminal_episode` quando o Crítico cheio deixa de existir (R6).
- `services/conflict_turn.py:328-335` — carta `estabilizar` registra `scars_pending` (R8).

### Assinaturas

```python
def _stabilizer_for(down_id: str, actors_by_id: dict, sides: dict, *, scene: dict | None = None) -> dict | None
def ensure_combat_sheet(sheet: dict, *, is_ally: bool = False) -> dict
def reset_terminal_episode(participant: dict) -> None   # last_stand_resolved=False, stabilization_attempts=0, last_stand_pending=False
```

Sem mudança de schema de save: `combat["scene_allies"]` já existe (passa a conter fichas atualizadas).

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)
`tests/test_bug_combate_morte_aliados.py`: `test_ally_stabilizes_player` (R1), `test_player_stabilizes_ally` (R2),
`test_companion_has_full_death_flow_and_no_enemy_policy` (R3), `test_scene_ally_damage_persists_between_rounds`
(R4/R5), `test_terminal_flags_reset_after_wound_treated` (R6/R7), `test_estabilizar_card_registers_scar` (R8),
`test_solo_death_unchanged` (R9, regressão).
### Etapa 1 — orchestrator/party/combat (R1–R5)
### Etapa 2 — death_flow/world_utils/conflict_turn (R6–R8)
### Etapa 3 — regressão `uv run pytest` + playtest offline `recrutador` e `combate` 40 turnos: grep de `cause: sem
aliado` com aliado em cena = 0; `deaths_log` coerente.

## 5. Critérios de aceite

- [x] 7 testes vermelhos → verdes; `tests/test_death_flow.py`, `test_aliados_combate.py`, `test_conflito_*.py`,
      `test_cutover_audit.py` verdes.
- [x] `uv run pytest` verde; playtest offline com run_id.
- [x] Saves antigos com `combat.scene_allies` em snapshot continuam carregando (o formato é o mesmo).
- [x] Guard de FallbackLLM mantido em `generate_scar` (sem site novo).

## 6. Smoke test com LLM real

1. Recrutar Brunna Ponte-Alta → combate → jogador cai → Brunna tenta estabilizar (log) → sobrevive com Cicatriz.
2. Combate de 3 rodadas com aliado ferido: Vitalidade do aliado decresce entre rodadas; no fim o NPC reflete o total.
3. Descansar com Médico/kit → novo combate → quase-morte dispara Última Ação de novo.

## 7. Riscos & compatibilidade

- A letalidade cai com aliados (intencional pela spec 07); o baseline `letalidade-early-game-v2` deve ser remedido.
- Companheiro com categoria `companheiro` não foge sozinho (sem `pursuit_policy`): coerente com chase/abandono.
- MockLLM: `generate_scar` já cai no fallback determinístico.

## 8. Pontos de decisão do dono

- **D-A (reset ao fim do conflito sem tratar o Crítico):** default NÃO resetar (regra "sem imortalidade"); só ao
  tratar o Ferimento. Alternativa: resetar após descanso longo mesmo sem tratamento.
- **D-B (quem pode estabilizar):** default qualquer aliado consciente e não-terminal; alternativa: exigir
  adjacência na cena (`conflict_scene.distance`), mais tático porém mais mortal.

## 9. Evidência requerida

- `uv run pytest` completo; testes antes/depois; run_id dos playtests `recrutador`/`combate`.
- `docs/<spec>/README.md` com os scripts `combate/r1.py`, `r8.py`, `r11.py` transcritos e revisão `Sol` independente.

## 10. Execução (2026-10-16)

- Decisões: D-A default (não resetar sem tratar o Crítico; reset só ao tratar o Ferimento ou ao fim do conflito sem Crítico cheio); D-B default (qualquer aliado consciente e não-terminal; sem adjacência; ordem party → transitório → Agilidade).
- Desvio menor: `_revive` zera `stabilization_attempts` (R7) preservando o valor em `res["attempts"]`; `ensure_combat_sheet` também força `companheiro` para fichas com `transient`/`origin_npc`.
- SPEC-226 (XP por transição vivo→morto) preservada. Playtests offline: `recrutador` 20261016-022456-507850 e `combate` 20261016-022500-708445, 0 erros.
- Smoke real (seção 6) não executado (sem LLM real); mecânica é determinística e coberta por testes.
