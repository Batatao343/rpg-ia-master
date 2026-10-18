# SPEC-272 — Decidir: ligar ou apagar capacidades do conflito que só os testes usam

> **Status:** `draft` · **Revisão independente 2026-10-18:** SAFE WITH CHANGES — decisão item a item continua obrigatória; apagar exige adendo nas specs `done` de origem (ver §8)
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** decisão do dono, por capacidade (ligar no motor ou apagar)
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Astra` (≡ Opus) · **REVIEW_REQUIRED:** `true` — toca o motor de conflito
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Os motores aditivos da migração de conflitos (conflito-03/04/07/09/12) trazem funções
públicas que **só os testes chamam**: nenhum nó do grafo, serviço, API ou playtest as usa.
É o mesmo padrão "a capacidade existe, o motor não liga" que a SPEC-050 corrigiu nas classes:
o teste passa, mas o jogador nunca vê a mecânica.

| Módulo | Funções só-teste | Linhas |
|---|---|---|
| `services/conflict_scene.py` | `visible_objects`:317, `discover_object`:336, `set_postura`:265, `consume_postura_on_attack`:280, `clear_sustained_postura`:291, `add_reinforcement_trigger`:388, `fire_reinforcement`:397, `stop_guard`:426, `alert_party`:514 | ~97 |
| `services/chase.py` | `simulate_abandoned_companion`:193, `abandon_companion`:171, `offer_sacrifice`:257, `chase_attack`:269, `luck_roll`:126, `chase_conductor`:105, `approach_virtude`:113 | ~95 |
| `services/death_flow.py` | `resolve_surrender`:329, `last_stand_pay`:118, `can_be_nonlethal`:310, `apply_nonlethal_finish`:319 | ~57 |
| `services/conflict_resolution.py` | `general_test`:197, `multiply_principal`:90, `net_advantage`:80 | ~46 |
| `services/bestiary_knowledge.py` | `apply_persisted_knowledge`:133, `reveal_card`:93, `reveal_resistance`:108, `is_card_revealed`:125, `is_resistance_revealed`:129 | ~45 |
| `services/conflict_summary.py` | `validate_narrative_consistency`:225 | ~20 |
| `services/tactical_profile.py` | `get_or_generate_profile`:416, `player_retains_party_control`:287, `profile_takes_over`:282 | ~17 |
| `services/encounter_preparation.py` | `validate_creature_selection`:210 | ~11 |
| `services/cards.py` | `suggested_virtue_cards`:211 | 6 |
| `combat_mechanics.py` | `resolve_damage_formula`:107 (só na lista SOBREVIVE de `tests/test_cutover_audit.py`) | 14 |

Total: **~410 linhas de produto** + os testes correspondentes. Números de linha medidos
no commit da auditoria.

## 2. Requisitos

- **R1** — Para cada linha da tabela, o dono escolhe **ligar** (vira spec de feature própria,
  com smoke real) ou **apagar** (entra nesta spec).
- **R2** — Apagar = remover a função, os testes unitários que só exercitam ela e as
  entradas em `tests/test_cutover_audit.py`, se houver.
- **R3** — Antes de apagar, confirmar com grep que nenhum chamador apareceu desde a
  auditoria e que a função não é alcançada por nome (dicionário de handlers, `HANDLED_KINDS`).
- **R4** — Se `test_cutover_audit.py` passar a listar só itens apagados, apagar o teste também.
- **R5** *(revisão)* — Cada capacidade apagada foi **entregue como requisito** de uma spec `done`
  (SPEC-064 cena, SPEC-065 resolução, SPEC-068 morte/rendição/captura, SPEC-069 perfil tático,
  SPEC-070 fuga/perseguição, SPEC-072 preparação de encontro, SPEC-073 resumo canônico, SPEC-075 Cartas). Apagar = acrescentar à spec de origem uma linha
  "capacidade removida pela SPEC-272 (nunca ligada ao motor)" para não deixar critério de aceite
  `done` falso, e atualizar `docs/design/CARTAS.md:59` se `suggested_virtue_cards` sair.
- **R6** *(revisão)* — Efeitos em cascata a decidir junto:
  `get_or_generate_profile` é o único chamador de `generate_tactical_profile` (`tactical_profile.py:423`):
  apagar o primeiro torna o gerador LLM da SPEC-069 inteiro órfão. `suggested_virtue_cards` é o
  único leitor de `data/cards/virtude_sugeridas.json` (gerado por `gen_cards_v4.py:806`, testado
  por `test_conflito_autoria_cartas.py:145`): apagar deixa dado + gerador sem consumidor.
  `fire_reinforcement` tem follow-up registrado na SPEC-226:165 (id de instância único ao ligar
  reforços): se apagar, encerrar esse follow-up.
- **R7** *(revisão)* — Antes de decidir, tratar o conjunto como achado do mesmo tipo da SPEC-050
  (mecânica entregue e morta), não como lixo: o default sugerido é **ligar** o que o jogador
  esperaria ver (rendição, golpe não-letal, abandono de companheiro, revelação persistente do
  bestiário) e **apagar** só helpers sem valor de jogo (`net_advantage`, `multiply_principal`,
  `luck_roll` isolado, `resolve_damage_formula`).

### Fora de escopo

Mudar a regra de qualquer mecânica que está ligada.

## 5. Critérios de aceite

- [ ] Tabela de decisão preenchida pelo dono no PR
- [ ] `uv run pytest` verde
- [ ] `uv run python -m playtest run --all --turns 30` (MockLLM) sem violação nova
- [ ] Corpus de evals `encounter_manifest` verde via `evals` CLI (régua não editada)
- [ ] Project Index regenerado em checkout limpo

## 6. Smoke

Para o que for apagado: 1 campanha `combate` de 10 turnos com DeepSeek; zero erro.

## 7. Riscos & compatibilidade

Risco **médio**: o grep não enxerga chamadas montadas em string. Rollback: `git revert`.

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE WITH CHANGES** (a spec já exige decisão do dono por item; o risco é decidir "apagar" sem
saber o que mais cai junto).

Verificado: as 35 funções da tabela têm **zero** chamadores fora de `tests/` (nem na própria módulo, nem em
`evals/`, JSON/YAML, `HANDLED_KINDS`). A cutover conflito-13 está `done`, então nada delas está reservado
a ela; `stop_guard` deixou de ser necessário porque `reset_turn_budget` já zera `guarding`
(`conflict_scene.py:65`, correção da SPEC-232).

Achados (viraram R5–R7):
1. Cada função é requisito entregue de spec `done` (064/065/068/069/070/072/073/075). Apagar sem adendo deixa
   critério de aceite `done` falso.
2. Cascatas: `get_or_generate_profile` → `generate_tactical_profile` (gerador LLM da SPEC-069) inteiro órfão;
   `suggested_virtue_cards` → `virtude_sugeridas.json` + parte do `gen_cards_v4.py` sem consumidor e
   `docs/design/CARTAS.md:59` desatualizado; `fire_reinforcement` tem follow-up aberto na SPEC-226:165.
3. É o mesmo padrão "entregue e nunca ligado" da SPEC-050; recomendação: ligar o que tem valor de jogo.
