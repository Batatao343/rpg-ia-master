# SPEC-222 — Privacidade/LGPD: logs sem conteúdo de jogo, exclusão/export completos e transparência

> **Status:** `in-progress` (19/10: **delete de campanha com arte verde no staging** — retrato real gerado pelo fluxo quote+confirmação (OpenAI, US$ 0,011), `DELETE /game/save` enfileirou `purge_blobs` e o próximo `rpg-cron-jobs` agendado apagou os 2 objetos do bucket (≤ 1 ciclo, sem disparo manual; evidência `docs/staging-wave-2026-10-17/evidence/spec222_art_purge.json`). Seguem pendentes só a compra fake/teste (`purchase_token IS NULL`: exige chave Stripe test, inexistente; Play fake proibido em hosted) e o domínio de produção. 18/10: SMTP próprio no staging (Resend, modo teste) e páginas legais finais publicadas; seguem pendentes compra fake/teste com `purchase_token IS NULL`, delete de campanha com arte (o staging agora tem `OPENAI_API_KEY`, mas a conta OpenAI está sem créditos — 429 `insufficient_quota`) e o domínio de produção. 17/10: migration `20261016120000` aplicada no staging; smoke parcial verde — sentinela ausente dos logs da função, `/account/export` com as tabelas novas e sem `purchase_token`. Faltam: compra fake/teste (Play fake é proibido em hosted) e delete de campanha com arte (sem gerador pago no staging), e o texto legal da política pelo titular)
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-17
> **Depende de:** nenhuma · evolui SPEC-190/194/195 `done`; complementa SPEC-197 R3/R-10 (ordem final 2026-10-15)
> **Desbloqueia:** gate legal da SPEC-197; Data Safety da SPEC-198 (ordem final 2026-10-15)
> **Origem:** auditoria de segurança 2026-10-15 — achados PRIV-01 (+PRIV-09), PRIV-02, PRIV-03, PRIV-04, PRIV-05 (parcial), PRIV-06, PRIV-07
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `true` — toca exclusão de dados e declarações legais
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

A política de privacidade (`docs/spec197/legal/privacy-policy.md`) e o Data Safety (`docs/spec198/data-safety.md`) declaram "logs técnicos sem conteúdo de jogo", exclusão de dados privados com retenção só do extrato financeiro por identificador opaco, e listam os operadores. O código diverge em cinco pontos verificados:

1. **`print()` com conteúdo de jogo no stdout** (logs da Vercel): `agents/archivist.py:123` imprime os fatos extraídos de cada turno (texto do jogador/narração), `api.py:2679` o nome do personagem, `agents/librarian.py:42,46` a consulta do jogador; mais ~20 `print` em `agents/*` com exceções cruas. Só os logs `rpg.*` passam por `safe_json`/`redact`.
2. **Exclusão/export incompletos**: `infrastructure/account_lifecycle.py:8-13` lista `PRIVATE_TABLES`/`FINANCIAL_TABLES` fixas; `app.google_play_purchases` (com `purchase_token` **cru**, `order_id`, `google_state`), `app.wallet_debt_entries` e `app.purchase_reconciliation_state` — criadas depois (SPEC-194/195) — não são apagadas nem exportadas, e a retenção não está declarada.
3. **Apagar campanha não apaga imagens**: `DELETE /game/save/{id}` em perfil DB (`infrastructure/postgres_turns.py:345-374`) apaga `app.games` (cascade em `assets`), mas nenhum `blob_store.delete` roda — objetos `users/{owner}/games/{game}/…` ficam órfãos até a exclusão da conta.
4. **Terceiros não declarados**: o provedor de imagem é OpenAI (`infrastructure/openai_images.py`, recebe `appearance` e PNG do herói) e está como `<...>`; `web/index.html:9-12` carrega Google Fonts (IP/UA de todo visitante ao Google), ausente da política.
5. **Consentimento**: as páginas `/privacidade/` e `/termos/` já existem (geradas por `web/scripts/legal.mjs`, linkadas em `App.tsx:847-848`), mas o signup não tem texto de aceite, aviso de processamento por IA/terceiros nem idade mínima (`<18/13?>` indefinido — decisão do dono, R-10).

