# SPEC-337 — Testes HTTP dinâmicos de segurança (headers, cookies, CORS, vazamento, IDOR) + correções L1/L2/L4

> **Status:** `approved` (aprovada em 2026-10-27 pelo dono: "escreva as specs e depois implemente"; as 6 decisões do discovery de 27/10 são definitivas, ver §8)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Depende de:** nenhuma em código.
> **Desbloqueia:** SPEC-338 (fuzz Schemathesis reutiliza a fixture de dois principals e o check de headers/vazamento desta spec).

---

## 1. Contexto & Objetivo

A API tem defesas HTTP espalhadas: headers no middleware de correlação, cookies de sessão, CORS, CSRF por Origin, envelope de erro e filtro de dono no store. Cada uma tem testes pontuais. Não existe uma bateria que exercite **cada superfície HTTP real** (SPA estática, 404 fora da API, 413, 422, 429, 500, stream) e confira o conjunto. As lacunas:

- **Headers:** `_correlation_boundary` (`api.py:607-668`) aplica `X-Request-ID`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, `X-Frame-Options`, `Cache-Control: no-store` e CSP com `setdefault` (`api.py:651-667`). Um handler pode sobrescrever. HSTS só sai com `RPG_COOKIE_SECURE=1` (`api.py:662-665`). Há testes só em `/health` e `/game/saves` (`tests/test_surfaces_221.py:87-103`). Nenhum teste cobre SPA, 404 fora da API, 500 ou stream. O mount da SPA só existe se `web/dist` existir (`api.py:7161-7163`), e o CI roda o pytest antes do `npm run build` (`.github/workflows/validate.yml:64` × `:93`).
- **Cookies:** os atributos vêm de `cookie_settings` (`services/auth_sessions.py:86-92`), do CSRF (`api.py:759-768`), de `rpg_recent` (`api.py:857-868`) e de `rpg_deletion` (`api.py:1197-1205`). As limpezas estão em `api.py:1000-1004` e `:1257-1261`. Nenhum teste lê o `Set-Cookie` cru, cookie por cookie, em login, refresh, reauth, delete e logout.
- **CORS:** `RPG_CORS_ORIGINS` tem default localhost e usa `allow_credentials=True` (`api.py:247-268`). O teste existente checa só a configuração de boot (`tests/test_boot_policy.py`). Nenhum teste confere `Access-Control-Allow-Origin` (ACAO), preflight negado ou o `origin_denied` do CSRF (`services/auth_sessions.py:68-75`, chamado em `api.py:324-333`).
- **IDOR:** o filtro por dono existe (`infrastructure/local_adapters.py:134-139`; `postgres_turns.py` sempre `owner_id=%s`). Nenhum teste percorre **todas** as rotas com id usando dois principals.
- **RLS fora do CI:** `scripts/audit_local_gate.py:54-71` roda uma lista fixa de arquivos. `tests/test_rls_local.py` e `tests/test_storage_security_local.py` não estão nela, então a RLS real não roda no job `audit-local` (`.github/workflows/audit-local.yml:47`).

O mapeamento achou três bugs pequenos (nenhum IDOR entre tenants). Esta spec os corrige com teste vermelho antes:

- **L1 (baixo-médio):** `DELETE /game/save/{id}` consulta o recibo **sem** `kind`/`game_id`/`request_hash` (`api.py:7031-7034`). Com isso, a validação de `PostgresTurnCoordinator.receipt` (`infrastructure/postgres_turns.py:648-662`) é pulada. Se o cliente reusa a `Idempotency-Key` de um turno já concluído, recebe 200 com o recibo daquele turno (um `GameResponse` inteiro) e nada é apagado. O handler de exceção repete o problema na segunda consulta (`api.py:7052`).
- **L2 (baixo):** `POST /game/{g}/art/{gen}/quality` (`api.py:4724-4752`) chama `DynamicArtRepository.set_quality`, que filtra só `generation_id` + `owner_id` (`services/dynamic_art.py:126-134`). Ele não confere se `gen` pertence a `g`, diferente do `GET` irmão (`api.py:4667`).
- **L4 (baixo):** o 422 devolve `jsonable_encoder(exc.errors())` (`api.py:171`). No Pydantic v2 cada erro traz `input` (e às vezes `ctx`/`url`), então uma senha curta enviada a `/auth/signup` volta ecoada no corpo da resposta. O cliente web lê só `loc` e `msg` (`web/src/http.ts:43-56`).

