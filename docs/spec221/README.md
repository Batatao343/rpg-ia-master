# SPEC-221 — evidencia

Mudancas: `/metrics` com Bearer (404 sem token), cache SQL 15 s, gauge `rpg_metrics_db_error`, rate limit 12/min;
`Cache-Control: no-store` em /game,/account,/auth; HSTS (so com RPG_COOKIE_SECURE=1, sem preload);
CSP `form-action 'self'`; `services/body_limit.py` (413 por Content-Length e por contagem; ASGI puro, SSE intacto);
`safe_attachment_filename` no export da cronica (SPEC-235 preservada).

Testes: `tests/test_surfaces_221.py` (22 casos). Env nova `RPG_METRICS_TOKEN` opcional: ausente = 404 em perfil DB, sem
afetar boot. Decisoes: D-A sem preload, D-B unsafe-inline mantido, D-C 404.
Revisao Sol: rate limit de /metrics agora isenta o scraper autenticado (scrape de 5 s caia em 429);
webhook Stripe com margem no middleware (320 KiB) p/ o handler aplicar o proprio teto; teste de pior caso
legitimo de /game/new (<64 KiB) e de STT 8 MiB/Stripe nao cortados.
Smoke LOCAL (substitui staging): `evidence/local_smoke.txt` (+ script `evidence/local_smoke.py`) — perfil
`local` contra Supabase local + Prometheus v3.13.2 com bearer: `up==1`, `min_over_time(up[40s])==1`.
Limites: staging remoto nao exercitado; rate limit de /metrics por processo (sem SPEC-219).