Fatos adicionais: sem TTL para `usage_events`, `operations`/`jobs` terminais, `account_deletions`, `finops_evaluations` (PRIV-07); export é `select *` síncrono com colunas internas e sem conteúdo de blobs (PRIV-06); `services/prose_guard.py:260` loga abertura da narração em claro (PRIV-09).

Objetivo: o código passa a cumprir o que a política diz — e a política passa a dizer o que o código faz — com testes que impedem regressão (nenhuma tabela nova com `owner_id` fora das listas; nenhum `print` com conteúdo de jogo).

## 2. Requisitos

- **R1** — Zero `print()` em código de produção (`agents/`, `services/`, `infrastructure/`, `api.py`, `persistence.py`, `rag.py`, `llm_setup.py`, `character_creator.py`): substituídos por `logging.getLogger("rpg.<area>")` com `safe_json` e apenas contagens/ids pseudonimizados/`type(exc).__name__`. Teste AST (`tests/test_no_print_in_production.py`) falha se um `print(` aparecer fora de `scripts/`, `playtest/`, `game_engine.py` (CLI) e `__main__`.
- **R2** — Teste de "vazamento de conteúdo": um turno MockLLM com `input_text="SENTINELA-9f3c"` e nome de personagem `Sentinela-7b2a` não produz nenhuma linha em stdout/stderr/caplog contendo as sentinelas (inclui `rpg.prose`, PRIV-09).
- **R3** — Inventário dinâmico de tabelas por owner: `tests/test_owner_tables_inventory.py` (Postgres local) lista toda tabela `app.*` com coluna `owner_id` e exige que cada uma esteja em `PRIVATE_TABLES ∪ FINANCIAL_TABLES ∪ RETAINED_WITH_REASON` (dicionário `{tabela: motivo legal}` em `account_lifecycle.py`). Hoje falha com `google_play_purchases`, `wallet_debt_entries`, `purchase_reconciliation_state`.
- **R4** — `google_play_purchases`: após `state='consumed'` (ou terminal `consume_failed`), `purchase_token` é substituído por `NULL` (migration: coluna passa a `nullable`; `token_sha256` permanece para idempotência) e `google_state` reduzido ao subconjunto financeiro (`orderId`, `purchaseState`, `purchaseTimeMillis`, `consumptionState`, `purchaseType`); no `finish()` da exclusão, as linhas do owner têm `purchase_token=NULL` e `google_state` minimizado. `wallet_debt_entries`/`purchase_reconciliation_state` entram em `FINANCIAL_TABLES` (retidas, exportadas).
- **R5** — `export()` devolve também as três tabelas (sem `purchase_token`), com listas explícitas de colunas por tabela (fim do `select *`; colunas internas `lease_token`, `request_sha256`, `payload` de jobs excluídas) e, para `assets` com `status='ready'`, URLs assinadas de 300 s (ponto D-A: ZIP em job fica fora).
- **R6** — `DELETE /game/save/{id}` em perfil DB: antes do `delete from app.games`, selecionar `object_key` de `app.assets where game_id=%s and owner_id=%s`; marcar `delete_pending` e enfileirar job `purge_blobs` (fila existente) que chama `blob_store.delete` e só então remove a linha; idempotente; o cron `/internal/cron/jobs` drena. Teste Postgres local + blob store fake: após delete + drenagem, 0 objetos no prefixo.
- **R7** — TTL/purge no cron existente (`/internal/cron/operations`): `operations` terminais > 90 d, `jobs` terminais > 30 d, `usage_events` > 13 meses (prazo fiscal/contábil declarado — D-B), `finops_evaluations` > 180 d, `cron_requests` já 2 d; `account_deletions` com `status='deleted'` reduzida a `(owner_id, deleted_at)` após 30 d e mantida pelo prazo legal declarado (D-B).
- **R8** — Política e Data Safety: preencher OpenAI (imagens + STT fallback), Groq (STT primário, LLM), DeepSeek/outros LLM de `ROUTES`, Jina (embeddings), Cloudflare Turnstile, Supabase (Auth/DB/Storage), Vercel (hospedagem/IP), Stripe, Google Play, SMTP; **Google Fonts**: self-hostear as 2 famílias em `web/public/fonts` e remover `preconnect`/`<link>` (preferido, elimina o terceiro — D-C) ou declarar. Seção §5 lista as tabelas retidas e prazos de R4/R7. Teste `web/tests/legal.test.mjs`: nenhum `<...>` restante; `scripts/release/checklist.py --legal-url` já exige ausência de rascunho.
- **R9** — UI de consentimento: no `AuthScreen` (signup) texto "Ao criar conta você concorda com os Termos e a Política de Privacidade; texto e voz enviados ao jogo são processados por provedores de IA listados na política" com links; checkbox de idade mínima conforme D-D; `AccountScreen` já expõe export/delete (confirmar visível). Teste Playwright (`web/e2e`) assertando links + checkbox obrigatório.
- **R10** — Compatibilidade: `RETAINED_WITH_REASON` e os prazos são a fonte da seção §5 da política (gerada/validada por teste que compara nomes de tabelas).

