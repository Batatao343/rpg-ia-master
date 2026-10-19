# Área 07 — Segredos e supply chain (auditoria 2026-10-15)

Escopo: segredos rastreados/histórico, .gitignore, Android, deps Python/Node, workflows, Vercel, Supabase, scripts admin, Docker.
Arquivos inspecionados: `git ls-files` (filtro de nomes), `git grep` de padrões de segredo, `git log --all -G` (histórico), `.gitignore`,
`.vercelignore`, `vercel.json`, `.env.example` (apenas nomes de chave), `web/android/**` (manifests, build.gradle, variables.gradle, .gitignore,
Java), `web/capacitor.config.ts`, `scripts/android/*.ps1`, `pyproject.toml`, `uv.lock`, `requirements*.txt`, `web/package.json`/lock,
`web/scripts/legal.mjs`, `.github/workflows/*.yml`, `scripts/staging/vercel_env.py`, `scripts/cloud_doctor.py`, `scripts/admin_*.py`,
`supabase/config.toml`, `supabase/seed.sql`, `infra/`. Nenhum valor de segredo foi lido ou impresso. `.env` não foi aberto.

Resumo: 0 crítica, 0 alta, 0 média, 4 baixa, 3 info.

## Achados

### 07-01 — `.gitignore` raiz não cobre `.env.*` (exceto `.env.staging`), `*.pem`, `*.keystore`, `*.key`, `google-services.json`
- **Severidade:** baixa
- **Categoria:** Segredos / Config
- **Local:** `.gitignore` (linhas `.env`, `.env.staging`); `web/android/.gitignore:104-105` cobre só `keystore.properties` e `*.jks`
- **Evidência:** `git check-ignore -v` ignora `.env`, `.env.staging`, `keystore.properties`, `*.jks`, `local.properties`; NÃO ignora `.env.local`,
  `.env.production`, `x.keystore`, `google-services.json` (saída vazia para eles).
- **Cenário:** dev cria `.env.production`/`.env.local` (padrão Vite/Vercel `vercel env pull` gera `.env.local`/`.env.production.local`) ou salva
  service account/`*.pem` na raiz e faz `git add -A` → segredo commitado. Hoje nada foi commitado (histórico limpo), é risco preventivo.
  `.vercelignore` já exclui `.env.*`, então o deploy está protegido; só o git não.
