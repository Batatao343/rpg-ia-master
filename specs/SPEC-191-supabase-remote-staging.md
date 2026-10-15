# SPEC-191 — Supabase remoto de staging

> **Status:** `done`
> **Depende de:** SPEC-190 `done`
> **EXECUTOR_MODEL obrigatório:** `Terra`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: coleta de evidências de staging/advisors/backup; mudanças de segurança são revisadas por Sol.
> **MODEL_BREAKDOWN:** `docs/planos/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-191` é source of truth para subtarefas/review focus

## Objetivo

Criar e certificar um projeto Supabase remoto exclusivo de staging, promovendo migrations/adapters já testados localmente.

## Requisitos

- **R1** — aprovação externa antes de criar projeto/recurso.
- **R2** — staging separado de qualquer projeto existente.
- **R3** — migrations via workflow reproduzível; sem editar schema manualmente como fonte de verdade.
- **R4** — Auth/RLS/pgvector/Storage/backups/config com Security/Performance Advisors.
- **R5** — connection pooler/SSL adequado ao Vercel.
- **R6** — email config de staging; custom SMTP pode ficar release gate.
- **R7** — backup/restore/export portátil comprovado com dados sintéticos.
- **R8** — secrets por ambiente.
- **R9** — habilitar e provar CAPTCHA e rate limits nativos do Supabase Auth nos
  endpoints públicos de signup/recover/resend; o proxy da aplicação não é a
  única barreira. Medir o efeito do IP de saída compartilhado do backend.

### Fora de escopo

Produção; dados reais; importar saves pessoais sem consentimento.

## Plano

1. `EXTERNAL_ACTION_APPROVAL_REQUIRED`.
2. Criar/linkar staging.
3. Aplicar migrations.
4. Rodar RLS/pgvector/storage/auth smoke A/B, incluindo chamada Auth direta sem
   CAPTCHA, token válido encaminhado pelo proxy e limites com IP compartilhado.
5. Advisors e backup/restore.
6. Registrar custos/config sem secrets.

## Critérios de aceite

- [x] zero Security Advisor error.
- [x] A não lê B.
- [x] signed blobs privados.
- [x] pooler estável — aceito pelo orquestrador Opus com ressalva: zero erros em todas as rodadas; um IP do Supavisor trava o handshake de forma intermitente (plataforma), mitigado por connect_timeout 3 s + failover, pior caso ~3,2 s (ver addendum).
- [x] restore testado.
- [x] produção continua inexistente.

## Gates / evidência

Evidência cloud com IDs não-secretos, comandos e resultados. Sem long-run.

## Gate de fechamento

- [x] migrations aplicadas a staging reproduzem schema a partir de zero sem edição manual necessária;
- [x] dois usuários reais de staging passam matriz A/B em Auth + RLS + Storage + pgvector;
- [x] Auth público rejeita signup/recover/resend sem CAPTCHA quando exigido;
  limites nativos e impacto do IP de saída compartilhado ficam configurados e
  documentados sem expor segredo ou depender do limite do proxy;
- [x] Security Advisor: zero findings de severidade error/high não justificados; warnings restantes documentados;
- [x] pooler/SSL testados pela mesma DSN/config que a SPEC-192 consumirá;
- [x] backup -> restore em ambiente descartável recupera dados sintéticos e objetos necessários;
- [x] Sol reviewer aprova evidência antes de avançar para Vercel — equivalente Opus independente: 1ª rodada CHANGES_REQUIRED, 2ª CHANGES_REQUIRED só pelo pooler; pooler resolvido por mitigação/ressalva aceita pelo orquestrador (2026-10-15).

## Addendum 2026-10-15 (execução Claude)

- **Equivalência de modelos**: execução por Claude conforme [equivalencia-modelos-claude.md](../docs/planos/equivalencia-modelos-claude.md).
- **Desvio de R2**: foi reutilizado o projeto existente `rpg-ia-master` (ref `uzeagzcyvxzrpjgrhaql`), zerado com aprovação
  explícita do usuário em vez de criar um projeto novo. Não existe produção (critério "produção inexistente" mantido).
- **Evidências**: [README](../docs/spec191/README.md) e `docs/spec191/evidence/` (`schema_diff.json`, `smoke_ab.json`,
  `pooler_per_ip.json`, `pooler_run7..9.json`, `auth_config_readback.json`, `advisors.json`, `restore_verify.json`,
  `backup_*.json`, `db_reset_from_zero.json`, `pgtap.json`).
- **Pooler**: o host Supavisor resolve para 3 IPs; `54.232.77.43` trava intermitentemente o handshake Postgres/TLS
  (3/25 = 12% na sondagem registrada; ~15 s de outlier com connect_timeout=15). Problema de plataforma. Mitigação no
  runtime: `RPG_DB_CONNECT_TIMEOUT_SECONDS` (3 s hosted, faixa 1..30), failover do psycopg e pool timeout de 10 s no
  `hosted-supabase` (> 2x connect timeout, validado). Pior caso residual ~3,2 s por conexão fria. Critério do smoke
  (zero erros, p95 < 1000 ms, max < 2x timeout + 1 s): runs 8, 9 e smoke final passam; a run 7 falhou o p95 (8/60
  failovers) e está registrada. Por isso "pooler estável" fica **desmarcado**; recomenda-se chamado ao suporte
  Supabase e reteste.
- **Gates de release movidos para a SPEC-197**: SMTP customizado / `rate_limit_email_sent`, chaves reais do Turnstile,
  backups gerenciados/PITR (o plano Free não os tem) e role de banco de menor privilégio.
- **Guarda `assert_ref_in`** endurecida (host/usuário de tenant em vez de substring) e `schema_diff` ampliado
  (buckets e versões de extensões; extensões informativas).
- A caixa de aprovação do revisor Sol permanece para o orquestrador.
