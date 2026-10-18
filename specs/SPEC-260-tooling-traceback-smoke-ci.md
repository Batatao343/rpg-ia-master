# SPEC-260 — Tooling: traceback no playtest/evals, evidência de falha no post-deploy smoke e artifacts no CI

> **Status:** `draft` — aguardando aprovação do dono. Prioridade sugerida: **P3**.
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** nenhuma
> **Desbloqueia:** —
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Haiku` (≡ Haiku) · **REVIEW_MODEL:** `Terra` (≡ Sonnet, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** `playtest/runner.py:1267-1272` guarda só `repr(e)` (sem traceback; `traceback` nunca importado); startup (`1368`) idem; `invariant.runner_crash` trunca em 180 chars (`~1690-1720`); `playtest/telemetry.py:273-291` idem; vários `except Exception` sem detalhe (`runner.py:1023,1120,1220,1459,1506`; `telemetry.py:88,864,1177,1208`). `evals/__main__.py:76` imprime `eval failed closed: {error}` sem caso nem traceback. `scripts/post_deploy_smoke.py:67-72` só escreve a evidência em sucesso (`print` + `return 1` na falha) — e o workflow exige o arquivo (`if-no-files-found: error`, `post-deploy-smoke.yml:34-39`), gerando um segundo erro enganoso; `checks` não tem status/latência. `validate.yml` não sobe artifacts.

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — Playtest: registro de erro por turno ganha `traceback` (≤ 40 linhas, `traceback.format_exception`, sem locals) no JSONL; idem startup e `invariant.runner_crash` (mensagem sem truncar a 180).
- **R2** — Evals CLI: falha imprime `case_id`/suite e traceback em stderr; JSON de saída inclui `error_type`.
- **R3** — `post_deploy_smoke.py`: evidência escrita sempre (`status: failed`, `failed_check`, `http_status`, `latency_ms` por check, `git_sha` esperado/obtido); continua checks independentes após a 1ª falha.
- **R4** — `validate.yml`: em falha, sobe `pytest` JUnit XML + `--tb=short` log como artifact (`if: failure()`).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Mudar o conteúdo dos smokes.

## 3. Design técnico

- **Alterados:** `playtest/runner.py`, `playtest/telemetry.py`, `evals/__main__.py`, `scripts/post_deploy_smoke.py`, `.github/workflows/validate.yml`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`tests/test_playtest_harness.py::test_error_record_has_traceback`; `tests/test_post_deploy_smoke.py::test_failure_writes_evidence`.

### Etapa 2 — Implementação

R1–R4.

### Etapa 3 — Verificação

`uv run pytest` verde; workflow `validate` com falha induzida em branch de teste sobe o artifact.

## 5. Critérios de aceite

- [ ] Erro de playtest mostra arquivo:linha do motor.
- [ ] Smoke falho deixa evidência JSON.
- [ ] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [ ] `uv run pytest` verde (suíte completa offline).
- [ ] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [ ] Saves antigos continuam carregando.

## 6. Smoke test

1. `uv run python scripts/post_deploy_smoke.py` contra URL inválida ⇒ JSON `status: failed` + exit 1.

## 7. Riscos & compatibilidade

- Tracebacks do playtest são locais (gitignored) — sem PII de produção.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.
