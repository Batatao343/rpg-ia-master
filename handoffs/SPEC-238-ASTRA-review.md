# SPEC-238 — revisão Astra independente do congelamento J1b

Revisor: Astra (≡ Opus, contexto separado; não escreveu a SPEC-238). Objeto: branch
`spec-217`, commits `bc9f8ca` (pré-registro + código), `7736600` (doc) e `d5841e7`
(resultados/freeze). Nenhuma chamada live nesta revisão. O FROZEN
(`spec217_frozen.jsonl`) **não foi aberto**: só `sha256sum` (= selo `442725e5…9d48`).

## Veredito: **APPROVED — com uma emenda do revisor (features de local desligadas na J2)**

Política final que a J2 testa:

```python
FROZEN_J1B_POLICY = LootPolicy(loot_stage=True, loot_guard=True, loot_tau=0.50)
# variant_id = "plain+target+guard@0.50+lootsrc+lguard@0.50" (base = FROZEN_J1_POLICY, digest J1 80225d16…10f5)
FROZEN_J1B_LOCATION_FEATURES = False  # emenda Astra
# braço B: frozen_j1b_request(case.input) + frozen_loot_decision(...)
# regra:   r9_7_loot_source(observations)
FROZEN_J1B_STRUCTURE_DIGEST = (
    "sha256:75635c8994f8a421989653e1383052017feccde024ceaab731da69e739ef2247"
)
```

O digest do executor `1f6a5982…70f0` fica **superado**. O novo digest cobre o digest J1,
a política, a pergunta de fonte, a flag de local e o código de `loot_features`,
`j1b_request`, `loot_guard_ok`, `loot_hybrid_decision`, `merchants_at`,
`frozen_j1b_request`, `frozen_loot_decision` e `r9_7_loot_source`
(`test_frozen_j1b_digest_matches_code`).

## Verificações

| # | Item | Resultado |
|---|---|---|
| 1 | Hashes | raw `b5a3a6d0…23bf`, summary `e884fb7b…c13a`, ledger `eb67f104…3627`, oráculo `129ac6fb…0493` conferem no worktree **e** na cópia do scratchpad. Summary reproduzido offline (fora do worktree) com hash idêntico — também depois da emenda. |
| 2 | Ledger | 90 entradas: p1 52 + p2 8 + j1b 30, todas `jev`; `j1_calls 60`, `j1b_calls 30`, `total 90/190`, reserva US$ 0,90. Entradas 61–90 = j1b, 13:06:22Z–13:06:30Z. |
| 3 | Pré-registro | `bc9f8ca` commitado 13:05:57Z; 1ª chamada J1b 13:06:22Z; raw `product_sha=bc9f8ca`, `product_dirty=false`. |
| 4 | Vazamento | `git diff 908d066 d5841e7 -- evals/experiments/data` só adiciona o oráculo DEV; nenhum código cita `spec217_frozen.jsonl` (testes). Raw só leva `frozen_lock_hash_only`. Grade, τ_loot e desempate decididos só com DEV. |
| 5 | Produção | `DecisionState` ganhou dois campos opcionais `None`; `wire_body` usa `exclude_none` ⇒ payload do rollout inalterado (`test_production_rollout_payload_still_unchanged`). `jev_rollout.py` sem diff, `RPG_JEV_ROUTER_MODE` default `off`, `PRIMARY_CALIBRATION=None`, sem schema de save. |
| 6 | Não-regressão da estrutura | 17/17 rotas e 12/12 alvos não-loot iguais à P1 da J1 com a pergunta extra. Somado à P2 da J1, basta para a J2 trocar `frozen_request` por `frozen_j1b_request` (ponto 1 do handoff). |

## Pontos abertos — decisões

**(b) Local ausente — o guard é seguro? Sim; mas local presente não é.** Com
`merchant_here`/`craft_station = None`, SHOP só passa com verbo `trade`, CRAFT só com
`craft`, TREASURE exige ausência de ambos — falha fechada para o CLASSIFY (testes novos
`test_guard_fails_closed_without_location`). O risco está no outro lado: **o DEV nunca
carregou local** (provado em `test_dev_never_exercised_location_features`), mas
**toda fixture do FROZEN tem `world.current_location_id`** (`docs/spec217/corpus.md`).
Na J2 as features entrariam no fio pela primeira vez (formato de requisição nunca
medido) e `merchant_here=True` deixaria SHOP passar só com "pego" — o caso
"pego as moedas do mercador" num local com mercador viraria SHOP aceito. Pela perda
assimétrica (R9.7 dá `NO_GO` com uma fonte errada) e sem nenhuma evidência a favor,
**desliguei as features na J2**. Não é ajuste a dados: o DEV não contém informação sobre
elas (todas `None`). Com a emenda, a requisição J2 é byte a byte a medida — conferido:
o `request_digest` de `frozen_j1b_request` bate com as 30 linhas do raw. Re-score do raw
pelo caminho congelado: 28/30, 0 erro (idêntico). Custo: só cobertura em SHOP/CRAFT sem
verbo explícito, que caem no CLASSIFY do mesmo caso/réplica (B = A).

