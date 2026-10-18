# SPEC-218 — Fail-closed de perfil e configuração de segurança em deploy exposto

> **Status:** `in-progress` (**18/10:** staging redeployado em a3f87e6 (`hardened=true`); `checklist --env staging` com as 4 URLs legais: 12/14 OK (`git_clean_tree` falhou só pelas próprias edições de docs ainda não commitadas), `legal_pages`/`environments_restricted`/`ci_green`/`health_sha` verdes; BLOQUEADO só por `open_p0_p1` = R-02 (SMTP; titular enviando a chave Resend) e R-12 (cron em producao inexistente; staging verificado) — R-01/03/06/07/09/11/13 aceitos pelo titular em 18/10, R-10/R-14 fechados com evidencia (`docs/spec197/risk-register.md`, `docs/spec197/evidence/checklist-a3f87e6331af.*`). Antes, 17/10: staging verde em `hardened=true`, OpenAPI 404, `post_deploy_smoke` verde.)
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-18
> **Depende de:** nenhuma · evolui SPEC-181 `done` e o checklist da SPEC-197 `in-progress` sem reabri-los (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-212, SPEC-219, SPEC-224; gate de release da SPEC-197 (ordem final 2026-10-15)
> **Origem:** auditoria de segurança 2026-10-15 — achados AUTHZ-01 (alta), SESS-06/AUTHZ-07, PAG-04, LLM-06, PRIV-08, AUTHZ-10/INFRA-06, INFRA-03, INFRA-04, INFRA-05 (ver `RELATORIO.md`)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet, ver docs/planos/equivalencia-modelos-claude.md)
> **REVIEW_MODEL:** `Astra` (≡ Opus em contexto separado, revisão adversarial) · **REVIEW_REQUIRED:** `true` — único achado **alto** da auditoria; falha = API inteira aberta
> **EVAL_AUTHORING_REQUIRED:** `false` — cobertura por testes determinísticos de contrato (`tests/`), sem eval narrativo

---

## 1. Contexto & Objetivo

O perfil `legacy` (sem login, saves em disco, memória FAISS) é o **default** quando `RPG_RUNTIME_PROFILE` está ausente, e o único guard "legacy só em loopback" valida a variável declarada `RPG_BIND_HOST`, não o bind real — e só roda quando `get_runtime()` é chamado, o que o caminho legacy da API nunca faz. O `Procfile` sobe `uvicorn api:app --host 0.0.0.0` sem exigir perfil. Resultado: um deploy em qualquer plataforma (Railway/Render são o alvo da SPEC-104; preview/ambiente novo na Vercel) que esqueça a env expõe `/game/*` e `/account/*` sem autenticação nem CSRF, com saves compartilhados entre todos os visitantes e chaves de LLM gastáveis por anônimos. Hoje a Vercel está protegida apenas porque `scripts/staging/vercel_env.py` seta o perfil — nada no código impede o esquecimento.

Na mesma família: nos perfis `hosted*`, `RPG_COOKIE_SECURE` tem default `0`, o captcha vem desligado (`RPG_AUTH_CAPTCHA_REQUIRED` default `0`), `RPG_TELEMETRY_SECRET` ausente degrada o pseudônimo para a chave pública `local-telemetry-only`, a ausência de chave de provider cai silenciosamente em `MockLLM`, kill switches falham abertos com store ilegível, e `/docs`/`/openapi.json` ficam publicados. `RuntimeConfig.validate()` não verifica nenhum desses itens; só `scripts/release/checklist.py` lista as envs — e um checklist não é um guard.

Fatos observados no HEAD (`d6af933`, árvore suja da SPEC-197/198):

