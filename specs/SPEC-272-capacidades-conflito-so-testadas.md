# SPEC-272 — Decidir: ligar ou apagar capacidades do conflito que só os testes usam

> **Status:** `draft`
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