**Objetivo:** uma bateria offline (no `pytest` default) e uma local (stack Supabase, no `audit-local`) que provem as defesas HTTP superfície por superfície e rota por rota, mais as três correções.

## 2. Requisitos

### Headers
- **R1 — conjunto mínimo em toda resposta.** Em toda superfície da tabela abaixo, a resposta tem:
  - `X-Request-ID` não vazio;
  - `X-Content-Type-Options: nosniff`;
  - `Referrer-Policy: same-origin`;
  - `Permissions-Policy: camera=(), microphone=(self), geolocation=()`;
  - `X-Frame-Options: DENY`;
  - `Content-Security-Policy == api.CONTENT_SECURITY_POLICY`, exceto nos caminhos de `api._DOCS_PATHS` (`api.py:491`), que **não** têm CSP.

  Superfícies: `GET /health`; `GET /` e `GET /assets/x.js` da SPA (fixture com `StaticFiles` em `tmp_path`); `GET /nao-existe` (404 fora da API); 404 da API (`GET /game/state?game_id=<uuid inexistente>`); 422 (`POST /auth/login` com corpo inválido); 413 (corpo acima do `BodyLimit`); 429 (rate limit ligado na fixture); 500 forçado (handler que levanta); `POST /game/action/stream` (`api.py:6734`); perfil DB: 401 sem sessão e 403 `origin_denied`.
- **R2 — `Cache-Control: no-store`** em toda resposta de `/game*`, `/account*` e `/auth*` (incluindo 4xx/5xx) e em `/data/map?game_id=…`. **Não** sai em `/data/options` nem nos assets da SPA.
- **R3 — HSTS** igual a `max-age=63072000; includeSubDomains` em todas as superfícies do R1 quando `RPG_COOKIE_SECURE=1`, e ausente quando não.
- **R4 — handler não enfraquece header.** Varredura em `app.routes`: nenhuma resposta das superfícies do R1 traz `X-Frame-Options` diferente de `DENY` nem CSP diferente da constante. Isso pega um `setdefault` vencido por um handler.

### Cookies
- **R5 — atributos por cookie, lidos do `Set-Cookie` cru** (`response.headers.get_list("set-cookie")`), em login, refresh, reauth e `account/delete`, com `RPG_COOKIE_SECURE` em 0 e em 1:

  | Cookie | HttpOnly | SameSite | Path | Max-Age |
  |---|---|---|---|---|
  | `rpg_access` | sim | Lax | `/` | — |
  | `rpg_refresh` | sim | Strict | `/auth/refresh` | — |
  | `rpg_csrf` | **não** | Strict | `/` | — |
  | `rpg_recent` | sim | Strict | `/` | 300 |
  | `rpg_deletion` | sim | Strict | `/account/delete` | 604800 |

  Para todos os cookies: nenhum tem `Domain`, e `Secure` aparece se e só se `RPG_COOKIE_SECURE=1`.
- **R6 — limpeza com o mesmo Path.** `POST /auth/logout` e `account/delete` emitem `Max-Age=0` (ou `expires` no passado) com o **mesmo Path** em que o cookie foi criado. Um Path diferente não apaga o cookie no navegador.
- **R7 — legacy sem cookie de sessão.** No perfil legacy, `/auth/login`, `/auth/refresh` e `/auth/signup` respondem 404 (`api.py:774-775`) e nenhum `Set-Cookie` sai.

### CORS e Origin
- **R8 — ACAO só para origem listada.**
  - Com `Origin: http://localhost:5173` (default): `Access-Control-Allow-Origin` igual à origem, `Access-Control-Allow-Credentials: true` e `Vary` contendo `Origin`.
  - Com `Origin: https://evil.example`: nenhum `Access-Control-Allow-Origin`.
  - Nunca sai `Access-Control-Allow-Origin: *`.
- **R9 — preflight.** `OPTIONS /health` com origem listada e `Access-Control-Request-Method: POST` responde 200 com o método em `Access-Control-Allow-Methods`. Respondem 400 sem `Access-Control-Allow-Origin`:
  - origem não listada;
  - método `PUT`;
  - header pedido fora da allowlist (`x-evil`).
