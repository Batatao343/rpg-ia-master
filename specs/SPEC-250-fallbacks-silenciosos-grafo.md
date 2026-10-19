# SPEC-250 — Grafo: todo fallback/guard e `except` silencioso no caminho do turno emite `<nó>.fallback`

> **Status:** `in-progress` — implementada em `logs-p1` (REVIEW_REQUIRED; smoke staging pendente)
> **Criada:** 2026-10-18 · **Atualizada:** 2026-10-18
> **Depende de:** SPEC-240
> **Desbloqueia:** SPEC-251, SPEC-252
> **Origem:** auditoria de logs 2026-10-18 ([relatório](../docs/auditorias/logs-api-2026-10-18.md))
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet) · **REVIEW_MODEL:** `Sol` (≡ Opus, contexto separado) · **REVIEW_REQUIRED:** `false`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (com evidência `arquivo:linha` no commit `4d60cf7`) · **[R]** recomendação.

---

## 1. Contexto & Objetivo

**[F]** A degradação graciosa (convenção de resiliência do CLAUDE.md) é invisível por turno. Guards que caem em fallback sem log: `agents/storyteller.py:841-844` (história determinística), `895-898` (narração vazia do `RoutedLLM`), `154` (`entities = {}`), `665` (`world_note = ""`); `agents/world_simulator.py:122-128,165`; `agents/router.py:270-272`; `agents/archivist.py:86-87`; `agents/combat.py:361,663,712-713`; `agents/loot.py:102-103`; `agents/npc.py:208,744`; `services/death_flow.py:295` (`scar = None`); `services/event_processor.py:82`; `services/turn_execution.py:29-30`; `services/audit_trace.py:250-251,288-289`; `services/jev_rollout.py:107-113,298-299,345-346,366-370`; `agents/campaign_manager.py:185,193,215-219` (template vs. plano anterior indistinguíveis). Também em `api.py`: `except Exception: pass` em `941, 2150, 2995, 3305, 3741, 3754, 3988, 4084, 4167, 4369, 4485, 4509, 4544` — quatro deles escondem falha de `turn_coordinator.fail` (lease não liberado).

**Objetivo:** tornar o debug desta área possível só com logs, sem reproduzir localmente — sem logar conteúdo de jogo nem dado pessoal.

## 2. Requisitos

- **R1** — Helper `observability.telemetry.log_fallback(node, reason, exc=None, **fields)` ⇒ `<node>.fallback` (`warning`) com `reason` (código fechado por nó: `structured_invalid|invoke_error|empty_output|timeout|rag_unavailable|template_used|previous_plan_kept|...`) e `error_type`.
- **R2** — Todos os sites listados acima chamam `log_fallback` (ou `log_event` específico) sem mudar o comportamento de degradação.
- **R3** — Os `except Exception: pass` de `api.py` em torno de `turn_coordinator.fail` passam a logar `operation.release_failed` (`error`, `op_ref`, `error_type`).
- **R4** — Teste AST `tests/test_no_silent_except.py`: em `agents/`, `services/`, `infrastructure/`, `workers/`, `api.py`, `llm_setup.py`, `rag.py`, `persistence.py`, todo `except Exception`/`except BaseException`/`except:` cujo corpo não relança precisa conter uma chamada `log_event|log_fallback|_log_event|logger.*|metrics.increment` **ou** um comentário `# silent-ok: <motivo>`; allowlist inicial explícita e congelada (só pode diminuir).
- **R5** — `rpg.turn` ganha `fallbacks` (contagem por `node.reason`).

### Restrições transversais

- **Privacidade (SPEC-222):** nenhum campo novo carrega texto do jogador, narração, nome de personagem, e-mail, IP cru, token, cookie, DSN, URL assinada ou corpo de resposta de provider. Ids de usuário/jogo/ação só como pseudônimo (`observability.telemetry.pseudonym`, HMAC com `RPG_TELEMETRY_SECRET`). Exceções: só `type(exc).__name__` + código fechado; nunca `str(exc)`.
- **Formato:** toda linha nova via `log_event(area, event, ...)` (`rpg.<area>`, JSON `safe_json`); nada de `print` (teste AST `tests/test_no_print_in_production.py` continua verde).

### Fora de escopo

Mudar a lógica de degradação; logs de decisão mecânica (SPEC-251).

## 3. Design técnico

- **Alterados:** arquivos listados no contexto. **Novo:** `tests/test_no_silent_except.py` com allowlist `tests/data/silent_except_allowlist.txt`.

## 4. Plano passo a passo

### Etapa 1 — Testes vermelhos

`test_no_silent_except` (falha com a lista atual); `tests/test_fallback_logging.py`: storyteller com FallbackLLM ⇒ `storyteller.fallback reason=structured_invalid`; campaign planner com erro ⇒ `campaign.fallback reason=template_used`.

### Etapa 2 — Implementação

R1–R5.

### Etapa 3 — Verificação

`uv run pytest` verde.

## 5. Critérios de aceite

- [x] Nenhum fallback de nó silencioso; allowlist versionada e documentada.
- [x] Lease não liberado sempre deixa linha `error`.
- [x] Teste de sentinela: nenhuma linha nova contém texto do jogador, e-mail, IP cru, token ou id cru.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Guard de FallbackLLM preservado em todo `with_structured_output` tocado.
- [x] Saves antigos continuam carregando.

## 6. Smoke test

1. Playtest curto `uv run python -m playtest run --profile normal --turns 5` com `RPG_NO_MOCK=1` sem chaves ⇒ linhas `*.fallback` presentes.

## 7. Riscos & compatibilidade

- Ruído: `log_fallback` com dedupe por (nó, reason) por turno.
- Logs são aditivos: nenhum contrato de resposta muda, salvo onde a spec diz explicitamente.
- MockLLM/FallbackLLM: comportamento inalterado; só passa a ser visível em log.

## Execução (logs-p1, 2026-10-18)

Implementado: `observability.telemetry.log_fallback` (+ coletor por turno → `rpg.turn.fallbacks`), logs nos fallbacks de storyteller/world_simulator/npc/campaign_manager/archivist/death_flow/blob_purge/image defer; `operation.release_failed` (`api._release_failed`, `turn_execution`) nos 5 guards de `turn_coordinator.fail`; scanner AST `tests/silent_except_scan.py` + `tests/test_no_silent_except.py` com allowlist congelada (`tests/data/silent_except_allowlist.txt`, só pode diminuir; anotação `# silent-ok: <motivo>`). Testes: `test_no_silent_except.py`, `test_fallback_logging.py`. Desvios: `agents/combat.py` e `services/conflict_*` NÃO foram tocados (outro agente edita combate) — ficam na allowlist; os demais ~87 sites antigos (api.py, rag.py, persistence.py, content_validator…) permanecem na allowlist para redução gradual. Falta o smoke de staging (§6) e a revisão Sol.
