# SPEC-290 — revisão (review)

> **Veredito:** `APPROVED`
> **Revisor:** Opus (revisor independente) · **Data:** 2026-10-19 · **Commit revisado:** `a88f14f`

## Escopo

Branch `spec-290` (`git diff main...spec-290`, commit `a88f14f`): `agents/bestiary.py`,
`api.py` (`_build_combat_simulator_state`), `tests/test_spec290_chefe_sobrevivencia.py`,
spec. Fora: `world_utils` (SPEC-289), valores do bônus.

## Verificação dos requisitos

- **R1** — `apply_encounter_survival` usa o campo quando presente; ausente → default por
  `combat_mechanics.normalize_categoria` (campo `categoria`, `type` só como fallback de
  ficha legada, mapa fechado `_CATEGORIA_CANON`). Nunca por nome. Lacaio/padrão/elite: 0.
  Curados: os 13 Chefe/Nomeado de `data/bestiary.json` já trazem o campo (12), sem mudança.
- **R2** — `EnemySchema.categoria` é `Literal` (o LLM não escolhe valor livre);
  `materialize_enemy_concept` grava 12 para `chefe`; geração nova e overlay legado devolvem
  `_scaled_copy` (cópia) após `save_enemy(base)`. Overlay v4 em cache-hit passa por `_ready_v4`
  sobre `dict(db[...])` (cópia). Guard `isinstance(res, EnemySchema)` + `try/except` intactos;
  fallback segue `lacaio` (sem bônus).
- **R3** — laboratório calcula `encounter_level = compute_encounter_level(danger, danger)` da
  categoria (chefe 6, nomeado 5 → 2 passos, teto do SPEC-287) e aplica sobre `deepcopy(template)`;
  `gamedata.BESTIARY` intacto. `danger` local só alimenta o `world` do próprio laboratório.
- **R4** — nenhum consumidor exige o campo; reload não chama `apply_encounter_survival`
  (únicos callsites: `_ready_v4`, `_scaled_copy`, laboratório).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | tests/test_spec290_chefe_sobrevivencia.py | Testes não provavam o round-trip real do overlay (save_enemy → load → cache-hit repetido) nem o reload do save do laboratório. | Adicionados `test_real_overlay_round_trip_does_not_accumulate` e `test_lab_chefe_save_load_keeps_value` (commit desta revisão). |
| P2-2 | P2 | api.py:3248 | No laboratório os aliases legados `hp`/`max_hp` do inimigo ficam com o valor do template (só `vitalidade`/`max_vitalidade` refletem o bônus). O motor usa só Vitalidade; sem efeito hoje. | Não corrigido (pré-existente, cosmético). |

## Correções aplicadas

- Testes de round-trip (P2-1), commit `test: SPEC-290 review round-trip tests`.

## Pendências

Nenhuma bloqueante. P2-2 fica como nota.

## Comandos rodados

```text
py.sh -m pytest tests/test_spec290_chefe_sobrevivencia.py + spec287/simulador/bestiário → 137 passed (antes das adições)
py.sh -m pytest tests/test_spec290_chefe_sobrevivencia.py tests/test_combat_simulator.py → 21 passed, 0 falhas
POST /game/combat-simulator (TestClient, mock) → mon_urso_tita 16 → 40 (+24); mon_cao_rebite 14 → 14
```
