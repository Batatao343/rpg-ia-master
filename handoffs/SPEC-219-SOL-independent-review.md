# SPEC-219 — Revisão Sol independente

- **Data:** 2026-10-17
- **Revisor:** Sol (Opus, contexto separado; não escreveu a implementação)
- **Base:** branch `spec-219` empilhada em `spec-218` (`755fd74`)
- **Veredito:** **APPROVED** com 4 correções aplicadas na revisão (abaixo). A spec segue `in-progress` só por evidência de staging.

## Escopo revisado

`services/abuse_policy.py`, `api.py` (`_rate_limit`, `_session_boundary`, `_owner_rate_limit`, `_enforce_owner_budget`,
`QuotaExceeded`, SSE), `infrastructure/supabase_identity.py` (pré-validação + cache), `infrastructure/postgres_turns.py`
(`PostgresDailyQuota`), migration `20261017110000_owner_daily_counters.sql`, `infrastructure/account_lifecycle.py`,
`infrastructure/stripe_payments.py` (ordens abertas), `services/daily_spend_cap.py` (R8), `services/retention.py`,
`services/account_security.py`, `web/src/http.ts`/`api.ts`, testes novos e o teste local editado.

## Ataques verificados (sem defeito)

- **Replay/dupla contagem:** a cota diária e o limite por owner de turnos rodam dentro do `operation_scope`, depois do recibo e de
  `_action_already_processed`; POST e SSE compartilham `_execute_action` (1 consumo por turno). Duas requisições com o mesmo
  `action_id` disputam o claim; a perdedora não chega ao contador.
- **Corrida no contador:** `INSERT … ON CONFLICT DO UPDATE … WHERE count < max` reavalia sob lock da linha; recusa não consome
  (teste Postgres com 2 threads verde).
- **Relógio:** dia calculado no banco (UTC); `retry_after` sempre ≥ 1.
- **IP spoofing (R5/R4):** `X-Forwarded-For` só é lido com `RPG_TRUSTED_PROXY_HOPS=N` e pela direita; na Vercel usa
  `x-vercel-forwarded-for` (definido pela plataforma). Valor malformado cai em `client.host`, nunca levanta.
- **Revogação:** o cache guarda só o resultado do GoTrue; `app.runtime_session_active` roda a cada request (o pool sempre existe
  no runtime DB), então logout/revogação/exclusão são imediatos entre instâncias. Atraso residual de ≤ 20 s apenas para ban sem
  revogação de sessão (D-C aceito).
- **Pré-validação:** formato, `exp` (+60 s), `aud == authenticated`, `iss` com prefixo `{SUPABASE_URL}/auth/v1` (confere com o
  GoTrue local: `GOTRUE_JWT_ISSUER=http://127.0.0.1:55321/auth/v1`). `alg`/assinatura continuam no GoTrue, como a spec manda.
- **Memória:** `_authfail_until` (2000), cache do verificador (2048), `_rate_hits` (1000) limitados.
- **PII:** métrica `rpg_rate_limited_total{class,scope}` sem ids; log `rpg.abuse` e chaves de IP pseudonimizadas. A chave
  `user:{owner}:{class}` no `rate_limit_buckets` é a definida na spec (R2), igual ao `speech:` pré-existente.
- **Fail-open:** contador ausente/indisponível e leitura do cap de texto falham abertos com log; limites por minuto continuam.
  Coerente com §7 (não derrubar o jogo); o freio financeiro restante é IP/owner por minuto.
- **Anti-esquecimento:** teste varre todas as rotas POST/DELETE `/game|/account` e exige classe.

## Correções aplicadas

1. **Deploy antes da migration quebrava conta** — `export()` e a exclusão (`finish`) iteravam `owner_daily_counters` sem
   checar existência → erro em export **e na exclusão de conta**. Agora `OPTIONAL_TABLES` + `to_regclass` pulam a tabela
   ausente (só tabelas opcionais custam consulta). Teste `test_export_and_delete_skip_daily_counters_before_migration`.
2. **JWT aninhado → 500** — payload `[[[…` (cabe num cookie) disparava `RecursionError` no `json.loads` da pré-validação,
   escapando do `except Unauthorized` (500 e sem consumir `authfail`). Agora `RecursionError` é capturado e token > 8 KiB é
   recusado antes do decode. Teste `test_deeply_nested_payload_is_unauthorized_not_500`.
3. **Cache estendia o `exp`** — um token cacheado continuava aceito até 20 s após vencer (a pré-validação tolera 60 s de
   skew). Hit de cache agora exige `exp > now`. Teste `test_cache_never_outlives_the_token_exp`.
4. **Visitante sem cookie enchia o `authfail`** — o bootstrap da SPA deslogada (401 sem cookie) consumia o balde do IP; atrás de
   NAT isso bloqueava usuários válidos por 15 min sem nenhuma chamada ao verificador a evitar. Agora só conta falha quando há
   cookie `rpg_access`. Teste `test_missing_cookie_does_not_consume_the_authfail_bucket`.
5. (teste) `test_spec222_retention_local` fixava o conjunto de `RETENTION_RULES`; atualizado com `owner_daily_counters`.

## Teste local editado pelo implementador

`test_stale_jwt_denied_in_backend_direct_wallet_and_storage`: só o payload do JWT falso ganhou `exp/aud/iss` para passar a
pré-validação; nenhuma asserção mudou. A falha (`storage.objects` do owner B, linha 175/176) **reproduz na base SPEC-218**
(worktree limpo em `755fd74`), logo não é causada aqui — compatível com o estado do Supabase local compartilhado (migration da
SPEC-224 aplicada por outro worktree). Não foi alterado.

## Riscos residuais (não bloqueiam)

- R6 por desenho: IP bloqueado por `authfail` recebe 429 inclusive com token válido (spec). Mitigado pela correção 4.
- Em instância fria o bloqueio pré-verificador só vale após a próxima falha (balde compartilhado no Postgres).
- Matcher não normaliza `//`; caminhos não roteados não chegam a handler com custo.

## Evidência

- `pytest` completo offline: ver commit (exit 0).
- `-m infra_local` (Postgres 127.0.0.1:55322): `test_daily_quota_postgres` + `test_spec222_retention_local` verdes; suíte
  infra_local inteira só com a falha pré-existente acima.
- Ruff nos arquivos tocados: verde. `npm test` 118/118, `npm run build` verde.

## Falta para `done`

SPEC-218 aterrissar; aplicar `20261017110000_owner_daily_counters.sql` no staging; medição R5 (header de IP real na Vercel);
smoke §6 no staging com códigos/`Retry-After` e a métrica `rpg_rate_limited_total`.
