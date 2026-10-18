# SPEC-249 — Linha de boot: perfil, build, adapters, modo LLM, embeddings e segredos ausentes

> **Status:** `draft` — aguardando aprovação do dono. Prioridade sugerida: **P1**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-239
> **Desbloqueia:** SPEC-261, SPEC-262
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** Nada registra com que configuração uma instância subiu. `assert_boot_policy` (`api.py:71`) é fail-closed mas não loga o perfil; `get_runtime()/build_runtime()` (`infrastructure/runtime.py:741-760`) são lazy e silenciosos; `apply_serverless_defaults` (`runtime.py:726-738`) seta `RPG_NO_MOCK`/cache sem log. `pseudonym()` usa a chave pública `local-telemetry-only` se `RPG_TELEMETRY_SECRET` faltar (`telemetry.py:61`) — silenciosamente. A falha de criação do pool (`runtime.py:633-646`) só aparece como traceback. Em serverless, cada cold start é uma “instância”: sem linha de boot não dá para correlacionar um erro com um deploy/config.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `runtime.boot` (`info`) 1× por processo, no primeiro request ou no import do `api`: `git_sha` (12 chars), `profile`, `hardened`, `region` (`VERCEL_REGION`), `llm_mode` (`routes|legacy:<provider>|mock|fallback`), `llm_providers_with_key` (lista de nomes, nunca valores), `embedding_provider`, `jev_mode`, `projection_mode`, `log_level`, `cold_start_ms` (do import ao 1º request), `instance_ref` (uuid curto).
- **R2** — `runtime.config_warning` (`warning`) para: `RPG_TELEMETRY_SECRET` ausente/curto (pseudônimos fracos), `GIT_SHA` vazio, `RPG_CORS_ORIGINS` default em perfil hosted.
- **R3** — Falha de construção do runtime/pool ⇒ `runtime.build_failed` (`error`) com `component` (`db_pool|admin_pool|vector|blob|identity`) e `error_type`, antes de relançar.
- **R4** — `instance_ref` é incluído na correlação (SPEC-240) de toda linha daquele processo.
- **R5** — Teste: o boot nunca contém DSN, host do banco, chaves, e-mails (sentinelas nos env vars de teste).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Expor esses dados em endpoint público (só `/health` existente).

## 3. Design técnico

- **Novo:** `observability/boot.py::log_boot_once()`. **Alterados:** `api.py`, `infrastructure/runtime.py`, `observability/telemetry.py` (`instance_ref`).

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_boot_log.py`: `test_boot_logged_once`, `test_boot_has_no_secrets`, `test_missing_telemetry_secret_warns`, `test_pool_failure_logged`.

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [ ] Cada instância tem 1 `runtime.boot`; toda linha tem `instance_ref`.
- [ ] Zero segredos (teste).
- [ ] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [ ] Saves antigos continuam carregando.

## 6. Smoke test

1. Staging: após deploy, `vercel logs --query runtime.boot` mostra o `git_sha` deployado e `llm_mode=routes`.

## 7. Riscos & compatibilidade

- Nenhum.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.
