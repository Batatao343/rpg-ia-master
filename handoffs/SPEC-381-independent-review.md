# SPEC-381 — revisão independente (spec `draft`, não código)

> **Veredito:** `CHANGES_REQUIRED`. Equivale a **SAFE-WITH-CHANGES**: a spec é executável e segura
> depois das mudanças abaixo. Como está escrita, a Etapa 5 já quebra o oráculo R6(b) e causa uma
> regressão silenciosa de métrica em produção.
> **Revisor:** Opus (spec-reviewer, independente) · **Data:** 2026-11-03 · **Commit revisado:** `main` em `b278f6af`/`2a6e0945` (o `api.py` não mudou desde `bcddd605`; o delta é só `tests/test_spec367_fallback_portrait.py`)

## Escopo

Revisei `specs/SPEC-381-refactor-api-routers.md` (509 linhas) contra o source real, a auditoria (§6
e §6.5), as specs 378, 379, 384 e 385, o FastAPI instalado (`0.141.1`, Starlette `1.6.0`, `uv.lock:555`)
e sondas em subprocesso (`import api`, introspecção de `app.routes`, `app.user_middleware`,
`app.exception_handlers` e `openapi()`, e apps mínimos de experimento no scratchpad). Também rodei
pytest focado (12 testes, `-n 0`, verdes). Não editei spec, código nem testes.

**W1, rodado 2× (início e depois da retomada):** nenhuma branch ativa toca `api.py`, exceto
`spec-214`: 1 commit à frente, de 2026-10-17, 1.552 atrás da `main` e branch morta. 367 e 368 já
pousaram suas edições de `api.py` (`566a4efc`, `061c330b`). **Pela letra da W1, a 381 nunca
começa** enquanto `spec-214` existir (ver P2-1).

## Fatos conferidos

| Fato na spec | Real (03/11, `main`) | Status |
|---|---|---|
| 7.940 linhas | 7.965 | ok (muda) |
| 65 decoradores de rota | 65 `@app.<método>`; `app.routes` = 65 APIRoute + 4 Route de docs + 1 `_IncludedRouter` (cron) + 1 Mount | ok |
| 8 handlers | 8 `@app.exception_handler`. `app.exception_handlers` tem 9 entradas: a 9ª é `WebSocketRequestValidationError`, default do FastAPI | ok, mas o R6(d) precisa saber da 9ª |
| 5 middlewares | `user_middleware` = `_correlation_boundary`, `_rate_limit`, `_session_boundary`, `BodyLimitMiddleware`, `CORSMiddleware` | ok. CSP e access log **não** são middlewares: estão dentro de `_correlation_boundary` (`api.py:620-685`). O texto da R2 confunde |
| sem `on_event`/`lifespan`/`Depends`/`app.state`/`dependency_overrides` | 0 `Depends(`, 0 `dependency_overrides` em tests, 0 `app.state`/`request.app`, startup/shutdown 0 | ok |
| ~140 patches, 34 nomes, ~50 arquivos | **137 `setattr(api…)` + 1 string `"api._image_finance"`, 34 nomes, 43 arquivos** | ok (o número de arquivos é menor) |
| "2 decoradores na mesma função" só no confirm | **3 funções** com 2 rotas: `auth_email_request`, `auth_logout`, `confirm_player_art` | parcial |
| `operationId` não depende do módulo | confirmado: o default é `{nome}_{path}_{método}`; OpenAPI igual em app plano × `include_router` (experimento) | ok |
| componentes OpenAPI sem colisão `módulo__Nome` | 39 schemas, nenhum com `__`. Mover um DTO não muda o nome, salvo se duas classes com o mesmo nome coexistirem | ok |
| `tests/test_abuse_policy.py:386-398` exige `_execute_action` como `ast.Name` em `game_action` e `_stream_turn_events` | confirmado. Além disso, `owners == ["_execute_action","game_prologue","new_game"]` exige juntar as funções de **vários** arquivos num só dict | ok, falta detalhar (P2-4) |
| `/account/checkout/skus` antes de `/{order_id}` | confirmado. Nenhum path é registrado em dois grupos com métodos diferentes | ok |
| `importlib.reload(api)` em `test_boot_policy.py:134,136,341,347` | confirmado. Env lida no nível do módulo: só `:99-100` (`_DOCS_ON`) e `_CORS_ORIGINS` | ok |
| `playtest/invariants.py` lê `api.X` em `except` silencioso | confirmado: `:2175` (`format_response`), `:2487` (`_npcs_block`), `:2589` (`_world_block`), `:2859` (`_combat_block`, **sem** try) | ok |
| "11 testes leem `api.py` como texto/AST" | **13**: faltam `tests/test_bug_api_pending_erros.py:144` (`inspect.getsource(api)`, asserção **negativa**) e `tests/test_spec361_integracao.py:324` (`getsource(api._execute_action)`, negativa) | **errado** (P1-3) |
| "§3.4: `api.game_graph.invoke` seguro por identidade enquanto reexportado" | `game_graph` é nome **patchado** (16×), e a R10 proíbe reexportar nome patchado | **contradição** (P1-4) |

