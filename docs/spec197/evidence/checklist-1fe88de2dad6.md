# Release checklist - staging @ 1fe88de2dad6

Resultado: **BLOQUEADO** (falhas: git_clean_tree, legal_pages, open_p0_p1)

| check | status | detalhe |
|---|---|---|
| git_clean_tree | FALHA | {"sha": "1fe88de2dad6b766ef4067314f4cde4a86945612", "dirty_files": 19} |
| specs_176_196_done | OK | {"not_done": {}, "checked": 21} |
| ci_green | PULADO | "gh unavailable or unauthenticated" |
| migrations_drift | OK | {"local_count": 22, "remote_count": 22, "pending": [], "remote_only": [], "version_mismatch": []} |
| eval_locks_unchanged | OK | "eval governance valid: 6 dataset(s)" |
| budget_alert_config_present | OK | {"missing": []} |
| kill_switch_store_reachable | OK | {"switches_recorded": 1, "switched_off": []} |
| health_sha | OK | {"http": 200, "deployed_sha": "1fe88de", "expected": "1fe88de2dad6b766ef4067314f4cde4a86945612"} |
| vercel_env_names | OK | {"missing": [], "forbidden_present": []} |
| legal_pages | FALHA | "no privacy/terms/support/refund URLs configured (--legal-url name=url)" |
| open_p0_p1 | FALHA | {"open_p0_p1": ["R-01", "R-02", "R-03", "R-04", "R-05", "R-06", "R-07", "R-09", "R-10", "R-11", "R-12", "R-13", "R-14"], "p2_awaiting_acceptance": ["R-15", "R-1 |
