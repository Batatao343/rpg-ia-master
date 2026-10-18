# SPEC-253 — Persistência: migrações de save, schema recusado, checkpoint e retry atômico logados

> **Status:** `draft` — aguardando aprovação do dono. Prioridade sugerida: **P2**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-240
> **Desbloqueia:** —
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `migrate_state`/`_migrate_v*` (`persistence.py:194-260`) aplicam v3→v8 sem log de `from→to`; `IncompatibleSaveError` é relançado (`754`, `773`) e o handler 409 (`api.py:85-92`) não loga a versão; `restore_checkpoint_memory` (`persistence.py:454`) e `_replace_with_retry` (`40-52`, 6 tentativas com backoff) não logam; erros de save/load logam só a classe, sem `game_ref`/duração (`698,719,757,776,950,980,1048,1057`). `rag._read_meta` (`rag.py:577-582`) engole meta corrompido e escolhe silenciosamente o provider legado Gemini; `pgvector_memory.py:38` cai em `local-1024` e `:243-244` degrada busca semântica para texto sem log.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — `persistence.migrated` (`info`) com `from_version`, `to_version`, `steps`, `game_ref`; `persistence.save_schema_newer` (`warning`) com `found_version`, `supported_version`.
- **R2** — `persistence.checkpoint_written|checkpoint_restored` (`info`) com `game_ref`, `turn`; falhas já existentes ganham `game_ref` e `duration_ms`.
- **R3** — `_replace_with_retry`: `persistence.atomic_retry` (`debug` por tentativa) e `persistence.atomic_failed` (`error`, `attempts`).
- **R4** — `rag.meta_unreadable` (`warning`, `index` = nome lógico, nunca caminho absoluto) e `vector.profile_fallback` / `vector.semantic_degraded` (`warning`, `error_type`).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Mudar formatos de save.

## 3. Design técnico

- **Alterados:** `persistence.py`, `api.py:85-92`, `rag.py`, `infrastructure/pgvector_memory.py`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_persistence_logs.py`: `test_migration_logged_from_to`, `test_newer_schema_logged`, `test_atomic_retry_logged` (PermissionError simulado), `test_corrupt_meta_logged`.

### Etapa 2 — Implementação

R1–R4.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [ ] Carregar save v3 gera `persistence.migrated from_version=3`.
- [ ] Nenhum caminho absoluto/`game_id` cru em log.
- [ ] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [ ] Saves antigos continuam carregando.

## 6. Smoke test

1. Local (perfil legacy): carregar save antigo de fixture; staging: n/a (perfil DB) — validar só `checkpoint_*`.

## 7. Riscos & compatibilidade

- Nenhum.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.
