# Release checklist - staging @ f2516b20976a

Resultado: **BLOQUEADO** (falhas: ci_green)

| check | status | detalhe |
|---|---|---|
| git_clean_tree | OK | {"sha": "f2516b20976a4205b92056349dc6b3110a8de61c", "dirty_files": 0} |
| specs_176_196_done | OK | {"not_done": {}, "checked": 21} |
| ci_green | FALHA | "no CI runs for this sha (push + wait required)" |
| migrations_drift | OK | {"local_count": 28, "remote_count": 28, "pending": [], "remote_only": [], "version_mismatch": []} |
| eval_locks_unchanged | OK | "eval governance valid: 11 dataset(s)" |
| budget_alert_config_present | OK | {"missing": [], "rpg_cron_finops_active": true} |
| kill_switch_store_reachable | OK | {"switches_recorded": 1, "switched_off": []} |
| health_sha | OK | {"http": 200, "deployed_sha": "f2516b20976a4205b92056349dc6b3110a8de61c", "expected": "f2516b20976a4205b92056349dc6b3110a8de61c"} |
| vercel_env_names | OK | {"missing": [], "forbidden_present": []} |
| legal_pages | OK | {"urls": ["privacy", "refund", "support", "terms"], "problems": {}} |
| open_p0_p1 | OK | {"open_p0_p1": [], "p2_awaiting_acceptance": ["R-15", "R-16", "R-17", "R-18", "R-19", "R-20", "R-21", "R-22", "R-23", "R-24", "R-25", "R-26", "R-27", "R-28"], " |
| workflows_permissions_pins | OK | {"files": 5} |
| gitleaks_main_green | OK | {"head": "a3f87e6331af", "conclusion": "success"} |
| environments_restricted | OK | {"verified_on": "2026-10-17"} |
