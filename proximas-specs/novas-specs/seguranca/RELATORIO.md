# Auditoria de segurança de dados e cibersegurança — 2026-10-15

> **Status:** concluída (8/8 áreas auditadas; 8 specs `draft` geradas). Orquestrador: Fable 5.1; 8 subagentes Sonnet (um por área), altos/médios verificados no source pelo orquestrador.
> Somente leitura do código (HEAD `d6af933` + árvore suja da SPEC-197/198); nenhum exploit remoto, nenhum provider pago, nenhum valor de segredo lido/impresso.
> Fonte dos achados: `achados/NN-area.md` (um por área, com seção "Verificado e OK"). Specs propostas: `SEC-NN-<slug>.md` nesta pasta (NN = prioridade; o coordenador numera como SPEC-XXX e move para `specs/`).

## 0. Resumo

| Severidade | Achados válidos (únicos após mesclar duplicatas) | Entradas na tabela (inclui duplicatas/descartados) |
|---|---|---|
| **Crítica** | 0 | 0 |
| **Alta** | **1** — perfil `legacy` (sem auth) é o default e nada falha fechado em deploy exposto (AUTHZ-01 ≡ SESS-06/AUTHZ-07) | 3 |
| **Média** | **15** — `/metrics` público; rate limit só por IP e lista curta; IP atrás de proxy (hipótese); logout sem revogar refresh + 500; lockout por e-mail; turnos sem cota por owner/cap de texto; RLS não efetivo (R-05); amplificação GoTrue; `quest_completed` sem prova; `print()` com conteúdo de jogo; delete/export ignoram 3 tabelas; delete de campanha não purga blobs; terceiros não declarados; `ValueError`→401 com mensagem interna; policies de Storage com escrita do cliente | 21 |
| **Baixa** | 24 | 26 |
| **Info** | 8 | 8 |
| **Descartados** | — | 6 (SESS-10, INJ-03, AUTHZ-11, PRIV-10, INFRA-09, PRIV-05 parcial) |

Controles **confirmados corretos** (não reauditar — detalhe nas seções "Verificado e OK" de cada área): isolamento por `owner_id` em todas as rotas `/game|/account` (sem IDOR); CSRF double-submit + Origin + `compare_digest`; cookies `HttpOnly/Secure(env)/SameSite`; webhook Stripe (raw body, HMAC, tolerância, `livemode=false`, valor/moeda/ordem conferidos, advisory lock); Google Play (HMAC de conta, token/order únicos, consume após crédito, fake barrado em hosted); wallet (append-only, sem overdraft, `FOR UPDATE`, ticket antes da rede, `Decimal`); cron `/internal/*` (Bearer `compare_digest`, fail-closed); SQL 100% parametrizado; path traversal (UUID + containment); SSRF (hosts fixos, sem redirect); STT (teto antes do body, magic bytes, ffmpeg sem shell, tmpdir sempre removido); XSS (`mdLite` escapa antes de formatar — **fecha a pendência da SPEC-211 sem achado**); CSP restritiva; `query_rag` sempre `public`; segredos de lore fora do prompt do NPC; ouro/loot/dano/nível/morte exclusivos do motor; nenhum segredo rastreado nem no histórico git; Android (`allowBackup=false`, sem cleartext, sem deep links, keystore fora do repo); deps Python acima dos CVEs conhecidos; logs `rpg.*` pseudonimizados; áudio STT efêmero; signed URLs 300 s; token de e-mail em fragmento de URL.

## 1. Cobertura por área

