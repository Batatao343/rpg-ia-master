# SPEC-400 §6 - smoke de integracao local (07/11/2026)

Ambiente: `RPG_FORCE_MOCK=1 RPG_ENEMY_DECKS=on`, sem chave. Sem LLM no caminho. Rodado em processo (nao via uvicorn): `ensure_combat_sheet` -> `json.dumps/loads` (simula save/load) -> `ensure_combat_sheet` (remontagem) -> `enemy_declaration` ferido (5/20), 4 chamadas.

Edicao declarada: no `mon_portao_que_morde`, a `absoluta` de `muito_ferido` recebe `action_key: "flee"` (simula save de antes da 395).

| Criatura | Declaracoes | Resultado |
|---|---|---|
| `mon_portao_que_morde` (abissal, absoluta, `flee` reinjetado) | `card`, `card`, `card`, `card` | nunca `flee` nem `move` |
| `mon_lacrador_de_saidas` (abissal flexivel) | `tactic flee` x4 | ainda foge |

Snapshot `docs/spec394/snapshot.py`: 373 ids identicas (`cmp` base x fix, antes e depois do R6).
