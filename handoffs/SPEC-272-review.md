# SPEC-272 — revisão independente (REVIEW_REQUIRED)

- **Revisor:** Opus (Astra ≡ Opus), não autor. Worktree `rpg-spec-272`, branch `spec-272`, rebased em `main` `5695cb4` (sem conflito).
- **Escopo:** commit `feat(spec272)` (original `b10a472`) + correção desta revisão.
- **Veredito:** **APPROVED** (com 1 correção aplicada e 1 achado pré-existente registrado).

## (a) Funções ligadas

| Ponto | Resultado |
|---|---|
| Determinismo de `_sync_enemy_knowledge` | OK — só lê `enemy_card_usage` (chaves criadas apenas em `cards.use_enemy_card`; reação não ofertada restaura o snapshot, SPEC-232 R3) e o overlay; sem RNG/LLM. |
| Vazamento de Carta não usada | OK — só Cartas efetivamente usadas entram em `revealed_cards`; `apply_persisted_knowledge` traz só o que já foi revelado do mesmo arquétipo e respeita `variant_exclusive_cards`. API (`api.py:1950`) projeta só `{id,name}`; o narrador não lê o campo. |
| Overlay só no perfil `legacy` | OK — mesmo guard de `dossiers._revealed_for` (`RPG_RUNTIME_PROFILE`); fora de `legacy` a revelação fica só no combate corrente. Teste `test_perfil_nao_legacy_revela_so_no_combate`. |
| `archetype_id` x manifesto (SPEC-203) | OK — o manifesto deriva `bestiary_id`/espécie de `_base_id(id)`, não de `archetype_id`; `assert_immutable` não é afetado. Eval `encounter_manifest` 31/31. |
| **Defeito encontrado** | Instâncias que não passam por `_instances` — reforço do orçamento (`_apply_encounter_budget` → `fill_encounter`, `id = f"{t['id']}_{i}"`) e saves antigos — chegavam sem `archetype_id`; `_archetype_id` caía no id da instância e o overlay gravava `mon_sanguessuga_braco_2` (visto no overlay do playtest), poluindo o bestiário e escondendo a revelação do dossiê. **Corrigido:** `_sync_enemy_knowledge` preenche `archetype_id = encounter_manifest._base_id(id)` quando falta. Teste novo `test_instancia_sem_archetype_id_usa_id_base_no_overlay` (falhava antes). Rerun: overlay só com chaves de arquétipo. |
| Sorte na fuga | OK — 1 `luck_roll` por aliado em `sides["ally"]`; `luck_to_advantage` limita a ±1 (conflito-09 R5). Usa o mesmo `rng` do combate (`random` global, como todo o resto do round — não piorou o determinismo). Nota menor: aliado inconsciente da party ainda rola (o `ally_ids` já filtra mortos de cena, não inconscientes); fora do escopo. |

## (b) Funções apagadas

`git grep` (fora de `specs/docs/handoffs`) de `net_advantage`, `multiply_principal`, `resolve_damage_formula`, `stop_guard`, `chase_conductor`, `resolve_surrender`, `last_stand_pay`: só `project_index/repo_graph.json` (regenerado pelo coordenador). Nenhuma string/dicionário de despacho com esses nomes. Adendos conferidos:
- SPEC-065/232: `roll_kept` usa só o sinal; `efeito_principal_multiplicador` aplicado em `conflict_orchestrator:759` — correto.
- SPEC-067: `reset_turn_budget` zera `guarding` (`conflict_scene.py:65`) — correto.
- SPEC-068: `pick_action` → `surrender` → `orchestrator:463` marca `surrendered`; `rende_*`/`nunca_rende` não existem em dado nenhum; `_resolve_last_stands` documenta ignorar custo — correto.
- SPEC-069/070/074: coerentes com o código.

## (c) Itens mantidos

Os 24 "manter" exigem declaração do jogador/UI ou mudam pipeline de dano/narração; manter preserva os consumidores de `generate_tactical_profile` e `virtude_sugeridas.json` (R6). Justificativa aceita.

## Gates

- `pytest` completo (sem pipe): tudo verde exceto 2 testes `test_project_index.py::test_real_index_*` — falham só por índice stale (fonte mudou), resolvido pelo rebuild do Project Index em checkout limpo (coordenador). Ruff do repo inteiro verde.
- `ruff check` nos arquivos tocados: verde.
- `evals.core.governance check`: 11 datasets válidos. `evals run --suite encounter_manifest`: passed, 31 casos.
- Playtest MockLLM `--all --turns 3`: 14/14 perfis, 0 erro, 0 violação.
- Playtest `--profile combate --turns 200`: 0 erro. **Achado pré-existente:** em checkout LIMPO (sem `saves_playtest/runtime`), `main` dá **133** `combat.no_progress` e o branch **130** (mesmo check, seed 0) — combate travado (ataque `ok` sem mudança mecânica a partir do round ~14). Com cache de runtime quente o mesmo run deu 0/0 (era a evidência do executor). Não é regressão da SPEC-272; recomenda-se spec própria.
- **Smoke §6 real:** `playtest run --profile combate --turns 10 --real` — 10/10, `mock=false`, DeepSeek, 0 erro, 0 violação, 6 turnos de combate (move/card/item), ~US$ 0,0053.
- Project Index: pendente (coordenador, rebuild em checkout limpo).
