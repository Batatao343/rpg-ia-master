# SPEC-376 — log de execução

## W1 (04/11, base `1b4dca5c`)
Fontes: (1) branches vivas `spec-370/372/373/374` (+ `bst-*`, `spec-359`, `spec-350c`); (2) status dos worktrees;
(3) `git log --since=2.days main`.
- Interseção real: só `docs/guias/AUTORIA.md` com `spec-374` (diff à frente da main) -> **Etapa A3 espera**.
- O worktree `C:/Users/guilh/AppData/Local/Temp/wtidx5` (branch `idx5`, 3 semanas) está com 2273 arquivos apagados
  (worktree quebrado); ele só gera falso positivo em todas as etapas. Ignorado; candidato a `git worktree remove` (dono).
- Fonte 3: arquivos tocados por commits já pousados na `main` (SPEC-361/377/379/371/362/350), todos `done`/landed
  e sem sessão com mudança pendente; liberados.
- Branches paradas sem relação: `spec-349-pre-sync`, `spec-350-fix`, `dependabot/*`, `bst-*` (arquivar).

## Etapa A (04/11)
- A1 `gen_cards_v4.py` e A2 `gen_classes_v2.py` removidos (D1=a, veredito em `deriva.md`); A3 (AUTORIA.md) **adiada**: `spec-374` trava o arquivo (W1).
- A4 (`_meta` dos JSON de classe) **cancelada** (D2: só se a W1 liberar): a spec manda esperar a SPEC-367 (approved, commita na `main`) e a SPEC-369 (draft, balanço de Cartas edita `data/cards/*`); registrado, trivial de refazer depois.
- A5 `migrate_bestiary_v4.py` agora exige `--write` (D3; destrutivo provado).
- B1: 3 scripts removidos (jev_primary_measure, spec236_daily_cap, spec279_usage_survives_delete); R3 limpo (so `ruff-baseline.toml` e docstring dos proprios). R14: `ruff_baseline.py` regerado reescrevia tambem `agents/archivist.py` e `services/prologue.py` (deriva alheia ja presente na `main`), entao a baseline foi editada a mao (so as linhas dos scripts apagados). `ruff_baseline.py --check` continua "stale" por essa deriva anterior (nao causada pela spec). Candidatos de cascata (R15): `jev_shadow_measure`, `projection_measure`.

## C0 — linha de base W2 (A), 04/11, base `90becbce` = HEAD do spec-376 apos A/B
- evals (12 suites do eval-gates, `--seed 7`): `eval-20261104T035202Z-90becbce` passed, hard_failures=[] (saida fora do repo).
- playtest `--all --turns 10 --seed 0`: run `20261104-005214-332601`; segunda rodada identica (assinatura por perfil: turnos, erros, violacoes, mortes, nivel, ouro, rotas, replans) -> deterministico.
- R23 matriz de import (8 ordens, subprocess novo, `RPG_FORCE_MOCK=1`): todas as 6 identidades `True` ANTES.

## Etapa C (04/11) — W2 B apos cada etapa
- C1 `tick_conditions` (+ teste proprio e `SURVIVING_FUNCTIONS`, D7), C2 `escort_stop`/`region_pressure`/`faction_relation`/`relation_label` (D6), C3 `_overlay_path`/`_npc_db_path`/`_infer_tier_from_name`, C4 stubs `ImportError` (`bestiary`, `npc`, `world_simulator`).
- Cada etapa: `evals run` (12 suites, seed 7) vs A: `passed`, `regressions: []`, deltas 0; playtest `--all --turns 10 --seed 0`: assinatura por perfil identica a A.
- R23: matriz de 8 ordens de import, 6 identidades `True` antes (C0) e depois (C4).
- C5 nao executada (D5: manter `resolve_card`/`valid_effect_kind`). C3: a nota do tier virou comentario curto na linha porque `generate_new_enemy`/`generate_new_npc` estavam no teto do size budget.
- Pendente: A3 (AUTORIA.md + adendo SPEC-273) espera a SPEC-374 (branch viva); A4 cancelada (D2).
- Adendo SPEC-273 deve ser feito junto da A3 (R8).
