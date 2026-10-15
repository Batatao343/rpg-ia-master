# SPEC-196: FinOps, margin guard e observabilidade comercial

Status: implementado offline; revisao Sol APPROVED_WITH_FOLLOWUPS (F1-F8 aplicados, ver fim); smoke no staging Postgres pendente.
Simulacao de margem: [margin-simulation.md](margin-simulation.md).

## Componentes
- `services/finops.py` (puro): margem por **canal x SKU x pricing_version x coorte** (semana ISO
  da 1a compra do dono). `gross`, `channel_fee` (REAL de `purchase_fee_records` quando conciliada,
  senao ESTIMADA pela fee da pricing_version, marcada `estimated|mixed`), `variable_cost`
  (`usage_events` x FX da versao, rateado por `shard_milli` entre as compras do dono),
  `contribution_margin`, `margin_pct`, meta 5% por SKU/canal/versao (sem imposto). Custo por
  turno / imagem / minuto de voz. Uso de donos sem compra aparece em `unallocated_variable_cost_brl`.
- **Infra fixa**: `data/finops_fixed_costs.json` (Vercel/Supabase, USD/mes; hoje 0 em Free/Hobby).
  Aparece como linha propria e em `operating_result_brl`; **nunca** entra na margem de SKU.
- `services/finops_alerts.py`: avaliadores + gauges Prometheus (labels fechados `kind, channel,
  sku_id, provider, model`; valores com cara de id viram `other`). `infrastructure/finops_reader.py`:
  SQL read-only (pool privilegiado, como a reconciliacao) + `FakeFinopsReader`.
- `POST /internal/cron/finops` (Bearer `RPG_CRON_SECRET`): roda relatorio + alertas + metricas;
  resposta sem ids de dono. Agendar a cada 15-60 min junto aos demais crons.
- Regras: `observability/alerts/finops.yml` (+ `finops.test.yml`, para `promtool test rules`).

## Alertas
| Alerta (`kind`) | Significado | Acao |
|---|---|---|
| `unknown_pricing` (bloqueante) | uso com `unknown-conservative-v1`: sem rate card do modelo | publicar card/versao; ate la o custo e estimado, nunca zero |
| `stale_rate_card` (bloqueante) | FX/rate card da versao vigente, ou cards instalados (llm 30d, image/speech 7d), vencidos | atualizar card; imagem nova e recusada enquanto stale |
| `cost_spike` | custo/provider na janela > 3x media das janelas anteriores | investigar fallback/loop; considerar `model:` switch |
| `expensive_fallback` | provedor fora de `RPG_FINOPS_PRIMARY_PROVIDERS` > 25% do custo LLM | checar saude do primario; kill switch do modelo caro |
| `wallet_mismatch` | saldo != soma do ledger | congelar ajustes admin, auditar `wallet_entries` |
| `webhook_backlog` | eventos de reconciliacao nao aplicados > 1h | ver cron `reconciliation`, eventos `parked` |
| `provider_failure` | >= 30% de tentativas falhas (min 20) | fallback ja cobre; avaliar switch |
| `margin_below_target` | SKU/canal/versao < 5% | reprecificar (nova pricing_version) |

Limiares: `RPG_FINOPS_SPIKE_FACTOR`, `_SPIKE_MIN_USD`, `_FALLBACK_SHARE`, `_FALLBACK_MIN_USD`,
`_FAILURE_RATIO`, `_FAILURE_MIN`, `_BACKLOG_SECONDS`, `_LLM_CARD_MAX_AGE_DAYS`.
`RPG_FINOPS_BLOCK_STALE=0` rebaixa o bloqueio por card stale a so-alerta (emergencia).

## Kill switches (server-side, persistentes, auditados)
Tabelas `app.kill_switches` + `app.kill_switch_audit` (append-only), RLS forcada, sem grant a
clientes; mudanca so por `app.set_kill_switch()` (estado + auditoria na mesma transacao).
Ausencia de linha = **habilitado** (falha segura); erro de leitura nunca desliga nada. Cache TTL
`RPG_KILL_SWITCH_TTL_SECONDS` (5s). Override de emergencia sem DB: `RPG_KILL_SWITCHES_OFF=a,b`.

| Chave | Efeito |
|---|---|
| `image_generation` | cotacao/geracao de imagem nova -> 503 `image_generation_disabled` (campanhas seguem legiveis) |
| `stt_fallback_expensive` | roteamento de voz usa so o 1o candidato (Groq); pula OpenAI |
| `model:<provider>/<model>` | candidato pulado no `RoutedLLM` (e STT); fallback ROUTES segue |
| `decision_backend:jev` | `decide_route` volta ao CLASSIFY atual |
| `new_purchases` / `new_purchases:stripe` / `new_purchases:google_play` | NOVOS checkouts/verify recusados; replays e leitura continuam |

CLI (dry-run por padrao; `--actor` e `--reason` obrigatorios):
```
uv run python scripts/admin_kill_switch.py off image_generation --actor guilherme --reason "custo anomalo INC-7"
uv run python scripts/admin_kill_switch.py off image_generation --actor guilherme --reason "..." --apply
uv run python scripts/admin_kill_switch.py on  image_generation --actor guilherme --reason "normalizado" --apply
uv run python scripts/admin_kill_switch.py list | audit
```

