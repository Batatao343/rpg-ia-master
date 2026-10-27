# SPEC-338 — Fuzz da API com Schemathesis in-process (legacy + perfil DB offline), job `api-fuzz` bloqueante

> **Status:** `approved` (aprovada em 2026-10-27 pelo dono: "escreva as specs e depois implemente"; as 6 decisões do discovery de 27/10 são definitivas, ver §8)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Depende de:** SPEC-337 (`done`). Usa a fixture `two_principals`, o `FakeTurnCoordinator` e os helpers `assert_security_headers`/`forbidden_leak` de `tests/fakes/two_principals.py`.
> **Desbloqueia:** —

---

## 1. Contexto & Objetivo

A SPEC-337 prova as defesas HTTP com casos escritos à mão. Falta a outra metade: **entradas que ninguém pensou em escrever**. Exemplos: string com 10 mil caracteres em `game_id`, inteiro negativo em campo de carta, unicode de controle no nome, JSON aninhado no lugar de string. Hoje um `ValueError`/`KeyError` vindo de entrada estranha só aparece em produção, como 500.

A API publica OpenAPI nos perfis legacy e local (`infrastructure/runtime.py:632-636`, `api.py:94-103`). Por esse schema, o Schemathesis gera requisições válidas e quase-válidas com Hypothesis e roda tudo **in-process**, sem servidor, sem rede e sem LLM real (`RPG_FORCE_MOCK=1` em `tests/conftest.py`). Duas limitações do schema:

- Só 5 rotas declaram `response_model` (`/game/new`, `/game/action`, `/game/death`, `/game/combat-simulator`, `/game/saves`: `api.py:4763`, `:6260`, `:6280`, `:3631`, `:7003`).
- Várias rotas leem o request cru, sem schema de entrada (webhook, transcriptions, refresh/logout, audit-export, DELETE save).

Por isso o oráculo **não** é conformidade de resposta, e sim:

- nenhum 5xx inesperado;
- headers de segurança presentes;
- nada vazado no corpo.

**Objetivo:** um teste `api_fuzz` fora do `pytest` default, rodado num job próprio do `validate.yml`, **bloqueante desde o início** (decisão D4). Ele fuzza dois perfis: legacy e DB-offline com dois principals (D2). O grupo de dependências `fuzz` fica isolado do runtime, do bundle Vercel e do pip-audit de produção, e tem pip-audit próprio (D6).

**Risco de partida:** o transporte ASGI do Schemathesis 4.x nunca foi testado com Starlette 1.6.0 (versão do `uv.lock`). A Etapa 0 é um spike com saída de fallback definida.

## 2. Requisitos

### Dependências
- **R1 — grupo `fuzz` isolado.** `pyproject.toml` ganha `[dependency-groups] fuzz = ["schemathesis>=4.32,<5"]` (ou o pin decidido no spike) e o `uv.lock` é regenerado.
  - O grupo **não** entra em `default-groups`, então `uv sync` (sem `--group fuzz`) não instala o Schemathesis.
  - `uv export --no-dev --no-hashes --no-emit-project --format requirements-txt` gera um `requirements.txt` **idêntico** ao atual: nenhuma versão de runtime muda. Prova: `git diff --exit-code requirements.txt` depois de reexportar.
  - Se a resolução mexer em algum pin de runtime, baixar o Schemathesis até uma versão que não mexa. Se nenhuma 4.x servir, parar e registrar no hand-back.
  - `tests/test_spec192_vercel_packaging.py::test_requirements_vercel_utf8_subset_of_lock` segue verde, e `schemathesis`/`hypothesis` não aparecem no `requirements.txt`.
- **R2 — pip-audit do grupo.** O job `api-fuzz` exporta só o grupo (`uv export --only-group fuzz --no-hashes --no-emit-project --format requirements-txt -o "$RUNNER_TEMP/fuzz-requirements.txt"`) e roda `uvx --from pip-audit==2.10.1 pip-audit -r "$RUNNER_TEMP/fuzz-requirements.txt" --progress-spinner off`, o mesmo pin de `validate.yml:60`. Advisory = job vermelho, sem allowlist inicial.

