# Release checklist - staging @ b9b0c753229d

Resultado: **BLOQUEADO** (falhas: git_clean_tree, legal_pages, open_p0_p1, environments_restricted)

| check | status | detalhe |
|---|---|---|
| git_clean_tree | FALHA | {"sha": "b9b0c753229d238399c056994c3113b045917d24", "dirty_files": 1} |
| specs_176_196_done | OK | {"not_done": {}, "checked": 21} |
| ci_green | PULADO | "gh unavailable or unauthenticated" |
| migrations_drift | OK | {"local_count": 28, "remote_count": 28, "pending": [], "remote_only": [], "version_mismatch": []} |
| eval_locks_unchanged | OK | "eval governance valid: 10 dataset(s)" |
| budget_alert_config_present | OK | {"missing": [], "rpg_cron_finops_active": true} |
| kill_switch_store_reachable | OK | {"switches_recorded": 1, "switched_off": []} |
| health_sha | OK | {"http": 200, "deployed_sha": "b9b0c753229d238399c056994c3113b045917d24", "expected": "b9b0c753229d238399c056994c3113b045917d24"} |
| vercel_env_names | OK | {"missing": [], "forbidden_present": []} |
| legal_pages | FALHA | "no privacy/terms/support/refund URLs configured (--legal-url name=url)" |
| open_p0_p1 | FALHA | {"open_p0_p1": ["R-01", "R-02", "R-03", "R-05", "R-06", "R-07", "R-09", "R-10", "R-11", "R-12", "R-13", "R-14"], "p2_awaiting_acceptance": ["R-15", "R-16", "R-1 |
| workflows_permissions_pins | OK | {"files": 5} |
| gitleaks_main_green | PULADO | "gh unavailable or unauthenticated" |
| environments_restricted | FALHA | "verificação manual pendente (ENVIRONMENTS_VERIFIED: AAAA-MM-DD)" |
