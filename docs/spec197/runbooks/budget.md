# Orcamento e limites de gasto (SPEC-197 R7)

Defesa em camadas: (1) teto no provedor (duro), (2) kill switches e alertas FinOps (nossos), (3) revisao diaria no
beta. Valores sao PROPOSTAS para o usuario confirmar em `external-inputs.md`.

| Camada | Onde | Limite sugerido (beta) | Quem |
|---|---|---|---|
| Supabase | Org > Billing: Spend Cap (Pro) | cap ligado; nenhum add-on sem aprovar | usuario |
| Vercel | Team > Billing > Spend Management (Pro) | alerta 50/75/100%, pausa no teto | usuario |
| DeepSeek | platform.deepseek.com, saldo prepago | recarga manual pequena; sem auto-recarga | usuario |
| Groq | console.groq.com, Billing/limits | free tier ou limite mensal | usuario |
| OpenAI (STT/imagem, se usado) | platform.openai.com > Settings > Limits | hard limit mensal + alerta | usuario |
| Jina (embeddings) | jina.ai dashboard | saldo prepago | usuario |
| Google (Gemini/Play) | Cloud Console > Budgets & alerts | alerta; sem chave Gemini se nao usada | usuario |
| Stripe | monitorar disputas/refunds | alertas por e-mail | usuario |

## Cap diario no app
- Custo por chamada e atribuido e comparado a margem em `services/finops.py`; `POST /internal/cron/finops` a cada
  15-30 min grava `app.finops_evaluations`. `FinopsCostSpike`, `FinopsMarginBelowTarget`, `FinopsExpensiveFallback`,
  `FinopsProviderFailure`, `FinopsEvaluationStale` pedem acao do operador.
- Resposta a custo anomalo: `off image_generation`, `off stt_fallback_expensive`, `off model:<p>/<m>` e, se preciso,
  `off new_purchases`. Playbook em `incident.md`.
- **Corte automatico diario (SPEC-197 R7, implementado):** defina `RPG_DAILY_SPEND_CAP_BRL` (ex. `30`). Sem a variavel
  (ou invalida/<=0) a funcao fica DESLIGADA. O cron `/internal/cron/finops` soma o gasto variavel do dia
  (`usage_events.cost_usd` x FX da pricing version mais nova, ou 6,0 se nao houver; dia = America/Sao_Paulo, UTC-3,
  ajustavel em `RPG_DAILY_SPEND_TZ_OFFSET_HOURS`). Acima do teto liga OFF `image_generation` e `stt_fallback_expensive`
  com ator `system:finops` e motivo na auditoria, uma unica vez (idempotente), e emite o alerta bloqueante
  `daily_spend_cap` (`FinopsDailySpendCap`). NUNCA religa sozinho: o humano faz
  `scripts/admin_kill_switch.py on <chave> --actor <voce> --reason "<motivo>" --apply`. Compras (`new_purchases`) e
  leitura de campanhas nao sao tocadas. Depende do cron estar agendado (R-12); cadencia 15-30 min.
- `data/finops_fixed_costs.json` deve refletir Supabase Pro + Vercel Pro reais antes da producao;
  `scripts/finops_margin_sim.py` reexecutado com precos live.

## Rotina
Diaria no beta: saldo dos provedores, `finops_evaluations`, `cron_health_alerts`, refunds/disputas.
Semanal: rate cards (`stale_rate_card`); modelo novo em `ROUTES` so apos card publicado.
