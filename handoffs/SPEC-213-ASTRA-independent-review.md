# SPEC-213 — Parecer Astra independente (16/10/2026)

**Veredito:** APPROVED_WITH_FIXES (correções aplicadas no mesmo ciclo; spec `done`, rollout `inline`).

## Achados e correções
1. **Critério §5 `infra_local` não atendido** (perfis com banco ficavam `inline`) → implementados outbox
   `project_archive` na transação do commit, execução do próprio job pela API após responder
   (`lease_key` + `JobWorker.run_leased`), apply com CAS + `require_job_fence` (`workers/projection_jobs.py`),
   espera/fallback do próximo turno dentro da cerca, cancelamento por época no restore e operação
   `archive_projection` para o uso de LLM (migration `20261016121500`).
2. **Linha de base perdida:** plano falho aguardando retry era sobrescrito pelo do turno seguinte → planos unidos.
3. **Duplicação de memória no timeout (R8):** executor não interrompível já gravara FAISS → timeout não reexecuta.
4. **R4 frágil no restore:** `carry_over_restore` herda a versão canônica viva e cancela projeção da época antiga.

## Verificado sem achado
D5 (guard/`validate_narrative` da prosa síncronos); R7 (revalidação contra evidência canônica atual);
corrida de dois turnos e dois clientes (lock legacy / lease+CAS em DB); SSE cortado após `done`; troca de
jogo; restart com pendente; save/reload; leitura sem lock (risco pré-existente em outros endpoints, aceito).

## Evidência
Suíte completa exit 0; `tests/test_projection_db_local.py` (8 + e2e HTTP perfil `local`); smoke browser
Chromium 1440 (selo "atualizando…" com narração visível); smoke real 8 turnos DeepSeek, US$ 0,032 est.
Detalhes: `docs/spec213/README.md`.