- **Impacto:** vazamento acidental de DATABASE_URL, service role, chave Stripe/Google.
- **Correção sugerida:** acrescentar ao `.gitignore`: `.env.*` + `!.env.example`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.keystore`,
  `google-services.json`, `*service-account*.json`, `signing.properties`. Opcional: pre-commit/CI com scanner de segredos (já existe scanner de bundle).
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido

### 07-02 — Workflows `validate.yml` e `audit-local.yml` sem bloco `permissions:`
- **Severidade:** baixa
- **Categoria:** Supply chain / CI
- **Local:** `.github/workflows/validate.yml:1-9`, `.github/workflows/audit-local.yml:1-15` (os demais declaram `contents: read`)
- **Evidência:** ausência de `permissions:` → `GITHUB_TOKEN` herda o default do repositório (pode ser read/write conforme config do repo).
- **Cenário:** ambos rodam em `pull_request`; PR de fork tem token read-only, mas PR de branch interna / push em main usa o default. Código de teste
  malicioso numa branch interna com default write poderia empurrar commits/tags.
- **Impacto:** escalada limitada a quem já tem push; defesa em profundidade.
- **Correção sugerida:** adicionar `permissions: { contents: read }` no topo dos dois workflows.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido

### 07-03 — Actions referenciadas por tag mutável (`@v4`, `@v5`), sem pin por SHA
- **Severidade:** baixa
- **Categoria:** Supply chain
- **Local:** todos os `uses:` em `.github/workflows/*.yml` (`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/setup-node@v4`,
  `actions/upload-artifact@v4`, `actions/download-artifact@v4`)
- **Cenário:** comprometimento de tag upstream executa código no runner; nos jobs `eval-provider`/`eval-holdout` o runner tem `GOOGLE_API_KEY`
  e `HOLDOUT_REPOSITORY_TOKEN`.
- **Correção sugerida:** pinar por SHA de commit (com comentário da versão) pelo menos nos workflows com `environment:` e secrets
  (`eval-protected.yml`); Dependabot para actions.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido

### 07-04 — `eval-protected.yml` executa código do próprio branch/ref do dispatch com secrets de Environment
- **Severidade:** baixa
- **Categoria:** CI / Segredos
- **Local:** `.github/workflows/eval-protected.yml:24-41` (job `eval-provider`, `GOOGLE_API_KEY`), `:52-76` (`eval-holdout`, token do repositório privado)
- **Evidência:** `workflow_dispatch` + `environment:`; o código executado (`scripts/run_llm_contract_gate.py`, `private-holdout/run_holdout.py` com
  `--product-root .`) vem do ref escolhido no dispatch. O 1º checkout usa credenciais persistidas por default; o do holdout usa `persist-credentials: false` (bom).
- **Cenário:** quem tem permissão de dispatch roda branch alterada que imprime/exfiltra `GOOGLE_API_KEY`; o holdout privado é executado contra
  produto controlável (risco de vazar casos privados, mitigado só por "agregado" validado depois).
- **Correção sugerida:** configurar no GitHub "Deployment branches" dos Environments (`eval-provider`, `eval-holdout`, `eval-governance`,
  `post-deploy-smoke`) restritos a `main` com required reviewers; `persist-credentials: false` no 1º checkout. (Configuração fora do repo — verificar.)
- **Confiança:** provável (depende da config de Environment, não visível no repo)
- **Já coberto por spec?** não
- **Status:** válido (verificar config)

### 07-05 — `esbuild 0.21.5` (via `vite 5.4.21`) abaixo do corte do advisory de dev server (< 0.25.0)
- **Severidade:** info
- **Categoria:** Supply chain
- **Local:** `web/package-lock.json` (`node_modules/esbuild` 0.21.5, `node_modules/vite` 5.4.21)
- **Evidência:** GHSA-67mh-4wv8-2f99: qualquer site pode enviar requests ao dev server do esbuild; Vite 5 não usa o servidor do esbuild (usa o próprio).
  Vite 5.4.21 já inclui as correções de CVE-2025-30208 (fs bypass, corrigido em 5.4.15+). Só afeta `npm run dev`, não o bundle/release.
- **Correção sugerida:** migrar para Vite 6.4+/7 quando conveniente; rodar `npm audit` no CI (documentado 0 na sessão 53 — reconfirmar).
- **Confiança:** provável
- **Já coberto por spec?** não
- **Status:** válido (baixo risco)

### 07-06 — Release Android com `minifyEnabled false`
- **Severidade:** info
- **Categoria:** Config/Infra
- **Local:** `web/android/app/build.gradle:54`
- **Evidência:** `minifyEnabled false` no buildType release. O app é WebView remoto (sem segredos no APK, scan = 0 achados), logo o ganho de R8 é só
  ofuscação de `PlayBillingPlugin`/`MainActivity`. Sem impacto de segurança direto.
- **Correção sugerida:** opcional, habilitar R8 com regras para Capacitor/Billing após teste.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido (informativo)

### 07-07 — Scripts de ops aceitam DSN completo (com senha) por `--dsn` em argv
- **Severidade:** info
- **Categoria:** Segredos
- **Local:** `scripts/export_game_data.py:21`, `scripts/migrate_file_saves.py:21`, `scripts/recover_operations.py:16` (default = `DATABASE_URL` do env),
  `scripts/chaos_test.py:138`, `scripts/load_test.py:235`, `scripts/verify_restore.py:35` (default local `postgres:postgres@127.0.0.1:55322`)
- **Evidência:** passar `--dsn postgresql://user:senha@…` expõe a senha em lista de processos/histórico do shell. Os admin críticos
  (`admin_kill_switch.py:29 --dsn-env`) já usam nome de variável, não o valor. Defaults locais (`postgres:postgres@127.0.0.1`) são credenciais de dev do Supabase local — OK.
- **Correção sugerida:** documentar "use DATABASE_URL via env" e/ou trocar `--dsn` por `--dsn-env` nos scripts que podem tocar staging/prod.
- **Confiança:** confirmado por leitura
- **Já coberto por spec?** não
- **Status:** válido (informativo)

## Verificado e OK
- **Sem segredos rastreados:** `git ls-files` só lista `.env.example`, `data/codex/secrets/*.md` + `lore_nova/secrets.txt` (lore de jogo, não credenciais),
  `scripts/android/new_upload_keystore.ps1` (script). Nenhum `.env`, `.pem`, `.jks`, `.keystore`, service account, dump ou `.db` rastreado.
- **Histórico limpo:** `git log --all --diff-filter=A` para `.env/.pem/.jks/.keystore` = vazio; `git log --all -G` com padrões de chave (OpenAI-style `sk-`, Groq `gsk_`,
  `sb_secret_`, Stripe `sk_live_`, Google `AIza`, Jina `jina_`) fora de `tests/`/`uv.lock` = vazio.
- **Padrões de segredo no HEAD:** hits só em fixtures/placeholder: `tests/test_hosted_supabase_contract.py`, `tests/test_spec191_staging_tools.py`,
  `tests/test_spec192_vercel_env.py` (sentinelas `*_SENTINEL`, `fake`, `hunter2`), DSNs locais `postgres:postgres@127.0.0.1:55322` (scripts dev/CI),
  `.env.example:127` (template `<senha>`), checagens de prefixo `sb_secret_` em `infrastructure/{runtime,supabase_blob,supabase_identity}.py` (validação, sem valor).
  `scripts/smoke_local_profile.py:53` usa senha de usuário sintético para GoTrue local. `web/e2e/*` senhas de teste mockadas.
- **`.env.example`**: somente nomes/valores não secretos (profiles, flags, nomes de modelo); nenhuma chave real.
- **Android:** `allowBackup="false"` (sessão/cookies não vão a backup); só `MainActivity` exported (LAUNCHER, sem deep links/intent-filters extras);
  `FileProvider exported=false`, paths só `cache-path`; permissões: INTERNET, RECORD_AUDIO, MODIFY_AUDIO_SETTINGS (BILLING vem da lib); `usesCleartextTraffic=false` +
  `network_security_config` base sem cleartext; debug source set permite apenas `10.0.2.2`; `setWebContentsDebuggingEnabled(BuildConfig.DEBUG)` (`MainActivity.java:24`);
  `minSdk 24`; `signingConfigs.release` lê só env `RPG_UPLOAD_*` ou `keystore.properties` (ignorado) — sem senha literal; build falha sem signing (`checkReleaseSigning`) e
  com `http://` sincronizado (`checkReleaseCleartext`).
- **Capacitor** (`web/capacitor.config.ts`): `server.url` https obrigatório (throw), `cleartext` só debug emulador, `allowNavigation: [host]`, `allowMixedContent:false`.
- **Keystore scripts:** `new_upload_keystore.ps1` recusa diretório em OneDrive, grava em `%USERPROFILE%\.rpg-signing` fora do repo com ACL restrita (icacls antes de escrever),
  senha aleatória (24 bytes) passada ao keytool via `-storepass:env` (não argv), nunca impressa, não sobrescreve. `release_build.ps1` lê o props e exporta para env do processo (sem argv/echo de senha).
- **Deps Python (uv.lock):** starlette 1.6.0, fastapi 0.141.1, httpx 0.28.1, cryptography 50.0.0, pillow 12.3.0, psycopg 3.3.4, urllib3 2.7.0, requests 2.34.2,
  aiohttp 3.14.3, pydantic 2.13.4, langchain-core 1.6.0, langchain-community 0.4.2, pyyaml 6.0.3, certifi 2026.7.22, h11 0.16.0 — todos muito acima dos limiares dos CVEs citados;
  `python-multipart` e `jinja2` não estão no lock (sem form-upload multipart/Jinja). Recomendado rodar `pip-audit` no CI para CVEs posteriores ao meu conhecimento.
- **`requirements.txt` == `requirements-vercel.txt`** (`diff -q` sem diferença; exportado do lock com `==` pinado, sem hashes — aceitável).
- **FAISS pickle:** `allow_dangerous_deserialization=True` em `rag.py` (661, 812, 845, 873, 938, 1065, 1208, 1293) lê só índices locais gerados pelo próprio app
  (`faiss_*_index/`, `data/saves_memory/`); perfis hosted usam pgvector (`runtime.py:188/237` mapeia faiss só no `legacy`) e `game_transfer`/`local_backup` não tocam FAISS. Sem caminho de upload de índice por usuário.
- **Node:** deps pinadas por lock; `@capacitor/*` 8.5.3 pinado; sem `postinstall/preinstall/prepare` em `web/package.json`; `vite 5.4.21` pós CVE-2025-30208.
  `web/scripts/legal.mjs`: lê só `docs/spec197/legal/*.md` do repo (build-time, fonte confiável), faz `esc()` (& < > ") ANTES de aplicar `**`/`*`/`` ` `` — sem passagem de HTML cru nem links, saída sem script inline.
- **Frontend sem segredos:** `git grep import.meta.env` em `web/src` = 0 (nenhum `VITE_*` exposto); `service_role`/`SUPABASE_SERVICE` em `web/src`, `web/android/app/src`, `web/public` = 0.
- **Workflows:** `eval-gates`, `eval-protected`, `post-deploy-smoke` declaram `permissions: contents: read`; nenhum `pull_request_target`; nenhum `${{ github.event.* }}`/head_ref em `run:`;
  inputs do `post-deploy-smoke` entram via `env:` (sem injeção de shell); nenhum `set -x`/`env`/`cat .env`; secrets só em jobs com `environment:` protegido e passados via `env:`;
  `audit-local` usa Supabase local sem segredos de cloud; artifacts enviados são `readiness_artifacts/*` (agregados/JUnit/manifest), sem `.env`/saves.
- **Vercel:** `.vercelignore` exclui `.env`, `.env.*` (mantém `.env.example`), `.git`, `saves*`, `playtest_runs`, `tests`, `docs`, `supabase`, `infra`, `web/android` etc.; `vercel.json` `excludeFiles` complementa.
  `scripts/staging/vercel_env.py` lê `.env.staging/.env` e imprime apenas nomes/targets; preview não recebe segredos (fail-closed); chave de teste Turnstile é pública Cloudflare.
- **Supabase:** `supabase/seed.sql` sem usuários/senhas; `config.toml` local (`site_url` localhost, `enable_confirmations = true`, senha mín. 8; sem `jwt_secret` customizado).
- **Scripts admin:** `admin_kill_switch.py` recebe `--dsn-env` (nome da var), só imprime JSON de estado; `admin_wallet_adjust.py` imprime resultado JSON; `cloud_doctor.py` imprime apenas
  `present/missing/valid/invalid` por variável — nunca valores.
- **Docker/compose:** não existem `Dockerfile*`/`docker-compose*` no repo; `infra/` não contém imagens nem senhas literais (grep `image:|password` vazio).
