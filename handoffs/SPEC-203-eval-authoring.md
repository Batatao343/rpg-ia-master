# SPEC-203 — handoff de autoria de evals (tarefa separada)

`EVAL_AUTHORING_REQUIRED: true`. O executor da SPEC-203 **não** editou `evals/`.
Casos a autorar (com aprovação do dono, régua protegida):

## state_rules
1. **Identidade do elenco estável por rodada.** Estado com `combat.encounter`
   congelado (participantes `enemy_bandido_1/2`) + 2 rodadas: elenco de
   `enemies` ⊆ manifesto; `species_label/bestiary_id/faction_id/role` imutáveis.
   Oráculo: `services.encounter_manifest.validate_roster == []` e
   `assert_immutable` sem erro.
2. **Reload preserva manifesto/fase/próximo passo** em `entering|active|resolving|ended`
   (`persistence._state_to_save_data → _raw_to_state`; `SCHEMA_VERSION` permanece 8).
3. **Lifecycle terminal → exploração.** Após `phase=ended` (≠ death) com
   `combat.result`, o 1º turno seguinte roteia `storyteller` e marca
   `combat.explore_resumed=True`; `death` mantém `death_pending`.
4. **Save v8 legado com combate ativo** ganha manifesto `legacy_migrated` e
   `phase=active` de forma idempotente; sem combate ativo → `phase=ended`.

## narrative_npc
5. **Prosa de combate não renomeia espécie do manifesto.** Narração que só cita
   espécie fora do elenco (ex.: "corvo" com elenco de bandidos) é marcada por
   `prose_guard.species_drift` e neutralizada para o texto determinístico.

Fixtures de referência: `tests/test_encounter_manifest.py`,
`tests/test_encounter_lifecycle_reload.py`, `tests/test_encounter_identity_repro.py`.
