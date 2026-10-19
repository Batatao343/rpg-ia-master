# Runbook de debug (SPEC-262)

> Para o operador: do relato ao log em poucos minutos, só com os logs, o `/metrics` e SQL somente-leitura.
> Catálogo de códigos de erro: [CODIGOS_DE_ERRO.md](CODIGOS_DE_ERRO.md) · eventos: [EVENTOS_DE_LOG.md](EVENTOS_DE_LOG.md) ·
> retenção/níveis: [LOGS_RETENCAO.md](LOGS_RETENCAO.md) · incidentes: [incident.md](../spec197/runbooks/incident.md).
> **Estado:** receitas escritas a partir do código e dos testes; a execução de cada uma em staging (dry-run) ainda
> está pendente (critério de aceite da SPEC-262).

## Convenções (valem para todas as receitas)

- Toda linha é JSON em stdout com `event` (`area.evento`), `level`, `logger`, `ts`, `instance_ref` e, quando existir,
  `request_id`, `action_ref`, `game_ref`, `owner_ref`. **Nunca** há texto do jogador, e-mail, IP cru, token ou id cru:
  ids aparecem só como pseudônimo (HMAC). Para achar o pseudônimo de um id conhecido:
  `uv run python scripts/log_ref.py owner|game|action <id>` (lê `RPG_TELEMETRY_SECRET` do ambiente, de `.env` ou de
  `--stdin`; use o segredo do ambiente **alvo**).
- Buscar logs (produção/staging): `npx vercel logs --environment production --since 30m --query "<texto>"`.
  Saída estruturada: acrescente `--json` e filtre com `jq`. Escolha o projeto/ambiente certo (staging é outro projeto).
- `request_id` = header `X-Request-ID` de toda resposta; o **código de suporte** que o usuário vê é o início dele.
- Métricas: `GET /metrics` com `Authorization: Bearer $RPG_METRICS_TOKEN` (`404` sem token).
- SQL: só `select`, no SQL editor do Supabase do ambiente (nunca em produção com escrita).

## (a) Usuário reporta erro com código de suporte

1. Peça o código (banner vermelho → “Código de suporte: `abcd1234`”; o botão Copiar leva o id completo).
2. `npx vercel logs --environment production --since 24h --query abcd1234` (ou o id completo, se vier).
3. Olhe a linha `http.request`: `status`, `error_code` (catálogo em CODIGOS_DE_ERRO.md), `route`, `duration_ms`.
   - `status>=500` → `http.unhandled_exception` com o mesmo `request_id`: `error_type` + `stack` (`modulo:linha`).
   - `error_code=session_*|csrf_*|credentials_invalid` → receita (e).
   - `operation_*|stale_version|pending_operation` → `operation.rejected` (motivo) e `db.lease_conflict`/`db.stale_version`.
4. Turno envolvido? Copie `action_ref` e siga a receita (b).
5. Sem nenhuma linha: o erro foi de rede/CDN antes do servidor (o cliente gera o `request_id` mesmo sem resposta).
   Confira `runtime.boot` do período (receita h) e o status da Vercel.

## (b) Turno falhou ou está lento (por `action_ref`)

1. Ache o `action_ref` (linha `rpg.turn`/`http.request` do relato) ou calcule: `uv run python scripts/log_ref.py action <action_id>`.
2. `npx vercel logs --since 1h --query <action_ref>` — a linha de vida do turno, na ordem:
   `router.decision` (`source`, `fallback_reason`, `route`, `jev_mode`) → `llm.attempt` (um por candidato: `provider`,
   `tier`, `node`, `outcome`, `http_status`, `latency_ms`, `fell_back`) → `*.fallback` (degradação de nó, `reason`) →
   `turn` (latência por fase, `fallbacks`, `llm_errors`, `llm_http_statuses`, `error`) → `sse.*`/`turn_delivery`.
3. Leitura rápida:
   - `llm.exhausted` (error) = todos os providers do tier falharam → receita (f).
   - `route_source=classify_fallback` = o CLASSIFY não devolveu decisão; o turno seguiu como história.
   - `sse.client_disconnected` + `sse.worker_finished_after_disconnect` = o cliente caiu, o servidor concluiu o turno.
   - `operation.rejected reason=operation_in_progress` = outra operação do mesmo jogo ainda tem o lease (`db.lease_conflict`).
   - `db.slow_query`/`db.pool_timeout`/`db.statement_timeout` = gargalo no banco (`query_name` é um rótulo estático).
4. Métrica: `rpg_turn_phase_seconds{phase=…}` e `rpg_db_query_seconds{query_name=…}` no `/metrics`.

## (c) Pagamento não creditado (Stripe / Google Play)

1. Stripe: `--query payments.stripe_webhook` no intervalo da compra. `outcome=applied|duplicate` = entregue;
   `signature_invalid` = segredo do webhook errado; `rejected` + `error_code` (ex.: `stripe_order_sku_authority_mismatch`) =
   evento autêntico recusado pelas regras; ausência de linha = o Stripe não chegou (veja o dashboard do Stripe → Webhooks).