## Achados

| ID | Sev. | Onde | Problema | Correção |
|---|---|---|---|---|
| P0-1 | P0 | spec §3.2, R6(b); FastAPI `0.141.1` `fastapi/routing.py:1586` | Neste FastAPI, `app.include_router(r)` **não copia** as rotas: põe **um** objeto `_IncludedRouter` em `app.routes`, sem `path`, `methods` nem `path_regex`. Isso foi provado no repo: o cron já aparece assim. Consequências: **(a)** o dump R6(b) muda por construção e o oráculo nunca fica byte-igual; **(b) regressão silenciosa de produção:** `services/body_limit.py:19-26 route_label()` percorre `app.routes` e pula quem não tem `methods`. Hoje `route_label('/internal/cron/jobs', routes=api.app.routes) == "other"` (provado). Depois do split, toda rota movida vira `"other"` na métrica `rpg_http_body_too_large_total` e no log `http.body_too_large` (`BodyLimitMiddleware` `:87`, `api.py:4509,4521,4610,4619`). OpenAPI e TestClient continuam iguais, então o oráculo não pega; **(c) testes que ficam vazios em silêncio:** `test_abuse_policy.py:78` (anti-esquecimento de classe de abuso: deixa de ver as rotas movidas e passa), `test_http_error_leakage.py:52 _body_routes` (lista encolhe), `test_spec195_reconciliation.py:417` (set de paths vazio, `not any` passa). Os que falham alto: `test_http_security_headers.py:177` (`seen > 20`) e `test_abuse_logging.py:111`. `scope["route"]` continua sendo o `APIRoute` original (provado), então o label do `_correlation_boundary` (`api.py:654`) não muda | Trocar `app.include_router(router)` por **cópia plana**: `app.router.routes.extend(router.routes)` no ponto do bloco (helper `_mount_router` em `api.py`). Experimento: tipos `APIRoute`, OpenAPI igual, 405/Allow igual. Diferença conhecida: `dependency_overrides_provider` vira `None` em vez de `app`, inofensivo com 0 `Depends`; se quiser identidade total, criar as rotas com `app.router.add_api_route(**…)`. Acrescentar ao R6(b) o **tipo de cada entrada** (proíbe `_IncludedRouter` novo) e um teste: `route_label` com 1 path de cada router devolve o template e não `"other"` |
| P1-1 | P1 | §3.6 `tests/test_spec381_api_surface.py` "roda na suíte default"; SPEC-385 | Um golden byte-igual de `openapi()` em `docs/spec381/before/`, **permanente** na suíte default, congela a API para todas as specs futuras: 384 D8/D9 (remove alias), 385 e qualquer rota nova. Também vira a **segunda fonte** do mesmo contrato que o snapshot da 385 (apontado pelo revisor da 385) | Tornar o golden **temporário**: só vale durante a 381 e é apagado (ou convertido) na Etapa 15. Fonte única depois: o snapshot de forma da 385, com `--update` explícito. Escrever na spec: "R6 é oráculo de equivalência da refatoração, não contrato". Os dumps congelados ficam em `docs/spec381/` só como evidência |
| P1-2 | P1 | R17 × "cada commit fica verde" × Etapa 14 | `ruff-baseline.toml` só tem `api.py`. Arquivo novo recebe **todas** as regras ("new files get every rule"), e o código movido carrega E402/F401/I001/B904. O `ruff check` do CI (e o hook `ruff` do `.pre-commit-config.yaml`, se instalado) reprova **cada** commit das Etapas 2–12. Deixar a Etapa 14 para o fim viola a W4 | Regenerar `scripts/dev/ruff_baseline.py` **no mesmo commit** de cada módulo novo e conferir o subconjunto e a soma da R17 por etapa. Proibir `ruff check --fix` **e** o `ruff format` automático do hook sobre os módulos novos (rodar `ruff format --check`; se reformatar, a etapa para) |
| P1-3 | P1 | §3.5 / R14 | Faltam 2 scanners com asserção **negativa**, que ficam vazios sem barulho: `test_bug_api_pending_erros.py:144` (`"{req.backstory}" not in inspect.getsource(api)`: o código de criação de personagem sai de `api.py` e o teste passa sem olhar nada) e `test_spec361_integracao.py:324` | Incluir os dois no `API_FILES`/R14 (o primeiro lendo o texto de todos os `API_FILES`; o segundo é retarget para `routes.turn._execute_action`). Contar 13 e não 11. Exigir no handoff do executor o grep `getsource\(\s*api\|Path\("api\.py"\)` refeito no commit-base |
| P1-4 | P1 | §3.4 × R10 × R13 | (a) `game_graph` é patchado (16×) **e** usado como objeto: `setattr(api.game_graph, "invoke"…)` em `test_prompt_guard.py:211,217` e `test_speech_api.py:90,93`. Sem reexport (R10), esses `api.game_graph.invoke` dão `AttributeError`. A §3.4 diz o contrário. (b) Os nomes patchados também são **lidos/chamados** pelos testes, não só patchados: `api._execute_action(req)` (`test_abuse_policy.py:373-379`), `api._commit_turn(` (`test_bug_morte_checkpoint.py:146,169,242`, `test_api_attempt_telemetry.py:96`), `api._run_turn(`, `api._game_lock(` (6), `api._resolve_save_file(` (`test_fase10.py:68`), `api._image_finance(` (`test_spec196_finops.py:379,830,831`), `api.load_game_state`, `api._sse_log`. A R13 só permite trocar "alvo de patch ou import" | Na R13, permitir explicitamente o **retarget de leitura/chamada** dos 34 nomes (`api.X` → `<lar>.X`), dentro da regra "só muda o prefixo". Corrigir a §3.4: `api.game_graph.*` é retarget para `routes.turn.game_graph`. O inventário da Etapa 0 ganha `kind: read` |
| P1-5 | P1 | R5 × R9 ("reexport = mesmo objeto") | `_FAKE_GOOGLE` (`api.py:4339`, religado por `global` em `:4350`) **não pode ser reexportado**: o reexport em `api.py` captura `None` para sempre. A R5 o põe na lista de identidade. Mesmo cuidado com qualquer nome que hoje é reatribuído | Tirar `_FAKE_GOOGLE` dos reexports. `test_spec381_reexports_are_identical` deve recusar reexport de nome que tenha `global <nome>` no lar (checagem AST) |
| P1-6 | P1 | R6 + R13 vs. monkeypatch inócuo (pergunta 3) | O OpenAPI/TestClient **não** detecta patch inócuo. A R10 (sem reexport ⇒ `AttributeError`) e a R13(c) cobrem esquecer o alvo e cópia por `from lar import X`. Não cobrem: alias (`_f = load_game_state`), tabela de despacho montada no import, default de parâmetro e closures. A prova do revisor por amostragem (3 nomes) é fraca para 34 | Acrescentar um oráculo dinâmico de **vivacidade de patch**: um plugin pytest temporário (`scripts/dev/patch_liveness.py`, não versionado na suíte) que embrulha `MonkeyPatch.setattr` e envolve o valor callable num contador. Gera `{test_id: {nome: chamadas>0}}` no commit-base (alvo `api`) e na ponta (alvo `lar`), sobre os 43 arquivos do inventário (`-n 2`). Os conjuntos têm de ser **iguais**. Para os não-callables (`_DOCS_PATHS`, `_CLIENT_ERROR_LOG_MAX_PER_MIN`, `game_graph`): mutação, isto é, patch com valor sentinela inválido e o teste tem de falhar antes e depois |
| P2-1 | P2 | W1 / Etapa 0.1 | `spec-214` (morta, 17/10) toca `api.py` e mantém a W1 não vazia para sempre | O coordenador decide arquivar `spec-214` (ou a W1 passa a ignorar branches sem commit nos últimos N dias e que já foram superadas). Registrar como pré-condição da Etapa 0 |
| P2-2 | P2 | R6(d) | `exception_handlers` traz o handler default do FastAPI para `WebSocketRequestValidationError` (9 entradas) | Documentar 8 próprios + 1 default. O dump inclui as 9 |
| P2-3 | P2 | R2 / §3.1 grupo 0 | "CSP e access log" aparecem como itens de `api.py`, mas estão dentro de `_correlation_boundary` (e `_access_log` está em `:524`). O texto pode induzir o executor a criar middleware novo | Reescrever: "`_correlation_boundary` (com CSP/headers e `_access_log`) fica em `api.py`" |
| P2-4 | P2 | R12/R14, `test_abuse_policy.py:386-403` | Ao ler vários arquivos, `functions` vira um dict por nome. Nomes de função duplicados entre módulos (ex.: dois `_bind_corr` locais) se sobrescrevem. E `owners` só bate se `game_prologue` (art) e `new_game` (turn) chamarem `_enforce_owner_budget` como `ast.Name`. Se a R11 fizer o executor usar `api_core._enforce_owner_budget(...)` (`ast.Attribute`), o teste falha. Falha alta, mas leva o executor a "corrigir" o teste | Fixar na spec: `_enforce_owner_budget` não é patchado, então é importado por nome simples (`from api_core import _enforce_owner_budget`). `API_FILES` falha se houver nome de função de nível de módulo duplicado entre os arquivos |
| P2-5 | P2 | rotas que usam `app` | `api.py:4509,4521,4610,4619` passam `routes=app.routes`. No router de billing, `app` não existe (a R3 proíbe importar `api`) | Listar como **a única** mudança de corpo permitida: `request.app.routes`. Equivalente: após `reload(api)` hoje `app` também é o novo. Com o P0-1 corrigido, o `route_label` continua achando o template |
| P2-6 | P2 | catálogo de eventos (`scripts/gen_event_catalog.py:171`, `rglob`) | O catálogo identifica wrapper por **nome** (`WRAPPERS.get(name.split(".")[-1])`). Se um router chamar o wrapper por outro alias, o evento some de `observability/events.py`/`EVENTOS_DE_LOG.md` | Manter os aliases (`_log_event`, etc.) idênticos nos módulos novos. Acrescentar ao W2: `gen_event_catalog.py --check` byte-igual |
| P2-7 | P2 | R5 / `reload(api)` | Hoje `importlib.reload(api)` **zera** `_rate_hits`, `_game_locks`, `_authfail_until`, `_PORTRAIT_SIGN_CACHE` e `_client_error_last`. Depois do split, eles moram em módulos que não são recarregados e **não** zeram. Risco baixo: os testes limpam explicitamente | Registrar como diferença aceita e rodar `tests/test_boot_policy.py` + 1 arquivo vizinho na mesma sessão xdist |
| P2-8 | P2 | 384 × 381 | A 384 D9 fala em "router SSE"; na 381 o SSE fica em `routes/turn.py` (D2) | Alinhar o texto da 384 (coordenador) |

