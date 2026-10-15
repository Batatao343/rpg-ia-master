# SPEC-182 — Metering real de uso e custo

> **Status:** `draft`
> **Depende de:** SPEC-181 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: inventário de metadata/rate cards e relatório; normalização/cobrança ficam com Sol.
> **MODEL_BREAKDOWN:** `examples/spec-model-contract.yaml` → `SPEC-182` é source of truth para subtarefas/review focus

## Objetivo

Substituir a heurística 1200/400 como fonte financeira por eventos normalizados de usage, com provenance e pricing version, preservando playtest estimado apenas como fallback explícito.

## Requisitos

- **R1** — `usage_events` append-only vinculado a owner/operation/game/category/provider/model.
- **R2** — capturar input/output/cache/audio/image/decision units quando provider expõe; se Jev tiver sido promovido, normalizar também `usage`/cost/model do decision backend.
- **R3** — `cost_basis = provider_reported | token_priced | rate_card | estimated`, nunca misturar sem sinalizar.
- **R4** — versionar rate cards; desconhecido falha fechado para billing ou usa reserva conservadora marcada.
- **R5** — attempts/fallbacks billable entram no custo da operação quando aplicável; normalizador deve expor custo já consumido e estimativa conservadora da próxima tentativa para permitir `spend_ceiling` da wallet sem saldo negativo.
- **R6** — streaming produz usage final sem double count.
- **R7** — telemetria e ledger nunca armazenam prompt/narrativa/áudio.
- **R8** — `app.turns.llm_cost_usd` passa a receber custo consolidado real/normalizado, mantendo compatibilidade histórica.

### Fora de escopo

Wallet, Stripe, UI de conta, definir preço dos pacotes.

## Plano

1. Fixtures por provider/stream/structured retry.
2. Schema/migration + repository.
3. Normalizador único.
4. Integrar RoutedLLM/decision backend/embedding/image seams sem duplicação.
5. Relatório compara estimate antigo vs normalized sem usar long-run.

## Critérios de aceite

- [ ] uma operação com fallback soma tentativas corretamente.
- [ ] replay/idempotency não duplica usage.
- [ ] cost_basis sempre presente.
- [ ] unknown model não vira custo zero silencioso.
- [ ] redaction verde.

## Gates / evidência

Corpus determinístico + 3–5 chamadas reais curtas somente com aprovação/orçamento para validar metadata de providers. Sem long-run.

## Contrato de idempotência/attribution

Cada `usage_event` precisa de uma chave determinística que identifique a tentativa lógica (operação + componente + ordinal/attempt id). Replays de operação não podem criar eventos novos. Failed attempts só entram em custo quando o provider reportar/for conhecido que houve consumo billable; `unknown` nunca vira zero silencioso.

## Gate de fechamento

- [ ] fixtures cobrem success, fallback, retry structured, timeout pré-resposta, resposta billable com erro, streaming final e replay;
- [ ] uma operação com N attempts produz exatamente N eventos esperados e um consolidado único no turno;
- [ ] `llm_cost_usd` histórico continua carregável e novos valores vêm do consolidado normalizado;
- [ ] prompt/narrativa/áudio bruto não aparece em tabela/log/metric;
- [ ] provider/model desconhecido resulta em `cost_basis=unknown/estimated-conservative` e bloqueia billing exato, nunca `0`;
- [ ] review Sol independente aprova attribution/fallback/streaming.
