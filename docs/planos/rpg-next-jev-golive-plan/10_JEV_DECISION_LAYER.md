# Jev como decision layer — avaliação pós-evals

Este pacote NÃO assume que Jev substitui `ModelTier.CLASSIFY`. Ele mede a hipótese e só habilita rollout reversível quando os gates definidos antes dos runs forem satisfeitos.

## Estado observado

No `main` `1beefc432cce5ded4e3468e42c5e583aa4431a44`:

- `dm_router` usa `ModelTier.CLASSIFY` depois de gates Python;
- corpus routing protegido: 25 casos, 21 classification + 4 contratos/normalização;
- runner canônico força MockLLM e não mede provider real;
- `evals/experiments/` é o lugar para benchmark live sem tocar na régua;
- não há holdout privado;
- Project Index é selective-only.

## API Jev

Contrato a reverificar no dia da execução:

- `POST https://jevmodel.org/v1/systemone`;
- Bearer auth com `JEVMODEL_API_KEY` server-side;
- `Idempotency-Key` por tentativa lógica;
- tipos `choice`, `score`, `noul`;
- Choice 2–20 opções;
- até 8 perguntas por request;
- `state` serializado até limite oficial vigente;
- resposta registra model/usage/confidence/probabilities quando aplicável.

Jev não entra no `RoutedLLM`; recebe DTO mínimo por um `DecisionBackend` próprio.

## Hipóteses testáveis

1. `route` bounded pode ser resolvido por Choice sem regressão.
2. `loot_context` bounded pode ser resolvido por Choice.
3. `target` pode ser Choice somente quando a cena oferece <=20 IDs canônicos seguros; caso contrário é `unrepresentable` e cai para CLASSIFY.
4. Campos free-form/mixed continuam no LLM.

## A/B

- A = CLASSIFY real atual, incluindo fallback chain real.
- B = Jev-only para a decisão que está sendo medida.
- Pipeline candidate de produção futura = Jev + threshold/fallback CLASSIFY, medido/decidido apenas na SPEC-180.
- Expected/oracle nunca entram no candidate backend.
- Resultados brutos são persistidos antes do resumo.
- SPEC-178 usa 3 réplicas pareadas confirmatórias dos casos classifier-eligible.

## Target/loot

SPEC-179 congela corpus experimental antes da primeira chamada live. Casos mínimos: 0/1/multi candidate, alias, segredo/out-of-scene, inimigo, loot contexts, unknown e >20 candidates. O corpus experimental não vira regression automaticamente.

## Promoção

Resultado formal da SPEC-180:

- `NO_GO` — regressão/leak/unavailability;
- `SHADOW` — qualidade não-regressiva, mas evidência/cobertura/benefício ainda insuficiente;
- `PRIMARY_WITH_FALLBACK` — somente se regras pré-declaradas da SPEC-180 passarem.

Mesmo quando apto a primary, default pós-spec é `shadow`. Mudar default para primary exige aprovação explícita do usuário. Shadow não controla gameplay.

## Sem alegação de generalização

Sem holdout privado, o benchmark é development/regression evidence. Não usar linguagem de “melhor em geral”.