## Consumidores fora de `tests/` (pergunta 2)

- `vercel_app.py:16` (`from api import app`), `scripts/audit_local_server.py:47`,
  `scripts/latency_baseline.py:246,509`, `scripts/smoke/spec351_opening.py:85` e
  `scripts/smoke_local_profile.py:59` usam só `api.app`. `playtest/latency_llm.py:213` troca
  `get_llm` varrendo `sys.modules`, então pega os módulos novos. Seguro.
- `evals/core/adapters.py:1188` (`api.format_response`) é caminho **protegido** (W5). O reexport é
  obrigatório e o teste de identidade da R9 cobre. Não achei `_source()`/digest de `api.py` em
  `evals/experiments`.
- `observability/events.py:12-16` tem `"api.*"` como nome de evento literal (área), não módulo. Os
  loggers usam nomes explícitos (`rpg.turn`, `rpg.account`), sem `__name__`. Seguro.
- Bundle: `vercel.json:10` e `.vercelignore` não excluem `routes/` nem `api_*.py`. Não há pacote
  `routes`/`api_*` no `.venv`. `pyproject` não tem `py-modules`/coverage `source=`. A R15 está ok.
- Gates por caminho: `scripts/ci_eval_scope.py:29`, `scripts/dev/eval_publish.py:30` e
  `scripts/project_index_ab_harness.py:40` (R16 ok). Nenhum workflow tem filtro `paths:` com `api.py`.