- **R10 — Origin no CSRF (perfil DB).** `POST /game/equip` com CSRF válido:
  - `Origin` não listada → 403 `origin_denied`;
  - sem `Origin` → 403 `origin_denied`;
  - `Origin: null` → 403 `origin_denied`;
  - origem listada → passa da fronteira (status ≠ 403).

### Vazamento em erro
- **R11 — corpo malformado não vaza.** Para **cada** `APIRoute` com corpo, nos perfis legacy e DB-offline, enviar:
  - `b"{"`;
  - JSON do tipo errado (`[]`);
  - string de 300 KB.

  Status nunca é 500 (exceto o 413 do `BodyLimit`). O corpo nunca contém `Traceback`, `File "`, `site-packages`, `C:\`, `/home/`, `/tmp/`, `psycopg`, `SQLSTATE`, `select ` (case-insensitive) ou o valor do `RPG_SESSION_SECRET`. Valem também as rotas de corpo cru: `/payments/stripe/webhook`, `/account/transcriptions`, `/auth/refresh`, `/auth/logout`.
- **R12 — 500 genérico.** Um handler que levanta `RuntimeError("segredo-interno C:\\x")` gera 500 com corpo exatamente `{detail:"internal_error", code:"internal_error", request_id:<igual ao header>}`, sem a mensagem nem o caminho.
- **R13 — L4: 422 sem eco de entrada.** Todo item de `detail` no 422 tem só `type`, `loc` e `msg`, sem `input`, `ctx` nem `url`. Prova: `POST /auth/signup` com `password="curta-XYZ"` → a string `curta-XYZ` não aparece no corpo. O formato `{detail:[…], code:"validation_failed", request_id}` (`api.py:171-173`) continua.

### IDOR
- **R14 — matriz offline com dois principals.** Fixture `two_principals`: perfil DB offline (`RPG_RUNTIME_PROFILE=local`), `FileGameStore` + coordenador fake + `MemoryRateLimiter`, e identidade com tokens `a`/`b`. O principal **B** tenta cada rota com o `game_id` de A. Resultado: 404 (ou 403/409 genérico onde a rota já responde assim), corpo sem nenhum campo do estado de A (nome do personagem semeado) e o estado de A inalterado no store depois de cada mutação. Rotas cobertas:
  - por query: `/game/state`, `/game/map`, `/game/codex`, `/game/codex/dossiers`, `/game/history`, `/game/chronicle/export`, `/data/map?game_id=`;
  - por body: `/game/action`, `/game/action/stream`, `/game/equip`, `/game/cards/prepare`, `/game/levelup`, `/game/death`, `/game/chronicle/search`;
  - por path: `DELETE /game/save/{id}`, `/game/{id}/audit-export`, `/game/{g}/operations/{op}`, `/game/{g}/operations/{op}/cost`, `/game/{g}/art/quote`, `/game/{g}/art/{gen}`, `/game/{g}/art/{gen}/quality`.

  Rotas que dependem de Postgres (`runtime.resources[0]`) recebem um repositório fake por monkeypatch. Se nem isso der, a rota fica só na matriz local (R16) e a omissão vai listada no docstring do teste.
- **R15 — controle positivo.** O próprio A recebe 200 em ao menos `/game/state`, `/game/history` e `/game/saves` (prova de que a fixture lê o store trocado). Sem isso, um 404 em B não prova nada.
- **R16 — matriz local (RLS + GoTrue reais).** `tests/test_http_idor_local.py` (`pytestmark = [infra_local, security_local]`) cria dois usuários confirmados (`tests/fakes/local_auth.py:28-48`). A cria uma campanha via `/game/new`, como em `tests/test_mutation_api_local.py:18-56`. B repete a matriz do R14 contra a API local (`RPG_AUDIT_BROWSER_URL`) e recebe 404/403/409, sem nenhum dado de A. Inclui `/account/checkout/{order_id}` com um `order_id` de A, se o fluxo local permitir criar o pedido sem rede; senão fica documentado no docstring.

### Correções
- **R17 — L1.** O `DELETE /game/save/{id}` no perfil DB valida o recibo com `kind="delete"`, `request_hash=sha256("delete:{game_uuid}")` e `game_id=None`, nas duas consultas (antes do `claim` e no `except Conflict`). Para isso: calcula o digest **antes** e usa `_validated_receipt` (`api.py:5136-5149`).
  - **Atenção:** `game_id=None`, e não o `game_uuid` sugerido no discovery. O `claim` do delete grava `game_id=None` de propósito (`api.py:7040`; `commit_delete` exige isso em `postgres_turns.py:583-584`, porque o recibo sobrevive ao cascade). Passar `game_uuid` faria **todo** retry legítimo dar 409. O alvo fica preso pelo hash.
  - Resultado esperado: (a) a key de um turno concluído reusada no DELETE → 409 `operation_request_mismatch`, e a campanha continua existindo; (b) a key de um delete de X reusada para Y → 409; (c) o retry do mesmo delete → 200 `{"ok": true}`, sem segundo efeito.
- **R18 — L2.** `set_quality` recebe `game_id` e filtra `and game_id=%s` no `UPDATE`, que segue atômico (`services/dynamic_art.py:126-134`). O endpoint passa `uuid.UUID(state["game_id"])`. Geração de outra campanha do mesmo dono → mesmo 409 `"Arte não disponível para avaliação."` de hoje (sem oráculo novo), e a linha não muda. `generation_id` que não é UUID → 409, como hoje.
- **R19 — L4.** `_validation_exception_handler` (`api.py:155-174`) monta `detail` como `[{"type", "loc", "msg"}]` a partir de `exc.errors()`, sem `input`/`ctx`/`url`. O log continua só com `loc` (`api.py:162-169`).

### Gate local
- **R20 — RLS no `audit_local_gate`.** A lista de `scripts/audit_local_gate.py:58-70` passa a incluir `tests/test_rls_local.py`, `tests/test_storage_security_local.py` e `tests/test_http_idor_local.py`. O gate injeta no ambiente do pytest `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` e `SUPABASE_SERVICE_ROLE_KEY`, lidos de `_supabase_status()`, como em `scripts/start_local_api.py:37-39`. Sem isso, `test_storage_security_local.py` pula em silêncio (`:28-29`).
- **R21 — skip não passa no gate.** O gate lê o `results.xml` e devolve código ≠ 0 se algum teste desses três arquivos ficou `skipped`. A RLS precisa de fato rodar.

### Fora de escopo
- **L3:** `load_game_state` engole qualquer exceção do store e devolve `None`, então um banco fora do ar vira 404 em vez de 5xx (`persistence.py:875-886`). Vai registrado em §7, sem correção.
- **Preflight sob `_session_boundary` (decisão 5, só documentar).** O `_session_boundary` (`api.py:308-337`) fica **fora** do CORS (o `CORSMiddleware` é o mais interno, `api.py:253`) e exige principal até em `OPTIONS`. Um preflight cross-origin em `/game*` no perfil DB tomaria 401 sem cabeçalhos CORS. Hoje não afeta ninguém: a SPA é same-origin, e o Android carrega o site hospedado (`web/capacitor.config.ts:3-6`). Sem teste e sem correção nesta spec.
- Fuzz gerado por schema (SPEC-338). Mudar a política de CSP, Permissions-Policy ou cookies. Rate limit por rota. Pentest externo.

## 3. Design técnico

**Arquivos novos (testes)**
- `tests/fakes/two_principals.py`. Ele não define testes, então não entra na coleta do pytest (`testpaths = ["tests"]` coleta só `test_*.py`).
  - `@pytest.fixture two_principals(monkeypatch, tmp_path) -> TwoPrincipals`, com os campos `client_a`, `client_b`, `a: Principal`, `b: Principal`, `store: FileGameStore`, `coordinator`, `game_a: UUID` e `seed_name: str`.
  - O que a fixture faz:
    - `monkeypatch.setenv("RPG_RUNTIME_PROFILE", "local")`. Precisa ser o env, e não só `api._database_profile`, porque `persistence.load_game_state` lê o env direto (`persistence.py:843`).
    - `RPG_SESSION_SECRET` com 32 chars e `RPG_AUTH_CAPTCHA_REQUIRED=0`.
    - Monkeypatch de `infrastructure.runtime.get_runtime` para um `SimpleNamespace` com `identity_verifier`, `rate_limiter=MemoryRateLimiter()`, `game_store=FileGameStore(tmp_path/"games")`, `turn_coordinator=FakeTurnCoordinator()`, `resources=()`, `memory_store=None` e `blob_store`. O padrão é o de `tests/test_account_lifecycle_security.py:20-83`.
    - Cada client leva o cookie `rpg_access=a|b`, CSRF assinado (`tests/test_session_hardening.py:77-80`) e `Origin: http://localhost:5173`.
  - `game_a` é semeado em duas fases: um `/game/new` legacy (MockLLM) gera um estado válido, e esse estado vai para `store.create(a, state)`. Assim a fixture não depende de builder privado.
  - `FakeTurnCoordinator(InProcessTurnCoordinator)` acrescenta `receipt(principal, op, *, game_id=None, kind=None, request_hash=None)` com **a mesma** semântica de `postgres_turns.py:641-663`. Recibo de outro dono = `None`. Com `kind` informado e divergência de kind/hash/game_id (menos `new_game`) → `Conflict`. Também acrescenta `commit_delete(principal, claim, game_id, *, receipt)`, que exige `claim.game_id is None`, chama `store.delete` (filtro de dono), levanta `NotFound` se não apagou e grava o recibo. Registra as chamadas (`calls`) para os asserts.
  - `spa_mount` (fixture): se já houver um mount `frontend`, usa esse. Senão, cria `tmp_path/dist/index.html` e `assets/x.js` e insere `Mount("/", StaticFiles(..., html=True))` em `api.app.router.routes`. Remove no teardown.
  - `forbidden_leak(body: str) -> list[str]`: helper puro com a lista do R11, reutilizado pela SPEC-338.
  - `assert_security_headers(response, *, path: str, hsts: bool) -> None`: helper puro do R1–R3, reutilizado pela SPEC-338.