| Área | Arquivo de achados | Status |
|---|---|---|
| 01 AuthN/AuthZ e isolamento multi-tenant | `achados/01-authz-tenant.md` | concluída (1 alta, 5 médias, 3 baixas, 5 info) |
| 02 Sessão/CSRF/cookies/CORS/CSP/headers/Turnstile/rate limit/Android | `achados/02-sessao-csrf-headers.md` | concluída (6 médias, 2 baixas, 2 info) |
| 03 Pagamentos/wallet/reconciliação/kill switches | `achados/03-pagamentos-wallet.md` | concluída (1 média, 4 baixas, 1 info) |
| 04 Injeção (SQL/path/SSRF/deserialização/XSS/upload) | `achados/04-injecao.md` | concluída (2 baixas, 1 info) |
| 05 Prompt injection / abuso de LLM | `achados/05-prompt-injection-llm.md` | concluída (2 médias, 3 baixas, 1 info) |
| 06 Privacidade/LGPD | `achados/06-privacidade-lgpd.md` | concluída (5 médias, 3 baixas, 2 info) |
| 07 Segredos e supply chain | `achados/07-segredos-supply-chain.md` | concluída (4 baixas, 3 info; zero segredos) |
| 08 Infra/config | `achados/08-infra-config.md` | concluída (2 médias, 5 baixas, 1 info) |

## 2. Tabela de achados (todos, inclusive descartados)

