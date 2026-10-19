# SPEC-285 — revisão (review)

> **Veredito:** `APPROVED` (após 1 correção P1 aplicada na branch)
> **Revisor:** Opus (subagente independente) · **Data:** 2026-10-19 · **Commit revisado:** `d557c2e` (correção em `26ed770`)

## Escopo

Branch `spec-285` (`git diff main...spec-285`): `services/conflict_orchestrator.py`
(R3 proteção simétrica, R4 controle tático 2→1), `scripts/migrate_bestiary_v4.py` +
`data/cards/bestiario.json` (R5 Toque Gélido 5→3), `tests/test_spec285_lethality.py`,
`tests/test_tactical_archetypes_runtime.py`, `docs/spec285/` (arena + README) e a spec.
Fora: tuning de classe (SPEC-049), escala de encontro 5+ (SPEC-287), rótulo da causa de
morte (SPEC-288).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/conflict_orchestrator.py:1398` | R3 com dupla contagem: um companheiro (lado do herói, sem `is_player`) que usa Carta de bestiário `protecao`/`buff_defesa` num aliado já entra em `enemy_support_cards` (o nome engana: é "não-player") e é estendido pelo caminho da SPEC-283; o ramo novo do lado do jogador estendia de novo (+2 turnos). Reproduzido com `bst_postura_muralha`: duração 1→2→3. | Ramo novo pula `(actor_id, card_id)` já presentes em `enemy_support_cards`. Teste `test_companion_support_card_on_player_extends_once` (vermelho sem a correção). |
| P2-1 | P2 | `tests/test_spec285_lethality.py:238` | Guarda R5 calculava o tick do DoT só por `dano_base`; o motor (`_effect_amount`) prioriza `valor`. Uma Carta DoT futura com `valor` escaparia da guarda. | Tick usa `ct._effect_amount`, mesma precedência do motor. |

Verificado sem achado:

- **R3 não vaza para o inimigo:** o ramo novo só roda para ator fora de `sides["enemy"]`,
  com alvo em `_same_side_ids` do ator; `_extend_ally_defense` filtra tipo defensivo,
  alvo ≠ ator e alvo que já agiu. Proteção no próprio ator não muda (teste existente).
- **R4 restrito ao controle tático genérico:** a única mudança é o `duration` do ramo
  `control` de `_resolve_tactical_action`; Cartas de controle (`aplicar_condicao`,
  `taunt`, `marca`) mantêm a `duracao` autoral. O teste novo cobre a ordem
  "Místico depois do alvo" (controle na rodada seguinte) e o de arquétipo cobre a
  ordem inversa; `test_tactical_archetypes_runtime` inteiro verde.
- **R5 via gerador:** rodei `scripts/migrate_bestiary_v4.py` no worktree; `git status`
  limpo — gerador idempotente e o JSON versionado é exatamente o gerado (diff de 1 linha).
- **M1/M5 reproduzidos (3 seeds, 21–23, `combate --turns 200`, mock):** branch
  26/48 = **0,542** vs `main` (`da4f1ca`) 28/48 = 0,583; `combat.no_progress` = 0 nos 6
  runs. Direção e magnitude coerentes com o 0,532 (12 seeds) da §8.
- Metas M1–M5 justificadas na §2 (âncora pré-283 medida, régua SPEC-056 mantida).

## Correções aplicadas

- `26ed770` — P1-1 (dedupe no ramo R3 + teste de regressão) e P2-1 (tick da guarda).

## Pendências

Nenhuma nova. Follow-ups já registrados na spec: escala de encontro no nível 5+
(SPEC-287) e rótulo da causa de morte (SPEC-288).

## Comandos rodados

```text
pytest tests/test_spec285_lethality.py tests/test_tactical_archetypes_runtime.py → 32 passed
pytest -k companion sem a correção do orquestrador → 1 failed (sum(calls)==2)
scripts/migrate_bestiary_v4.py → working tree limpo (gerador idempotente)
scripts/validate_content.py → 0 erros · 0 avisos (bestiário OK)
ruff format --check / ruff check (arquivos tocados) → ok
playtest run --profile combate --turns 200 --seed 21..23 (branch e main) → 0,542 vs 0,583; no_progress 0
pytest -q -n auto (suíte completa) → exit 1 só por índice stale (spec_index, project_index ×2) e o link deste handoff (criado agora)
```