- `tests/test_http_security_headers.py` cobre R1–R4.
- `tests/test_http_cookie_flags.py` cobre R5–R7. Reusa a identidade fake de `account_client`, extraída para `two_principals.py` ou importada.
- `tests/test_http_cors.py` cobre R8–R10.
- `tests/test_http_error_leakage.py` cobre R11–R13. Itera `[r for r in api.app.routes if isinstance(r, APIRoute) and r.include_in_schema and r.body_field]` mais a lista fixa de corpo cru.
- `tests/test_http_idor_offline.py` cobre R14, R15 e os testes de L1/L2 offline.
- `tests/test_http_idor_local.py` cobre R16 e os testes de L1/L2 contra Postgres real (`pytestmark = [pytest.mark.infra_local, pytest.mark.security_local]`, skip sem `RPG_AUDIT_BROWSER_URL`).

**Arquivos alterados (produto)**
- `api.py:7011-7060` (L1): calcula o `digest` antes da primeira consulta. As duas consultas viram `_validated_receipt(runtime.turn_coordinator, principal, operation_id, game_id=None, kind="delete", request_hash=digest)`, com a proteção `callable` de hoje para coordenadores sem `receipt`.
- `api.py:4743-4747` + `services/dynamic_art.py:126-134` (L2): `set_quality(self, principal: Principal, generation_id: UUID, *, game_id: UUID, approved: bool) -> None`, com `where generation_id=%s and owner_id=%s and game_id=%s and status in (...)`. O único chamador é `api.py:4743`.
- `api.py:155-174` (L4): `detail = [{"type": e.get("type"), "loc": list(e.get("loc", ())), "msg": str(e.get("msg", ""))} for e in errors]`. Sai o `jsonable_encoder`, porque os campos já são serializáveis.
- `scripts/audit_local_gate.py` (R20/R21): três arquivos novos na lista; env do Supabase vindo de `_supabase_status()` (import de `scripts.start_local_api`); depois do pytest, faz o parse de `results.xml` (`xml.etree`) e devolve 1 se algum `testcase` desses arquivos tiver `<skipped>`.