- [F] `api.py:87-88` `_database_profile()` → `os.getenv("RPG_RUNTIME_PROFILE", "legacy") != "legacy"`; `api.py:94` o middleware `_session_boundary` devolve `call_next` imediatamente quando o perfil não é DB. Nenhuma rota `/game|/account` exige principal em legacy.
- [F] `infrastructure/runtime.py:186` `RuntimeConfig.from_env` default `legacy`; `:220` `bind_host=values.get("RPG_BIND_HOST","127.0.0.1")`; `:249` `if not _loopback_host(self.bind_host): raise`. `from_env()` só é chamado por `get_runtime()` (lazy, `:470`).
- [F] `infrastructure/runtime.py:446-456` `apply_serverless_defaults` (chamado em `vercel_app.py`) só ajusta `RPG_RUNTIME_CACHE_DIR` quando o perfil JÁ é `hosted*`; não força perfil nem falha.
- [F] `Procfile:1` `web: uvicorn api:app --host 0.0.0.0 --port $PORT`.
- [F] `api.py:262` `secure = os.getenv("RPG_COOKIE_SECURE", "0") == "1"` (também `:346`, `:542`); `services/account_security.py:40-45,61-62` captcha `required` default `0` e `validate_captcha` retorna sem checar no modo `app`.
- [F] `observability/telemetry.py:64-66` `key = secret or os.getenv("RPG_TELEMETRY_SECRET") or "local-telemetry-only"`.
- [F] `llm_setup.py:1088-1100` sem nenhuma key → `MockLLM` salvo `RPG_NO_MOCK=1`; `scripts/release/checklist.py:39` `FORBIDDEN_IN_PROD = ("RPG_FORCE_MOCK", "RPG_GOOGLE_PLAY_FAKE")`.
- [F] `services/kill_switches.py:100-140` fail-open por default; `RPG_KILL_SWITCH_FAIL_CLOSED` opt-in vazio (decisão SPEC-196 F1, consciente — aqui só muda o default em hosted).
- [F] `api.py:60-64` `FastAPI(...)` sem `docs_url=None`; `api.py:161,202` `_DOCS_PATHS` isentos da CSP.
- [F] `scripts/release/checklist.py:27-39` REQUIRED_ENV staging/production já lista `RPG_RUNTIME_PROFILE`, `RPG_COOKIE_SECURE`, `RPG_AUTH_CAPTCHA_REQUIRED`, `RPG_CORS_ORIGINS`, `RPG_SESSION_SECRET` — o guard em código deve ser a MESMA lista (fonte única).
- [R] `RPG_SESSION_SECRET` ausente já falha fechado em runtime (`CsrfSigner` → 401 em toda mutação) — bom, mas só na primeira mutação, não no boot.

Objetivo: **um processo que escuta fora de loopback ou roda em plataforma de hospedagem nunca sobe em `legacy` nem com config insegura** — falha no boot, com mensagem clara, e a lista de exigências vive em UM lugar compartilhado por `RuntimeConfig.validate`, `cloud_doctor` e `checklist`.

## 2. Requisitos