| ID | Título | Sev. | Área | Local | Confiança | Verificação do orquestrador | Spec |
|---|---|---|---|---|---|---|---|
| AUTHZ-01 | Perfil `legacy` (sem login) é o default; `Procfile` sobe `0.0.0.0` sem exigir perfil; guard de loopback valida só `RPG_BIND_HOST` declarado e é lazy | **alta** | 01 | `Procfile:1`; `api.py:87-94`; `infrastructure/runtime.py:186,220,249,446` | confirmado | **Confirmado** por leitura (converge com SESS-06). Deploy sem `RPG_RUNTIME_PROFILE` = API inteira sem auth/CSRF, saves compartilhados, custo LLM anônimo | SPEC-218 |
| AUTHZ-02 | RLS não é barreira efetiva: backend conecta como role elevada, nunca `SET ROLE rpg_api`/`request.jwt.claim.sub` | média | 01 | `infrastructure/postgres.py:25-60`; migration `20260819002358_auth_rls.sql` | confirmado | **Confirmado** (0 hits de `SET ROLE`/`set_config` no runtime); já rastreado como R-05 P1 aberto no risk-register (sem spec de implementação) | SPEC-223 |
| AUTHZ-03 | Cada cookie `rpg_access` inválido gera 1 chamada ao GoTrue (`/auth/v1/user`) sem pré-validação local, cache ou rate limit | média | 01 | `api.py:103-105`; `infrastructure/supabase_identity.py:146-160` | provável | **Confirmado** que não há cache/pré-checagem; efeito de 429 upstream = provável | SPEC-220 |
| AUTHZ-04 | Duplicata de SESS-03 (rotas caras fora do rate limit; `chronicle/search` custa embedding sem cobrar) | média | 01 | `api.py:3677-3707` | confirmado | Mesclado em SESS-03 | SPEC-220 |
| AUTHZ-05 | Duplicata de SESS-02 (IP sem proxy) | média | 01 | `api.py:802` | hipótese | Mesclado em SESS-02 | SPEC-220 |
| AUTHZ-06 | Duplicata de SESS-01 (`/metrics`); acrescenta exposição de `rpg_llm_cost_usd_total{provider,tier}` | média | 01 | `api.py:1608-1692` | confirmado | Mesclado em SESS-01 | SPEC-219 |
| AUTHZ-07 | Duplicata de SESS-06 (defaults inseguros hosted; `cloud_doctor` não checa) | média | 01 | `api.py:262`; `services/account_security.py:44-47`; `scripts/cloud_doctor.py` | confirmado | Mesclado em SESS-06 | SPEC-218 |
| AUTHZ-08 | Duplicata de SESS-05 (lockout por e-mail) | baixa | 01 | `services/account_security.py:80-90` | confirmado | Mesclado em SESS-05 | SPEC-221 |
| AUTHZ-09 | OIDC (hosted/portable) não valida `aud`/`azp`, `email_verified`; `iss` assumido se ausente | baixa | 01 | `infrastructure/oidc_identity.py:36-54` | confirmado | Aceito (perfil não usado em produção; bloquear antes de ativar) | SPEC-221 |
| AUTHZ-10 | `/docs`, `/redoc`, `/openapi.json` abertos em hosted; CSP relaxada nesses paths | baixa | 01 | `api.py:60-64,161,202` | confirmado | Aceito | SPEC-219 |
| AUTHZ-11 | Informativos (tabelas sem RLS mas sem grant; oráculo de UUID em `claim`; senha mín. 8; CSRF sem vínculo) | info | 01 | vários | — | **Descartados** pelo subagente, revisados: sem vetor | — |
| SESS-01 | `/metrics` público roda 3 queries no Postgres por scrape; vaza filas/FinOps; esgota pool (1 conexão em hosted-supabase) | média | 02 | `api.py:1608-1692` | confirmado | **Confirmado** por leitura (sem auth, fora de `_session_boundary` e de `_rate_limit`) | SPEC-219 |
| SESS-02 | Rate limit usa `request.client.host` sem tratar proxy Vercel (bucket compartilhado ou spoof) | média | 02 | `api.py:802`; `services/account_security.py:83` | hipótese | Confirmada a ausência de leitura de `x-vercel-forwarded-for`; comportamento real do runtime = a medir no staging | SPEC-220 |
| SESS-03 | Rate limit por IP cobre só 8 rotas; `art/brief`, `art/quote`, `chronicle/search`, `checkout`, `google/verify` sem limite | média | 02 | `api.py:790-801` | confirmado | **Confirmado** (lista fechada de paths) | SPEC-220 |
| SESS-04 | Logout não revoga refresh quando o access expirou (Android: 14 dias); CSRF inválido/GoTrue≠2xx no logout → 500 | média | 02 | `api.py:577-590`; `infrastructure/supabase_identity.py:138-144` | confirmado | **Confirmado**: `logout()` levanta `Unauthorized`; não há `@app.exception_handler`; refresh só apagado no cliente | SPEC-221 |
| SESS-05 | Lockout direcionado: bucket por e-mail (5/15 min) conta tentativas antes de validar senha | média | 02 | `services/account_security.py:81-91` | confirmado | **Confirmado** por leitura | SPEC-221 |
| SESS-06 | Perfis `hosted*` não falham fechado sem `RPG_COOKIE_SECURE=1`, CORS explícito, captcha obrigatório; `RPG_RUNTIME_PROFILE` ausente ⇒ `legacy` (sem auth) mesmo com `VERCEL` | média→**alta** (reclassificada) | 02 | `api.py:87,262`; `infrastructure/runtime.py:186,446`; `services/account_security.py:40-45` | confirmado | **Confirmado**: `apply_serverless_defaults` não força perfil; deploy sem a env expõe `/game/*` sem login (custo LLM em `/game/prologue`). Elevada a alta por impacto de misconfig total | SPEC-218 |
| SESS-07 | Login modo `app` sem checagem de Origin (login CSRF) | baixa | 02 | `api.py:282-306` | provável | Aceito como baixa (staging/prod usam `gotrue`) | SPEC-221 |
| SESS-08 | Sem `Cache-Control: no-store` em `/game/*`,`/account/*`; HSTS só via Vercel | baixa | 02 | `api.py:164-205` | confirmado | Aceito | SPEC-219 |
| SESS-09 | CSP `style-src 'unsafe-inline'`, sem `form-action` | info | 02 | `api.py:149-160` | confirmado | Aceito (endurecimento) | SPEC-219 |
| SESS-10 | CSRF não vinculado à sessão; `rpg_recent` reutilizável na janela | info | 02 | `services/auth_sessions.py:37-54` | — | **Descartado** (SameSite=Strict + Origin; sem vetor sem XSS) | — |
| PAG-01 | Cap diário opt-in, reativo (cron) e sem cobrir LLM de texto; turnos sem cota por owner | média | 03 | `services/daily_spend_cap.py:1-15,107-147`; `api.py:790-831` | confirmado | **Confirmado**; SPEC-197 R-11 declara a limitação, nenhuma spec cria cota por owner | SPEC-220 |
| PAG-02 | Compras de teste do Play (`purchaseType=0/2`) creditadas em produção | baixa | 03 | `services/google_play.py:68,86-93` | confirmado | Aceito (lista de testers controlada pelo operador) | SPEC-222 |
| PAG-03 | `/account/checkout`, `google/verify`, `art/quote` sem rate limit → ordens/sessões Stripe e linhas imutáveis ilimitadas | baixa | 03 | `api.py:2035-2050,2113-2135,2446-2490` | confirmado | Aceito; mesmo tema de SESS-03 | SPEC-220 |
| PAG-04 | Kill switches fail-open por default com store ilegível | baixa | 03 | `services/kill_switches.py:100-140` | confirmado | Decisão SPEC-196 F1; proposto default fail-closed p/ `image`/`stt_fallback` em hosted | SPEC-218 |
| PAG-05 | Duplicata de SESS-02 (rate limit atrás de proxy) | baixa | 03 | `api.py:803-807` | hipótese | Mesclado em SESS-02 | SPEC-220 |
| PAG-06 | Usuário pagante pode estourar o cap global e desligar imagem/STT p/ todos | info | 03 | `services/daily_spend_cap.py:107-147` | provável | Aceito como informativo (cap por owner em SPEC-220) | SPEC-220 |
| INJ-01 | `Content-Disposition` do export usa `isalnum()` Unicode → 500 com nome fora de latin-1 | baixa | 04 | `api.py:3736-3738` | provável | Aceito (robustez; sem splitting) | SPEC-219 |
| INJ-02 | Sem teto global de body antes do parse Pydantic (DoS de memória em self-host) | baixa | 04 | `api.py` (sem middleware de body) | provável | Aceito (Vercel 4,5 MB mitiga) | SPEC-219 |
| INJ-03 | FAISS `allow_dangerous_deserialization=True` | info | 04 | `rag.py:661,…` | confirmado | **Descartado** (índice de sessão só no perfil `legacy`; globais vêm do repo) | — |
| LLM-01 | `quest_completed`/`secret_revealed`/`npc_killed` propostos pelo LLM sem prova determinística: +200 XP +20 ouro por instrução do jogador | média | 05 | `services/world_validators.py:72-90,41-52,30-38`; `services/event_processor.py:277-325` | confirmado | **Confirmado** por leitura (`_v_quest_completed` só checa `status=="active"`); efeito confinado ao próprio save | SPEC-223 |
| LLM-02 | `relationship_change` do NPC sem clamp por turno (pula gate de recrutamento ≥7) | baixa | 05 | `agents/npc.py:114,549` | confirmado | Aceito | SPEC-223 |
| LLM-03 | Texto do jogador/backstory sem delimitador nem instrução anti-injeção; persiste no resumo/memória | baixa | 05 | `agents/archivist.py:640-690`; `api.py:2705` | confirmado | Aceito (defesa em profundidade; números protegidos em Python) | SPEC-223 |
| LLM-04 | Duplicata de PAG-01 com números: ~43k turnos/dia/conta ≈ US$ 35–430/dia; sem cota por owner | média | 05 | `api.py:775-831`; `services/daily_spend_cap.py` | confirmado | Mesclado em PAG-01 | SPEC-219 |
| LLM-05 | Catálogo global de NPC/inimigo gerado de texto do jogador, compartilhado entre tenants, regrava tudo a cada criação; nome sem teto força tier SMART | baixa | 05 | `agents/npc.py:160-177,240-285`; `agents/bestiary.py:171-240` | confirmado | Aceito | SPEC-223 |
| LLM-06 | Hosted sem key de provider cai silenciosamente em MockLLM | info | 05 | `llm_setup.py:1088-1100` | confirmado | Aceito; tratado como requisito de config fail-closed | SPEC-218 |
| PRIV-01 | `print()` joga fatos/nome/consulta do jogador no stdout (logs Vercel); contradiz política e Data Safety | média | 06 | `agents/archivist.py:123`; `api.py:2679`; `agents/librarian.py:42,46`; outros `print` em `agents/*` | confirmado | **Confirmado** (grep: ~20 `print` em `agents/` fora do caminho `safe_json`) | SPEC-222 |
| PRIV-02 | Delete/export de conta ignoram `google_play_purchases` (purchase_token cru), `wallet_debt_entries`, `purchase_reconciliation_state`; retenção não declarada | média | 06 | `infrastructure/account_lifecycle.py:8-13`; migrations `20261015130000`, `20261015140000` | confirmado | **Confirmado** (listas `PRIVATE_TABLES`/`FINANCIAL_TABLES` lidas) | SPEC-222 |
| PRIV-03 | `DELETE /game/save/{id}` em perfil DB não remove blobs de imagem (órfãos até exclusão da conta) | média | 06 | `infrastructure/postgres_turns.py:345-374`; `api.py:3628-3665` | confirmado | Aceito pelo grep do subagente (`blobs.delete` só em `account_lifecycle.py:97`) | SPEC-222 |
| PRIV-04 | Terceiros reais não declarados: OpenAI (imagens) como `<...>`, Google Fonts (IP de todo visitante), SMTP | média | 06 | `infrastructure/openai_images.py:30-53`; `web/index.html:9-12`; `docs/spec197/legal/privacy-policy.md` §4 | confirmado | Aceito; parcialmente já em SPEC-197 R-10 (placeholders) — Google Fonts é novo | SPEC-222 |
| PRIV-05 | "Sem link para política/termos na UI, sem rota pública" + sem aviso de IA/idade | média→**baixa** (reclassificada) | 06 | `web/src/components/AuthScreen.tsx`; `App.tsx:847-848` | parcial | **Parcialmente descartado**: `/privacidade/` e `/termos/` são gerados no build (`web/scripts/legal.mjs`) e linkados em `App.tsx:847-848` (R-10 SPEC-197). Resta: texto de aceite no signup, aviso de processamento por IA e idade mínima `<18/13?>` | SPEC-222 |
| PRIV-06 | Export parcial (sem blobs/Google/dívida) e síncrono com `select *` (colunas internas) | baixa | 06 | `infrastructure/account_lifecycle.py:28-38` | confirmado | Aceito | SPEC-222 |
| PRIV-07 | Sem TTL para `usage_events`, `operations`/`jobs` terminais, `account_deletions`, `finops_evaluations` | baixa | 06 | migrations | confirmado | Aceito | SPEC-222 |
| PRIV-08 | `pseudonym()` usa chave pública `local-telemetry-only` sem `RPG_TELEMETRY_SECRET`; nada exige a env em hosted | baixa | 06 | `observability/telemetry.py:64-66` | confirmado | Aceito; requisito de config → SPEC-218 R3 | SPEC-218 |
| PRIV-09 | `rpg.prose` loga abertura da narração em claro | info | 06 | `services/prose_guard.py:260` | confirmado | Agrupado com PRIV-01 | SPEC-222 |
| PRIV-10 | Alertas FinOps sem ids de usuário | info | 06 | `observability/metrics.py:12-41` | — | **Descartado** (controle correto) | — |
| 07-01 | `.gitignore` não cobre `.env.*`, `*.pem`, `*.keystore`, `google-services.json` (preventivo; histórico limpo) | baixa | 07 | `.gitignore`; `web/android/.gitignore:104-105` | confirmado | Aceito | SPEC-225 |
| 07-02 | `validate.yml`/`audit-local.yml` sem `permissions:` | baixa | 07 | `.github/workflows/validate.yml:1-9`, `audit-local.yml:1-15` | confirmado | Aceito | SPEC-225 |
| 07-03 | Actions por tag mutável (`@v4/@v5`), sem pin por SHA | baixa | 07 | `.github/workflows/*.yml` | confirmado | Aceito | SPEC-225 |
| 07-04 | `eval-protected.yml` roda código do ref do dispatch com secrets de Environment; restrição de branch não visível no repo | baixa | 07 | `.github/workflows/eval-protected.yml:24-76` | provável | Aceito (verificar config de Environments no GitHub) | SPEC-225 |
| 07-05 | esbuild 0.21.5 (dev server only) abaixo do advisory | info | 07 | `web/package-lock.json` | provável | Aceito (só `npm run dev`) | SPEC-225 |
| 07-06 | Release Android `minifyEnabled false` | info | 07 | `web/android/app/build.gradle:54` | confirmado | Aceito (informativo) | SPEC-225 |
| 07-07 | Scripts de ops aceitam `--dsn` com senha em argv | info | 07 | `scripts/export_game_data.py:21` etc. | confirmado | Aceito (informativo) | SPEC-225 |
| INFRA-01 | `_session_boundary` envolve `call_next` no `try` que captura `ValueError` → qualquer `ValueError` de handler vira 401 com `str(exc)` (vaza detalhe, mascara 5xx, front desloga) | média | 08 | `api.py:103-146` | confirmado | **Confirmado** pela leitura do middleware | SPEC-220 |
| INFRA-02 | Policies de `storage.objects` `to authenticated` permitem insert/update/delete no prefixo do usuário (bypass de quota; apagar/sobrescrever arte paga) | média (defesa em profundidade) | 08 | `supabase/migrations/20260820113242_dynamic_storage_bucket_rls.sql:18-52` | provável | Policies **confirmadas** ativas; premissa "chave publishable pública no front" é **falsa** (0 hits em `api.py`/`web/src`) — pré-condição hoje não satisfeita, mas a chave é pública por design da Supabase; backend usa service role, policies de escrita são desnecessárias | SPEC-224 |
| INFRA-03 | `RPG_RATE_LIMIT<=0` desliga o rate limit em qualquer perfil | baixa | 08 | `api.py:783-790` | confirmado | Aceito | SPEC-218 |
| INFRA-04 | Flags que enfraquecem segurança sem bloqueio em código hosted; checklist valida nomes, não valores | baixa | 08 | `scripts/release/checklist.py:39`; `llm_setup.py:1088-1112` | confirmado | Aceito | SPEC-218 |
| INFRA-05 | `RPG_CORS_ORIGINS` sem validação (`*`/http aceitos); `allow_headers=*` | baixa | 08 | `api.py:66-80` | provável | Aceito | SPEC-218 |
| INFRA-06 | `/docs`/`/openapi.json` listam `/internal/cron/*` e modelos de pagamento; páginas sem CSP | baixa | 08 | `api.py:59-63,161,202`; `services/cron_internal.py:20` | confirmado | Aceito (aprofunda AUTHZ-10) | SPEC-218 |
| INFRA-07 | `auth_config.py` não fixa senha mínima/rotação de refresh/`jwt_exp` no Auth remoto; GoTrue chamável direto | baixa | 08 | `scripts/staging/auth_config.py:30-52` | provável | Aceito | SPEC-220 |
| INFRA-08 | Falhas CSRF/Origin saem como 401 com mensagens distintas (deveria ser 403 genérico) | info | 08 | `api.py:146` | confirmado | Aceito | SPEC-220 |
| INFRA-09 | `pseudonym()` chave default | — | 08 | `observability/telemetry.py:64-66` | — | **Descartado** (duplicata de PRIV-08) | — |

