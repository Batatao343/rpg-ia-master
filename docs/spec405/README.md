# SPEC-405 — evidência

## Etapa 0 (11/11) — linha de base e R0
- Oráculo W2 A: `evals run` (13 suítes do eval-gates, `--seed 7`) `passed`, `hard_failures=[]`; `playtest run --all --turns 10 --seed 0` (17 perfis; assinatura = linhas `turnos= erros= violações=`). Saídas fora do repo.
- R0: `git grep -nw <SIMBOLO> -- '*.py' '*.yaml' '*.yml' '*.toml' '*.json' '*.sh' '*.ts' '*.tsx'` (excluindo docs/historico, specs, handoffs, docs/descricao_projeto, CHANGELOG.md) para os 19 símbolos do R1/R2 (CrimeCandidate, PrisonerRef, LawReceipt, _debug_scores, has_curated_art, reload_config, seed_from_proposal, search_intent, deed_event_types, seed_ids, _soul_for_quest, utc_now, run_with_context, _TRAVEL_CUES, ARMADURAS, ESCUDOS, _error_code_of, _MEMORIAL_DETAIL, CalendarDate): cada um só aparece na própria definição. Nenhum sai do plano.