### Fora de escopo

- Cobrança/`usage_events` em si (SPEC-182); backups gerenciados (SPEC-197 gate); DPO/registro de operações (processo, não código).
- Pseudônimo com chave pública (PRIV-08) — requisito de config em SPEC-218.

## 3. Design técnico

- **Arquivos alterados:** `agents/*.py`, `api.py`, `services/prose_guard.py` (R1/R2); `infrastructure/account_lifecycle.py` (R3–R5: `RETAINED_WITH_REASON`, `EXPORT_COLUMNS`, minimização Google); `infrastructure/google_play_payments.py` (R4 no consume); `infrastructure/postgres_turns.py` + `infrastructure/postgres_jobs.py` (R6 job `purge_blobs`); `services/cron_internal.py` (R7); `supabase/migrations/2026MMDD_privacy_retention.sql` (R4 nullable + R7 índices por data); `docs/spec197/legal/privacy-policy.md`, `docs/spec198/data-safety.md` (R8); `web/index.html`, `web/public/fonts/*`, `web/src/styles.css` (R8 fontes); `web/src/components/AuthScreen.tsx` (R9).
- **Arquivos novos:** `tests/test_no_print_in_production.py`, `tests/test_turn_logs_no_game_content.py`, `tests/test_owner_tables_inventory.py` (marker Postgres), `tests/test_game_delete_purges_blobs.py`, `tests/test_account_export_columns.py`, `web/e2e/consent.spec.ts`.
- **Schemas:** `RETAINED_WITH_REASON: dict[str, str] = {"google_play_purchases": "obrigação fiscal/antifraude — token anulado", "wallet_debt_entries": "...", "purchase_reconciliation_state": "...", "account_deletions": "prova de exclusão"}`; `EXPORT_COLUMNS: dict[str, tuple[str, ...]]`.

## 4. Plano passo a passo

### Etapa 0 — Reprodução (vermelhos no HEAD)
1. `test_turn_logs_no_game_content` (capfd: sentinela aparece hoje via `print` do archivist); `test_owner_tables_inventory` (3 tabelas fora das listas); `test_game_delete_purges_blobs` (objeto permanece); `test_no_print_in_production` (≥20 ocorrências).

### Etapa 1 — Logs (R1, R2)
1. **Testes:** os dois acima + caplog para `rpg.prose` sem texto da narração.
2. **Implementação:** substituição mecânica dos `print`; `prose_guard` loga `where` + hash.

### Etapa 2 — Inventário, minimização Google, export (R3–R5)
1. **Testes:** inventário verde após listas; `test_google_token_nulled_after_consume`; `test_finish_minimizes_google_rows`; `test_export_includes_new_tables_without_token`; `test_export_columns_exclude_internal`; `test_export_assets_signed_urls_300s`.
2. **Implementação + migration.** **Verificação:** `uv run pytest -m infra_local` (Postgres local) + suíte.