## 3. Mapeamento achado → spec

| Spec (arquivo) | Título | Sev. máx. | Achados cobertos | Depende de | Review |
|---|---|---|---|---|---|
| `SPEC-218-fail-closed-perfil-config-hosted.md` | Fail-closed de perfil e configuração em deploy exposto | **alta** | AUTHZ-01, SESS-06/AUTHZ-07, PAG-04, LLM-06, PRIV-08, AUTHZ-10/INFRA-06, INFRA-03, INFRA-04, INFRA-05 | — | Astra (true) |
| `SPEC-219-cota-por-owner-rate-limit-proxy.md` | Cota de custo por owner, cobertura do rate limit e IP real atrás de proxy | média (impacto de custo alto) | PAG-01/LLM-04, SESS-02/AUTHZ-05/PAG-05, SESS-03/AUTHZ-04/PAG-03, AUTHZ-03, PAG-06 | SPEC-218 | Sol (true) |
| `SPEC-220-sessao-logout-lockout-oidc.md` | Sessão: revogação no logout, erros 401/403 consistentes, lockout, OIDC, Auth remoto | média | SESS-04, SESS-05/AUTHZ-08, SESS-07/AUTHZ-10(b), AUTHZ-09, INFRA-01, INFRA-07, INFRA-08 | — | Sol (true) |
| `SPEC-221-superficies-operacionais-headers.md` | `/metrics` autenticado, `no-store`/HSTS/CSP, teto de body, export robusto | média | SESS-01/AUTHZ-06, SESS-08, SESS-09, INJ-01, INJ-02 | — | Sol (false) |
| `SPEC-222-privacidade-lgpd-logs-retencao.md` | Logs sem conteúdo de jogo, exclusão/export completos, terceiros declarados, consentimento, TTL | média | PRIV-01/09, PRIV-02, PRIV-03, PRIV-04, PRIV-05 (parcial), PRIV-06, PRIV-07 | — | Sol (true) |
| `SPEC-223-llm-autoridade-mecanica-prompt-injection.md` | Prova determinística para eventos propostos pelo LLM; delimitação da entrada; catálogo por tenant | média | LLM-01, LLM-02, LLM-03, LLM-05 | — (coordena com SPEC-199/203) | Sol (true) + eval |
| `SPEC-224-rls-efetivo-role-minimo-storage.md` | Role de menor privilégio + `SET LOCAL ROLE` por request; Storage sem escrita do cliente | média (fecha R-05 P1) | AUTHZ-02, INFRA-02 | SPEC-218 | Astra (true) |
| `SPEC-225-supply-chain-ci-release-hygiene.md` | gitignore, permissions/pins/Dependabot/gitleaks/audits, `--dsn-env`, compras de teste do Play | baixa | 07-01..07-05, 07-07, PAG-02 | — | Sol (false) |