2. `payments.checkout_failed` (`stage=create|order`) explica o 503 de checkout.
3. Google Play: `--query payments.google_verify`: `outcome` é o código (`google_play_purchase_cancelled`,
   `google_play_token_conflict`, `google_play_unavailable` + `upstream_status`…) ou `credited`/`pending`.
   Métrica `rpg_payment_verifications_total{provider,outcome}`.
4. SQL (somente-leitura) para o estado financeiro:
   ```sql
   select order_id, status, updated_at from app.payment_orders order by updated_at desc limit 20;
   select event_id, event_type, provider_created from app.stripe_events order by provider_created desc limit 20;
   ```
5. Carteira: `wallet.settle_failed|recovery_item_failed|reservation_uncertain` (com `op_ref`) = reserva retida para
   conciliação; não credite à mão sem evento do provider (veja incident.md → “Outage de provider”).

## (d) E-mail de autenticação não chegou (GoTrue / SMTP)

1. `--query auth.upstream`: `op` (signup, reset, resend…), `public_code` (código fechado), `upstream_status`.
   `over_email_send_rate_limit` = limite de envio atingido (SMTP próprio, ver política de limites do Supabase).
2. Resposta ao usuário é sempre genérica (anti-enumeração): ausência de erro na tela não prova entrega.
3. Supabase Dashboard → Logs → Auth (mesmo horário) e o painel do provedor SMTP (Resend) para o bounce/entrega.
4. Métrica `rpg_auth_email_delivery_failures_total{action,status_class}`.

## (e) Login / recuperação falhando (`auth.*`)

1. `--query auth.session_rejected` (ou `auth.csrf_rejected`, `auth.captcha_rejected`, `auth.rate_limited`).
2. Campo `reason` (interno) × `public_code` (o que o usuário viu): `bad_signature|expired|revoked|missing…` → sessão;
   `csrf_missing|csrf_invalid|origin_denied` → página desatualizada/origem fora da allowlist (`origin_host` só se permitida);
   `turnstile_error:*` → captcha. `auth.rate_limited` (amostrado 1/min por `key_ref`) = bloqueio por tentativas.
3. `key_ref` também é pseudônimo: não revela e-mail/IP. Compare com `uv run python scripts/log_ref.py owner <id>`.
4. Métrica `rpg_auth_rejections_total{reason}`.

## (f) Provider LLM fora ou caro

1. `--query llm.exhausted` e `--query llm.attempt` filtrando `level:warning`: `provider`, `outcome` (`invoke_error`,
   `invalid_structured`, `circuit_open`, `kill_switch`, `build_error`), `http_status` (`401/402` = chave/saldo,
   `429` = quota, `5xx` = provider).
2. `circuit_open` = o candidato foi aberto por erro permanente até o fim da campanha/deploy; `kill_switch` = operador
   desligou (`scripts/admin_kill_switch.py audit`).
3. `llm.mock_selected` / `llm.fallback_llm_selected` (warning/error) = o processo está sem chaves ou em modo simulado —
   em perfil hospedado isso é incidente.
4. Custo: `rpg_llm_cost_usd_total`, alertas FinOps em `observability/alerts/finops.yml`; desligar modelo:
   `off model:<provider>/<modelo>` (incident.md).

## (g) Job ou cron travado

1. `--query job.failed` / `job.dead` / `job.lease_lost` (campos `kind`, `attempt`, `error_code` — `exc:<Classe>` quando o
   handler não definiu código, `will_retry`, `next_run_in_s`). O `request_id` do job é o do turno que o criou.
2. Cron: `--query rpg.cron` (resultado do `drain_jobs` traz `processed`, `failed`, `dead`, `deferred`).
3. SQL:
   ```sql
   select kind, status, attempts, max_attempts, last_error_code, updated_at
     from app.jobs where status in ('retry','dead') order by updated_at desc limit 30;
   select * from app.cron_health_alerts order by created_at desc limit 20;
   ```
4. `db.lease_conflict reason=lease_lost|fence_invalid|worker_late` = outro worker assumiu o lease (esperado em retry).
5. Projeção `post_response` pendente: veja `rpg_jobs{kind,status}` e `rpg_job_oldest_age_seconds`.

## (h) Um deploy novo quebrou algo

1. `--query runtime.boot`: `git_sha` (12 chars) do deploy, `profile`, `hardened`, `llm_mode`
   (`routes|legacy:<p>|mock|fallback`), `llm_providers_with_key`, `jev_mode`, `projection_mode`, `cold_start_ms`.
   `/health` mostra o mesmo `git_sha`/`profile`.
2. `--query runtime.config_warning` (`telemetry_secret_weak`, `git_sha_missing`, `cors_default_in_hosted`) e
   `runtime.build_failed` (`component=db_pool|admin_pool|vector|blob|identity` + `error_type`) para falha de subida.
3. Compare `http.request` com `status>=500` antes/depois do `instance_ref` novo. Rollback: `rollback.md`
   (promover o deploy anterior).
4. Detecção de versão do cliente vs servidor (`build_skew`) é da SPEC-261 (ainda não implementada).
