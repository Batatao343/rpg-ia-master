# SPEC-217 J2 — A/B confirmatório no FROZEN (execução única)

**Veredito pela R9 pré-registrada: `GO`** (R9.1–R9.7 todas verdes). Evidência
confirmatória de uma única execução no corpus FROZEN, nunca visto antes. Nada foi
ligado: `RPG_JEV_ROUTER_MODE` segue `off` e `PRIMARY_CALIBRATION = None`. Os
próximos passos (R14 porte + calibração, R15 shadow) dependem de revisão Astra deste
resultado e, no caso do shadow, de autorização própria do dono.

## Execução

| Item | Valor |
|---|---|
| Run | `SPEC-217-J2-20261018T134801Z` (`evals/runs/jev-router-hybrid/20261018T134801Z/`, gitignored) |
| Runner | `evals/experiments/spec217_j2.py`, commit `3d1aca465b5783ba2c6779e7bfaeb7094ea3652d` (13:47:40Z), árvore limpa (`product_dirty=false`) |
| 1ª chamada / fim | 13:48:12Z (ledger n=91) / 13:49:41Z (n=190) |
| FROZEN | `sha256:442725e5…9d48` (21 casos: 16 elegíveis + 5 gates) |
| Oráculo de fonte (R9.7) | sidecar selado `sha256:d9c860ec…c38d` (referência = oráculo) |
| Política B | `plain+target+guard@0.50+lootsrc+lguard@0.50`, digest J1 `80225d16…10f5`, J1b `75635c89…2247`, features de local OFF |
| Braço A | router atual (gates Python → CLASSIFY), DeepSeek em todas as 50 chamadas, sem fallback/retry/regeneração |
| Pareamento | seed `SPEC-217-J2`; 3 réplicas; ordem dos casos e braço inicial por réplica declarados no raw antes da 1ª chamada |
| Sanidade | 4 chamadas (A, B, A, B) no caso sintético `spec217.j2.sanity.observe`, fora dos dois corpora; não pontuada |

## Resultado R9

| Regra | A (CLASSIFY) | B (híbrido) | Critério | Passa |
|---|---:|---:|---|:---:|
| R9.1 acerto de rota (48 obs.) | 45/48 (93,75 %) | **48/48 (100 %)** | B ≥ A − 2,5 pp e ≤ 1 perda pareada | ✓ (0 perdas, 3 ganhos) |
| R9.2 acerto de alvo (24 obs. `target`) | 24/24 | 24/24 | B ≥ A; nenhum alvo fora dos candidatos | ✓ (0 fora; B×A concordam 24/24) |
| R9.3 escalada insegura | 0 | **0** | B = 0 | ✓ |
| R9.4 latência do router p50 | 1.480 ms | **238 ms** | ganho ≥ 500 ms | ✓ (−1.242 ms) |
| R9.4 latência do router p95 | 1.806,55 ms | 1.655,25 ms | B ≤ 1,10 × A | ✓ (razão 0,916) |
| R9.5 gates Python (15 obs.) | rota = B | rota = A | mesma rota, 0 chamadas | ✓ (15/15 iguais ao oráculo) |
| R9.6 erro de provider | 0 | 0 | zero | ✓ |
| R9.7 fonte do loot (B coberto) | — | 9/9 | 0 erro vs oráculo | ✓ |

Latência do Jev isolado: p50 236 ms, p95 280,9 ms. Medida da estação de trabalho
(não `gru1`); o p50 de A ao vivo (1.480 ms) bate com o gate real da SPEC-214
(1.473 ms). Latência de B no fallback = Jev + CLASSIFY do mesmo caso/réplica.

## Cobertura e casos que não foram ao Jev

| Medida | Valor |
|---|---|
| Decididas pelo Jev | **44/48 (91,7 %)** |
| Fallback `combat_guard` | 3 (um caso de combate legítimo × 3 réplicas: sem verbo de ataque do léxico; caiu no CLASSIFY, que acertou) |
| Fallback `low_confidence` | 1 (caso `combat_escalation` crítico, réplica 3; CLASSIFY acertou `storyteller`) |

As 3 vitórias de B são o mesmo caso de loot (×3 réplicas): o CLASSIFY roteou para
`npc_actor`, o Jev decidiu `loot` com fonte `SHOP` = oráculo. Por isso a fonte do loot
do braço A contra o oráculo fica em 6/9 (informativo), contra 9/9 de B.

## Chamadas e custo

| Fase | Jev | CLASSIFY | Total | Reserva |
|---|---:|---:|---:|---:|
| Sanidade | 2 | 2 | 4 | US$ 0,04 |
| Réplicas (16 × 3 × 2) | 48 | 48 | 96 | US$ 0,96 |
| **J2** | **50** | **50** | **100 / 100** | **US$ 1,00** |
| Spec acumulada (J1 60 + J1b 30 + J2 100) | | | **190 / 190** | **US$ 1,90** |

Custo real `unavailable` (o provedor do Jev não informa custo; tokens CLASSIFY:
37.162 de entrada, 6.878 de saída). Zero folga restante no teto da spec.

## Artifacts (R11)

| Arquivo | SHA-256 |
|---|---|
| `raw.json` | `f1a257a7830f99be5427925d7f2f4f7f8f2944a76a642f6a15148a7f51df3519` |
| `summary.json` | `454e814c3c76ad1c0cc2d2e016493babfc4ea0c614fa16f9ce26808024b18ef1` |
| `ledger.json` (após a J2) | `5c2c32da8cb0710723c6791d482122833b1e963780912ef500eed4b7f9eb9cc1` |

Raw gravado antes do score (o score só roda com `--phase summarize`); summary
reproduzível offline: `python -m evals.experiments.spec217_j2 --phase summarize
--run-dir <dir>`. Cópia fora do worktree no scratchpad da sessão (`spec217-raw/j2/`),
hashes conferidos. Marcador de execução única: `evals/runs/jev-router-hybrid/J2_STARTED.json`
+ `j2_runs` no ledger; nova execução exige `--owner-rerun-authorization`.

## Observações para a revisão

- A sanidade A #1 levou 12,5 s (conexão fria do DeepSeek); não entra no score.
- R9.3 conta a decisão **final** de B, inclusive fallback herdado do A; A também teve
  0 escaladas.
- Pequena amostra (16 casos × 3): a regra é conservadora e passou com folga; o shadow
  (R15) é a confirmação no ambiente real.

## Próximos passos (não executados)

1. Revisão Astra independente deste resultado (critério de aceite da spec).
2. R14: portar a estrutura congelada para `services/jev_rollout.py` atrás de `off` e
   congelar `PRIMARY_CALIBRATION = ("SPEC-217-J2-20261018T134801Z", 0.50)` em commit
   separado, revisado por Astra.
3. R15: shadow em staging ≥ 50 turnos reais — exige run e teto próprios autorizados
   pelo dono (fora dos 190 desta spec). `primary` em produção = aprovação separada.