**Sem schema novo, sem migração, sem mudança de contrato público** além de o 422 perder `input`/`ctx`/`url` (o cliente não lê, `web/src/http.ts:50-53`).

## 4. Plano passo a passo

### Etapa 0 — fixture e controle positivo (valida a hipótese do store)
1. **Testes:** `tests/test_http_idor_offline.py::test_owner_reads_own_game_through_swapped_store` (R15): A recebe 200 em `/game/state`, `/game/history` e `/game/saves`, e o nome semeado aparece. `test_fixture_is_database_profile`: `api._database_profile()` é verdadeiro e um client sem cookie recebe 401 em `/game/state`.
2. **Implementação:** `tests/fakes/two_principals.py`. Se o 200 de A falhar porque falta algo no runtime fake, completar a fixture. Nunca relaxar o teste. Achado que exija mudar produto: parar e registrar no hand-back.
3. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_http_idor_offline.py -q -k "owner_reads or fixture_is"`.

### Etapa 1 — testes vermelhos de L1, L2 e L4 (antes das correções)
1. **Testes:**
   - `test_http_idor_offline.py::test_delete_rejects_idempotency_key_of_other_operation` (L1-a): A conclui um turno fake com a key K (`coordinator.claim(..., kind="turn", game_id=game_a)` + `complete`). `DELETE /game/save/{game_a}` com `Idempotency-Key: K` → 409 `operation_request_mismatch`, e `store.get(a, game_a)` continua existindo. **Hoje fica vermelho** (200 com o recibo do turno).
   - `test_delete_rejects_key_reused_for_other_game` (L1-b): é vermelho.
   - `test_delete_retry_same_key_is_idempotent` (L1-c): já verde, é a guarda de regressão do `game_id=None`.
   - `test_art_quality_rejects_generation_of_other_game` (L2): `DynamicArtRepository` fake por monkeypatch em `services.dynamic_art`, com uma geração `gen` da campanha `g2` do mesmo dono. `POST /game/{game_a}/art/{gen}/quality` → 409 e a geração não é alterada. Vermelho.
   - `tests/test_http_error_leakage.py::test_422_does_not_echo_input` (L4): vermelho.
   - Local: `test_http_idor_local.py::test_delete_key_reuse_conflicts_on_postgres` e `test_art_quality_cross_game_on_postgres`. O segundo pula com motivo explícito se a stack não tiver uma geração `ready` semeável sem rede.
2. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_http_idor_offline.py tests/test_http_error_leakage.py -q -k "delete or art_quality or 422"`. Esperado: L1-a, L1-b, L2 e L4 **falham**, L1-c passa. Registrar a saída no histórico da spec.