### Coleta e marcação
- **R3 — marker `api_fuzz` fora do default.**
  - `pyproject.toml:91`: `addopts` passa a `-q -m "not llm_contract and not llm_playtest and not api_fuzz"`, e `markers` ganha `api_fuzz`.
  - `uv run pytest` (default) seleciona zero testes `api_fuzz`. Prova: `pytest --collect-only -q -m api_fuzz` lista os testes, e o default não os executa.
- **R4 — ausência do pacote.** Sem o Schemathesis instalado, o módulo faz `pytest.importorskip("schemathesis")`. Com `RPG_API_FUZZ_REQUIRED=1` (setado no CI), faz `import schemathesis` direto, e a falta do pacote é **erro** de coleta, nunca skip silencioso.
- **R5 — coleta barata.** O schema é carregado por fixture (`schemathesis.pytest.from_fixture` ou equivalente da 4.x confirmado no spike), e não no import do módulo. A suíte default não gera OpenAPI por causa deste arquivo.
- **R6 — guarda do docs-only.** O arquivo `tests/test_api_fuzz_schemathesis.py` não contém nenhum trecho que case com `DOC_TEST_PATTERN` (`scripts/ci_docs_only.py:22`):
  - nenhum `.md`;
  - nenhum `docs/`;
  - nenhum `"docs"` entre aspas duplas.

  As exclusões de caminho usam regex sem esses literais (ex.: `^/(re)?doc`). Prova: `test_api_fuzz_file_is_not_a_doc_test`, offline e no default, aplica o regex ao arquivo.

### Escopo das operações
- **R7 — exclusões fixas** (com motivo em comentário no teste):

  | Operação | Motivo |
  |---|---|
  | `POST /payments/stripe/webhook` | assinatura sobre corpo cru, com testes próprios |
  | `POST /account/transcriptions` | upload cru |
  | `POST /game/action/stream` | streaming |
  | `POST /game/{game_id}/art/confirm` e `/art/player/confirm` | wallet + worker |
  | `POST /game/{game_id}/art/{generation_id}/quality` | wallet + worker |
  | `POST /account/checkout` e `POST /account/purchases/google/verify` | rede |

  Documentação e esquema não entram. Rotas com `include_in_schema=False` (`/metrics`, `/telemetry/*`, `/internal/cron/*`: `api.py:289`, `:3158`, `:3245`, `:3404`) já ficam fora.
- **R8 — rotas caras com orçamento menor.** `/game/new`, `/game/prologue`, `/game/combat-simulator` e `/game/art/brief` (grafo + MockLLM) rodam num teste separado com `max_examples=5`. As demais usam `max_examples=25`.
- **R9 — perfil legacy.** Fuzz de todas as operações do schema menos as do R7, com o ambiente do `tests/conftest.py`:
  - `RPG_FORCE_MOCK=1`, `RPG_RATE_LIMIT=0`;
  - saves, memória e cache em `tmp_path`;
  - embeddings desligados.
- **R10 — perfil DB-offline.** Fuzz com a fixture `two_principals` (SPEC-337): `RPG_RUNTIME_PROFILE=local`, store em arquivo e `FakeTurnCoordinator`. Toda requisição leva o cookie `rpg_access=a`, cookie + header de CSRF válidos e `Origin: http://localhost:5173`, para o fuzz passar da fronteira de sessão e chegar ao handler.
  - Operações: **allowlist explícita** das que o runtime fake atende. Ponto de partida, a confirmar na Etapa 2:
    - `/game/state`, `/game/map`, `/game/codex`, `/game/codex/dossiers`, `/game/history`, `/game/saves`;
    - `/game/chronicle/export`, `/game/chronicle/search`, `/data/map`;
    - `/game/equip`, `/game/cards/prepare`, `/game/levelup`, `/game/death`, `/game/action`;
    - `DELETE /game/save/{game_id}`, `/game/{game_id}/operations/{operation_id}` e `/cost`;
    - `/auth/config`, `/auth/login`, `/auth/signup`, `/auth/logout`.
  - Rota que dependa de `runtime.resources[0]` (Postgres) fica fora, com o motivo listado.
