# SPEC-390 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus 5.5 / Sol · **Data:** 2026-11-04 · **Commit revisado:** `c26c7ea3`

## Escopo

`git diff main...spec-390` (1 commit `c26c7ea3`): `services/round_log.py` (`_voce`, `_taunt_lines`),
`services/turn_outcome.py` (`_quest_titles`, `finalize_outcome`, `public_outcome`), `tests/test_spec390_text.py`
e §9 da spec. O smoke real §6 ficou fora (é do coordenador).

O que está correto:
- **R2.** O `receipt_id` é calculado antes de `quest_titles` (`turn_outcome.py:257-263`), então o hash não muda. O teste
  troca o título e compara o `receipt_id`. `quests_completed` continua `list[str]`. `public_outcome` lê o mapa e cai no id
  quando ele falta, o que cobre o save antigo e tem teste. O campo é `dict[str,str]` serializável; `public_outcome` é
  whitelist, então `quest_titles` não vaza cru. O `outcomeToast` já usa `title`.
- **R3.** O ramo da vítima "Você" fica isolado e o texto de vítima inimiga não muda (`test_spec353_registry`/`smoke7`
  verdes). Pela API, a seed `13 armadura` produz "Você está provocado por …" (verificado pela varredura abaixo).
- **R1 (parcial).** A linha "provocado por <herói>, muda de alvo." vira "provocado por você"; com outro ator, o nome fica.
- **TDD.** O executor escreveu a implementação antes dos testes. Para conferir, rodei `tests/test_spec390_text.py` contra
  a `main` num worktree descartável: os 6 testes de comportamento **falham** (R1, R3, R2×2, API voto, API entrega). Os 2
  testes de guarda (outro ator, vítima inimiga) passam, como deveriam.
- Sem flag nova, sem LLM, sem `except`, sem segredo. `conflict_orchestrator.py`/`api.py`/`agents/npc.py` não foram
  tocados. `dup_helpers`: nenhum nome repetido. As funções novas são curtas e `round_log.py` (934 linhas) fica abaixo de 1.000.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/round_log.py:249-252` (origem `services/conflict_orchestrator.py:2743`) | O nome do herói ainda aparece na seed `13 voto`. A outra saída do Voto, "Goblin resiste à provocação de Smoke368.", passa por `_HUMAN_LINE_RES` (`round_log.py:51`) e não é convertida. Varredura com a API real e MockLLM, 6 sementes: 3 ocorrências na mensagem de `/game/action`. Isso quebra o R1 ("a linha do Voto/Provocação não traz o nome do herói") e o R4 ("nome do herói 0× nas superfícies da `13 voto`"). | Em `_voce`, converter também `^(.+?) resiste à provocação de {hero}\.$` → `"{X} resiste à sua provocação."` (ou "à provocação de você"; o mesmo ponto único do R1). O nome de outro ator fica. |
| P1-2 | P1 | `tests/test_spec390_text.py:84-85` | A guarda do R4 é estreita demais: só afirma `f"provocado por {HERO}" not in text`, e por isso não pegou o P1-1. Também falta o que o R4 exige pela API: (a) a seed `13 armadura` (o R3 pela API, com "Você está provocado por" e herói 0×); (b) id cru nas superfícies de `13 voto`/`13 armadura`. | Varrer as superfícies de texto (mensagem/registro de `/game/action` e entradas de `/game/history`) sem `player_stats.name`, que é dado legítimo, e afirmar `HERO not in` em cada uma. Parametrizar `voto` e `armadura`, com regex de id (`\w+_\w+`, hex de 24) como na varredura do smoke-local 389 item 11. Adicionar teste unitário para a linha "resiste". |
| P2-1 | P2 | `tests/test_spec390_text.py` | O BRIEF/TESTES.md pede que teste novo não use o nome `test_specNNN_*.py`. A spec (§4) pediu esse nome, então isto não bloqueia. | De preferência, mover para `tests/test_combat_text_smoke8.py` ou para dentro de `test_combat_text_smoke7.py`, com a spec na docstring. |

## Correções aplicadas

(nenhuma ainda — 1ª rodada)

## Pendências

Nenhuma aceita como follow-up (política zero pendência): P1-1 e P1-2 precisam entrar nesta branch.

## Comandos rodados

```text
bash scripts/dev/pt.sh tests/test_spec390_text.py tests/test_spec353_registry.py tests/test_combat_text_smoke7.py tests/test_spec355_provocacao_rodada.py tests/test_turn_outcome_endpoints.py tests/test_spec363_rare_scenarios.py → 122 passed
worktree descartável da main + tests/test_spec390_text.py (pytest -p no:xdist) → 6 failed / 2 passed (os testes provam a mudança)
varredura temporária (removida) 13 voto/armadura × 6 sementes via TestClient → voto: "Goblin resiste à provocação de Smoke368." 3×; armadura: "está provocado por" presente, sem herói no texto
bash scripts/dev/py.sh scripts/dev/dup_helpers.py --diff main...HEAD → nenhuma função nova com nome já usado
```