Sem spec (descartados ou informativos sem ação): SESS-10, INJ-03, AUTHZ-11, PRIV-10, INFRA-09, 07-06 (minify — opcional).

## 4. Ordem recomendada de execução

1. **SPEC-218** (alta; pré-requisito dos demais; pequena — 3 etapas; review Astra).
2. **SPEC-219** (custo/abuso do beta pago; inclui a medição do IP no staging que SPEC-220/04 reutilizam).
3. **SPEC-220** (sessão + erro 401/403 + `_session_boundary`; pode rodar em paralelo com SPEC-219 — arquivos distintos salvo `api.py`).
4. **SPEC-224** (R-05 do risk-register; exige janela de deploy com rotação de DSN — agendar após SPEC-218 e antes da promoção a produção; review Astra).
5. **SPEC-222** (privacidade; bloqueia Data Safety/Play e o gate legal da SPEC-197 — pode andar em paralelo com 2–4 por tocar tabelas/docs/UI distintos).
6. **SPEC-221** (superfícies; rápida; `/metrics` com token precisa do runbook antes do scrape em produção).
7. **SPEC-223** (gameplay; coordenar com SPEC-199/203 para não conflitar em `storyteller`/`event_processor`; eval separado).
8. **SPEC-225** (higiene; `Luna` para o mecânico; a qualquer momento).