- **R1** — Detecção de "exposto": função pura `infrastructure.runtime.exposure_markers(env) -> set[str]` devolve os marcadores presentes dentre `VERCEL`, `RAILWAY_ENVIRONMENT`, `RENDER`, `K_SERVICE`, `FLY_APP_NAME`, `PORT` (sem `RPG_BIND_HOST` loopback explícito), `RPG_BIND_HOST` não-loopback. Testável sem rede.
- **R2** — Boot fail-closed: `api.py` chama, no import do módulo (antes de registrar rotas), `infrastructure.runtime.assert_boot_policy(env)`: se `exposure_markers` não vazio E perfil efetivo `legacy` E `RPG_ALLOW_LEGACY_EXPOSED != "1"` → `RuntimeError("legacy_profile_exposed: ...")` listando os marcadores. Em perfil DB, chama `RuntimeConfig.from_env()` (que já valida) no boot, não lazy.
- **R3** — `RuntimeConfig.validate()` para `hosted` e `hosted-supabase` exige: `RPG_COOKIE_SECURE=1`; `len(RPG_SESSION_SECRET) >= 32`; `len(RPG_TELEMETRY_SECRET) >= 32`; `RPG_CORS_ORIGINS` explícito, sem `*`, sem `localhost`/`127.0.0.1`, todas `https://`; captcha `required=1` com `site_key` (e `RPG_TURNSTILE_SECRET` quando modo `app`); `RPG_NO_MOCK=1` ou ao menos uma key de provider presente (`llm_setup._any_key_available()`); `RPG_FORCE_MOCK` e `RPG_GOOGLE_PLAY_FAKE` ausentes/`0`. Override explícito e único: `RPG_ALLOW_INSECURE_HOSTED=1` (só para laboratório; o checklist de release o coloca em `FORBIDDEN_IN_PROD`).
- **R4** — Fonte única: a lista de exigências por perfil sai de `infrastructure/runtime.py` (`HOSTED_SECURITY_REQUIREMENTS`), e `scripts/release/checklist.py` + `scripts/cloud_doctor.py` importam dela (sem duplicar strings). Teste de paridade: toda chave em `REQUIRED_ENV["production"]` relacionada a segurança consta em `HOSTED_SECURITY_REQUIREMENTS`.
- **R5** — Kill switches em hosted: default de `RPG_KILL_SWITCH_FAIL_CLOSED` passa a `image_generation,stt_fallback_expensive` quando perfil `hosted*` e a env está ausente (compras continuam fail-open — revenue path, decisão SPEC-196 mantida). Env explícita (inclusive vazia `""`) vence o default.
- **R6** — Docs/OpenAPI: em perfil DB, `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` salvo `RPG_EXPOSE_OPENAPI=1`; `_DOCS_PATHS` deixa de ser isenção da CSP quando desligado. Em `legacy`/`local` nada muda.
- **R7** — `Procfile` e scripts de start: `Procfile` usa `--host ${RPG_BIND_HOST:-127.0.0.1}`; `README`/`docs/operacao` dizem que hospedagem exige `RPG_RUNTIME_PROFILE=hosted*`. `scripts/start_local_api.py` continua `127.0.0.1`.
- **R8** — Mensagens de erro de boot NUNCA incluem valores de env (só nomes e o motivo).
- **R9** — `GET /health` passa a expor `profile` (`legacy|local|portable|hosted|hosted-supabase`) e `hardened: bool` (resultado de R3) — sem outros detalhes — para que o smoke pós-deploy (`scripts/post_deploy_smoke.py`) afirme `profile != legacy and hardened`.
- **R10** — Compatibilidade: suíte offline (`RPG_FORCE_MOCK=1`, perfil legacy, sem marcadores) continua subindo `api.app` sem mudança; `tests/conftest.py` garante que `VERCEL`/`PORT` não vazam do ambiente do CI para os testes (monkeypatch/limpeza).
- **R11** — Validação de VALORES (não só presença) em `hosted*` (achados INFRA-03/04/05): `RPG_RATE_LIMIT` inteiro ≥ 1 (valores ≤ 0 são recusados — hoje desligam o limitador, `api.py:785`); `RPG_AUTH_EMAIL_CONFIRMATION_REQUIRED=1`; `RPG_CORS_ORIGINS` validado item a item (`https://host[:port]`, sem path, sem `*`, sem `localhost`/`127.0.0.1`); `LLM_PROVIDER` ausente (roteamento só por `ROUTES`/`RPG_ROUTES`) ou em allowlist; `RPG_FORCE_MOCK`, `RPG_GOOGLE_PLAY_FAKE`, `RPG_ADMIN_ALLOW_PROFILE`, `RPG_KILL_SWITCHES_OFF`, `RPG_ALLOW_INSECURE_HOSTED`, `RPG_ALLOW_LEGACY_EXPOSED`, `RPG_EXPOSE_OPENAPI` ausentes/`0` (lista `FORBIDDEN_IN_HOSTED` única, importada pelo checklist como `FORBIDDEN_IN_PROD`). O middleware CORS passa a `allow_methods`/`allow_headers` explícitos (`GET, POST, DELETE, OPTIONS`; `content-type, x-csrf-token, x-request-id, x-rpg-client, idempotency-key`).
- **R12** — Router `/internal/cron/*` registrado com `include_in_schema=False` (INFRA-06); quando docs estão ligados em perfis não-DB, o schema não lista rotas internas.

### Fora de escopo

- Trocar o rate limit, cotas por owner ou cobrança de turno (SPEC-219).
- Role de banco de menor privilégio / `SET ROLE` (SPEC-224, R-05).
- Mudar a semântica de `legacy` em uso local (CLI/`uv run uvicorn` em loopback continua sem login, por design).
- Chaves reais de Turnstile/SMTP/backups (gates SPEC-197, decisão do dono).

## 3. Design técnico