## Tabela por requisito/etapa

| Item | Parecer |
|---|---|
| R1–R4 | ok (R2: texto do P2-3) |
| R5 | ok, menos `_FAKE_GOOGLE` (P1-5) e reload (P2-7) |
| R6 | **muda**: cópia plana (P0-1), tipo de rota no dump, 9 handlers, golden temporário (P1-1) |
| R7 | ok |
| R8 | ok; acrescentar o catálogo de eventos (P2-6) |
| R9–R13 | ok com P1-4 (retarget de leitura e `game_graph`) e P1-6 (vivacidade dinâmica) |
| R14 | 13 scanners, não 11 (P1-3); dict multi-arquivo (P2-4) |
| R15–R16 | ok |
| R17 | baseline por etapa, não no fim (P1-2) |
| R18–R20 | ok (golden de 404 antes do helper é bom) |
| Etapa 0 | + arquivar `spec-214` (P2-1); inventário com `kind: read` |
| Etapas 5–12 | `extend(router.routes)` em vez de `include_router`; baseline do ruff no mesmo commit |
| Etapa 15 | + apagar ou converter `test_spec381_api_surface` (P1-1) |

## Correções aplicadas

Nenhuma: esta é a revisão de uma spec draft.

## Pendências

O autor ou o coordenador aplica P0-1 e P1-1..6 na spec antes de `approved`. A decisão sobre
`spec-214` (P2-1) e o alinhamento da 384 (P2-8) ficam com o coordenador.

## Comandos rodados

```text
git diff/for-each-ref (W1, 2x) → só spec-214 (morta) toca api.py
uv run --frozen python s381_probe.py → 65 APIRoute, 4 Route, 1 _IncludedRouter, 1 Mount; 5 middlewares; 9 handlers; 0 startup
uv run --frozen python s381_inv.py → 137 setattr + 1 string, 34 nomes, 43 arquivos
uv run --frozen python s381_mini.py → include_router gera _IncludedRouter; scope["route"] = APIRoute; OpenAPI igual
uv run --frozen python -c route_label(...) → '/internal/cron/jobs' → "other" (cego a router incluído)
uv run --frozen python s381_flat.py → routes.extend(router.routes): APIRoute plano, OpenAPI e 405 iguais
py.sh -m pytest -n 0 (abuse_policy x2, abuse_logging x1, http_error_leakage) → 12 passed
```
