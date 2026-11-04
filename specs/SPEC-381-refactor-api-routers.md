# SPEC-381 — Fatiar `api.py` em routers por domínio, DTOs e montagem de resposta (refatoração pura)

> **Status:** `approved` (04/11, dono: "vai executando o que puder"; D1–D10 = recomendações do §8)
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03 (revisão independente aplicada: `handoffs/SPEC-381-independent-review.md`; ver "Resposta à revisão" no fim)
> **Origem:** `docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md` §4.1 itens 1, 8 e 9, §3 R8, §5 letra E e §6 inteiro (letra E → SPEC-381; regras W1–W8, W1 na versão revisada)
> **Depende de:** SPEC-367 e SPEC-368 **pousadas**. A revisão confirmou que já pousaram as edições de `api.py`: `566a4efc` e `061c330b`. SPEC-378 **recomendada antes** (helpers comuns), com a condição D10: a 378 não toca `api.py`.
> **Desbloqueia:** SPEC-385 (contrato front↔back), hoje **adiada (DEFER)**. Por isso o dump de OpenAPI desta spec é só oráculo temporário (R6), e não contrato.
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true` · **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato conferido no código em 03/11 (arquivo:linha) · **[H]** hipótese que a Etapa 0 prova ou derruba · **[D]** decisão do dono (§8).

> **Linhas citadas mudam.** `api.py` está sendo editado por outras branches enquanto esta spec é
> escrita: `def _creature_art_live` estava em `api.py:2857` no início da leitura e em `api.py:2864`
> no fim. A Etapa 0 refaz todos os números no commit-base. O que vale é o **nome** da função.

---

## 1. Contexto & Objetivo

[F] `api.py` tem 7.940 linhas. Nele ficam o boot, 8 exception handlers, 5 middlewares, 65
decoradores de rota, os DTOs, a montagem de resposta e o pipeline do turno. Toda feature nova
toca esse arquivo, e quase toda onda paralela briga por ele. A auditoria (§4.1 item 1) propõe
dividir em módulos `APIRouter`. O saldo de linhas é zero: o ganho é ler e editar menos.

O dono pediu **muito cuidado para não quebrar nada**. Esta spec é refatoração pura (W2/W3): o
contrato HTTP, a ordem das rotas, a ordem dos middlewares e dos handlers, o OpenAPI, os logs e o
custo de import ficam **iguais**. As quatro armadilhas reais não estão na API em si. Estão em volta
dela:

1. **monkeypatch inócuo.** [F] Há 137 chamadas `monkeypatch.setattr(api, "<nome>", …)` mais 1
   alvo-string (`"api._image_finance"`), em 43 arquivos de teste, sobre 34 nomes distintos
   (contagem da revisão; inventário na §3.4). Os testes também **leem e chamam** esses nomes
   (`api._execute_action(req)`, `api._game_lock(...)` etc.). Reexportar `X` em `api.py` **não**
   faz o patch valer para o código movido, porque ele lê o global do próprio módulo. O teste
   continua verde e passa a testar outra coisa.
2. **scanner inócuo.** [F] 13 testes e 1 allowlist leem `api.py` como **texto, AST ou
   `inspect.getsource(api)`** (§3.5). Código movido para fora de `api.py` some da varredura em
   silêncio. Dois desses testes têm asserção **negativa** e passam vazios.
3. **rota incluída "opaca".** [F] No FastAPI instalado (`0.141.1`, `uv.lock:555`),
   `app.include_router(r)` não copia as rotas. Ele põe **um** objeto `_IncludedRouter` em
   `app.routes`, sem `path` nem `methods`. O cron (`api.py:303`) já aparece assim. Quem percorre
   `app.routes` fica cego para as rotas movidas. Exemplos: `services/body_limit.py:19-26
   route_label` (rotula a métrica `rpg_http_body_too_large_total`) e 3 testes que passariam
   vazios (R21).
4. **ciclo e cold start.** [F] Há 432 linhas `import`/`from … import` indentadas (dentro de
   função) em `api.py` (auditoria §3 R8 contou 417). Elas existem por cold start da Vercel
   (19–59 s) e para evitar ciclos. Não sobem.

A spec também faz três limpezas pequenas, **depois** do split e em commits próprios com golden
(§4.1 item 8 da auditoria): `_load_or_404()`. `_art_repository()` e `_client_ip` ficam para
decisão do dono (D5/D6), porque nenhum dos dois é equivalente puro.

## 2. Requisitos

### 2.1 Forma final

- **R1** [F] **Nenhum pacote `api/`.** Ao lado de `api.py` ele quebraria `import api`,
  `uvicorn api:app` (`Procfile:1`, `scripts/start_local_api.py:53`) e `from api import app`
  (`vercel_app.py:16`). Os nomes novos (D1) são:
  - `routes/` (pacote, com `__init__.py` vazio), um módulo por domínio (§3.1);
  - `api_core.py`: helpers usados por mais de um router e pelos middlewares;
  - `api_models.py`: DTOs Pydantic compartilhados;
  - `api_presenters.py`: montagem de resposta.
  [F] Não existe `routes/`, `api_*.py` nem pacote `routes` no `.venv` (Glob em 03/11).
- **R2** `api.py` fica só com: imports e `assert_boot_policy` (`api.py:99`); criação do `app`
  (`api.py:102-109`); envelope de erro e os 8 exception handlers; CORS e `BodyLimitMiddleware`;
  os 3 middlewares `http` (`_session_boundary`, `_rate_limit` e `_correlation_boundary`). O
  `_correlation_boundary` já contém o CSP, os headers e a chamada a `_access_log` (`api.py:524`,
  `:620-685`). **Não** se cria middleware novo. Ficam também em `api.py`: a montagem plana de
  cada router **na ordem original** (`_mount_router`, §3.2; nunca `include_router`, R21); o mount
  estático (`api.py:7930-7933`); o `__main__` (`api.py:7935-7940`); os reexports da R9.
- **R3** **Direção única de import:** `api.py → routes/* → api_presenters → api_models`, e todos
  podem usar `api_core`. Nenhum módulo novo importa `api` (nem `import api` nem `from api import`),
  em nenhum nível. Motivo: `python api.py` roda como `__main__`, e um `import api` dentro de
  `routes/` executaria o arquivo uma segunda vez, com um segundo `app`.
- **R4** **Os efeitos colaterais de import continuam em `api.py`, na mesma posição relativa:**
  `assert_boot_policy(os.environ)` (`:99`), `configure_logging()` (`:1342`), `log_boot_once()`
  (`:1345`), `set_llm_telemetry_hook(...)` (`:1434`), `set_llm_attempt_telemetry_hook(...)`
  (`:1509`) e `app.middleware("http")(_correlation_boundary)` (`:1718`). As funções podem se mudar
  para `api_core`; a **chamada** fica. Os módulos novos só definem coisas. Exceção: os decoradores
  `@router.<método>`.
- **R5** **Estado mutável tem um só dono e nunca é religado.** `_authfail_until` (`:412`),
  `_game_locks`/`_game_locks_guard` (`:1391-1392`), `_rate_hits` (`:1615`), `_metrics_hits`
  (`:1628`), `_PORTRAIT_SIGN_CACHE`, `_client_error_last` (`:3611`), `_metrics_sql_cache`
  (`:3703`) e as 3 `ContextVar` (`:1353-1361`) moram cada um num único módulo. `api.py` reexporta
  **o mesmo objeto** (identidade), porque ~50 testes fazem `api._rate_hits.clear()`,
  `api._authfail_until.clear()` e afins (§3.4). Ninguém reatribui esses nomes.
  **Nome religado por `global` nunca é reexportado**, porque o reexport congela o valor antigo:
  - [F] `_FAKE_GOOGLE` (`api.py:4339`, religado em `:4350`) mora só em `routes/billing.py` e não
    aparece em `api.py`;
  - `_CODE_RE` fica em `api.py`, junto com `_error_code_of`.
  `test_spec381_reexports_are_identical` recusa (por AST) reexport de nome que tenha
  `global <nome>` no lar.
  **Diferença aceita (P2-7):** hoje `importlib.reload(api)` zera esses dicionários; depois do
  split, eles moram em módulos que não são recarregados e não zeram. Os testes já limpam
  explicitamente. A verificação é rodar `tests/test_boot_policy.py` junto com um arquivo vizinho
  que usa `_rate_hits` (`tests/test_fase10.py`) na mesma sessão `-n 2`.

### 2.2 Oráculo de equivalência (W2), criado **antes** de mover qualquer linha

- **R6** **Superfície HTTP idêntica byte a byte, antes e depois.** O dump é gerado no commit-base
  (Etapa 0) e congelado. Nenhum commit posterior desta spec pode alterá-lo; se for preciso, a
  etapa para (W3). **R6 é oráculo de equivalência desta refatoração, não contrato da API.** Ele
  vale só enquanto a 381 estiver em voo. Na Etapa 15, `tests/test_spec381_api_surface.py` é
  apagado e os dumps ficam em `docs/spec381/` só como evidência. Assim nenhuma spec futura (384,
  rota nova) herda um golden de OpenAPI congelado. A fonte única de contrato, quando existir, é o
  snapshot da SPEC-385, hoje adiada, com `--update` explícito. O dump cobre:
  - (a) `json.dumps(app.openapi(), sort_keys=False, ensure_ascii=False, indent=1)`;
  - (b) a lista ordenada de `app.routes`, com o **tipo de cada entrada** (`APIRoute`, `Route`,
    `Mount` ou `_IncludedRouter`). Assim fica proibido aparecer um `_IncludedRouter` novo, e o
    único permitido é o do cron que já existe. Para `APIRoute`: `(type, path, sorted(methods),
    name, endpoint.__qualname__, include_in_schema, status_code, response_model.__qualname__ |
    None, response_class.__name__)`. Para `Mount`/`Route`: `(type, path, name)`. Para o
    `_IncludedRouter` do cron: `(type, [paths das rotas internas])`. O `__module__` do endpoint
    fica de fora, porque muda por design;
  - (c) `app.user_middleware` em ordem: `(cls.__name__, dispatch.__name__ se houver,
    kwargs ordenados)`. [F] São 5 hoje: `_correlation_boundary`, `_rate_limit`,
    `_session_boundary`, `BodyLimitMiddleware` e `CORSMiddleware`;
  - (d) `app.exception_handlers` em ordem de inserção: `(exc.__qualname__, handler.__name__)`.
    [F] São 9 entradas: os 8 handlers próprios e o default do FastAPI para
    `WebSocketRequestValidationError`. O dump inclui as 9;
  - (e) `len(app.router.on_startup)`, `len(app.router.on_shutdown)` e o tipo de
    `app.router.lifespan_context`. [F] Hoje não há `on_event` nem `lifespan` em `api.py`.
  São dois dumps, cada um num subprocesso limpo: perfil `legacy` (ambiente da suíte) e perfil
  hosted (env do `secure_env()` de `tests/test_boot_policy.py`, sem as rotas `/docs`).
- **R7** **Custo de import.** Dois oráculos, antes e depois:
  - (a) **determinístico:** o conjunto `set(sys.modules)` depois de `import api` só ganha
    `api_core`, `api_models`, `api_presenters`, `routes` e `routes.*`. Nenhum módulo
    pré-existente entra nem sai. A ordem de primeiro import dos módulos pré-existentes vai para o
    handoff como diff informativo; qualquer diferença precisa de justificativa;
  - (b) **tempo:** mediana de 5 execuções de
    `bash scripts/dev/py.sh -X importtime -c "import api"`, linha cumulativa de `api`. A mediana
    depois do split não passa de 105 % da mediana antes.
  Nenhum import de dentro de função sobe para o topo do módulo (§3 R8 da auditoria). Um import
  local é movido junto com a função onde está, sem mudar.
- **R8** **W2 completo**, rodado pelo coordenador no commit-base e na ponta: suíte completa 1×;
  `evals run` nas 12 suítes do `eval-gates.yml` com `--seed 7` e depois `evals compare` sem
  diferença; `playtest run --all --turns 10 --seed 0` com a mesma contagem de violações por perfil
  e o mesmo desfecho. Também o catálogo de eventos byte-igual. [F] O script não tem `--check`.
  O procedimento é rodar `bash scripts/dev/py.sh scripts/gen_event_catalog.py` e depois
  `git diff --exit-code observability/events.py docs/operacao/EVENTOS_DE_LOG.md`, que tem de
  sair vazio. O catálogo acha os wrappers de log **por nome** (`scripts/gen_event_catalog.py:222`,
  `WRAPPERS`), então os módulos novos usam os mesmos aliases (`_log_event`, `log_fallback` etc.)
  e nenhum outro.

### 2.3 Monkeypatch, reexports e scanners (W3)

- **R9** **Reexports em `api.py`.** Ficam reexportados:
  - os nomes lidos como `api.X` **fora de `tests/`**: `app`, `format_response`, `_npcs_block`,
    `_world_block`, `_combat_block` (`playtest/invariants.py:2177,2489,2591,2862`;
    `evals/core/adapters.py:1194`);
  - os nomes que `tests/` só **lê** ou chama, sem patch: `GameResponse`, `ActionRequest`,
    `QuotaExceeded`, `health_check`, `_factions_block`, `_world_block`, `_stream_turn`,
    `_rate_hits` etc. A lista completa sai da Etapa 0.
  Cada reexport é o **mesmo objeto** do módulo-lar, e `test_spec381_reexports_are_identical`
  assegura `api.X is <lar>.X` para todos. Nomes patchados (R10) e nomes religados por `global`
  (R5) **nunca** entram nesta lista. Isso vale também para `game_graph`: os patches de atributo
  `api.game_graph.invoke` viram `routes.turn.game_graph.invoke` (§3.4).
  [F] As leituras de `playtest/invariants.py` ficam dentro de `try/except Exception` com
  `# silent-ok` (ex.: `:2174-2181`). Se o reexport sumir, a invariante para de checar **sem
  erro**. Por isso o teste de identidade é obrigatório.
- **R10** **Nome patchado não é reexportado.** Cada um dos 34 nomes da §3.4 tem um único
  **módulo-lar**, e `api.py` não reexporta esse nome. Assim, um `monkeypatch.setattr(api, "X")`
  esquecido falha alto com `AttributeError`: o `raising=True` é o default do pytest. Uma única
  exceção: `_npcs_block`. O leitor que o teste quer afetar, `playtest/invariants.py:2489`, lê
  `api._npcs_block`, então o patch de `tests/test_spec304_playtest.py:85-87` continua efetivo via
  reexport. O teste não muda.
- **R11** **Leitura no lar, na hora da chamada.** Quando um nome patchado é usado em mais de um
  módulo, inclusive pelos middlewares de `api.py` (caso de `_database_profile`), quem não é o lar
  o lê como atributo do lar (`api_core._database_profile()`). Proibido
  `from api_core import _database_profile` nesses módulos. Default de parâmetro também não pode
  capturar nome patchado (`def f(loader=load_game_state)` congela o objeto original).
- **R12** **Co-localização obrigatória.** Quando um nome é patchado **e** um teste de AST exige
  chamada por nome simples (`ast.Name`), chamador e chamado ficam no mesmo módulo. [F] Caso
  concreto: `tests/test_abuse_policy.py:386-398` exige `_execute_action` como `ast.Name` em
  `game_action` e em `_stream_turn_events`. Ao mesmo tempo, `tests/test_error_envelope.py:147`,
  `tests/test_spec293_rotulo_faccao.py:242` e `tests/test_turn_trace_logs.py:165` patcham
  `api._execute_action` e exercitam `/game/action/stream`. Conclusão: **SSE e pipeline do turno
  vão para o mesmo módulo** (`routes/turn.py`, D2), e não para dois, como sugeria a auditoria.
- **R13** **Única mudança de teste permitida (W3): trocar o prefixo `api.` por `<lar>.`**, no
  **mesmo commit** que move `X`. Vale para patch (`setattr(api, "X")`, alvo-string `"api.X"`),
  import (`from api import X`), **leitura ou chamada** (`api._execute_action(req)`,
  `api._commit_turn(`, `api._game_lock(`, `api._image_finance(`, `api.load_game_state` etc.) e
  atributo de objeto (`api.game_graph.invoke`). Só o prefixo muda: asserção, fixture, dado e
  contagem ficam iguais. O inventário da Etapa 0 registra cada ocorrência com
  `kind: setattr | string | from_import | read | attr_object | reload`.
  `test_spec381_patch_targets_live` lê o inventário congelado
  (`docs/spec381/patch_inventory.json`) e verifica três coisas para cada `(arquivo, nome, lar)`:
  - (a) o lar define `nome` no nível do módulo;
  - (b) `api.py` não reexporta `nome`, salvo a exceção da R10;
  - (c) nenhum módulo da API além do lar tem `nome` no namespace global.
- **R13b** **Vivacidade dinâmica do patch** (P1-6). A R13 é estática e não pega alias
  (`_f = load_game_state`), tabela de despacho montada no import, default de parâmetro nem
  closure. Por isso existe `scripts/dev/patch_liveness.py`: um plugin pytest temporário, carregado
  com `-p`, que **não** entra na suíte default. Ele funciona assim:
  - embrulha `MonkeyPatch.setattr` e troca cada valor *callable* por um proxy que conta chamadas;
  - gera `{test_id: {nome: chamado (bool)}}` sobre os 43 arquivos do inventário (`-n 2`);
  - roda duas vezes: no commit-base, com alvo `api`, e na ponta, com alvo `<lar>`. Os dois
    conjuntos têm de ser **iguais**. Um `True` que vira `False` é patch inócuo e para a etapa.
  Nomes não-callable (`_DOCS_PATHS`, `_CLIENT_ERROR_LOG_MAX_PER_MIN`, `game_graph`) são
  verificados por **mutação**: os testes do inventário desses nomes rodam com um valor sentinela
  inválido e têm de **falhar** antes e depois.
- **R14** **Scanners de fonte cobrem os módulos novos.** Os 13 testes e a allowlist da §3.5
  passam a ler `api.py + api_core.py + api_models.py + api_presenters.py + routes/*.py`. Para isso
  existe um helper único, `tests/api_sources.py`, com `API_FILES: tuple[Path, ...]` e
  `api_source_text() -> str` (substitui `inspect.getsource(api)`). A asserção não muda (D3).
  `API_FILES` **falha alto** se houver nome de função de nível de módulo repetido entre os
  arquivos. Motivo: `tests/test_abuse_policy.py:386-404` junta as funções num dict por nome, e
  uma duplicata sobrescreveria a outra em silêncio. [F] Esse teste exige
  `owners == ["_execute_action", "game_prologue", "new_game"]` com `_enforce_owner_budget` como
  `ast.Name`. Como `_enforce_owner_budget` **não** é patchado, ele é importado por nome simples
  (`from api_core import _enforce_owner_budget`) em `routes/art.py` e `routes/turn.py`, nunca como
  `api_core._enforce_owner_budget(...)`. O executor refaz no commit-base o grep
  `getsource\(\s*api|Path\("api\.py"\)|"api\.py"\)\.read|/ "api\.py"` e anexa o resultado ao
  handoff. Oráculo: cada scanner registra antes e depois **quantos itens varreu e quantos
  achou**, e as contagens são iguais. Exemplos: handlers `except` amplos, códigos 503, chamadas
  `admin_connection(`, `with_structured_output`. As chaves de `tests/data/silent_except_allowlist.txt`
  trocam `api.py::f::n` por `<arquivo novo>::f::n`. O conjunto `(f, n)` fica igual.

### 2.4 Bundle, CI e lint

- **R15** **Bundle da Vercel inclui os módulos novos.** [F] `vercel.json:10` (`excludeFiles`) e
  `.vercelignore` não excluem `routes/` nem `api_*.py`. Esse estado fica travado por um teste
  novo, `tests/test_spec381_bundle.py`, que verifica dois pontos: nenhum glob de `excludeFiles`
  ou linha do `.vercelignore` casa com `routes/__init__.py`, `routes/turn.py` e `api_core.py`; e
  `vercel_app.app is api.app` continua (já coberto por `tests/test_spec192_vercel_packaging.py:35`).
- **R16** **Gates por caminho reconhecem os módulos novos.** Entram ao lado de `api.py` em
  `scripts/ci_eval_scope.py:29` (`FRONTEND_FILES`), `scripts/dev/eval_publish.py:30`
  (`PRODUCT_FILES`) e `scripts/project_index_ab_harness.py:40`. Os dois primeiros recebem
  `routes/` e `api_*.py` como prefixo ou conjunto. Sem isso, mudar `routes/turn.py` deixaria de
  disparar o e2e e o gate de eval.
- **R17** **Lint, por commit:** a dívida do Ruff passa para os arquivos novos sem crescer (D4).
  [F] Arquivo novo recebe todas as regras (`ruff-baseline.toml:2`), e o código movido carrega
  E402/F401/I001/B904. Por isso, cada commit que cria ou enche um módulo novo (Etapas 2–12) roda
  `bash scripts/dev/py.sh scripts/dev/ruff_baseline.py` **no mesmo commit** e confere duas regras
  antes de fechar:
  - (a) os códigos de cada arquivo novo são subconjunto de
    `["B904","E402","F401","F841","I001","UP035"]` (`ruff-baseline.toml:16`);
  - (b) a soma de violações em `ruff check --statistics` sobre `api.py` e os módulos novos é igual
    à do commit-base.
  Proibido `ruff check --fix` no código movido: o `I001` reordena import e muda a ordem de efeito
  colateral (R4). Também proibido deixar o hook `ruff format` do `.pre-commit-config.yaml`
  reformatar os módulos novos. O que vale é `ruff format --check`; se ele pedir reformatação, a
  etapa para e reporta, porque o código movido já sai formatado.
- **R21** **Montagem plana das rotas** (P0-1). [F] `app.include_router(r)` no FastAPI `0.141.1`
  põe um `_IncludedRouter` opaco em `app.routes`. Hoje, com o cron,
  `route_label('/internal/cron/jobs', routes=api.app.routes) == "other"` (provado pela revisão).
  Se o split usasse `include_router`, três coisas aconteceriam:
  - **regressão de produção sem barulho:** toda rota movida passaria a ser `"other"` em
    `rpg_http_body_too_large_total` e no log `http.body_too_large` (`services/body_limit.py:19-26`,
    `:87`; `api.py:4509,4521,4610,4619`);
  - **testes que passam vazios:** `tests/test_abuse_policy.py:78` (classe de abuso),
    `tests/test_http_error_leakage.py:52` (`_body_routes`) e
    `tests/test_spec195_reconciliation.py:417` (`not any` sobre um set vazio);
  - **falha alta:** `tests/test_http_security_headers.py:177` (`seen > 20`) e
    `tests/test_abuse_logging.py:111`.
  Correção testada pela revisão: `app.router.routes.extend(router.routes)` no ponto do bloco, via
  helper `_mount_router(router)` em `api.py`. As rotas ficam `APIRoute` planas, e OpenAPI e
  405/`Allow` ficam iguais. Diferença conhecida e aceita: `dependency_overrides_provider` vira
  `None` em vez de `app`, o que é inofensivo porque há 0 `Depends(` e 0 `dependency_overrides`. O
  cron segue com o `include_router` de hoje: mudar isso seria mudar comportamento.
  `tests/test_spec381_route_label.py` chama `route_label` com 1 path concreto de cada router novo
  e verifica que volta o template da rota, nunca `"other"`.
  **Única mudança de corpo de função permitida** (P2-5): nos 4 sites que passam
  `routes=app.routes` (`api.py:4509,4521,4610,4619`, que vão para `routes/billing.py`), trocar por
  `routes=request.app.routes`, porque `app` não existe no router (R3). É equivalente: depois de
  `reload(api)`, `app` já é o novo `app`, e `request.app` também.

### 2.5 Limpezas pós-split (commits próprios, golden antes)

- **R18** [F] **`_load_or_404`.** São 22 sites com o padrão "resolver save → carregar → 404". Eles
  usam dois textos ("Jogo não encontrado." e "Nenhum jogo salvo encontrado.") e dois loaders
  (`load_game_state` e `_load_unlocked_or_locked`). Linhas:
  `api.py:4067,4087,4107,4131,4173,4189,4202,4678,4704,4985,5059,5154,5234,6801,6926,7381,7413,7473,7535,7638,7843,7890`.
  Contrato do helper em `api_core`:
  `_load_or_404(game_id: str | None, *, detail: str = "Jogo não encontrado.", locked_read: bool = False) -> tuple[str | None, dict]`.
  Ele resolve `_resolve_save_file` e `load_game_state`/`_load_unlocked_or_locked` **na hora da
  chamada** (R11). Só substitui sites cuja sequência é exatamente essa, sem nada no meio. Sites
  com passo intermediário ficam como estão e são listados no handoff. Golden obrigatório (Etapa
  13): status e corpo (sem `request_id`) de **cada** rota afetada, com `game_id` inexistente de
  formato válido e com `game_id` omitido sem save, iguais antes e depois.
- **R19** [F] **`_art_repository` não é equivalente puro.** `api.py:5171-5172` usa defaults
  (`or "gpt-image-2-2026-04-21"`, `or "valoria-dynamic-v1"`), e `api.py:5247-5248` não usa
  (`str(profile.get("model"))` vira `"None"` se a chave faltar). Hoje o perfil tem as duas chaves
  (`data/dynamic_art_profiles.json:3-4`), então na prática não há diferença. No código, há. Só
  entra com D5.
- **R20** [F] **`_client_ip` fica.** O wrapper de `api.py:1653-1656` é preso por
  `tests/test_abuse_policy.py:158`, que procura o texto literal `"remote_ip=_client_ip(request)"`.
  Inlinear mudaria a asserção (W3). Trocar por alias no topo
  (`from services.abuse_policy import client_ip as _client_ip`) sobe um import local (R7). D6.

### Fora de escopo

- Aliases de rota sem uso (`/game/{id}/art/player/confirm`, `/auth/logout`, `/game/map` vs.
  `/data/map`) e a métrica `DEPRECATED`: vão para a SPEC-384 (§4.1 item 9 da auditoria).
- Mudar contrato, DTO, `response_model`, nome de campo ou os 18 `dict[str, Any]` do
  `GameResponse`: SPEC-385.
- Subir imports locais para o topo, trocar `_database_profile` por `is_database_profile()` (isso
  seria da SPEC-378, ver D10) e renomear rota, função de endpoint ou `operationId`.
- Dividir `routes/turn.py` (~2.500 linhas) além do que a R12 permite. Fica para uma spec futura,
  depois que os testes de AST/substring forem trocados por testes de comportamento (SPEC-379).
- `Depends()` para auth/save. Mudaria o OpenAPI (R6).
- Tocar `web/`, `services/`, `agents/`, `persistence.py` ou qualquer caminho de
  `evals/protected-paths.txt` (W5).
- Editar `ESTADO_ATUAL.md`, `ROADMAP.md`, `specs/index.yaml` e `project_index/` (o coordenador
  integra; `project_index/domains.yaml:35` e `state_ownership.yaml` citam `api.py`).

## 3. Design técnico

### 3.1 Grupos confirmados em `api.py` (03/11, antes de 367/368 pousarem)

| # | Destino | Faixa em `api.py` | Linhas | Rotas | Observação |
|---|---|---|---|---|---|
| 0 | `api.py` (fica) | 1–685, 1340–1835 (parte) | ~1.150 | 0 | boot, 8 handlers (`:149,161,192,203,221,247,255,1769`), CORS `:268`, BodyLimit `:288`, cron `:303` (segue com `include_router`), `_session_boundary :323`, `_rate_limit :1670`, `_correlation_boundary :1718` (já contém o CSP e chama `_access_log :524`), `_mount_router` |
| 1 | `api_core.py` | 308–495 (helpers), 1346–1835, 5555–5963 (ledger de operação) | ~950 | 0 | `_database_profile`, `_error_response`, authfail, telemetria e hooks, `_game_lock`, `_resolve_save_file`, `_reject_*`, rate-limit state, `QuotaExceeded`, `_enforce_owner_budget`, `_begin_state_mutation`/`_commit_state_mutation`/`_release_failed`/`_fail_operation`/`_validated_receipt`/`_op_*` (usados por equip/cartas **e** turno) |
| 2 | `api_models.py` | 1836–2135 | ~300 | 0 | DTOs compartilhados (`GameResponse`, `ActionRequest`, `CreateCharacterRequest`, `Art*`, `Equip`/`Prepare`/`Espolio`/`Loja`/`Forja`/`LevelUp`, `Visual*`). DTOs de uma rota só (`AuthRequest :686`, `CheckoutRequest :4285`, `ClientErrorReport :3581` etc.) vão com o router |
| 3 | `api_presenters.py` | 2136–3487 | ~1.350 | 0 | `format_response`, `_format_response_raw`, `_combat_block` (~250), `_world_block`, `_cards_block`, `_npcs_block`, `_factions_block`, retratos (`_portrait_*`, `_creature_art_live`) |
| 4 | `routes/auth.py` | 686–1339 | ~650 | 14 | auth, conta, `audit-export`, `account/delete` |
| 5 | `routes/ops.py` | 3488–3806 | ~320 | 4 | `/health`, `client-latency`, `client-error`, `/metrics` |
| 6 | `routes/read.py` | 3807–4249 | ~440 | 12 | mapa, state, codex, dossiers, history, glossário, simulador, preview |
| 7 | `routes/billing.py` | 4250–4734 | ~485 | 14 | conta/saldo, Stripe, Google Play, transcrição, operações/custo. **`/account/checkout/skus` (`:4291`) antes de `/account/checkout/{order_id}` (`:4452`)**: a ordem importa |
| 8 | `routes/art.py` | 4735–5275 | ~540 | 7 | prólogo, brief, quote, confirm, status, quality |
| 9 | `routes/turn.py` | 5276–5554, 5964–7404 | ~2.500 | 4 | `/game/new`, `/game/action`, `/game/death`, `/game/action/stream` + pipeline + SSE (R12) |
| 10 | `routes/play.py` | 7405–7737 | ~330 | 6 | equip, cartas/prepare, espólio, loja-cartas, forja, levelup |
| 11 | `routes/saves.py` | 7738–7925 | ~190 | 4 | saves, delete, crônica search/export |

[F] Total: 65 decoradores `@app.*` (14+4+12+14+7+4+6+4), mais as rotas do `_cron_router` e o
mount `/`. A auditoria contou 66 rotas, 7 handlers e 2 middlewares. A contagem real em 03/11 é
65 decoradores, **8** handlers (`QuotaExceeded` em `:1769`) e **5** middlewares (2
`add_middleware` + 3 `http`). `app.exception_handlers` tem 9 entradas: as 8 próprias e o default
do FastAPI. [F] `app.routes` = 65 `APIRoute` + 4 `Route` de docs + 1 `_IncludedRouter` (cron) +
1 `Mount`. Três funções carregam 2 rotas cada, e os dois decoradores ficam juntos na mesma
função: `auth_email_request` (`:951-952`), `auth_logout` (`:1274-1276`) e `confirm_player_art`
(`:5044-5045`). A Etapa 0 fecha os números pela R6(b).
[H] Os limites entre os grupos 1 e 9 (o que é ledger compartilhado e o que é só do turno) saem
do grafo de chamadas da Etapa 0. A regra é: helper chamado por 2 ou mais grupos vai para
`api_core`.

### 3.2 Ordem das rotas

`app.routes` hoje segue a ordem: docs (do `FastAPI(...)`), cron (`_IncludedRouter`, `:303`),
grupos 4→5→6→7→8→9→10→11 e o mount. Cada router entra **no ponto exato de `api.py` onde o bloco
estava**, por montagem plana (R21), e **nunca** por `include_router`:

```python
def _mount_router(router: APIRouter) -> None:
    """SPEC-381 R21: copia as APIRoute planas (include_router criaria um _IncludedRouter opaco)."""
    app.router.routes.extend(router.routes)
```

No fim, as chamadas `_mount_router(...)` ficam juntas antes do mount, na ordem 4, 5, 6, 7, 8, 9,
10, 11. O `APIRouter()` vem sem `prefix`, `tags`, `dependencies` nem `responses`, para que as
`APIRoute` criadas pelo decorador tenham os mesmos parâmetros das de hoje. A R6(b), com o tipo de
cada entrada, confere.

### 3.3 Estrutura de cada router

```python
# routes/play.py
from fastapi import APIRouter, HTTPException
import api_core  # nomes patchados: api_core._database_profile(), api_core.load_game_state(...)
from api_core import _bind_corr, _begin_state_mutation  # não patchados: nome simples
from api_models import EquipRequest

router = APIRouter()


@router.post("/game/equip")
def game_equip(
    req: EquipRequest,
): ...  # corpo idêntico, exceto o prefixo `api_core.` nos nomes patchados
```

### 3.4 Inventário de patch (Etapa 0 congela em `docs/spec381/patch_inventory.json`)

[F] Grep de 03/11, conferido pela revisão: `setattr\(\s*(api|api_mod|api_module)\s*,\s*"…"`
(de uma linha e multilinha), mais `"api._image_finance"` em `tests/test_http_idor_offline.py:217`.
São **137 chamadas + 1 string, em 43 arquivos, sobre 34 nomes**. Além delas, há leituras e
chamadas diretas dos mesmos nomes (`kind: read`), por exemplo:
- `api._execute_action(req)` (`tests/test_abuse_policy.py:373-379`);
- `api._commit_turn(` (`tests/test_bug_morte_checkpoint.py:146,169,242`; `tests/test_api_attempt_telemetry.py:96`);
- `api._game_lock(` (6×);
- `api._resolve_save_file(` (`tests/test_fase10.py:68`);
- `api._image_finance(` (`tests/test_spec196_finops.py:379,830,831`).
Lar proposto entre parênteses:

`_database_profile` (core, ~30 patches) · `load_game_state`, `save_game_state`,
`_resolve_save_file`, `_load_unlocked_or_locked`, `_game_lock`, `_require_saved`,
`_schedule_chronicle_jobs`, `_failed_pending_operation` (core) · `game_graph`, `_execute_action`,
`_run_turn`, `_commit_turn`, `_log_turn`, `_sse_log`, `_await_projection_db`, `_projection_owner`,
`_begin_turn_operation`, `_action_already_processed`, `_apply_action_options`,
`_begin_create_operation`, `_create_game` (turn) · `_creature_art_live`,
`_portrait_price_estilhas`, `_portrait_sign`, `_portrait_store`, `_npcs_block` (presenters) ·
`_guard_image_effect`, `_image_finance` (art) · `_google_play`, `_stripe_payments` (billing) ·
`_load_metrics_sql`, `_CLIENT_ERROR_LOG_MAX_PER_MIN` (ops) · `_DOCS_PATHS` (**fica** em `api.py`,
quem lê é o middleware de correlação).

Patches em **atributo de objeto** alcançado via `api`:
- `api.game_graph.invoke` (`tests/test_prompt_guard.py:211,217`; `tests/test_speech_api.py:90,93`):
  como `game_graph` é nome patchado (16×) e não é reexportado (R10), o alvo vira
  `routes.turn.game_graph.invoke` (R13, `kind: attr_object`);
- `api.GameResponse.model_validate` (`tests/test_turn_trace_logs.py:259`) e
  `api._turn_logger.info` (`tests/test_streaming.py:226`): seguros por identidade, porque esses
  nomes não são patchados e o reexport é o mesmo objeto (R9). Também entram na Etapa 0: `from api import X`
em `tests/test_abuse_logging.py:107,120`, `test_ci_eval_gates.py:140`, `test_fase2.py:303,333`,
`test_onboarding.py:110` e `test_weather_global.py:97` (só `app`, `health_check`,
`_factions_block` e `_world_block`, que são leitura e ficam reexportados). Entram ainda
`importlib.reload(api)` em `tests/test_boot_policy.py:134,136,341,347`. Depois do split, o reload
refaz `app`, handlers, middlewares e `_mount_router`, mas **não** recarrega `routes/*`. As
mesmas `APIRoute` passam a ser compartilhadas pelo `app` velho e pelo novo, o que é inofensivo,
porque nenhuma rota guarda referência ao `app`. Por isso
os routers não podem ler env no nível do módulo (hoje só `_DOCS_ON :100` e `_CORS_ORIGINS
:262`, os dois ficam em `api.py`).

### 3.5 Scanners de fonte (R14)

[F] `tests/silent_except_scan.py:16` (+ `tests/data/silent_except_allowlist.txt`, 17 chaves
`api.py::…`), `tests/test_abuse_logging.py:185`, `tests/test_abuse_policy.py:158,386,408`,
`tests/test_api_fuzz_harness.py:41` (allowlist de 503; roda no CI em `validate.yml:110`),
`tests/test_error_envelope.py:13`, `tests/test_rls_runtime_config.py:232,257-260` (conta
`admin_connection(` ≥ 3 e classifica módulos que abrem conexão; precisa classificar os novos),
`tests/test_spec299_prisoner_api.py:72`, `tests/test_spec305_perception.py:154`,
`tests/test_spec352_creature_portraits.py:409` e `tests/test_structured_output_guards.py:12`. Mais
dois, com asserção **negativa** (a revisão achou):
- `tests/test_bug_api_pending_erros.py:144` (`"{req.backstory}" not in inspect.getsource(api)`):
  passa a usar `api_source_text()`;
- `tests/test_spec361_integracao.py:324` (`getsource(api._execute_action)`): retarget para
  `routes.turn._execute_action`.
São **13** no total.
`tests/test_ci_docs_only.py` e `tests/test_beta_gameplay_gate.py:36` usam `"api.py"` como string
de caminho e não mudam.

### 3.6 Oráculos novos (Etapa 0)

- `scripts/dev/api_surface_dump.py --out <dir> [--profile legacy|hosted]`: gera `openapi.json`,
  `routes.json`, `middleware.json`, `handlers.json` e `lifecycle.json` (R6), mais
  `modules.json` (R7a), cada um num subprocesso limpo.
- `docs/spec381/before/` (congelado na Etapa 0) e `docs/spec381/importtime_before.txt`.
- `tests/test_spec381_api_surface.py` (**temporário**, R6): compara o dump vivo com
  `docs/spec381/before/`, byte a byte. Roda na suíte default (~2 s) enquanto a 381 estiver em voo
  e é **apagado na Etapa 15**.
- `tests/test_spec381_structure.py`: nenhum módulo novo importa `api` (R3); nenhum `routes/*`
  chama `getenv`/`environ` no nível do módulo; patch-alvo vivo (R13); reexport idêntico e sem
  nome religado por `global` (R5/R9); nenhum `_IncludedRouter` além do cron (R21). Fica
  permanente.
- `tests/test_spec381_route_label.py` (R21): `route_label` devolve o template, nunca `"other"`,
  para 1 path de cada router. Fica permanente.
- `scripts/dev/patch_liveness.py` (R13b): plugin pytest por `-p`, fora da suíte default.
  Gera `docs/spec381/patch_liveness_{before,after}.json`.
- `tests/test_spec381_bundle.py` (R15).
- `tests/test_spec381_not_found_golden.py` + `docs/spec381/not_found_golden.json` (R18; criado
  na Etapa 13 **antes** do helper).

## 4. Plano passo a passo

**Regras de toda etapa:**
- antes de começar, **W1 vazio** (versão revisada, auditoria §6.2) para `api.py`, os arquivos de
  teste da etapa e os scanners. A W1 olha três fontes:
  1. branches vivas: com commit à frente da `main` **e** commit nos últimos 7 dias;
  2. mudanças não commitadas em todos os worktrees, inclusive o checkout principal;
  3. `git log --since=2.days --name-only main`.
  [F] `spec-214`, de 17/10 e morta, toca `api.py`, mas fica fora pela regra dos 7 dias. Ela vai
  para a lista de branches que o dono arquiva;
- 1 commit por etapa (W4), e cada commit fica verde, **incluindo `ruff check` e
  `ruff_baseline.py --check`** (R17);
- testes do escopo com `-n 2` no máximo;
- R6, `test_spec381_structure` e `test_spec381_route_label` em todo commit;
- nenhum `ruff --fix` nem reformatação automática.

Execução: **1 executor, 1 dia, sem pausa entre etapas**. A janela de trava é curta (D8).

### Etapa 0 — Inventário e oráculo (nenhum código de produto muda)

1. Confirmar que 367 e 368 pousaram e que a W1 revisada dá **vazio** para `api.py`. Se não der,
   a spec não começa.
2. Rodar os greps da §3.4 e da §3.5 no commit-base e gravar `docs/spec381/patch_inventory.json`
   no formato `[{file, line, name, kind: setattr|string|from_import|read|attr_object|reload, lar}]`.
   Gravar também `docs/spec381/readers.json` com os `api.X` lidos fora de `tests/`.
3. Escrever `scripts/dev/api_surface_dump.py`, `scripts/dev/patch_liveness.py` e os testes da
   §3.6. Gerar `docs/spec381/before/` (legacy e hosted), 5 medições de importtime e
   `patch_liveness_before.json`. Rodar a mutação dos nomes não-callable (R13b).
4. Coordenador: W2 itens 1–3 e o catálogo de eventos no commit-base (saída A).
5. **Verificação:** `test_spec381_api_surface` verde contra o próprio base.
   `test_spec381_structure` verde com o inventário vazio de movidos.

### Etapa 1 — `tests/api_sources.py` e scanners (só testes)

1. Criar `API_FILES` (hoje = `(api.py,)`) e `api_source_text()`, e apontar os 13 scanners para
   eles (R14). Registrar as contagens de cada scanner em `docs/spec381/scanner_counts_before.json`.
2. **Verificação:** os 13 testes verdes e as contagens iguais às do base.

### Etapa 2 — `api_models.py`

1. Mover os DTOs compartilhados (§3.1 grupo 2). `api.py` reexporta os que tests ou consumidores
   leem. Nenhum DTO está no inventário de patch.
2. **Verificação:** R6 byte-igual. Atenção: nomes de componente do OpenAPI e `model_rebuild`.
   Rodar testes que importam `GameResponse`/`ActionRequest`.

### Etapa 3 — `api_presenters.py`

1. Mover o grupo 3. Retargetar `_creature_art_live`, `_portrait_price_estilhas`, `_portrait_sign`
   e `_portrait_store` nos testes (`test_spec352_*`, `test_spec363_portrait_offer`,
   `test_spec364_portrait_debit`). Os sites de arte que continuam em `api.py` chamam
   `api_presenters._portrait_store(...)` (R11). `_npcs_block` segue a exceção da R10.
2. **Verificação:** R6. `test_spec381_structure`. Testes do inventário desses 5 nomes, mais
   `tests/test_spec304_playtest.py`, `test_fase2`, `test_weather_global`, `test_spec345_*` e
   `test_spec354_*`.

### Etapa 4 — `api_core.py`

1. Mover os helpers compartilhados (§3.1 grupo 1, conjunto fechado pelo grafo da Etapa 0). No
   mesmo commit: todo leitor, inclusive os middlewares e as rotas que ainda estão em `api.py`,
   passa a `api_core.<nome>` para os nomes patchados. Os testes desses nomes são retargetados
   (R13). Os efeitos colaterais ficam em `api.py` (R4). O estado mutável tem lar único (R5).
2. **Verificação:** R6, R7a e `test_spec381_structure`. Testes do inventário de
   `_database_profile`, `load_game_state`, `save_game_state`, `_resolve_save_file` e `_game_lock`
   (~35 arquivos).

### Etapas 5–11 — Um router por commit, do menor risco ao maior

Cada etapa segue os mesmos passos:
1. criar `routes/<x>.py` e mover o bloco;
2. chamar `_mount_router(router)` no lugar do bloco (R21);
3. retargetar os patches, leituras e chamadas dos nomes que mudam de lar (R13);
4. regenerar a baseline do Ruff (R17);
5. rodar R6, a estrutura, o `route_label` e os testes que tocam as rotas do grupo.
Na Etapa 8 (`billing`) entra a troca `app.routes` → `request.app.routes` (R21). Ordem: **5** `saves` → **6** `play` → **7** `art` → **8** `billing` → **9** `read` →
**10** `ops` → **11** `auth`.

### Etapa 12 — `routes/turn.py` (a mais arriscada, por último)

1. Mover `/game/new`, `/game/action`, `/game/death`, `/game/action/stream`, o pipeline e o SSE
   **juntos** (R12). Retargetar os 15 nomes do lar `turn`. `api.py` deixa de ligar o nome
   `game_graph`, mas mantém `import main` na mesma posição (`api.py:68`) para não mudar a ordem
   de import (R7a). `game_graph` passa a ser ligado em `routes/turn.py`.
2. **Verificação:** R6, R7 (a e b), `test_spec381_structure`, `tests/test_streaming.py`,
   `test_abuse_policy`, `test_hardening_persistencia_sse`, `test_latency_metrics_compat`,
   `test_turn_trace_logs`, `test_error_envelope`, `test_spec293_rotulo_faccao`,
   `test_api_attempt_telemetry` e `test_bug_morte_checkpoint`. Depois, rodar **uma vez** todos
   os ~154 arquivos de `tests/` que citam `api.` com `-n 2`, em background com timeout.

### Etapa 13 — Golden de 404 e `_load_or_404` (não é puro na aparência; R18)

1. Primeiro commit: `tests/test_spec381_not_found_golden.py` +
   `docs/spec381/not_found_golden.json` gerado no código **antes** do helper.
2. Segundo commit: o helper e as substituições. O golden não muda. Os sites com passo
   intermediário ficam como estão e vão listados.
3. (Só com D5 = unificar) Terceiro commit: `_art_repository`, com teste que fixa os dois
   comportamentos.

### Etapa 14 — Gates por caminho

1. R16 (`ci_eval_scope`, `eval_publish`, `project_index_ab_harness`). A baseline do Ruff já foi
   regenerada em cada etapa (R17); aqui só se confere a soma final contra o commit-base.
2. **Verificação:** `ruff check` e `ruff format --check` verdes; `ruff_baseline.py --check`
   verde.

### Etapa 15 — Pouso

1. Coordenador: W2 de novo na ponta (saída B) e `evals compare --current B --baseline A` sem
   diferença. Playtest com a mesma contagem e catálogo de eventos byte-igual. Executor:
   `patch_liveness_after.json` igual ao `before` e mutação dos não-callable repetida (R13b).
   Por último, um commit apaga `tests/test_spec381_api_surface.py`; os dumps ficam em
   `docs/spec381/` só como evidência (R6).
2. Smoke local real: `uv run uvicorn api:app --port 8000` e `python api.py` (`__main__`), cada um
   seguido de `bash scripts/smoke_api.sh 8000` e `bash scripts/dev/py.sh scripts/smoke_local_profile.py`.
3. [F] **O e2e do web não serve de oráculo aqui.** `web/playwright.config.ts:52-60` sobe só o
   Vite, e o backend é o falso de `web/e2e/fixtures.ts`. Como `web/` não muda,
   `npm run test:e2e -- --workers=1` roda 1× só como não-regressão do front, sem valor de prova
   para a API.
4. Revisão independente (W7, Sol). O revisor refaz R6 e R7a por conta própria e confere o
   diff do `patch_liveness`. Por amostragem, escolhe 3 nomes do inventário e troca o alvo de
   volta para `api.X`: o teste tem de **falhar** com `AttributeError`.
5. §6 em staging.

## 5. Critérios de aceite

- [ ] R6: dumps `legacy` e `hosted` byte-iguais a `docs/spec381/before/` (com tipo de rota e 9 handlers); `test_spec381_api_surface` apagado no fim
- [ ] R21: nenhum `_IncludedRouter` novo; `route_label` devolve o template para 1 path de cada router
- [ ] R7: conjunto de `sys.modules` só com os módulos novos; importtime ≤ 105 % (mediana de 5)
- [ ] R3/R4/R5: `test_spec381_structure` verde (sem `import api` nos módulos novos, efeitos colaterais em `api.py`, estado com identidade, `_FAKE_GOOGLE` não reexportado)
- [ ] R9–R13: os 34 nomes com lar único e patch vivo; nenhum teste com asserção alterada (`git diff` de `tests/` só mostra prefixo `api.`→`<lar>.`, import e `API_FILES`)
- [ ] R13b: `patch_liveness` antes = depois; mutação dos não-callable falha antes e depois
- [ ] R14: contagens dos 13 scanners iguais ao base
- [ ] Catálogo de eventos byte-igual (R8)
- [ ] R15/R16/R17: bundle, gates por caminho e baseline do Ruff conforme
- [ ] R18: golden de 404 igual; lista de sites não convertidos no handoff
- [ ] `api.py` ≤ ~1.300 linhas; maior módulo novo é `routes/turn.py`
- [ ] W2 completo: suíte, evals `compare` sem diferença, playtest com mesma contagem
- [ ] Revisão independente (Sol) aprovada, com a prova de patch vivo
- [ ] Saves antigos carregam (nenhuma mudança em `persistence.py`; `test_spec265_legacy_mana_saves` e afins verdes)
- [ ] §6 executado em staging

## 6. Smoke test real (staging)

Deploy via `/staging-deploy` (flags de staging atuais, sem ligar nada novo) e depois, com LLM
real (5 requests de LLM, dentro da quota):

1. `GET /health`: 200, `profile`/`hardened` iguais ao último deploy. O cold start do 1º request
   vai para o handoff (comparar com 19–59 s).
2. Login → `POST /game/new`: 200, `GameResponse` com `player`, `world` e `combat` presentes.
3. `POST /game/action`: 200 com narração. Depois `GET /game/state`: turno avançou.
4. `POST /game/action/stream`: eventos SSE na ordem de sempre, até o `done`. Header
   `X-Accel-Buffering: no` presente (`vercel.json:13-26`).
5. Uma rota de cada router novo sem LLM: `GET /auth/config`, `GET /account/balance`,
   `GET /game/history?game_id=…`, `GET /game/saves`, `POST /game/equip` (item inválido → 4xx
   igual ao de antes) e `GET /metrics` sem token (401/404 igual ao de antes).

## 7. Riscos & compatibilidade

- **Rota opaca via `include_router`:** é regressão de métrica em produção (`route_label` →
  `"other"`) e deixa 3 testes vazios. Coberto por R21 (montagem plana), pelo tipo de rota na
  R6(b) e por `test_spec381_route_label`.
- **Monkeypatch inócuo** (o maior risco): coberto por R10 (sem reexport, falha alto), R11
  (leitura no lar), R13 (teste estático), R13b (vivacidade dinâmica e mutação) e a prova do
  revisor.
- **Scanner inócuo:** coberto por R14 (`API_FILES` único, 13 scanners, contagem igual, falha em
  nome duplicado).
- **Golden congelando a API para sempre:** R6 é temporário e apagado na Etapa 15.
- **Commit vermelho por lint:** a baseline é regenerada por commit (R17).
- **Ciclo de import / execução dupla em `__main__`:** R3 e o smoke com `python api.py`.
- **Cold start da Vercel:** R7 (conjunto de módulos e tempo) e o 1º request no §6. Nenhum import
  sobe.
- **Ordem de middleware e de handler:** todos ficam em `api.py`, sem mudar de linha relativa.
  R6(c)(d) confere.
- **Startup events / lifespan:** hoje não existem. R6(e) trava; um `APIRouter` com `on_startup`
  acidental muda o dump.
- **Ordem de rota:** `/account/checkout/skus` antes de `/account/checkout/{order_id}`; mount `/`
  por último (`tests/test_spec267_static_mount.py`). R6(b) e §3.2.
- **`importlib.reload(api)`** (`tests/test_boot_policy.py`): routers não são recarregados. Por
  isso não podem ler env no nível do módulo (§3.4).
- **Conflito com outras sessões:** W1 antes de cada etapa, a janela de 1 dia e a trava anunciada
  (D8).
- **Saves e MockLLM:** sem mudança de schema nem de agente. MockLLM e FallbackLLM continuam
  iguais.

## 8. Decisões do dono

- **D1 — Nomes.** `routes/` + `api_core.py` + `api_models.py` + `api_presenters.py`
  (recomendado). Alternativa: `api_routes/`. `api_core` não constava do pedido original, mas é
  inevitável: sem ele, os routers teriam de importar `api` (ciclo, R3).
- **D2 — SSE junto com o pipeline do turno** em `routes/turn.py` (~2.500 linhas), em vez de um
  módulo SSE separado. O motivo está na R12: um teste de AST mais 3 testes que patcham
  `_execute_action` e exercitam o stream. Recomendado: aceitar e dividir depois da SPEC-379.
- **D3 — Scanners leem os arquivos novos** (R14). Isso é mudança de *alvo*, não de asserção.
  Recomendado: tratar como permitido pela W3.
- **D4 — Lint.** (a) Transferir a dívida do Ruff para os arquivos novos sem crescer, com a
  baseline regenerada a cada commit (recomendado, R17); ou (b) corrigir a dívida no código movido. A opção (b) não é pura: o B904
  muda o `__cause__` e o I001 muda a ordem de import.
- **D5 — `_art_repository`.** (a) Fora da 381 (recomendado: os defaults divergem, R19); ou
  (b) unificar com defaults, num commit não-puro com teste que fixa os dois lados.
- **D6 — `_client_ip`.** Manter o wrapper (recomendado; R20).
- **D7 — `_load_or_404` nesta spec** (R18, golden antes) ou adiado. Recomendado: nesta spec,
  depois do split.
- **D8 — Janela de trava de `api.py`.** Enquanto a 381 estiver em voo (~1 dia), nenhuma outra
  spec ou sessão toca `api.py`, os testes do inventário ou os scanners. O coordenador anuncia isso
  em `ESTADO_ATUAL.md` § Bloqueios. A 381 só começa com W1 vazio.
- **D9 — Oráculo HTTP.** Aceitar que o e2e do web (backend falso) **não** prova a API. A prova
  fica com R6, os testes `TestClient`, o smoke local real e o §6.
- **D10 — Fronteira com a SPEC-378.** Os helpers de `api.py` (`_load_or_404`,
  `_database_profile`/`is_database_profile`) ficam com a 381, e a 378 não toca `api.py`. Se a
  378 trocar `_database_profile` antes, os ~30 patches desse nome mudam de alvo duas vezes.

## Resposta à revisão (`handoffs/SPEC-381-independent-review.md`, CHANGES_REQUIRED)

Todos os P0/P1 foram aplicados, e todos os P2 que dependiam só desta spec também.

| ID | Resposta |
|---|---|
| P0-1 | **Aplicado.** Nova R21: montagem plana por `_mount_router` (`app.router.routes.extend`), proibição de `include_router` nos routers novos e tipo de cada entrada na R6(b). Teste novo `test_spec381_route_label`. §3.2 reescrita. O cron fica como está (mudar seria mudar comportamento) |
| P1-1 | **Aplicado.** R6 é oráculo temporário e não contrato. `test_spec381_api_surface` é apagado na Etapa 15. A fonte única de contrato fica para a SPEC-385 (DEFER) |
| P1-2 | **Aplicado.** R17: baseline regenerada e conferida (subconjunto e soma) em cada commit. Proibidos `--fix` e reformatação automática pelo hook; vale só `ruff format --check` |
| P1-3 | **Aplicado.** 13 scanners na §3.5/R14, `api_source_text()` no lugar de `inspect.getsource(api)` e grep de conferência no handoff |
| P1-4 | **Aplicado.** R13 cobre leitura, chamada e atributo de objeto (`kind: read`/`attr_object`). §3.4 corrigida: `api.game_graph.invoke` → `routes.turn.game_graph.invoke` |
| P1-5 | **Aplicado.** R5: `_FAKE_GOOGLE` sai dos reexports. O teste de identidade recusa nome com `global` no lar |
| P1-6 | **Aplicado.** Nova R13b: plugin `scripts/dev/patch_liveness.py` (contador de chamadas, antes = depois) e mutação para os não-callable |
| P2-1 | **Aplicado** pela W1 revisada (branches sem commit há mais de 7 dias ficam fora). Arquivar `spec-214` fica com o coordenador ou o dono |
| P2-2 | **Aplicado.** R6(d) e §3.1: 8 handlers próprios + 1 default = 9 entradas |
| P2-3 | **Aplicado.** R2 e §3.1: CSP e access log estão dentro do `_correlation_boundary`; nenhum middleware novo |
| P2-4 | **Aplicado.** R14: `API_FILES` falha com nome de função duplicado; `_enforce_owner_budget` importado por nome simples |
| P2-5 | **Aplicado.** R21: `request.app.routes` é a única mudança de corpo permitida (4 sites de billing) |
| P2-6 | **Aplicado.** R8: catálogo de eventos byte-igual. O script não tem `--check`, então a prova é rodar o gerador e `git diff --exit-code` |
| P2-7 | **Aplicado.** R5: registrado como diferença aceita, com verificação na mesma sessão |
| P2-8 | **Não aplicado aqui:** o texto fica na SPEC-384, que esta tarefa não pode editar. O coordenador alinha "router SSE" → `routes/turn.py` |

Rejeições: nenhuma.