### Etapa 2 — correções L1, L2, L4
1. **Implementação:** conforme §3 (Arquivos alterados). Para a L4, rodar antes `Grep` por `\["detail"\]\[0\]\[` e `"input"` em `tests/` e ajustar só testes que leiam `input` do 422. Não pode haver nenhum em `evals/`; se houver, parar.
2. **Verificação:** o mesmo comando da Etapa 1, tudo verde, mais `bash scripts/dev/py.sh -m pytest tests/test_session_hardening.py tests/test_account_lifecycle_security.py tests/test_surfaces_221.py -q -n 2`.

### Etapa 3 — headers (R1–R4)
1. **Testes** (`tests/test_http_security_headers.py`):
   - `test_security_headers_on_every_surface[surface]`, parametrizado pela tabela do R1, legacy e DB;
   - `test_no_store_on_session_paths_only` (R2);
   - `test_hsts_toggle_on_every_surface` (R3);
   - `test_no_route_overrides_frame_or_csp` (R4);
   - `test_docs_paths_have_no_csp`.
   - 500 forçado: monkeypatch de `api.load_game_state` para levantar `RuntimeError` + `TestClient(app, raise_server_exceptions=False)`. 429: `RPG_RATE_LIMIT=1` + `_rate_limit_max` baixo via monkeypatch. Stream: `POST /game/action/stream` sem save → lê o status e os headers, sem consumir o corpo.
2. **Implementação:** nenhuma esperada. Se algum header faltar numa superfície, corrigir em `_correlation_boundary` e registrar o desvio na spec.
3. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_http_security_headers.py -q`.

### Etapa 4 — cookies (R5–R7)
1. **Testes** (`tests/test_http_cookie_flags.py`):
   - `test_cookie_attributes[login|refresh|reauth|delete][secure0|secure1]`, com parser próprio de `Set-Cookie` (split por `;`, nomes de atributo case-insensitive);
   - `test_logout_and_delete_clear_with_same_path`;
   - `test_legacy_auth_routes_404_without_set_cookie`.
2. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_http_cookie_flags.py -q`.