### Etapa 3 — Delete de campanha purga blobs (R6) e TTL (R7)
1. **Testes:** blob fake conta deletes; idempotência; cron purge com fixtures datadas.
2. **Implementação:** §3.

### Etapa 4 — Política/Data Safety/fontes/consentimento (R8–R10)
1. **Testes:** `web/tests/legal.test.mjs` sem `<...>`; teste Python que compara `RETAINED_WITH_REASON.keys()` com a seção §5 da política (parser simples); `web/e2e/consent.spec.ts`; `test_index_html_has_no_external_font_hosts`.
2. **Implementação:** §3. **Verificação:** `uv run pytest -q`, `npm run build`, `npm test`, `checklist.py --legal-url`.

## 5. Critérios de aceite
- [x] Etapa 0 vermelha no HEAD, verde ao final; R1–R10 cobertos; suíte Python/Node/e2e verdes; Postgres local verde. (R8/R10 do texto da política: ver desvios.)
- [ ] Staging: turno real → logs da função Vercel sem texto do jogador (inspeção manual de 1 turno com sentinela); compra fake/teste → após consume `purchase_token IS NULL`; delete de campanha com arte → objeto some do bucket em ≤ 1 ciclo de cron; `/account/export` contém as novas tabelas sem token. **Pendente:** exige aplicar a migration `20261016120000_privacy_retention.sql` no staging e deploy (coordenador). **17/10 (parcial):** migration aplicada + deploy; sentinela: 0 ocorrências em 337 linhas de log de `/game/action`; export 200 com `owner_daily_counters` e sem chave `purchase_token`. Não exercidos: compra fake e delete com arte. **19/10:** delete com arte ✔ — `scripts/staging/spec222_art_purge.py`: retrato real (OpenAI, `rate_card` US$ 0,011445, reserva `settled`) → 2 objetos no bucket `rpg-dynamic` → `DELETE /game/save/{id}` 200 com job `purge_blobs` (2 chaves) `queued` → o `rpg-cron-jobs` agendado seguinte (≈50 s depois) o concluiu (`succeeded`, 1 tentativa) e o prefixo da campanha ficou com 0 objetos (`spec222_art_purge.json`). **Resta:** compra fake/teste com `purchase_token IS NULL` (sem chave Stripe test no staging; Play fake proibido em hosted).
- [ ] Política e Data Safety sem `<...>`; `web/dist/index.html` sem `fonts.googleapis.com`; signup com aceite + links. **Parcial:** `web/dist` sem Google Fonts ✔, signup com aceite + idade ✔, Data Safety alinhado ao código ✔; **17/10: texto legal publicado** em `web/legal/*.md` (`status: final`, sem `<...>`, sem banner RASCUNHO) com os dados do titular (controlador Guilherme dos Santos Medeiros, contato guilherme.smedeiros1@gmail.com, arrependimento 7 dias, idade 18+, retenção 5 anos); revisão jurídica recomendada. Pendem apenas: domínio de produção (URLs públicas das páginas) e prazo de logs da Vercel (descrito como padrão do provedor).
- [x] Revisão Sol independente APPROVED (17/10, com correções — `handoffs/SPEC-222-SOL-independent-review.md`): declaração 18+ exigida pela API (`SignupRequest.age_confirmed: Literal[True]`, 422), job `purge_blobs` idempotente no FileBlobStore e sem chaves com `..`, 6 `print` novos de main (SPEC-209–215) migrados para `log_event`.

### Execução (2026-10-16) — defaults e desvios