**(a) R9.7 — necessária? Sim.** Sem ela, um loot coberto com fonte errada (comprar em
vez de achar) passa na R9.1 (rota certa) e é um erro funcional real. **Referência
certa: o rótulo esperado, como rota/alvo.** O FROZEN foi autorado com
`expected = {route, target}` apenas (`handoffs/SPEC-217-eval-authoring.md`), logo hoje não
há rótulo de fonte. Regra final:

1. **Preferida:** antes da J2, o papel de autoria de evals (o mesmo que autorou o FROZEN;
   nunca o executor nem este revisor) grava um sidecar selado
   `evals/experiments/data/spec217_frozen_loot_oracle.json` (+ `.sha256`) com a fonte dos
   3 casos `loot` do FROZEN e proveniência, commitado antes da 1ª chamada; o runner o
   valida pelo hash. Referência de R9.7 = esse oráculo.
2. **Sem sidecar** (dono não autoriza o passo de autoria): referência = fonte **efetiva** de
   A no mesmo caso/réplica (`loot_context or "TREASURE"`, como `agents/router.py`), e
   observação em que A não roteou `loot` é **erro** (inverificável ⇒ fail-closed). A
   escolha (1 ou 2) é declarada no raw antes da 1ª chamada.
3. Escopo: observações com B decidido pelo Jev e rota `loot`; 0 erro, senão `NO_GO`.
   Concordância B×A de fonte e acurácia de fonte de A contra o oráculo são reportadas
   (informativo). Implementada como `r9_7_loot_source` (pura, testada, no digest).

**(c) 3 rótulos do rationale — aceitáveis para DEV? Sim.** "Compro duas poções de Kess",
"Vendo a espada velha para Brynja" ⇒ SHOP; "Pego a espada caída" ⇒ TREASURE são
inequívocos pelo contrato do router e pelo próprio léxico de verbos; a evidência DEV é
de desenvolvimento, sem promoção. Os outros 10 são conferidos contra a fonte por teste.

## Requisitos bloqueantes para o executor da J2

Herdados da revisão J1 ([parecer](SPEC-217-ASTRA-J1-review.md)), atualizados:

1. **Runner FROZEN de execução única** (`--corpus frozen`): valida o FROZEN contra o selo e
   o `.sha256`; recusa se `structure_digest(FROZEN_J1B_POLICY) != FROZEN_J1B_STRUCTURE_DIGEST`
   (e o digest J1); marcador durável recusa 2ª execução sem flag explícita do dono; a sonda
   de gate (`eligible_cases`) roda antes de qualquer chamada; só esse processo lê o FROZEN.
2. **Ledger compartilhado** `spec217-j1/ledger.json` (hoje 90): contador `j2_calls` ≤ 100 e
   total ≤ 190; incrementa **antes de cada tentativa de rede de cada braço** (Jev e cada
   tentativa CLASSIFY via `jev_router_ab._capture_classify`/`_provider_slot`). Conferir
   `remaining() ≥ 4 + 2×N×3` antes de começar (N = 16 ⇒ 100, folga zero na J2).
3. **Parada (R10):** qualquer tentativa CLASSIFY com `outcome != success`, `fell_back`,
   `attempt_index > 0` ou regeneração de structured output, e qualquer `JevError` ⇒
   `blocked-by-provider`, sem score.
4. **Sanidade:** 4 chamadas (2 por braço) num caso fora dos dois corpora; erro ⇒ parar.
5. **Pareamento:** 3 réplicas; ordem dos elegíveis embaralhada por seed declarada no raw;
   ordem dos braços dentro do caso alternada por seed declarada. Gates Python: 0 chamadas.
6. **Braço B = `frozen_j1b_request` + `frozen_loot_decision`** (nunca `j1b_request` nem as
   features de local). Fallback de B = resultado do CLASSIFY do mesmo caso/réplica,
   **incluindo a fonte**.
7. **Braço A ao vivo:** latência = wall time do CLASSIFY; registrar por observação `route`,
   `active_npc_name`, `loot_context` cru e fonte efetiva (`loot_context or "TREASURE"` quando
   rota `loot`). B: latência = Jev se coberto; Jev + CLASSIFY no fallback.
8. **R9 como funções puras testadas sobre o raw:** R9.1 não-inferioridade −2,5 pp e ≤ 1 perda
   pareada; R9.2 alvo (ID de B vs alvo de A mapeado nome→ID pelo mesmo `scene_view`; nenhum
   alvo fora dos candidatos); R9.3 0 escalada insegura; R9.4 Δp50 ≥ 500 ms e
   p95(B) ≤ 1,10×p95(A); R9.5 gates; R9.6 zero erro de provider; **R9.7 =
   `r9_7_loot_source`** com a referência declarada (sidecar ou A fail-closed).
9. Raw antes do score; summary reproduzível offline; hashes no README; artifacts copiados
   para fora do worktree (R11).

## Observações não bloqueantes

- O guard de loot também protege rota: um `loot` do Jev sem verbo de item cai no CLASSIFY.
- Os raws J1/J1b vivem no worktree (gitignored) e no scratchpad; não remover o worktree
  antes de copiá-los para um lugar durável.

## Verificação desta revisão

Testes novos em `tests/test_spec238_loot.py` (guard fail-closed, DEV sem local, requisição
e decisão J2 sem local, paridade com as 30 requisições medidas, R9.7). Suíte e Ruff: ver
mensagem do commit.