### Etapa 5 — CORS (R8–R10)
1. **Testes** (`tests/test_http_cors.py`):
   - `test_allowed_origin_gets_acao_with_credentials`;
   - `test_unknown_origin_gets_no_acao`;
   - `test_preflight_allowed`;
   - `test_preflight_denied[origin|method|header]`;
   - `test_mutation_origin_denied[evil|missing|null]`;
   - `test_mutation_allowed_origin_passes_boundary`.

   Usam as origens default (`api._CORS_ORIGINS` é calculado no import, `api.py:247-251`; nada de setenv).
2. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_http_cors.py -q`.

### Etapa 6 — vazamento (R11, R12)
1. **Testes** (`tests/test_http_error_leakage.py`): `test_malformed_body_no_leak[route][payload][profile]`, `test_raw_body_routes_no_leak[route]`, `test_unhandled_500_is_generic`. Nenhuma string `docs/` e nenhum `.md` no arquivo (`scripts/ci_docs_only.py:22`).
2. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_http_error_leakage.py -q -n 2`.

### Etapa 7 — matriz IDOR offline (R14)
1. **Testes** (`tests/test_http_idor_offline.py`): `test_principal_b_cannot_touch_game_a[route]`, parametrizado pela lista do R14. Cada caso confere o status, a ausência de `seed_name` no corpo e que `store.get(a, game_a).version` não mudou.
2. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_http_idor_offline.py -q -n 2`.

### Etapa 8 — matriz local + gate (R16, R20, R21)
1. **Testes:** `tests/test_http_idor_local.py::test_principal_b_cannot_touch_game_a_local[route]`.
2. **Implementação:** `scripts/audit_local_gate.py` (lista, env e checagem de skip). Teste offline `tests/test_audit_local_gate_contract.py`:
   - lê o source do gate e assegura que os três arquivos estão na lista;
   - roda a função de parse de skip num `results.xml` sintético: com skip → 1, sem skip → 0.

   Para isso, extrair `_skipped_security_tests(junit_path) -> list[str]`.
3. **Verificação (stack local de pé, `scripts/dev_stack.py start`):** `bash scripts/dev/py.sh scripts/audit_local_gate.py` → código 0, e `readiness_artifacts/audit/results.xml` sem `skipped` nos três arquivos. Offline: `bash scripts/dev/py.sh -m pytest tests/test_audit_local_gate_contract.py -q`.

## 5. Critérios de aceite

- [ ] Etapa 1 registrada no histórico: L1-a, L1-b, L2 e L4 vermelhos antes da correção, com a saída do pytest.
- [ ] `bash scripts/dev/py.sh -m pytest tests/test_http_security_headers.py tests/test_http_cookie_flags.py tests/test_http_cors.py tests/test_http_error_leakage.py tests/test_http_idor_offline.py tests/test_audit_local_gate_contract.py -q -n 2` verde.
- [ ] R17: reusar a key de um turno no DELETE → 409, e a campanha continua existindo; retry do mesmo delete → 200 (offline e Postgres local).
- [ ] R18: `quality` com uma geração de outra campanha → 409, sem alterar a linha (offline; local se semeável).
- [ ] R19: nenhum item de `detail` no 422 tem `input`/`ctx`/`url`; `curta-XYZ` não aparece no corpo.
- [ ] R20/R21: `scripts/audit_local_gate.py` roda `test_rls_local.py`, `test_storage_security_local.py` e `test_http_idor_local.py` sem nenhum skip; código 0 com a stack local; o job `audit-local` verde no PR.
- [ ] Testes existentes de sessão, CSRF e superfícies seguem verdes (Etapa 2).
- [ ] `uv run pytest` verde (suíte completa offline, só o coordenador, no pouso).
- [ ] Sem `with_structured_output` novo (N/A ao guard de FallbackLLM).
- [ ] Saves antigos continuam carregando (sem mudança de persistência; a suíte cobre).

## 6. Smoke test real

Sem LLM: sem custo de quota. A infra real é o Supabase local e o staging, só leitura.

1. **Stack local:** `scripts/dev_stack.py start` + `bash scripts/dev/py.sh scripts/audit_local_gate.py` → código 0; anexar `readiness_artifacts/audit/summary.json` e a contagem de testes dos três arquivos novos.
2. **Staging, headers:** `curl -sSI https://rpg-ia-master-staging.vercel.app/health` e `curl -sSI https://rpg-ia-master-staging.vercel.app/` têm `nosniff`, `X-Frame-Options: DENY`, CSP, HSTS (`RPG_COOKIE_SECURE=1` no staging) e `X-Request-ID`.
3. **Staging, CORS:** `curl -sS -o /dev/null -D - -H "Origin: https://evil.example" https://rpg-ia-master-staging.vercel.app/health` → sem `Access-Control-Allow-Origin`.
4. **Staging, L4** (depois do deploy): `POST /auth/signup` com `{"email":"x@y.z","password":"curta-XYZ","age_confirmed":true}` → 422 sem `curta-XYZ` no corpo. Esse 422 sai antes do provedor de identidade, então não cria conta.
5. Anexar as saídas no handoff `handoffs/SPEC-337-*-review.md`.