- **Defaults §8 adotados:** D-A URLs assinadas 300 s no JSON (`asset_downloads`, `format_version: 2`); D-B `usage_events` 13 meses, `account_deletions` compactada após 30 d e apagada após 5 anos, retenção financeira 5 anos; D-C self-host (Cinzel, Cinzel Decorative, EB Garamond — latin/latin-ext, ~290 KB) + CSP sem Google; D-D 18 anos com checkbox obrigatório.
- **R1:** `print` → `observability.telemetry.log_event` (`rpg.<area>` + `safe_json`, só contagens/ids de catálogo/`type(exc).__name__`). Escopo do teste AST ampliado para todo `.py` da raiz + `agents/ services/ infrastructure/ observability/ workers/` (exclui `game_engine.py`, `scripts/`, `playtest/`, `evals/`, `__main__`). O CLI `python rag.py` configura logging para stdout no `__main__`.
- **R4 (desvio):** minimização das linhas Google feita em `begin()` (antes do tombstone), não em `finish()`: o trigger `account_write_fence` bloqueia UPDATE após o tombstone. Anulação no consumo é imposta no banco (trigger `protect_google_play_purchase` reescrito) — o código não depende da coluna nullable para consumir. `google_state` já era um snapshot sem token; o subconjunto mantido é `purchase_state, consumption_state, purchase_type, quantity` (`orderId`/`purchaseTime` já são colunas próprias). Backfill de linhas terminais/de contas excluídas na migration.
- **R6 (desvio):** `app.assets` cai por cascade com o jogo, então as chaves são capturadas antes do `delete` e vão no payload do job `purge_blobs` (enfileirado na mesma transação, `game_id` nulo, dedupe `game:<id>`); o handler também varre o prefixo `users/<owner>/games/<game>/` em `storage.objects`. Não há linha `delete_pending` porque a linha deixa de existir.
- **R7:** `services/retention.py` no cron `/internal/cron/operations`, lotes de 1000; operações referenciadas por `turns`/`usage_events`/`wallet_reservations` nunca são apagadas (o FK em cascade apagaria histórico/uso).
- **R10 (desvio):** a fonte gerada é `docs/spec222/retencao.md` (`scripts/gen_retention_doc.py`, teste de sincronia); a seção §5 da política só muda via handoff.
- **R9:** Playwright `web/e2e/consent.spec.ts`; specs de cadastro existentes (inclusive a jornada F01 de `critical-journeys.spec.ts`) ganharam o passo de marcar a idade — só o passo, sem mudar asserções.
- **Dependência de deploy:** o código é seguro sem a migration (a minimização em `begin()` só roda se `app.minimize_google_state` existir; `purge_blobs`/TTL/export não usam objetos novos). Mas R4 (token anulado, índices de TTL, backfill) **só vale depois de aplicar `supabase/migrations/20261016120000_privacy_retention.sql` no staging**; aplicar antes/junto do deploy.

## 6. Smoke test
Staging, sem LLM pago (MockLLM não existe em hosted — usar 1 turno real, custo ~US$ 0,001): sentinela no texto + inspeção de logs; delete de campanha com asset; export.

## 7. Riscos & compatibilidade
- Migration torna `purchase_token` nullable: `google_play_payments.consume` retry usa `purchase_token` — só anular DEPOIS de `consumed`/terminal (R4); testes de SPEC-194 continuam verdes.
- Self-host de fontes muda o bundle (~200 KB); licença OFL permite.
- TTL de `usage_events` afeta séries de 30 d do dashboard (SPEC-185) — 13 meses > 30 d, sem impacto.

## 8. Pontos de decisão do dono
- **D-A (export com blobs):** URLs assinadas 300 s no JSON vs ZIP assíncrono. **Default recomendado:** URLs assinadas agora; ZIP em spec futura.
- **D-B (prazos):** `usage_events` 13 meses; `account_deletions` 5 anos (prazo prescricional); demais conforme R7. **Default recomendado:** adotar e declarar.
- **D-C (Google Fonts):** self-host (remove terceiro) vs declarar. **Default recomendado:** self-host.
- **D-D (idade mínima):** 18 (conteúdo violento/IA; evita regime de menores) vs 13 com autodeclaração. **Default recomendado:** 18, checkbox obrigatório no signup e na listagem do Play.

## 9. Evidência requerida
- Saídas de `uv run pytest` (inclusive `-m infra_local`), `npm test`, e2e; vermelhos da Etapa 0.
- Transcrição (sem valores/ids) do smoke §6; diff da política/Data Safety; `docs/secXX/README.md` com decisões D-A..D-D e tabela de retenção; parecer Sol; `ESTADO_ATUAL.md`/`ROADMAP.md`; atualização de `docs/spec197/risk-register.md` R-10.