Paralelizável: {SPEC-219, SPEC-220}, {SPEC-222, SPEC-225} e SPEC-223 independem entre si; SPEC-218 primeiro; SPEC-224 numa janela própria.

## 5. Áreas não auditadas / limitações

- Nenhuma área ficou sem auditoria; nenhum subagente falhou por erro de API.
- **Hipóteses não medidas** (exigem staging): comportamento de `request.client.host` no runtime Vercel (SESS-02 — SPEC-219 R5 mede); rate limit do Supabase Auth sob amplificação (AUTHZ-03); restrição de branch dos Environments do GitHub (07-04 — configuração fora do repo).
- **Não executado**: nenhum teste/exploit contra staging/produção; nenhum provider pago; `pip-audit`/`npm audit` não rodados nesta auditoria (versões comparadas de memória — SPEC-225 R6 os coloca no CI).
- **Testes lidos por nome** (não por dentro) em parte das áreas 01/02 — as seções "Verificado e OK" indicam quando isso ocorreu.
- **Fora do escopo desta rodada**: bugs funcionais (pasta `../bugs/`), SPEC-199..217 já em `specs/`, gates já documentados como decisão do dono (chaves reais Turnstile/SMTP/backups/plano Vercel Pro — risk-register R-06/R-07/R-09/R-10).


