# SPEC-217 — evidência

Estado: **J1 concluída e congelada; revisão Astra APPROVED com emenda (guarda de combate ligada) — J2 liberada após implementar os requisitos do parecer.** Nenhum
GO/NO_GO ainda (só a J2 decide). Produção intacta: `RPG_JEV_ROUTER_MODE` default
`off`, `PRIMARY_CALIBRATION=None`, `services/jev_rollout.py` sem mudança de
comportamento (payload do rollout idêntico — campos novos do `DecisionState` são
opcionais e ficam fora do fio quando não definidos).

- Corpora: [corpus.md](corpus.md) (DEV `sha256:256d24bd…5f3d`; FROZEN
  `sha256:442725e5…9d48`, **não aberto** na J1 — só o hash do lock entra nos raws).
- Diagnóstico J1: [j1-diagnostico.md](j1-diagnostico.md).
- Variantes e resultados J1: [j1-variantes.md](j1-variantes.md).

## Orçamento

| Fase | Chamadas Jev | Chamadas CLASSIFY | Reserva | Teto |
|---|---:|---:|---:|---:|
| J1 P1 (triagem) | 52 | 0 | US$ 0,52 | — |
| J1 P2 (estrutura) | 8 | 0 | US$ 0,08 | — |
| **J1 total** | **60** | **0** | **US$ 0,60** | 60 |
| Spec acumulada | 60 | 0 | US$ 0,60 | 160 / US$ 1,60 |

Ledger durável (incrementa antes de cada requisição):
`evals/runs/jev-router-ab/spec217-j1/ledger.json` SHA-256
`beee946c5304d20616a310ceb7876cda4af47b53ac652c1b2c28248058d6a3cd`. Zero erro de
provider; custo real `unavailable` (só uso de tokens é reportado).

## Artifacts J1 (gitignored, worktree fora do OneDrive)

Diretório `evals/runs/jev-router-ab/spec217-j1/<timestamp>/` (o caminho da
instrução do executor; a R11 cita `jev-router-hybrid/` — mesmo conteúdo, desvio só
de pasta). Summaries reproduzidos offline do raw com hash idêntico
(`python -m evals.experiments.spec217_j1 --phase summarize|summarize-p2`).

| Run | raw.json SHA-256 | summary.json SHA-256 |
|---|---|---|
| P1 `SPEC-217-J1-p1-20261018T122448Z` (`20261018T122448Z/`) | `05f36dc8664652604bffed2847248ffe8a3cf4e44713538ef3ca509ea746d23d` | `bc5c3510f1f1d6d8436701fc631a7bb76342fca73bdf06b6cc1ce14dc2c3b76f` |
| P2 `SPEC-217-J1-p2-20261018T122535Z` (`20261018T122535Z/`) | `8e8338e41990846fdb6e239470721f70033c9a63faf2662e8b270c278a7ed358` | `ae9b38e843fba12daafd2fca388ae61899dc07748183cb201d5579e8b8ca52ce` |

Produto avaliado: commit `c5a721c7618667d1a9d2cd08d8b2315fe092e933`, árvore limpa.

## Congelamento (R6)

`FROZEN_J1_POLICY = plain+target+guard@0.50` (emenda Astra: guarda de combate ligada; `loot`→CLASSIFY),
hash de estrutura `sha256:80225d161ff31f226919c67b34195bdd864d5aece3c5dfc95f411093f3dd10f5`
em `evals/experiments/jev_router_hybrid.py`, travado por
`tests/test_spec217_j1.py::test_frozen_structure_digest_matches_code`.
Revisão: [handoffs/SPEC-217-J1-for-Astra.md](../../handoffs/SPEC-217-J1-for-Astra.md).
Parecer: [handoffs/SPEC-217-ASTRA-J1-review.md](../../handoffs/SPEC-217-ASTRA-J1-review.md) — APPROVED; hash anterior `950917…4b81` (sem guarda, sem código no digest) superado.