- **R11 — ids semeados.** Na fração dos exemplos que o hook aceitar, `game_id` (query, body e path) recebe o id real da campanha de A. A API exata da 4.x (`map_query`/`map_body`/`map_path_parameters` ou hooks equivalentes) fica definida no spike. Se não houver API estável, o fuzz roda só com ids gerados, e a cobertura com id válido fica com a SPEC-337 (registrar o desvio).

### Oráculo
- **R12 — sem 5xx inesperado.** Check próprio `no_unexpected_server_error`:
  - **qualquer** status ≥ 500 falha;
  - **exceção:** 503 cujo `detail` está numa allowlist fechada de desligamentos intencionais (`captcha_unavailable`, `stripe_disabled`, `stripe_catalog_unavailable`, `new_purchases_disabled`, `stripe_checkout_unavailable`, `google_play_disabled`, `google_play_unconfigured`, `image_generation_disabled`, `image_pricing_unavailable`, `image_quotes_unavailable`, `speech_disabled`, `speech_pricing_unavailable`). As fontes estão em `api.py:784`, `:904`, `:911`, `:3844-4068`, `:4145`, `:4205`, `:4436-4635`.
  - `500 internal_error` nunca é aceito.
  - O `not_a_server_error` embutido não é usado, porque rejeitaria esses 503 legítimos.
- **R13 — headers e vazamento.** Toda resposta passa por `assert_security_headers(response, path=…, hsts=False)` e por `forbidden_leak(body) == []` (helpers da SPEC-337). O 422 não tem `input` (L4, corrigida na SPEC-337).
- **R14 — conformidade desligada.** Checks de status não documentado, de schema de resposta e de content-type ficam **desligados**: a API não documenta 400/401/404/409/503. Isso fica num comentário de uma linha no teste.
- **R15 — o harness detecta bug.** Teste offline `test_harness_flags_injected_500` (no default, sem o marker `api_fuzz`, rodando só se o Schemathesis estiver instalado): uma mini app FastAPI de 2 rotas, uma levanta `RuntimeError` e a outra responde 200. O mesmo helper de execução do fuzz acusa a primeira e não acusa a segunda. Sem isso, um harness quebrado passaria verde.

### Determinismo, rede e tempo
- **R16 — reprodutível.** Hypothesis com `derandomize=True`, `database=None` (sem `.hypothesis/`, que não está no `.gitignore`), `deadline=None` e `suppress_health_check=[function_scoped_fixture, too_slow, filter_too_much]`. O autouse por função do `tests/conftest.py` é compartilhado entre os exemplos de uma operação; esse acúmulo em `tmp_path` é aceito. Duas rodadas seguidas com o mesmo commit produzem o mesmo conjunto de falhas.
- **R17 — rede bloqueada.** Fixture autouse do módulo:
  - `httpx.HTTPTransport.handle_request` e `httpx.AsyncHTTPTransport.handle_async_request` levantam `RuntimeError("network blocked in api_fuzz")`. O `TestClient` usa transporte próprio, então não é afetado.
  - `socket.socket.connect` recusa qualquer endereço fora de `127.0.0.1`/`::1`. Loopback continua liberado, porque o loop asyncio no Windows usa `socketpair`.

  Saídas conhecidas que a fixture cobre: `services/account_security.py:98`, `infrastructure/google_play.py:216`, `services/stripe_checkout.py:143`, `infrastructure/openai_images.py:97`, `infrastructure/supabase_blob.py:79` e `infrastructure/oidc_identity.py:87`. Prova: `test_network_is_blocked_inside_fuzz`.
- **R18 — orçamento de tempo.** Rodada local completa (`-m api_fuzz`, os dois perfis, serial) em **≤ 5 min**; no CI, `timeout-minutes: 15`. Cada item tem `@pytest.mark.timeout(180)`. A Etapa 4 mede com `--durations=15`. Se estourar, reduzir `max_examples` só das operações mais lentas e registrar.

