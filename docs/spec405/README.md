# SPEC-405 — evidência

## Etapa 0 (11/11) — linha de base e R0
- Oráculo W2 A: `evals run` (13 suítes do eval-gates, `--seed 7`) `passed`, `hard_failures=[]`; `playtest run --all --turns 10 --seed 0` (17 perfis; assinatura = linhas `turnos= erros= violações=`). Saídas fora do repo.
- R0: `git grep -nw <SIMBOLO> -- '*.py' '*.yaml' '*.yml' '*.toml' '*.json' '*.sh' '*.ts' '*.tsx'` (excluindo docs/historico, specs, handoffs, docs/descricao_projeto, CHANGELOG.md) para os 19 símbolos do R1/R2 (CrimeCandidate, PrisonerRef, LawReceipt, _debug_scores, has_curated_art, reload_config, seed_from_proposal, search_intent, deed_event_types, seed_ids, _soul_for_quest, utc_now, run_with_context, _TRAVEL_CUES, ARMADURAS, ESCUDOS, _error_code_of, _MEMORIAL_DETAIL, CalendarDate): cada um só aparece na própria definição. Nenhum sai do plano.

## Execução (11/11) — resultado
- Etapas 1–6 commitadas uma a uma; `inspect.signature(add_npc_memory)` (archivist) ficou fora (D1).
- Etapa 3: `scripts/smoke_api.sh` offline (MockLLM) `SMOKE OK`.
- W2 B final (HEAD da branch): `evals compare` B × A `passed: true`, `regressions: []`, todos os deltas 0.0; `playtest run --all --turns 10 --seed 0`: as 16 linhas por perfil (turnos/erros/violações/rota_top) idênticas a A (só muda o run id).
- Gates: `ruff format --check` e `ruff check` limpos; `size_budget.py` rc=0; `test_size_budget.py` verde; `dup_helpers.py --diff main...HEAD` sem helper novo; `git diff --shortstat main...HEAD`: 68 inserções, 425 deleções (saldo −357).
- Testes por etapa: E1 41 passed; E2 180 passed; E3 import + 63 passed (api/error codes) + suíte do escopo sem falhas; E4 203 passed; E5 18 + 258 passed; E6 112 passed, 1 skipped.
