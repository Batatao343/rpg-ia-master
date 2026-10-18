# Release checklist - staging @ a3f87e6331af

Resultado: **BLOQUEADO** (falhas: git_clean_tree, open_p0_p1)

| check | status | detalhe |
|---|---|---|
| git_clean_tree | FALHA | {"sha": "a3f87e6331af4f33b68cf66ac93683745f08bb62", "dirty_files": 7} |
| specs_176_196_done | OK | {"not_done": {}, "checked": 21} |
| ci_green | OK | {"runs": 3, "not_green": []} |
| migrations_drift | OK | {"local_count": 28, "remote_count": 28, "pending": [], "remote_only": [], "version_mismatch": []} |
| eval_locks_unchanged | OK | "eval governance valid: 11 dataset(s)" |
| budget_alert_config_present | OK | {"missing": [], "rpg_cron_finops_active": true} |
| kill_switch_store_reachable | OK | {"switches_recorded": 1, "switched_off": []} |
| health_sha | OK | {"http": 200, "deployed_sha": "a3f87e6331af4f33b68cf66ac93683745f08bb62", "expected": "a3f87e6331af4f33b68cf66ac93683745f08bb62"} |
| vercel_env_names | OK | {"missing": [], "forbidden_present": []} |
| legal_pages | OK | {"urls": ["privacy", "refund", "support", "terms"], "problems": {}} |
| open_p0_p1 | FALHA | {"open_p0_p1": ["R-02", "R-12"], "p2_awaiting_acceptance": ["R-15", "R-16", "R-17", "R-18", "R-19", "R-20", "R-21", "R-22", "R-23", "R-24", "R-25", "R-26", "R-2 |
| workflows_permissions_pins | OK | {"files": 5} |
| gitleaks_main_green | OK | {"head": "a3f87e6331af", "conclusion": "success"} |
| environments_restricted | OK | {"verified_on": "2026-10-17"} |