- **Arquivos alterados**
  - `infrastructure/runtime.py`: novos `exposure_markers(env)`, `assert_boot_policy(env)`, constante `HOSTED_SECURITY_REQUIREMENTS: tuple[Requirement, ...]` (`Requirement = NamedTuple(name, check: Callable[[Mapping], str | None])`, devolvendo motivo ou `None`); `RuntimeConfig.validate()` itera as requirements quando `profile in {"hosted","hosted-supabase"}` e `RPG_ALLOW_INSECURE_HOSTED != "1"`, agregando motivos em um único `ValueError("hosted_config_insecure: a, b, c")`. `apply_serverless_defaults` passa a também setar `RPG_KILL_SWITCH_FAIL_CLOSED` default (R5) e `RPG_NO_MOCK=1` quando ausentes em `hosted*`.
  - `api.py`: no topo (após `load_dotenv`, antes de `app = FastAPI(...)`): `from infrastructure.runtime import assert_boot_policy, docs_enabled; assert_boot_policy(os.environ)`; `app = FastAPI(..., docs_url="/docs" if docs_enabled() else None, redoc_url=..., openapi_url=...)`. `/health` ganha `profile` e `hardened` (R9). `_DOCS_PATHS` condicionado.
  - `services/kill_switches.py`: `_fail_closed_keys()` lê o default via `runtime.kill_switch_fail_closed_default(profile)`.
  - `scripts/release/checklist.py`, `scripts/cloud_doctor.py`: substituem a lista local por `HOSTED_SECURITY_REQUIREMENTS` + `FORBIDDEN_IN_PROD += ("RPG_ALLOW_INSECURE_HOSTED", "RPG_ALLOW_LEGACY_EXPOSED", "RPG_EXPOSE_OPENAPI")`.
  - `Procfile`, `.env.example` (documentar as 3 envs novas como "NUNCA em produção"), `docs/operacao/readiness/readiness-local.md` ou runbook de deploy.
  - `scripts/post_deploy_smoke.py`: asserta `profile != "legacy"` e `hardened is True`.
- **Assinaturas**
  ```python
  def exposure_markers(env: Mapping[str, str]) -> set[str]: ...
  def assert_boot_policy(env: Mapping[str, str]) -> None: ...   # levanta RuntimeError
  def docs_enabled(env: Mapping[str, str] | None = None) -> bool: ...
  def kill_switch_fail_closed_default(profile: str) -> tuple[str, ...]: ...
  HOSTED_SECURITY_REQUIREMENTS: tuple[Requirement, ...]
  ```
- **Formato de erro de boot** (stderr, sem valores):
  `RuntimeError: legacy_profile_exposed: markers=PORT,RAILWAY_ENVIRONMENT; set RPG_RUNTIME_PROFILE=hosted-supabase (or RPG_ALLOW_LEGACY_EXPOSED=1 for a lab)`.
- **`/health`** (R9): `{"status":"online","engine":...,"git_sha":...,"profile":"hosted-supabase","hardened":true}`.

## 4. Plano passo a passo

### Etapa 0 — Reprodução (testes vermelhos ANTES da correção)

1. **Testes** (`tests/test_boot_policy.py`, novo):
   - `test_legacy_exposed_boot_fails`: com `monkeypatch.setenv("PORT","8000")` e sem `RPG_RUNTIME_PROFILE`, `importlib.reload(api)` (ou chamada direta `assert_boot_policy`) levanta `RuntimeError` contendo `legacy_profile_exposed`. **Vermelho no HEAD** (hoje sobe).
   - `test_hosted_without_cookie_secure_fails`: env mínimo válido de `hosted-supabase` (reusar fixture de `tests/test_hosted_supabase_contract.py`) sem `RPG_COOKIE_SECURE` → `RuntimeConfig.from_env` levanta `ValueError` com `RPG_COOKIE_SECURE`. **Vermelho no HEAD.**
   - `test_hosted_captcha_disabled_fails`, `test_hosted_cors_localhost_fails`, `test_hosted_telemetry_secret_missing_fails`, `test_hosted_no_provider_key_and_no_nomock_fails`: idem. **Vermelhos.**
   - `test_docs_hidden_in_db_profile`: `TestClient(app)` em perfil DB → `GET /openapi.json` = 404. **Vermelho.**
2. **Verificação:** rodar só esse arquivo e registrar a saída (vermelho) em `docs/secXX/README.md`.

### Etapa 1 — `exposure_markers` + `assert_boot_policy` + boot no `api.py`

1. **Testes:** os de Etapa 0 (primeiros) + `test_legacy_loopback_without_markers_ok` (sem marcadores → não levanta) + `test_allow_legacy_exposed_override` + `test_boot_error_has_no_env_values` (setar `DATABASE_URL=postgres://u:SEGREDO@h/db` e afirmar que `"SEGREDO" not in str(exc)`).
2. **Implementação:** funções em `runtime.py`; chamada no topo de `api.py`; `tests/conftest.py` limpa `VERCEL|PORT|RAILWAY_ENVIRONMENT|RENDER|K_SERVICE|FLY_APP_NAME` (autouse) para a suíte continuar verde (R10).
3. **Verificação:** `uv run pytest tests/test_boot_policy.py tests/test_infrastructure_contracts.py -q`.