### CI
- **R19 — job `api-fuzz` bloqueante** em `.github/workflows/validate.yml`, irmão de `test` (não em `eval-gates.yml`):
  - `needs: scope`; `if: github.event_name != 'schedule' && needs.scope.outputs.docs_only != 'true'`;
  - `runs-on: ubuntu-24.04`; `timeout-minutes: 15`;
  - actions **com o mesmo pin SHA + comentário de tag** de `validate.yml:53-54` e `:67`, exigência de `tests/test_workflows_contract.py:32`;
  - passos: `uv sync --extra anthropic --group fuzz` → pip-audit do grupo (R2) → `RPG_API_FUZZ_REQUIRED=1 uv run pytest tests/test_api_fuzz_schemathesis.py -m api_fuzz -p no:cacheprovider --tb=short --junitxml=api-fuzz-junit.xml 2>&1 | tee api-fuzz.log; exit "${PIPESTATUS[0]}"` → `upload-artifact` em `failure()` com `api-fuzz-junit.xml` e `api-fuzz.log`, `retention-days: 7` (mesmo padrão de `validate.yml:66-75`).
  - Sem `-n`. `test_workflows_contract.py` segue verde.
- **R20 — nada protegido.** Nenhum arquivo novo entra em `evals/protected-paths.txt`, e nenhum caminho protegido é tocado.

### Fora de escopo
- Corrigir as falhas que o fuzz achar **fora** do que cabe nesta spec. Achado = teste vermelho. O implementador corrige no produto, numa etapa nova da spec, se o fix for local (validação de entrada, 4xx no lugar de 500). Se não for, abre achado para o coordenador e **não** exclui a operação para ficar verde, salvo decisão registrada.
- Fuzz contra staging/servidor real, stateful/links do OpenAPI, conformidade de schema de resposta e documentar 4xx no OpenAPI.
- L3 (`persistence.py:875-886` engole erro do store) e o preflight sob `_session_boundary` (`api.py:308`): continuam registrados na SPEC-337 §7.

## 3. Design técnico

**Arquivos novos**
- `tests/test_api_fuzz_schemathesis.py` (`pytestmark = pytest.mark.api_fuzz` só nos testes de fuzz):
  - fixtures `legacy_schema` e `db_schema`: carregam o schema de `api.app` pelo caminho decidido no spike e aplicam `.exclude(...)`/`.include(...)` (R7, R8, R10);
  - `test_fuzz_legacy_fast`, `test_fuzz_legacy_graph`, `test_fuzz_db_offline`: parametrizados por operação;
  - `run_case(case, *, client_kwargs) -> Response`: helper único de execução, usado também pelo R15;
  - `check_response(response, path) -> None`: R12 + R13;
  - `INTENTIONAL_503: frozenset[str]` (R12);
  - fixture autouse `_block_network` (R17).
- Testes offline (sem marker, no default): `test_api_fuzz_file_is_not_a_doc_test` (R6), `test_harness_flags_injected_500` (R15) e `test_network_is_blocked_inside_fuzz` (R17). Os dois últimos usam `importorskip`. Podem ficar num arquivo separado, `tests/test_api_fuzz_harness.py`, para não depender da seleção por marker.

**Arquivos alterados**
- `pyproject.toml`: `[dependency-groups].fuzz`, `addopts` (R3) e `markers` (`api_fuzz: fuzz de API com Schemathesis in-process (job api-fuzz; requer --group fuzz)`).
- `uv.lock`: regenerado (`uv lock`). O `requirements.txt` **não muda** (R1).
- `.github/workflows/validate.yml`: job `api-fuzz` (R19).
- `docs/guias/TESTES.md`: uma linha na tabela de camadas (`-m api_fuzz`, como rodar localmente: `uv sync --group fuzz`). É o único doc tocado; o coordenador pode preferir integrar no pouso.

