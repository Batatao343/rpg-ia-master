# Arquitetura alvo v1

```text
Web React/Vite ----------------------┐
                                    │ HTTPS / cookies / SSE
Android Capacitor ------------------┤
                                    v
                          Vercel / FastAPI
                         /       |        \
                        /        |         \
              Supabase Auth   Supabase    providers
                              Postgres     LLM/Jev/STT/Image
                              pgvector
                              Storage
                                  |
                                  v
                         durable async jobs
                      (topology proven in staging)
```

## Runtime

Não enfraquecer os perfis atuais `portable/hosted` OIDC+S3 para encaixar Supabase. Criar um contrato hosted-Supabase explícito, testado fail-closed. `PostgresPool` continua compartilhado por runtime; tamanho/timeout passam a ser configuração consciente de serverless/pooler.

## Frontends

- Uma base React/Vite.
- Web e API mesma origem quando possível.
- Android é shell Capacitor sobre o mesmo frontend, com adapters mínimos para billing/microfone.
- Sem React Native/Flutter no v1.
- Account vira rota/screen fora do jogo.

## Billing

```text
Stripe Checkout (web) ----\
                           > verified purchase -> wallet ledger
Google Play Billing -------/
                                     |
                                     v
                              Estilhas de Éter
                                     |
                      reserve -> usage -> settle/release
```

Wallet pertence à conta, nunca a `GameState`.

## Usage/read model

`usage_events` são vinculados a owner/reference/operation/game quando aplicável. `app.turns` é a ponte canônica para custo de turno. A UI de histórico recebe enrichment read-only; `presentation_history` não vira ledger nem recebe saldo.

Categorias iniciais:

- LLM attempts/fallbacks;
- Jev decision calls se promovido;
- embedding;
- STT;
- imagem;
- novos custos variáveis somente quando explicitamente versionados.

## Imagem

Provider de imagem fica atrás de quote owner-bound. Triggers automáticos existentes podem produzir cue/offer, não gasto. `external_result_uncertain` continua a fronteira de reconciliação para efeitos externos ambíguos.

## Worker

Não assumir que o loop atual cabe em Function. A spec de staging compara, preservando `JobQueue`/fencing/idempotência:

1. Postgres JobQueue + worker/service Python;
2. Vercel Services/Queues adapter quando fizer sentido;
3. fallback documentado se recurso beta não passar os gates.

Preferir a menor mudança que preserve a fila Postgres já certificada.

## Android billing

No app distribuído pela Play, créditos digitais usam Google Play Billing. Backend valida purchase token antes do crédito; wallet continua única. Stripe permanece web no v1. iOS é futuro.
