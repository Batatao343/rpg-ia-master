# SPEC-407 — regravação da baseline (--tighten)

Medido sobre a `main` 21c59bdc (405 e 406 já pousadas). Folga = base - atual.

## Antes (folgadas e órfãs)

| chave | base | atual | folga |
|---|---|---|---|
| agents/archivist.py | 1252 | 1237 | 15 |
| agents/combat.py | 3957 | 3946 | 11 |
| api_presenters.py | 1357 | 1353 | 4 |
| playtest/telemetry.py | 1671 | 1664 | 7 |
| routes/turn.py | 1915 | 1902 | 13 |
| services/card_effects.py | 1826 | 1817 | 9 |
| services/companion_soul.py | 1109 | 1105 | 4 |
| services/law.py | 1731 | 1705 | 26 |
| services/reputation.py | 1353 | 1349 | 4 |
| state.py | 1098 | 1082 | 16 |
| web/src/App.tsx | 1156 | ÓRFÃ | - |
| world_utils.py | 1983 | 1962 | 21 |
| agents/combat.py::_narrate_outcome | 114 | 111 | 3 |
| api_presenters.py::_combat_block | 252 | 247 | 5 |
| routes/turn.py::_stream_turn_events | 271 | 263 | 8 |
| services/conflict_orchestrator.py::enemy_declaration | 157 | 154 | 3 |
| services/event_processor.py::apply_event | 149 | 148 | 1 |

`web/src/App.tsx` (950 linhas, < 1000) saiu do limite: órfã, removida.

## Depois (saída de `--tighten`)

```
agents/archivist.py: 1252 -> 1237
agents/combat.py: 3957 -> 3946
api_presenters.py: 1357 -> 1353
playtest/telemetry.py: 1671 -> 1664
routes/turn.py: 1915 -> 1902
services/card_effects.py: 1826 -> 1817
services/companion_soul.py: 1109 -> 1105
services/law.py: 1731 -> 1705
services/reputation.py: 1353 -> 1349
state.py: 1098 -> 1082
removida: web/src/App.tsx
world_utils.py: 1983 -> 1962
agents/combat.py::_narrate_outcome: 114 -> 111
api_presenters.py::_combat_block: 252 -> 247
routes/turn.py::_stream_turn_events: 271 -> 263
services/conflict_orchestrator.py::enemy_declaration: 157 -> 154
services/event_processor.py::apply_event: 149 -> 148
```

16 entradas apertadas + 1 órfã removida; nenhuma subiu ou entrou. Segunda execução: sem alteração (idempotente).
