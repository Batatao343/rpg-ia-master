# Release checklist - staging @ be631ab60cc0

Resultado: **BLOQUEADO** (falhas: ci_green, open_p0_p1)

| check | status | detalhe |
|---|---|---|
| git_clean_tree | OK | {"sha": "be631ab60cc0b7ac78159dc80e3787b2f6b90c3d", "dirty_files": 0} |
| specs_176_196_done | OK | {"not_done": {}, "checked": 21} |
| ci_green | FALHA | {"runs": 3, "not_green": [{"workflow": "audit-local", "status": "in_progress", "conclusion": ""}, {"workflow": "validate", "status": "in_progress", "conclusion" |
| migrations_drift | OK | {"local_count": 22, "remote_count": 22, "pending": [], "remote_only": [], "version_mismatch": []} |
| eval_locks_unchanged | OK | "eval governance valid: 6 dataset(s)" |
| budget_alert_config_present | OK | {"missing": [], "rpg_cron_finops_active": true} |
| kill_switch_store_reachable | OK | {"switches_recorded": 1, "switched_off": []} |
| health_sha | OK | {"http": 200, "deployed_sha": "be631ab60cc0b7ac78159dc80e3787b2f6b90c3d", "expected": "be631ab60cc0b7ac78159dc80e3787b2f6b90c3d"} |
| vercel_env_names | OK | {"missing": [], "forbidden_present": []} |
| legal_pages | OK | {"urls": ["privacy", "refund", "support", "terms"], "problems": {}} |
| open_p0_p1 | FALHA | {"open_p0_p1": ["R-01", "R-02", "R-03", "R-04", "R-05", "R-06", "R-07", "R-09", "R-10", "R-11", "R-12", "R-13", "R-14"], "p2_awaiting_acceptance": ["R-15", "R-1 |
