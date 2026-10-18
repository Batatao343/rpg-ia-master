# SPEC-274 — Trocar variáveis de ambiente que ninguém define por constantes

> **Status:** `done` · **Revisão independente 2026-10-18:** SAFE WITH CHANGES — escopo invertido: documentar, não transformar em constante (ver §8)
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
- **R2** — *(revisado)* Manter os seis `getenv` e **documentá-los** (`.env.example` e, para os de
  cron, `docs/spec192/cron.md`, onde os irmãos `RPG_CRON_MAX_JOBS`/`RPG_CRON_MAX_DURATION_SECONDS` já
  estão). São botões operacionais de quem roda o staging: tamanho de lote dos crons de
  reconciliação/recuperação de wallet num incidente sem redeploy, janela de FinOps, raiz dos
  backups que alimenta `rpg_backup_age_seconds` (alerta em `observability/alerts/local.yml:17`),
  idade de manifesto stale do harness. Trocar por constante economiza zero linhas (cada um já é
  uma linha) e tira a válvula de escape. Só virar constante o que o operador declarar inútil.

### Fora de escopo

`OTEL_SERVICE_NAME` (padrão OpenTelemetry), `RPG_S3_*` (perfil portable),
`RPG_LOCAL_DB_URL` (script de staging), `RPG_PLAYTEST_SAVES_DIR`/`RPG_PLAYTEST_TURN_TIMEOUT_SECONDS` (opções do harness).

## 5. Critérios de aceite

- [ ] R1 registrado no PR
- [ ] `uv run pytest` verde

## 7. Riscos & compatibilidade

Risco **baixo**: quem setar a variável em produção perde o efeito; o R1 cobre. Rollback: `git revert`.

## 8. Revisão independente 2026-10-18

Revisor: Opus (Astra-style, adversarial), worktree `prune-review` @ `0784ff4`, a pedido do dono.

**Veredito: SAFE WITH CHANGES (escopo invertido).**

Verificado: as seis variáveis só aparecem no arquivo que as lê (e na auditoria). Mas:
- Os dois `RPG_CRON_MAX_*` são irmãos de `RPG_CRON_MAX_JOBS`/`RPG_CRON_MAX_DURATION_SECONDS`, documentados
  em `docs/spec192/cron.md:19-34` como botões de operação do cron serverless; reduzir lote num incidente
  sem redeploy é exatamente o uso.
- `RPG_BACKUP_ROOT` aponta o gauge `rpg_backup_age_seconds` (alerta em `observability/alerts/local.yml:17`)
  para onde os backups estão; é caminho dependente de ambiente (FS read-only na Vercel), não constante.
- Trocar `int(os.getenv(X, "50"))` por `50` economiza zero linhas.
O R2 agora manda documentar e manter.