### Etapa 2 — `HOSTED_SECURITY_REQUIREMENTS` em `validate()` + fonte única no checklist/doctor

1. **Testes:** restantes da Etapa 0 + `test_requirements_parity_with_release_checklist` + `test_allow_insecure_hosted_override_only_for_lab` + `test_validate_error_lists_all_missing_at_once` (mensagem agrega 3 motivos) + atualização de `tests/test_spec197_checklist.py` (import da lista) + `tests/test_hosted_supabase_contract.py` (fixtures ganham as envs novas).
2. **Implementação:** conforme §3; `cloud_doctor.py` imprime `present/missing` por requirement (nunca valores).
3. **Verificação:** `uv run pytest tests/test_boot_policy.py tests/test_spec197_checklist.py tests/test_hosted_supabase_contract.py tests/test_cloud_doctor*.py -q`.

### Etapa 3 — Defaults em hosted (kill switch fail-closed, `RPG_NO_MOCK`), docs off, `/health`, `Procfile`

1. **Testes:** `test_kill_switch_default_fail_closed_in_hosted` (`services/kill_switches` com store que levanta → `image_generation` off, `new_purchases` on) e `test_kill_switch_explicit_empty_env_wins`; `test_docs_hidden_in_db_profile` + `test_docs_visible_in_legacy`; `test_health_reports_profile_and_hardened`; `tests/test_spec192_vercel_env.py` (se cobre `apply_serverless_defaults`) ganha caso de `RPG_NO_MOCK`.
2. **Implementação:** conforme §3; `Procfile` e `.env.example`; `post_deploy_smoke.py`.
3. **Verificação:** `uv run pytest -q` completo; `npm run build` inalterado.

## 5. Critérios de aceite

- [x] R1–R10 com testes nomeados acima verdes; testes da Etapa 0 registrados vermelhos no HEAD e verdes depois.
- [ ] `uv run pytest` verde (suíte completa offline), `ruff` verde, `scripts/release/checklist.py --env staging` verde contra `.env.staging` (sem imprimir valores). **17/10:** pytest (3615 passed) e ruff verdes na branch integrada; checklist staging: checks de config verdes (migrations 28/28, env names sem proibidas, health_sha, kill switches, evals), resultado BLOQUEADO só por `legal_pages`, `open_p0_p1`, `environments_restricted` (gate SPEC-197) e árvore suja pela própria evidência. **18/10:** staging redeployado em a3f87e6 (`hardened=true`); `checklist --env staging` com as 4 URLs legais: 12/14 OK (`git_clean_tree` falhou só pelas próprias edições de docs ainda não commitadas), `legal_pages`/`environments_restricted`/`ci_green`/`health_sha` verdes; BLOQUEADO só por `open_p0_p1` = R-02 (SMTP; titular enviando a chave Resend) e R-12 (cron em producao inexistente; staging verificado) — R-01/03/06/07/09/11/13 aceitos pelo titular em 18/10, R-10/R-14 fechados com evidencia (`docs/spec197/risk-register.md`, `docs/spec197/evidence/checklist-a3f87e6331af.*`).
- [x] Smoke local: `RPG_RUNTIME_PROFILE` ausente + `PORT=8000 uv run uvicorn api:app --host 0.0.0.0 --port 8000` → processo NÃO sobe, stderr com `legacy_profile_exposed` e sem valores de env. Sem `PORT`, em loopback → sobe como hoje.
- [x] Staging Vercel (redeploy): `GET /health` devolve `profile=hosted-supabase`, `hardened=true`; `GET /openapi.json` = 404; smoke `scripts/post_deploy_smoke.py` verde. **Staging 17/10:** `/health` `profile=hosted-supabase`, `hardened=true`; `/openapi.json` e `/docs` = 404; `post_deploy_smoke.py` verde (`docs/staging-wave-2026-10-17/README.md`).
- [x] Revisão Astra independente APPROVED (com tentativa explícita de contornar R2 via `RPG_BIND_HOST=127.0.0.1` + `--host 0.0.0.0`: deve falhar por `PORT`/marcador de plataforma; documentar o limite: processo sem NENHUM marcador e bind manual 0.0.0.0 continua responsabilidade do operador — ponto de decisão D-B).
- [x] Saves antigos continuam carregando (nenhuma mudança de schema).

## 6. Smoke test

