# SPEC-238 — handoff J1b → revisão Astra (novo congelamento antes da J2)

Executor: Sol (≡ Opus). Branch `spec-217`. Pedido: revisar o **novo congelamento**
`plain+target+guard@0.50+lootsrc+lguard@0.50` (SPEC-238 R7), que substitui, para a
J2, a política J1 aprovada `plain+target+guard@0.50`. A J2 **não** foi executada.
O FROZEN não foi aberto.

## O que foi feito

1. Spec [SPEC-238](../specs/SPEC-238-jev-loot-source.md) (aprovada pelo dono: "boa, cria
   uma spec para o jev cobrir o loot e vamos usar ele também", com +30 chamadas, teto
   SPEC-217 160 → 190 / US$ 1,90).
2. `evals/experiments/spec238_loot.py`: estágio `loot_source` (`treasure|shop|craft|none`)
   na **mesma** requisição da J1; features públicas `merchant_here`
   (`data/merchants.json` via `economy.merchants_at`) e `craft_station` (`craft_tags`
   do mapa); `loot_hybrid_decision` envolve `hybrid_decision` da J1 **sem editá-lo**
   (digest J1 `80225d16…10f5` segue válido e é parte do novo digest). Só atua quando a
   J1 devolveria `loot_context_out_of_scope`; não-loot passa intacto (teste).
3. Guard de loot (Python, depois da confiança): exige verbo de item; SHOP ⇐ `trade` ou
   mercador; CRAFT ⇐ `craft` ou oficina; TREASURE ⇐ sem `trade`/`craft`.
4. `DecisionState` ganhou `merchant_here`/`craft_station` opcionais (`None` fora do fio;
   payload do rollout de produção inalterado — teste).
5. Oráculo de fonte dos 13 loot DEV em arquivo separado com hash e proveniência
   (10 conferidos por teste contra `routing_actions.jsonl`/corpus SPEC-179; 3 do
   rationale sintético do DEV). DEV/FROZEN intactos.
6. Pré-registro (amostra, grade, regra) commitado em `bc9f8ca` **antes** do run.

## Resultado (DEV, 30 chamadas, 0 erro de provider)

Cobertura 15/30 (baseline J1) → **28/30**; loot 13/13 com fonte correta; 0 erro de
rota/alvo/fonte; 0 escalada insegura; não-loot 17/17 rota e 12/12 alvo iguais à P1.
As 18 variantes empataram; desempate pré-registrado: guard ligado, τ_loot 0,50.
Latência Jev p50/p95 261,5/306,2 ms. Raw `b5a3a6d0…23bf`, summary `e884fb7b…c13a`
(reproduzido offline). Ledger 90/190. Detalhes:
[docs/spec217/j1b-loot.md](../docs/spec217/j1b-loot.md).

## Pontos para a revisão

1. **Mudança de requisição na J2.** A pergunta extra mudou zero respostas de rota/alvo
   na amostra (17/17, 12/12), mas a J2 passaria a mandar `j1b_request`, não
   `frozen_request`. Confirmar que a P2 da J1 + esta amostra bastam como evidência de
   não-regressão da estrutura.
2. **Guard.** Nunca disparou no DEV (todos os loot com verbo claro) e as features de
   local nunca foram exercitadas (DEV sem `current_location_id`). Mantido ligado pela
   perda assimétrica, como a guarda de combate. Avaliar se o guard é estrito demais
   (ex.: "pego as moedas do mercador" ⇒ TREASURE vs SHOP).
3. **R9.7 para a J2** (pré-registrada na SPEC-238 R8): fonte de B = `loot_context` do
   CLASSIFY no mesmo caso/réplica nos loot cobertos; 0 divergência; e 0 erro se o
   FROZEN tiver oráculo de fonte (o executor não sabe se tem — não abriu o arquivo).
   Confirmar que o runner da J2 deve registrar `loot_context` de A.
4. **Oráculo sintético.** 3 rótulos (buy.01/sell.01 ⇒ SHOP, pick.01 ⇒ TREASURE) vêm do
   rationale do DEV, não de dataset externo.
5. Digest: `FROZEN_J1B_STRUCTURE_DIGEST = sha256:1f6a5982d5b72c36c9bc67ddfaf3723eea19753ebe7cc0a713454247e61d70f0`
   (`test_frozen_j1b_digest_matches_code`; editar código J1 também o quebra).

## Produção

`RPG_JEV_ROUTER_MODE` default `off`, `PRIMARY_CALIBRATION=None`, `jev_rollout.py`
inalterado, sem mudança de schema de save.
