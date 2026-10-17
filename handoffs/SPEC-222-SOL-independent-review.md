# SPEC-222 — revisão Sol independente

- **Revisor:** Sol (≡ Opus, contexto separado; não escreveu a implementação)
- **Data:** 2026-10-17 · **Base:** `spec-222` rebaseado sobre `main` (`4c66dc8`), commit original `bfa1ac1`
- **Veredito:** **APPROVED com correções aplicadas** (abaixo). Status da spec segue `in-progress`
  só pelo que depende de fora do repo: migration + smoke em staging e texto legal do titular.

## Rebase

Conflitos em `web/src/styles.css` (CSS da SPEC-205/208 × consentimento) e `workers/run_worker.py`
(handler `project_archive` da SPEC-213 × `purge_blobs`): mantidos os dois lados. Após o rebase o
teste AST (R1) acusou 6 `print` novos vindos de `main` — corrigidos (ver D4).

## Achados e correções

| # | Severidade | Achado | Correção |
|---|---|---|---|
| D1 | Alta | A idade mínima (D-D, R9) só existia na UI: `POST /auth/signup` aceitava cadastro sem a declaração 18+. | `SignupRequest.age_confirmed: Literal[True]` → 422 antes de qualquer chamada ao provedor de identidade; `web/src/api.ts` envia `age_confirmed: true` (o formulário só submete com a caixa marcada); `scripts/staging/e2e_session.py` atualizado. Teste `test_signup_requires_server_side_age_confirmation` (ausente/false/valor não booleano → 422, identidade não chamada); `consent.spec.ts` asserta o payload. |
| D2 | Média | `purge_blobs` não era idempotente no `FileBlobStore`: `delete` de chave ausente devolve `False`, o job levantava `blob_purge_incomplete` e ia a `dead` após 10 tentativas (retry após purge parcial ou asset sem upload). | `_deleted_or_absent`: `False` seguido de `FileNotFoundError` no `open` conta como ausente; qualquer outro erro mantém o retry (Supabase mapeia 5xx para `NotFound`, então não é tratado como ausente). Teste com `FileBlobStore` real. |
| D3 | Média | Chaves com `..` dentro do prefixo da campanha passavam no `startswith` e o `FileBlobStore` resolve `..` (podia sair do prefixo de outra campanha do mesmo owner). | `_in_prefix` rejeita segmento `..` e `\`, aplicado ao payload, ao enfileiramento e à varredura de `storage.objects`. Teste dedicado. |
| D4 | Baixa | 6 `print` novos de `main` (SPEC-209–215): `agents/npc.py` imprimia `{exc}` (mensagem crua, pode conter conteúdo), 4 em `api.py` e 1 em `services/projections.py`. | Migrados para `log_event` (só `type(exc).__name__` e `where` de catálogo). |

## Verificado sem defeito

- **Retenção (R7):** nenhuma tabela financeira é alvo; `operations` referenciadas por `turns`/`usage_events`/`wallet_reservations` nunca são apagadas (os FKs `turns`/`usage_events → operations` são `ON DELETE CASCADE`, conferido em `pg_constraint`); `games.active_operation_id` é `SET NULL`; `wallet_settled_usage` guarda snapshot, então expirar `usage_events` não apaga extrato; jobs `queued`/`running` e operações `running` ficam.
- **Purge de campanha (R6):** chaves capturadas antes do `delete` (cascade em `assets`), job enfileirado na mesma transação com `game_id` nulo (não cai junto), dedupe `game:<id>`, escopo `users/<owner>/games/<game>/` com owner vindo do principal autenticado; o cron `/internal/cron/jobs` usa `build_handlers()` que inclui `purge_blobs`.
- **Export (R5):** colunas explícitas comparadas com `information_schema` — omitidos só hashes, leases, fences, payload/result de jobs, vetores, `purchase_token`, sessões/URLs Stripe e `actor_id` de staff; URLs assinadas só para `ready` dentro de `users/<owner>/`.
- **Google (R4):** trigger anula token e minimiza `google_state` ao entrar em estado terminal, impede restaurar/substituir token e transições a partir de terminal; `unconsumed()` ignora linhas sem token; `_public` não expõe token; backfill suspende o fence só para o UPDATE.
- **Fontes/CSP (R8):** sem `fonts.googleapis/gstatic` em `web/index.html`, `web/src`, `legal.mjs` nem na CSP; restam só stubs de rota em specs e2e antigos (inofensivos).

## Governança de eval

`uv run --frozen python -m evals.core.governance check --root .` → `eval governance valid: 10 dataset(s)`.
A edição da jornada F01 em `web/e2e/critical-journeys.spec.ts` (só o passo de marcar a idade) não
está sob o lock (`critical-journeys.yaml`/`manifest.lock.json` intocados); não exige relock nem
handoff de eval-authoring.

## Evidência

- `uv run --frozen pytest -q -p no:warnings --ignore=tests/test_project_index.py` → exit 0.
- `-m infra_local` (Postgres local 127.0.0.1:55322, migrations até `20261016121500`): `test_spec222_privacy_local`, `test_spec222_retention_local`, `test_owner_tables_inventory`, `test_game_delete_purges_blobs`, `test_account_lifecycle_local`, `test_spec194_google_play`, `test_spec195_reconciliation` → 15 passed, 0 skipped.
- `ruff check` (arquivos alterados vs `main`) → limpo. `npm test` → 116 pass. `npm run build` → ok.
- Playwright (config temporária na porta 4201, `--workers=1`, apagada depois): `consent`, `account-lifecycle`, `critical-journeys`, `account`, `checkout` → 54 passed; as 2 falhas eram `toHaveURL("…:4173/")` fixo no spec, que passam (8/8) com cópia temporária ajustada à porta.

## Pendências (fora do repo / follow-ups)

1. **Staging:** aplicar `supabase/migrations/20261016120000_privacy_retention.sql` e rodar o smoke §6 (sentinela nos logs Vercel, token nulo após consume, objeto some após delete de campanha, export com novas tabelas). O código é seguro antes da migration (minimização condicionada a `to_regproc`), mas R4 só vale depois dela.
2. **Texto legal:** §5 da política e `<...>` do controlador/SMTP/domínio pelo titular (`handoffs/SPEC-222-legal-text.md`).
3. **Follow-up (risco residual):** com `disable_signup=False` no GoTrue, um cadastro direto em `/auth/v1/signup` com a anon key contorna o gate 18+ da API. Avaliar desligar signup público no Auth e cadastrar só via proxy, ou gravar a declaração em `user_metadata` e checar no primeiro uso (SPEC-218/220).
4. **Follow-up:** a retenção financeira é declarada "5 anos", mas não há expurgo automático das tabelas de carteira após o prazo; o texto deveria dizer "no mínimo 5 anos" ou ganhar job de expurgo em spec própria. Jobs `purge_blobs` `dead` somem após 30 d junto com a lista de chaves; a exclusão de conta ainda varre o prefixo inteiro do owner.