**Esboço do caminho principal** (confirmar no spike; nomes da 4.x podem divergir):
```python
schema = schemathesis.openapi.from_asgi("/openapi.json", api.app)  # caminho A
schema = schemathesis.openapi.from_dict(api.app.openapi())  # caminho B
fast = schema.exclude(path_regex=EXCLUDED_RE).exclude(path_regex=GRAPH_RE)
```
O `api.app.openapi()` funciona independentemente de `openapi_url` (FastAPI gera o dict), o que torna o caminho B viável até em perfil sem documentação exposta.

## 4. Plano passo a passo

### Etapa 0 — spike: transporte ASGI × Starlette 1.6 (decide o caminho)
1. `uv add --group fuzz "schemathesis>=4.32,<5"`. Conferir o R1: `uv export --no-dev --no-hashes --no-emit-project --format requirements-txt -o requirements.txt` + `git diff --exit-code requirements.txt`. Se houver diff, baixar a versão até zerar.
2. Script descartável no scratchpad (não versionado) ou um teste `-k spike`, contra duas operações: `GET /health` e `POST /game/equip` (legacy, sem save → 404).
   - **Caminho A:** `from_asgi("/openapi.json", api.app)` + `case.call()` devolve status e headers do app. Critério: 10 exemplos de cada operação sem erro de transporte, e o `X-Request-ID` do `_correlation_boundary` presente.
   - **Caminho B** (A falha no load ou no `call`, por incompatibilidade com Starlette 1.x ou pela falta de `starlette_testclient`): `from_dict(api.app.openapi())`, com cada `case` enviado por `fastapi.testclient.TestClient(api.app)`. O helper `run_case` monta método, caminho formatado, query, headers, cookies e corpo a partir do `case` (via `case.call(session=…)`/`call_asgi`/`as_transport_kwargs`, o que a versão expuser) e devolve o `httpx.Response`. O oráculo (R12–R13) roda direto sobre ele, sem os validadores do Schemathesis.
   - **Caminho C** (nem A nem B na versão mais recente): fixar a última 4.x em que A ou B funcione (`schemathesis==4.x.y`).
   - Nada funciona em 4.x → **parar** e registrar o bloqueio no hand-back, com a mensagem de erro, para o coordenador decidir. Sem 3.x: depende de `starlette-testclient` e de `requests<3` antigos.
3. Confirmar no spike: `schemathesis.pytest.from_fixture` (R5), hooks de mapeamento de parâmetros (R11), `exclude/include` por `path_regex`/`method`, e onde ficam as `settings` do Hypothesis.
4. **Saída:** uma entrada no Histórico desta spec com versão, caminho (A/B/C), APIs confirmadas e tempo de 10 exemplos. Sem código de produto.

### Etapa 1 — testes do harness primeiro (vermelhos)
1. **Testes** (`tests/test_api_fuzz_harness.py`):
   - `test_api_fuzz_file_is_not_a_doc_test`: vermelho até o arquivo existir, e verde se não casar com o regex;
   - `test_harness_flags_injected_500`;
   - `test_network_is_blocked_inside_fuzz`: dentro da fixture, um `httpx.Client().get("https://example.com")` levanta `RuntimeError`, e `TestClient(api.app).get("/health")` dá 200;
   - `test_intentional_503_allowlist_matches_source`: todo `HTTPException(503, "<code>")` de `api.py`, achado por regex, está em `INTENTIONAL_503` ou numa lista explícita de excluídos (`speech_internal_error`, cuja rota sai pelo R7). Isso evita uma allowlist desatualizada.