## 7. Riscos & compatibilidade

- **L3 (registrado, fora de escopo):** `persistence.py:875-886` converte qualquer falha do store em `None`, e as rotas respondem 404 com o banco fora do ar. Isso esconde incidente e faz a matriz IDOR local passar por "404" mesmo com o banco quebrado. Por isso o R15/R16 exige o controle positivo (A lê 200) na mesma execução. Correção = spec própria.
- **Preflight latente** (§Fora de escopo): se algum dia houver cliente cross-origin com credenciais em `/game*`, o `_session_boundary` precisa deixar `OPTIONS` passar antes de exigir principal. Hoje não há esse cliente (`web/capacitor.config.ts:3-6`).
- **L1, risco do próprio fix:** passar `game_id=game_uuid`, como sugeria o discovery, quebraria todo retry legítimo (o recibo do delete tem `game_id` NULL). O teste L1-c é a guarda.
- **L4 é mudança de contrato do 422:** clientes que leiam `input` perdem o campo. O web não lê (`web/src/http.ts:50-53`); o Android usa o mesmo bundle. Testes e contratos de e2e que comparem o 422 inteiro: procurar antes (Etapa 2).
- **`audit-local` mais lento:** hoje está certificado em cerca de 3,5 min (`.github/workflows/audit-local.yml:2`), com timeout de 35 min (`:33`). Os três arquivos somam alguns minutos. Se `test_rls_local.py` ou `test_storage_security_local.py` falharem ao entrar pela primeira vez no CI, corrigir o ambiente do gate (env, ordem). Se for falha real de RLS, é bug de produto: abrir achado e não pular o teste (R21 proíbe skip).
- **Fixture altera `api.app.router.routes`** (mount da SPA): o teardown é obrigatório. Sob `-n 2` cada worker tem seu processo, sem vazamento entre workers.
- **MockLLM/FallbackLLM:** sem impacto. O `/game/new` da semente roda no MockLLM (`RPG_FORCE_MOCK=1` do `tests/conftest.py`).
- **Saves:** sem impacto. **Quota/latência:** zero.

## 8. Decisões do dono

Registradas pelo coordenador em 27/10 (o dono autorizou "escreva as specs e depois implemente"). Todas são definitivas:
- **D1:** a 337 corrige L1, L2 e L4, cada uma com teste vermelho antes. L3 fica fora, registrada como risco.
- **D2:** o fuzz roda nos perfis legacy e DB-offline, com a fixture de dois principals desta spec (consumida pela 338).
- **D3:** `test_rls_*` (o `_local`), `test_storage_security_local` e o novo `test_http_idor_local` entram na lista do `audit_local_gate`.
- **D4:** `api-fuzz` é bloqueante desde o início (SPEC-338).
- **D5:** preflight sob `_session_boundary`: só documentar.
- **D6:** o grupo `fuzz` ganha pip-audit próprio (SPEC-338).

## Histórico de mudanças

- 2026-10-27 · spec escrita (spec-author) a partir do discovery de 27/10. Correção ao discovery: o fix da L1 usa `game_id=None` (o recibo do delete é desacoplado da campanha), e não `game_uuid`.
