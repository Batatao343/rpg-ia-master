# SPEC-182 — Metering real de uso e custo

> **Status:** `done`
> **Depende de:** SPEC-181 `done`
> **EXECUTOR_MODEL obrigatório:** `Sol`
> **EXECUTOR_EFFORT obrigatório:** `High`
> **REVIEW_MODEL obrigatório:** `Sol`
> **REVIEW_EFFORT:** `High`
> **REVIEW_REQUIRED:** `true`
> **SUBSTITUIÇÃO DE MODELO:** proibida sem aprovação explícita do usuário; mismatch => `MODEL_HANDOFF_REQUIRED`
> **Delegação Luna permitida:** Luna: inventário de metadata/rate cards e relatório; normalização/cobrança ficam com Sol.
> **MODEL_BREAKDOWN:** `docs/rpg-next-jev-golive-plan/examples/spec-model-contract.yaml` → `SPEC-182` é source of truth para subtarefas/review focus

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

- [x] uma operação com fallback soma tentativas corretamente.
- [x] replay/idempotency não duplica usage.
- [x] cost_basis sempre presente.
- [x] unknown model não vira custo zero silencioso.
- [x] redaction verde.

## Gates / evidência

Corpus determinístico + 4 chamadas reais curtas autorizadas (2 DeepSeek, 2 Groq; invoke e stream), com teto US$ 0,50, para validar metadata de providers. Custo normalizado US$ 0,000041550. Evidência: [relatório](../docs/spec182/README.md) e [JSON redigido](../docs/spec182/live-metadata-2026-10-08.json). Revisão Sol High independente técnica e live **APPROVED** em [parecer](../handoffs/SPEC-182-SOL-independent-review.md). Sem long-run.

## Contrato de idempotência/attribution

Cada `usage_event` precisa de uma chave determinística que identifique a tentativa lógica (operação + componente + ordinal/attempt id). Replays de operação não podem criar eventos novos. Failed attempts só entram em custo quando o provider reportar/for conhecido que houve consumo billable; `unknown` nunca vira zero silencioso.

Prólogo e busca semântica são requests de leitura/preview sem `action_id` no contrato HTTP existente. Cada request aceito recebe uma operação nova; duas chamadas HTTP, inclusive retry do cliente, podem consumir o provider duas vezes. A idempotência acima vale para o replay da mesma operação interna, não para deduplicação entre requests sem chave. A busca usa claim sem exclusividade sobre o turno.

## Gate de fechamento

- [x] fixtures cobrem success, fallback, retry structured, timeout pré-resposta, resposta billable com erro, streaming final e replay;
- [x] uma operação com N attempts produz exatamente N eventos esperados e um consolidado único no turno;
- [x] `llm_cost_usd` histórico continua carregável e novos valores vêm do consolidado normalizado;
- [x] prompt/narrativa/áudio bruto não aparece em tabela/log/metric;
- [x] provider/model desconhecido resulta em `cost_basis=unknown/estimated-conservative` e bloqueia billing exato, nunca `0`;
- [x] review Sol independente aprova attribution/fallback/streaming.
