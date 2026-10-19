# SPEC-288 — revisão (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (coordenador) · **Data:** 2026-10-19 · **Commit revisado:** `14de056` (rebaseado em main `981174e`) + correções `e6eb69f`

## Escopo

Branch `spec-288`: `world_utils.check_encounter` (ramo `looming_threat`), `agents/combat.py`
(`_killer_identity`, `player_downed`, `death_context`), `playtest/runner.py` (`_death_cause`,
`killer_id`), `playtest/telemetry.py`, `tests/test_spec288_causa_morte.py`. Fora: rodada longa
de playtest (o executor declarou `combate --turns 200 --seed 21`; não repetida aqui).

## Verificação

1. **Criatura/escala/determinismo:** o ramo usa `pick_encounter_enemy(loc, eff, ...)`, idêntico ao
   ramo `high_danger` já existente: pool pela `region_id` do local, BOSS excluído, porte pela força
   escalada (`forced_encounter_danger`, apex não escala). Sem `bestiary_knowledge`/`projection` é
   round-robin por turno; com eles, o sorteio ponderado da 6.3 (mesmo comportamento do ramo vizinho).
   Conferido: Floresta dos Sussurros t10/11/12 → Aranha Lobo / Sombra Espreitadora / Caçador de Casca.
2. **Manifesto SPEC-203:** `enemy_id` do bestiário → `resolve_canonical_source` devolve
   `source=systemic` (fonte canônica (a)), sem cair no scanner. Teste novo prova.
3. **Gancho preservado:** `flavor = threat` chega à narração via `COMBAT START. {enc['flavor']}` no
   storyteller (`agents/storyteller.py:708`); `combat_target` agora é o nome da espécie.
4. **killer/killer_id:** `species_label_for` (template do bestiário, sem sufixo de instância);
   `killer_id` = id base do bestiário ou vazio. `death_context.killer` alimenta
   `continuity.death_history[].cause` (`services/continuity.py:61`) com a espécie. Sem PII (nome de
   criatura/NPC). Save antigo com inimigo-gancho: não quebra, rótulo continua o texto legado sem
   sufixo e `killer_id` vazio (teste novo). Payload do evento é dict livre — validador não barra a
   chave aditiva.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | playtest/telemetry.py:1012 | Fallback de `deaths_log` (sem `deaths_log` do runner nem continuity) lia só `killer` → `None` em morte por armadilha; violava R3. | Corrigido: `killer → cause → "desconhecida"` + `killer_id`. |
| P2-2 | P2 | tests/test_spec288_causa_morte.py | Teste original tinha `if enc.get("enemy_id")` — passaria sem resolver criatura. | Corrigido: 3 testes novos (determinismo + região + não-BOSS, fonte `systemic` do manifesto, save legado/lista vazia). |
| P2-3 | P2 | world_utils.py:913 | A criatura é regional, não temática da ameaça (ex.: "Corvane reativou câmara" → Aranha Lobo). | Follow-up: aceitável (mesmo critério do `high_danger`); afinidade ameaça→facção/tags pede spec própria. |

## Correções aplicadas

- `e6eb69f` — P2-1 e P2-2.

## Pendências

- P2-3 (afinidade temática da criatura com a ameaça) — dono decide se vira spec.
- Header da spec diz `REVIEW_REQUIRED: false`; revisão feita mesmo assim a pedido do coordenador.
- Índices (project/spec) stale na branch: rebuild no checkout limpo antes do push.

## Comandos rodados

```text
git rebase main → ok (main 981174e)
py.sh -m pytest tests/test_spec288_causa_morte.py → 6 passed
py.sh -m pytest -q (suíte completa) → exit 1; só 3 falhas de índice stale (test_project_index ×2, test_spec_index_tool ×1)
```
