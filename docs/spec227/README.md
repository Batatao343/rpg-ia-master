# SPEC-227 — Integridade de economia e inventário

Testes de reprodução: `tests/test_bug_economia_integridade.py` (15 testes). Escritos antes da correção:
todos falhavam no HEAD exceto `test_gold_never_negative_property` (R11 é defensivo). Testes adicionados após a revisão: ação não gasta com item recusado, log de clamp, recompra do único.

## O que mudou
- `inventory.py`: `remove_item` multi-entrada atômico (+`display_name`), `find_entry_in_inventory`,
  `reconcile_equipment`, `equipped_items`, `resolve_flavor_item`, `try_use_item` (valida antes de consumir).
- `services/economy.py`: venda exige mercador, usa retorno de `remove_item`, esvazia slots (`unequipped`),
  item livre não vendável; craft atômico; `restock(world, projection=)` preserva único segurado pelo mercador.
- `combat_mechanics.py`: slot sem posse não dá bônus/passiva (`equipped_ids`).
- `character_creator.py`/`progression.py`/`api.py`: nível > 1 nasce no 1 e sobe por XP
  (`auto_resolve_choices`) -> cap de Entropia respeitado, `pending_choices == []`; sabor do LLM via `resolve_flavor_item`.
- `persistence.py`: equipamento órfão reconciliado no load (sem bump de schema).
- `agents/loot.py`: `unequipped` em `last_economy_action`; restock recebe a projeção.

## Testes legados alterados
- `tests/test_itens_vivos.py::_player`: fixture passa a possuir no inventário o que equipa (R5).

## Resultado
Suíte completa offline: exit 0. Playtest offline comerciante 30 turnos: `20261016-011115-284902`, 0 erros, 0 violações.
Limite: smoke real (LLM) não executado.

## Smoke com LLM real (2026-10-16)

`agents.loot._parse_trade_intent` com DeepSeek `deepseek-v4-flash` (2 chamadas CLASSIFY, `RPG_NO_MOCK=1`):
- "Vendo as duas adagas para o ferreiro" → `sell`, `adagas`, `qty=2`.
- "Quanto custa a poção de cura menor?" → `observe` (sem transação).
Revisão Sol independente: APPROVED_WITH_FOLLOWUPS; follow-ups (a),(c),(d),(e),(f) aplicados; R10 restrito à criação
(narração segue a Fase 6.2, fica para spec futura de recompensa narrada).