## Numeração final (coordenador)

- SEC-01 → SPEC-218 (`specs/SPEC-218-fail-closed-perfil-config-hosted.md`)
- SEC-02 → SPEC-219 (`specs/SPEC-219-cota-por-owner-rate-limit-proxy.md`)
- SEC-03 → SPEC-220 (`specs/SPEC-220-sessao-logout-lockout-oidc.md`)
- SEC-04 → SPEC-221 (`specs/SPEC-221-superficies-operacionais-headers.md`)
- SEC-05 → SPEC-222 (`specs/SPEC-222-privacidade-lgpd-logs-retencao.md`)
- SEC-06 → SPEC-223 (`specs/SPEC-223-llm-autoridade-mecanica-prompt-injection.md`)
- SEC-07 → SPEC-224 (`specs/SPEC-224-rls-efetivo-role-minimo-storage.md`)
- SEC-08 → SPEC-225 (`specs/SPEC-225-supply-chain-ci-release-hygiene.md`)
- BUG-01 → SPEC-226 (`specs/SPEC-226-contabilidade-recompensas-xp.md`)
- BUG-02 → SPEC-227 (`specs/SPEC-227-economia-inventario-integridade.md`)
- BUG-03 → SPEC-228 (`specs/SPEC-228-morte-checkpoint-persistencia.md`)
- BUG-04 → SPEC-229 (`specs/SPEC-229-intencao-viagem-fuga-router.md`)
- BUG-05 → SPEC-230 (`specs/SPEC-230-npc-ciclo-de-vida-guard.md`)
- BUG-06 → SPEC-231 (`specs/SPEC-231-combate-morte-aliados.md`)
- BUG-07 → SPEC-232 (`specs/SPEC-232-combate-modificadores-passivas-reacoes.md`)
- BUG-08 → SPEC-233 (`specs/SPEC-233-mundo-perigo-clima-luz-storyteller.md`)
- BUG-09 → SPEC-234 (`specs/SPEC-234-memoria-rag-arquivista-resiliencia.md`)
- BUG-10 → SPEC-235 (`specs/SPEC-235-api-frontend-pending-erros.md`)
- BUG-11 → SPEC-236 (`specs/SPEC-236-finops-wallet-jobs-reprocesso.md`)
