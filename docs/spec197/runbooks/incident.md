# Incidentes (SPEC-197)

## Severidade e resposta
| Sev | Exemplo | Meta | Acao inicial |
|---|---|---|---|
| SEV1 | cobranca indevida/duplicada, vazamento de dados, ledger inconsistente, gasto LLM fora de controle | 15 min | desligar `new_purchases` e/ou `image_generation`; congelar deploys; avisar afetados |
| SEV2 | login/turno indisponivel, provider fora, cron parado, webhook acumulando | 1 h | kill switch do provider/modelo; rollback se for deploy; status aos usuarios |
| SEV3 | degradacao (latencia, voz, imagem) | 1 dia util | ticket e monitorar |

Papeis no beta pequeno: operador e comunicador = titular. Registrar linha do tempo em
`docs/spec197/evidence/incident-<data>.md`.

## Comunicacao
- Usuarios do beta: mensagem curta (o que houve, o que fazer, proxima atualizacao) pelo contato de `web/legal/support.md`.
- Dados pessoais afetados: avaliar comunicacao a ANPD e aos titulares (LGPD art. 48) com apoio juridico.
- Pagamentos: Stripe Dashboard (disputas/refunds) e Play Console; saldo/divida via `admin_wallet_adjust.py` (dry-run).

## Kill switches (`scripts/admin_kill_switch.py`, dry-run por padrao; chaves em `services/kill_switches.py`)
```
uv run python scripts/admin_kill_switch.py list
uv run python scripts/admin_kill_switch.py off image_generation --actor <voce> --reason "<motivo>" --apply
```
Contra o staging a partir da estacao: `uv run python scripts/admin_kill_switch.py --dsn-env RPG_STAGING_DB_URL --env-file .env.staging off image_generation --actor <voce> --reason "<motivo>" --apply`.
Medido no drill (`evidence/incident_drill.json`): CLI ~0,6 s; endpoint de cotacao de imagem passa a responder 503
`image_generation_disabled` em ~5 s (TTL do cache `RPG_KILL_SWITCH_TTL_SECONDS`, default 5 s); leitura do estado do
jogo segue 200; religar leva ~5 s. O cap diario (budget.md) usa o ator `system:finops` e nunca religa.
Chaves: `image_generation`, `stt_fallback_expensive`, `model:<provider>/<modelo>`, `decision_backend:jev`,
`new_purchases` e `new_purchases:<canal>` (`stripe`, `google_play`). Efeitos em docs/spec196/README.md (imagem: jobs
adiam, replay/leitura seguem; compras: 503 `new_purchases_disabled`). Fail-closed opcional:
`RPG_KILL_SWITCH_FAIL_CLOSED`. Google Play: compra paga recusada com o switch off NAO e creditada; religar em ate
~3 dias (reembolso automatico do Play); o app reenvia o token (R-19). Reativar so com causa conhecida
(`on ... --apply`); `audit` lista o historico imutavel.

## Saude de crons e FinOps
```sql
select * from app.cron_health_alerts order by created_at desc limit 20;      -- watchdog de 15 min
select jobid, status_code, created from net._http_response order by created desc limit 20;
select now() - max(evaluated_at) as age from app.finops_evaluations;          -- stale se > 2h
select evaluated_at, blocking_alerts, alerts from app.finops_evaluations order by evaluated_at desc limit 1;
```
Logs: `npx vercel logs --environment production --since 10m --query level:error` (linhas `rpg.cron`, `rpg.turn`).
Alertas em `observability/alerts/finops.yml` (FinopsCostSpike, FinopsWalletMismatch, FinopsWebhookBacklog,
FinopsProviderFailure, FinopsMarginBelowTarget, KillSwitchStoreUnreadable, FinopsEvaluationStale...). Sem Prometheus na
Vercel, a checagem e via SQL acima ate haver scrape.

## Outage de provider
1. Confirmar no status do provider e nos logs (HTTP 402 = saldo zerado).
2. `ROUTES` ja cai para o proximo candidato; fallback caro dispara `FinopsExpensiveFallback`.
3. Desligar o modelo: `off model:<provider>/<modelo>`; voz: `off stt_fallback_expensive` se o fallback custar caro.
4. Saldo zerado: recarregar e manter o switch off ate confirmar.
5. Stripe fora: checkout falha fechado; webhook tardio e reconciliado depois. Nao creditar manualmente sem evento.
6. Supabase fora: app falha fechado; comunicar; depois rodar `recover_operations` e `recover_account_deletions` (preview primeiro).

## Pos-incidente
Revisao em ate 5 dias: causa raiz, deteccao, lacunas; atualizar `risk-register.md`.