2. **Implementação:** `run_case`, `check_response`, `INTENTIONAL_503` e `_block_network` em `tests/test_api_fuzz_schemathesis.py`, reusando `assert_security_headers`/`forbidden_leak` da 337.
3. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_api_fuzz_harness.py -q`.

### Etapa 2 — fuzz legacy e DB-offline
1. **Testes:** `test_fuzz_legacy_fast`, `test_fuzz_legacy_graph` e `test_fuzz_db_offline` (R7–R14, R16).
2. **Implementação:** fixtures de schema, exclusões, allowlist do DB-offline e hooks de id semeado (R11).
   - Operação do DB-offline que dá 500 **por lacuna do runtime fake**: completar o fake (em `tests/fakes/two_principals.py`) ou tirar da allowlist com motivo.
   - 500 **real** de produto: vira achado (§Fora de escopo).
3. **Verificação:** `uv sync --group fuzz` e depois `bash scripts/dev/py.sh -m pytest tests/test_api_fuzz_schemathesis.py -m api_fuzz -p no:cacheprovider -q --durations=15`. Anotar o tempo total e as 15 mais lentas no Histórico.

### Etapa 3 — triagem dos achados
1. Cada falha vira (a) um teste de regressão determinístico com o exemplo mínimo do Hypothesis, em `tests/test_http_error_leakage.py` ou num arquivo do domínio, (b) uma correção local de validação (4xx) e (c) uma linha no Histórico.
2. Fix que não for local: registrar no hand-back e **não** excluir a operação sem decisão do coordenador.
3. **Verificação:** os testes de regressão novos verdes + o comando da Etapa 2 verde.

### Etapa 4 — marker, CI e orçamento
1. **Implementação:** `addopts`/`markers` (R3), `importorskip`/`RPG_API_FUZZ_REQUIRED` (R4) e o job `api-fuzz` (R19).
2. **Testes:**
   - `tests/test_workflows_contract.py` verde (pins);
   - `test_api_fuzz_job_contract` (novo, offline, em `tests/test_api_fuzz_harness.py`) lê o YAML e assegura:
     - o job existe, com `needs: scope` e `timeout-minutes <= 15`;
     - há passo com `--group fuzz`, com `pip-audit` sobre `--only-group fuzz` e com `-m api_fuzz`;
     - não há `-n auto`;
     - há `upload-artifact` em `failure()`.
3. **Verificação:**
   - `bash scripts/dev/py.sh -m pytest tests/test_workflows_contract.py tests/test_api_fuzz_harness.py tests/test_spec192_vercel_packaging.py -q`;
   - `bash scripts/dev/py.sh -m pytest --collect-only -q -m api_fuzz tests/test_api_fuzz_schemathesis.py | tail -3` (> 0 itens);
   - `bash scripts/dev/py.sh -m pytest tests/test_api_fuzz_schemathesis.py -q | tail -3`: sem `-m`, o addopts deseleciona tudo.
   - Rodada completa local cronometrada ≤ 5 min (R18).

## 5. Critérios de aceite

- [ ] Etapa 0 registrada no Histórico: versão do Schemathesis, caminho A/B/C, APIs confirmadas.
- [ ] `git diff --exit-code requirements.txt` limpo depois de `uv lock` + reexport; `schemathesis`/`hypothesis` ausentes do `requirements.txt` (R1).
- [ ] `bash scripts/dev/py.sh -m pytest tests/test_api_fuzz_harness.py tests/test_workflows_contract.py tests/test_spec192_vercel_packaging.py -q` verde (R6, R15, R17, R19, R12 allowlist).
- [ ] `bash scripts/dev/py.sh -m pytest tests/test_api_fuzz_schemathesis.py -m api_fuzz -p no:cacheprovider -q` verde nos dois perfis, em ≤ 5 min locais (R9, R10, R18).
- [ ] O default `uv run pytest` não executa nenhum `api_fuzz` (R3) e não fica mais lento de forma mensurável: coleta sem gerar OpenAPI (R5).
- [ ] Job `api-fuzz` verde num PR real, com o pip-audit do grupo verde e a duração anotada (≤ 15 min; meta ≤ 10).
- [ ] Todo achado da Etapa 3 tem teste de regressão determinístico + correção, ou está registrado no hand-back como bloqueio.
- [ ] `uv run pytest` verde (suíte completa offline, só o coordenador, no pouso).
- [ ] Sem `with_structured_output` novo (N/A ao guard de FallbackLLM). Saves antigos sem impacto.

## 6. Smoke test real

Sem LLM: sem custo de quota. A infra real é o runner do GitHub.

1. Abrir o PR e conferir que o job `api-fuzz` roda, passa e aparece como check obrigatório. Anotar a duração e a contagem de casos do JUnit.
2. **Prova de que bloqueia:** num commit temporário **só na branch**, injetar `raise RuntimeError` num handler simples (ex.: `/data/options`). O job `api-fuzz` fica vermelho, com o artefato JUnit/log no upload. Reverter o commit antes do pouso.
3. Rodar duas vezes seguidas localmente (`-m api_fuzz`) no mesmo commit: mesmo resultado (R16).
4. Anexar as saídas ao handoff `handoffs/SPEC-338-*-review.md`.

## 7. Riscos & compatibilidade

- **Transporte ASGI × Starlette 1.6 (principal):** não verificado. Mitigação: o spike da Etapa 0, com os caminhos B (TestClient próprio) e C (pin). Se o caminho B for o escolhido, os validadores do Schemathesis não são usados, e o oráculo é só o nosso (R12–R13), o que basta, já que conformidade está desligada.
- **Resolução do lock:** `hypothesis<7`, `pytest<10`, `requests<3`, `anyio<5` e `jsonschema-rs` são compatíveis no papel com o lock (pytest 9.1.1, requests 2.34.2, anyio 4.14.2), mas isso só foi confirmado sem rodar `uv lock`. O R1 trava qualquer mudança de pin de runtime.
- **Flakiness vs. bloqueante (D4):** `derandomize=True` + `database=None` tornam a geração determinística por commit. Uma falha intermitente vinda de estado compartilhado (o `tmp_path` reutilizado entre exemplos) se trata como bug do harness: isolar e corrigir. Retry automático não vale.
- **Achados reais podem travar o PR da spec:** é o propósito. A Etapa 3 corrige os locais. Exclusão de operação para ficar verde só com decisão registrada.
- **L3** (`persistence.py:875-886`): com o banco fake quebrado, a rota devolve 404 em vez de 500, então o fuzz não detecta falha de store. Fica registrado (SPEC-337 §7), sem correção.
- **Preflight sob `_session_boundary`** (`api.py:308-337`, mais externo que o CORS em `api.py:253`): o fuzz não manda `OPTIONS` cross-origin com credenciais e não muda esse quadro. Fica registrado, só documentação (D5).
- **Custo do CI:** um job extra de até 15 min por PR não-docs. Roda em paralelo ao `test` (30 min), então não aumenta o tempo de parede.
- **Memória local** (máquina de 16 GB): o fuzz roda serial, um processo. Nunca `-n auto`.
- **Saves/MockLLM/quota:** sem impacto. As rotas de grafo usam o MockLLM do conftest.

## 8. Decisões do dono

Registradas pelo coordenador em 27/10 (o dono autorizou "escreva as specs e depois implemente"). Todas são definitivas:
- **D1:** a SPEC-337 corrige L1, L2 e L4. L3 fica fora, registrada como risco.
- **D2:** o fuzz roda em dois perfis: legacy e DB-offline com a fixture de dois principals da 337. A 338 depende da 337.
- **D3:** `test_rls_*`, `test_storage_security_local` e `test_http_idor_local` entram no `audit_local_gate` (SPEC-337).
- **D4:** `api-fuzz` é bloqueante desde o início.
- **D5:** preflight sob `_session_boundary`: só documentar.
- **D6:** o grupo `fuzz` ganha pip-audit próprio (`uv export --only-group fuzz | pip-audit`).

## Histórico de mudanças

- 2026-10-27 · spec escrita (spec-author) a partir do discovery de 27/10. Acréscimos ao discovery:
  - allowlist de 503 intencionais, porque `not_a_server_error` rejeitaria os desligamentos legítimos (`api.py:784`, `:3844` etc.);
  - `RPG_API_FUZZ_REQUIRED` contra skip silencioso no CI;
  - schema por fixture para não pesar a coleta default;
  - `requirements.txt` imutável como trava de lock.
