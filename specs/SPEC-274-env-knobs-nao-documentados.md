# SPEC-274 — Trocar variáveis de ambiente que ninguém define por constantes

> **Status:** `draft`
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Origem:** auditoria ponytail 2026-10-18 ([relatório](../docs/auditorias/ponytail-poda-2026-10-18.md))
> **Depende de:** confirmação de quem opera o staging (Vercel env / Supabase cron) de que nenhuma está setada
> **Desbloqueia:** —
> **EXECUTOR_MODEL:** `Luna` (≡ Haiku) · **REVIEW_MODEL:** — · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Das 119 variáveis lidas por `os.getenv`/`os.environ` no código de produto, algumas
aparecem em **um arquivo só**: o que as lê. Não estão em `.env.example`, nos workflows,
nos scripts de staging, nos runbooks nem nos testes. São botões que ninguém aperta:

- `RPG_CRON_MAX_RECONCILE`, `RPG_CRON_MAX_WALLET_RECOVERY` (`services/cron_internal.py`)
- `RPG_FINOPS_ALERT_HOURS`, `RPG_FINOPS_REPORT_DAYS` (`services/finops_job.py`)
- `RPG_PLAYTEST_STALE_SECONDS` (`playtest/telemetry.py`)
- `RPG_BACKUP_ROOT` (`api.py`)

## 2. Requisitos

- **R1** — Conferir no painel da Vercel (`vercel env ls`) e nos crons que nenhuma está setada.
- **R2** — Setada: documentar no `.env.example` e manter. Não setada: trocar o `getenv` pelo
  default como constante de módulo.

### Fora de escopo

`OTEL_SERVICE_NAME` (padrão OpenTelemetry), `RPG_S3_*` (perfil portable),
`RPG_LOCAL_DB_URL` (script de staging), `RPG_PLAYTEST_SAVES_DIR`/`RPG_PLAYTEST_TURN_TIMEOUT_SECONDS` (opções do harness).

## 5. Critérios de aceite

- [ ] R1 registrado no PR
- [ ] `uv run pytest` verde

## 7. Riscos & compatibilidade

Risco **baixo**: quem setar a variável em produção perde o efeito; o R1 cobre. Rollback: `git revert`.
