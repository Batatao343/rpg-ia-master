# SPEC-272 — evidência (2026-10-18)

Decisão item a item em [specs/SPEC-272 §9](../../specs/SPEC-272-capacidades-conflito-so-testadas.md#9-execução-2026-10-18--tabela-de-decisão).

## O que mudou

- **Ligado:** revelação de Cartas do inimigo (`agents/combat._sync_enemy_knowledge` → `bestiary_knowledge.reveal_card`/
  `apply_persisted_knowledge`/`is_card_revealed`; instâncias recebem `archetype_id`) e Teste de Sorte dos aliados na fuga
  (`_attempt_flee` → `resolve_chase_round(companion_luck=[luck_roll…])`).
- **Apagado (7):** `net_advantage`, `multiply_principal`, `resolve_damage_formula`, `stop_guard`, `chase_conductor`,
  `resolve_surrender`, `last_stand_pay`. Adendo datado em SPEC-065/067/068/069/070/074/232.
- **Mantido (24):** com motivo na tabela; nenhum dado/gerador ficou órfão (`virtude_sugeridas.json`,
  `generate_tactical_profile` preservados).

Saldo de código: −104 / +34 linhas de produto.

## Testes

- Novo: `tests/test_spec272_conflito_ligado.py` (6) — sorte na fuga com/sem aliado, revelação + persistência por
  arquétipo, perfil não-legacy não grava overlay compartilhado, `archetype_id` na instância, `combat_node` revela a Carta
  usada na rodada.
- Reescritos: `test_vantagem_e_desvantagem_se_cancelam` (sobre `roll_kept`), Guarda expira por `reset_turn_budget`.
- Playtest MockLLM: `--all --turns 3` (14 perfis) e `--profile combate --turns 200` — 0 erro, 0 violação. O overlay do
  run de 200 turnos registrou Cartas reveladas por arquétipo (ex.: `bst_defesa_instintiva`, `bst_toque_gelido`).

## Limites

- Persistência entre encontros só no perfil `legacy` (o overlay não é escopado por dono/jogo; mesmo fail-closed de
  `dossiers._revealed_for`). Em perfis DB a revelação vale só no combate corrente.
- Resistências reveladas, rendição/golpe não-letal por declaração do jogador, abandono de companheiro e reforços
  continuam não ligados (feature própria).
- Pendentes: revisão independente, smoke real §6, eval `encounter_manifest`, Project Index.