## Runbook: mudanca de preco / provider
1. Medir: `uv run python scripts/finops_margin_sim.py` com o novo custo/fee; todos os SKUs >= 5%?
2. Preco/FX/fee/rate card novos = **nova** `pricing_version` + SKUs (migration de operador; versoes
   sao imutaveis). Atualizar o card em `data/pricing/` (hash/observed_at) no mesmo deploy.
3. Antes de subir: `stale_rate_card`/`unknown_pricing` devem estar verdes apos o cron `finops`.
4. Provider novo: adicionar modelo ao card ANTES de entrar em `ROUTES`; senao `unknown_pricing`.
5. Incidente de custo: `off model:<p>/<m>` (ou `image_generation`), confirmar gauge
   `rpg_finops_kill_switch_off`, investigar, reabilitar com motivo.
6. Voz: custo/minuto cobre apenas eventos com duracao (Groq, `audio_units` em ms).

## Limites conhecidos
- Margem e meta de 5% usam receita LIQUIDA (follow-up F3): `net = gross - refund_brl - dispute_brl`.
  Reversao por compra = (clawback + refund/reversal legado + divida aberta) - (claw_release + divida
  liberada), proporcional `amount_milli` da compra; disputa = estado `disputed|dispute_lost` ou
  `reversal`. Taxas reais (inclusive de disputa) ficam em `purchase_fee_records`; taxa e uso
  NAO sao devolvidos. Compra 100% revertida com taxa/uso = prejuizo (`meets_target=False`).
- Compra com `pricing_version` desconhecida e EXCLUIDA da margem e dispara
  `finops_unknown_purchase_pricing` (bloqueante); a contagem vai em `unpriced_purchases` no cron.
- Custo variavel e atribuido por dono (pro rata de `shard_milli`), nao por compra individual.
- Teste Postgres do reader/kill switch roda so com `RPG_TEST_DATABASE_URL` (ver testes).

## Follow-ups da revisao (F1-F8)
- **F1 fail-closed opcional**: erro de leitura do store e logado (so a classe do erro) e contado em
  `rpg_kill_switch_load_errors_total` (alerta `KillSwitchStoreUnreadable`). Default continua fail-open.
  `RPG_KILL_SWITCH_FAIL_CLOSED=new_purchases,image_generation` desliga essas chaves SOMENTE se o store
  esta ilegivel E nunca houve leitura boa (um snapshot bom em cache sempre vence).
- **F4 Google Play com `new_purchases` off**: `GET /account/purchases/google/profile` devolve
  `{"purchases_disabled": true}` (sem `obfuscated_account_id`); o app deve esconder os botoes de compra
  (cliente em `web/src/purchases` e da SPEC-193, ainda nao le o campo). Runbook: uma compra JA paga no
  Google e recusada no `verify` (`new_purchases_disabled`, 503) NAO e creditada nem consumida; o Play
  **reembolsa automaticamente em ~3 dias** se nao houver acknowledge. Preferir religar o switch antes
  disso: o app reenvia o mesmo token no proximo `verify` e a compra e creditada normalmente
  (estado `held` explicito nao implementado: exigiria migration/estado em `google_play_payments`, area SPEC-195).
- **F5 imagem**: worker `generate_dynamic_art` com `image_generation` off levanta `JobDeferred`; a fila
  recoloca em `queued` (+60s) sem consumir tentativa, sem chamar o provider e sem liberar a reserva.
  Replay de uma geracao existente (`/art/confirm` com quote ja confirmado) e leitura (`/game/state`)
  funcionam com o switch off; so cotacao e NOVO confirm retornam 503 `image_generation_disabled`.
- **F6**: FX do uso nao alocado e conversao da infra fixa usam a pricing_version MAIS NOVA.
- **F7 watchdog**: cada `POST /internal/cron/finops` grava uma linha owner-free em
  `app.finops_evaluations` (migration `20261015151000`, RLS forcada, sem grants) e o gauge
  `rpg_finops_evaluation_age_seconds{kind="finops"}` cresce a cada scrape de `/metrics` (alerta
  `FinopsEvaluationStale` > 2h). Sem scrape (Vercel), usar SQL. Watchdog pg_cron (o orquestrador agenda):
```sql
-- stale se nenhuma avaliacao nos ultimos 2h (retorna a linha-alvo; falhe o job se count > 0)
select now() - max(evaluated_at) as age, coalesce(max(evaluated_at) < now() - interval '2 hours', true) as stale
  from app.finops_evaluations;
-- bloqueios da ultima avaliacao
select evaluated_at, blocking_alerts, alerts from app.finops_evaluations order by evaluated_at desc limit 1;
```
  Agendar `POST /internal/cron/finops` a cada 15-30 min (mesmo mecanismo dos demais crons) e o watchdog
  acima a cada hora (`select cron.schedule('finops-watchdog','7 * * * *', $$ ... $$)`). Gauges de SKUs que
  sairam da janela sao removidos (margem por SKU = pior versao da janela).
