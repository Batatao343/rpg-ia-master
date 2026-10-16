# SPEC-222 — evidência (privacidade/LGPD)

Status: `in-progress` — código e testes locais entregues; faltam smoke em staging, texto legal
pelo titular (`handoffs/SPEC-222-legal-text.md`) e revisão Sol.

## O que mudou

| Req | Mudança |
|---|---|
| R1/R2 | 99 `print()` de produção → `observability.telemetry.log_event` (`rpg.<area>`, `safe_json`, só contagens/ids de catálogo/classe da exceção). `rpg.prose` loga hash da abertura, não o texto. Guard AST em `tests/test_no_print_in_production.py`. |
| R3 | `RETAINED_WITH_REASON` (motivo + prazo) em `infrastructure/account_lifecycle.py`; `wallet_debt_entries`/`purchase_reconciliation_state` em `FINANCIAL_TABLES`. Inventário dinâmico contra o Postgres local. |
| R4 | Migration `20261016120000_privacy_retention.sql`: `purchase_token` nullable; trigger anula o token e minimiza `google_state` ao chegar em `consumed`/`consume_failed` e proíbe repor/trocar token; backfill. Exclusão de conta minimiza as linhas Google em `begin()` (antes do tombstone). Retry de consume ignora linhas sem token. |
| R5 | Export com colunas explícitas (`EXPORT_COLUMNS`, sem leases/fencing/hashes/payload de jobs/vetores/token), inclui Google/dívida/reconciliação e `asset_downloads` com URL assinada de 300 s (`format_version: 2`). |
| R6 | `commit_delete` captura as chaves dos assets e enfileira `purge_blobs` na mesma transação; handler em `workers/blob_purge_jobs.py` (registrado no worker/cron de jobs) apaga as chaves + varre o prefixo da campanha; idempotente, falha → retry. |
| R7 | `services/retention.py` no cron `/internal/cron/operations`: operações terminais > 90 d (sem turns/uso/reserva), jobs terminais > 30 d, `usage_events` > 13 meses, `finops_evaluations` > 180 d, tombstones compactados após 30 d e apagados após 5 anos. |
| R8 | Fontes self-hosted (`web/public/fonts`, OFL) e `web/src/fonts.css`; `index.html`, páginas legais e CSP sem Google Fonts. `docs/spec198/data-safety.md` alinhado ao código (OpenAI imagens/STT, token, TTL, idade). Política: handoff. |
| R9 | `AuthScreen`: aceite com links Termos/Privacidade, aviso de IA, checkbox obrigatório "18 anos ou mais"; links legais na tela de acesso. |
| R10 | `docs/spec222/retencao.md` gerado do código (`scripts/gen_retention_doc.py`) e validado por teste. |

## Decisões (defaults da spec §8)

D-A URLs assinadas 300 s (ZIP fica p/ spec futura) · D-B 13 meses/5 anos · D-C self-host · D-D 18 anos.

## Testes

- Vermelhos no HEAD: `test_no_print_in_production` (99 ocorrências), `test_turn_logs_no_game_content`
  (stdout com "Criando personagem: Sentinela-7b2a"), inventário (3 tabelas fora das listas),
  `test_game_delete_purges_blobs` (sem job), `consent.spec.ts` (sem aceite).
- Novos: `tests/test_no_print_in_production.py`, `tests/test_turn_logs_no_game_content.py`,
  `tests/test_owner_tables_inventory.py`, `tests/test_spec222_privacy_local.py`,
  `tests/test_game_delete_purges_blobs.py`, `tests/test_spec222_retention_local.py`,
  `tests/test_spec222_transparency.py`, `web/e2e/consent.spec.ts`.
- Postgres local (`-m infra_local`, rollback, sem dados residuais): SPEC-222 + SPEC-190/194/195/196 verdes.

## Limites / pendências

- Smoke em staging (§6) não executado: requer aplicar a migration no staging e deploy.
- Política (`web/legal/privacy-policy.md`) não editada por agente; `<...>` de controlador/SMTP/domínio seguem com o titular.
- A idade é autodeclarada no cliente; o backend não registra o aceite (fora do escopo da spec).
- Logs JSON de `rpg.*` em nível `debug` não aparecem com a configuração padrão; avisos/erros sim.