Sem LLM real (zero custo): (1) boot negativo local (acima); (2) boot positivo `local` com Supabase local (`scripts/start_local_api.py`) inalterado; (3) deploy staging + `/health` + `/openapi.json` 404 + login/turno MockLLM-free já coberto por `scripts/staging/vercel_smoke`; (4) `cloud_doctor` contra `.env.staging` lista `present` para todos os requirements.

## 7. Riscos & compatibilidade

- **Falso positivo de exposição**: `PORT` é setado por alguns IDEs/containers de dev. Mitigação: `RPG_BIND_HOST=127.0.0.1` explícito remove `PORT` dos marcadores (R1) e `RPG_ALLOW_LEGACY_EXPOSED=1` existe para laboratório. Documentar em `.env.example`.
- **CI**: runners GitHub não setam esses marcadores; `conftest.py` limpa por segurança (R10).
- **Vercel preview** sem segredos (fail-closed já existente em `vercel_env.py`): com R2/R3 o preview passa a FALHAR no boot em vez de responder 401 — comportamento desejado; confirmar que `post-deploy-smoke` só roda em staging/prod.
- **MockLLM/FallbackLLM**: inalterados fora de hosted; em hosted sem key o boot falha (R3) em vez de simular.
- **Latência/quota**: nenhuma.

## 8. Pontos de decisão do dono

- **D-A (`PORT` como marcador):** incluir `PORT` torna o guard efetivo em Railway/Render/Heroku-like (todos injetam `PORT`), ao custo de exigir `RPG_BIND_HOST=127.0.0.1` em devs que setam `PORT`. **Default recomendado:** incluir.
- **D-B (bind real vs declarado):** uvicorn não expõe o host de bind ao app; não dá para detectar `--host 0.0.0.0` sem marcador. **Default recomendado:** aceitar o limite, documentar e manter `Procfile` em loopback por default (R7).
- **D-C (`/docs` em staging):** útil para QA. **Default recomendado:** desligado em todo perfil DB; `RPG_EXPOSE_OPENAPI=1` só em staging e listado em `FORBIDDEN_IN_PROD`.
- **D-D (kill switch de compras):** manter fail-open (SPEC-196). **Default recomendado:** manter; só imagem/STT-fallback fail-closed.

## 9. Evidência requerida

- Saída de `uv run pytest` completa (passed/skipped) e do arquivo `tests/test_boot_policy.py` isolado; saída vermelha da Etapa 0 no HEAD.
- Transcrição (sem valores) do boot negativo local e do `cloud_doctor`/`checklist` em staging; `GET /health` e `GET /openapi.json` do staging após redeploy (com `git_sha`).
- `docs/secXX/README.md` com: lista final de `HOSTED_SECURITY_REQUIREMENTS`, decisões D-A..D-D resolvidas, limite do D-B, e parecer Astra (`handoffs/`).
- Atualização de `docs/spec197/risk-register.md` (novo risco fechado: "perfil legacy exposto por esquecimento de env") e de `ESTADO_ATUAL.md`/`ROADMAP.md`.

## 10. Status da execução (2026-10-17, revisão Astra independente)

- Revisão Astra independente **APPROVED** após correções (parecer em `handoffs/SPEC-218-ASTRA-independent-review.md`): conftest limpa marcadores já no import (a coleta importa `api` antes das fixtures; `PORT` no shell derrubava a suíte), `DYNO` (Heroku) e `RPG_HOST` não-loopback (`python api.py`) viraram marcadores, fixture portable alinhada ao OIDC da SPEC-220.
- Bypass §5 verificado: `RPG_BIND_HOST=127.0.0.1` + `--host 0.0.0.0` falha pelo marcador da plataforma; limite D-B (processo sem nenhum marcador + bind manual 0.0.0.0) segue responsabilidade do operador.
- Desvios: `RPG_EXPOSE_OPENAPI` é proibido em todo `hosted*` (R11 vence D-C: staging é `hosted-supabase`, então docs ficam off lá também); `local` mantém docs ligados (R6).
- **Falta só (status `in-progress`):** critério 2 parte `checklist --env staging` e §6 itens 3–4 (redeploy staging + `/health` `hardened=true` + `/openapi.json` 404 + `cloud_doctor` todo `present`). Antes do redeploy o dono precisa: definir `RPG_TELEMETRY_SECRET` (≥32) no projeto Vercel/`.env.staging` e decidir o mock — `scripts/staging/vercel_env.py` ainda envia `RPG_FORCE_MOCK=1`, que agora é proibido em hosted (boot falha de propósito). Etapa 0 vermelha no HEAD não foi capturada separadamente.
