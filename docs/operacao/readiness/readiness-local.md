# Valoria — prontidão local

- Resultado: **READY**
- Commit: `eccb65d115a13f143d37b26801236e5c23448253`
- Gerado: 2026-08-20T13:19:43.819103+00:00

| Gate | Escopo | Estado | Evidência |
|---|---|---|---|
| G0 | suíte offline | passed | 1564 passed, 16 skipped, 14 deselected |
| G1 | integração local | passed | 13 passed; pgTAP 14/14 |
| G2 | segurança local | passed | 5 passed; RLS Auth Storage A/B |
| G3 | caos local | passed | 1 test; 5/5 cenários convergiram |
| G4 | carga multiworker | passed | 12 commits; dedupe 1 row; commit p95 32.257 ms; jobs 12 |
| G5 | soak de 1.000 turnos | passed | 1000/1000; 0 erros; 0 violações; 38 transações; runs 20260820-100653-360446..100749-180819 |
| G6 | backup/restore | passed | RPO 0; RTO 36.19 s; DB Auth Storage e login verificados |
| G7 | browser/build/lint/audits | passed | Vite 457; browser desktop/390 2x; 0 vulnerabilidades; 0 secrets; Prometheus Grafana Collector Tempo e 7 alertas verdes |
