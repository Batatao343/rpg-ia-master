# SPEC-217 J1b / SPEC-238 — estágio de fonte do loot (DEV)

Spec: [SPEC-238](../../specs/SPEC-238-jev-loot-source.md). Código:
`evals/experiments/spec238_loot.py`; testes: `tests/test_spec238_loot.py`.
Base: política J1 congelada `plain+target+guard@0.50`
(`sha256:80225d161ff31f226919c67b34195bdd864d5aece3c5dfc95f411093f3dd10f5`), reusada sem edição.

## Pré-registro (commitado antes de qualquer chamada live)

**Requisição:** a requisição congelada da J1 (rota `plain` + alvo quando há atores
em cena, mesmas features) + pergunta `loot_source` (`treasure|shop|craft|none`) +
`merchant_here`/`craft_station` (públicos; `None` fora do fio quando o local é
desconhecido — caso de todos os 13 loot do DEV). Uma chamada Jev por caso.

**Amostra (30 chamadas, determinística):** os 13 DEV `loot` + os 8 DEV
`critical=combat_escalation` + 9 outros elegíveis não-loot na ordem de
`sha256("SPEC-238-J1b|<case_id>")` (função `j1b_sample`). Zero CLASSIFY.

**Oráculo de fonte:** `evals/experiments/data/spec238_loot_oracle.json`
`sha256:129ac6fb9ff0c298c9b594d8db3afd756358063d4b7c5cbafe30d359fae00493`
(13 casos; proveniência por caso, conferida contra a fonte por teste).

**Orçamento:** ledger compartilhado `evals/runs/jev-router-ab/spec217-j1/ledger.json`
(antes: 60 J1, total 60). `j1b_calls` ≤ 30; total ≤ 190 (aprovação do dono
2026-10-18). Qualquer erro de provider para o run sem score; `max_retries=0`.

**Grade (offline sobre as mesmas respostas):** `loot_guard ∈ {com, sem}` ×
`τ_loot ∈ {0,50 … 0,90}` (passo 0,05) = 18 variantes. **Baseline** = a política J1
sem estágio (loot ⇒ CLASSIFY) sobre as mesmas respostas.

**Métricas por variante:** cobertura (casos resolvidos pelo Jev / 30), loot
cobertos, erros de rota, alvo e fonte nos cobertos, escaladas inseguras, motivos de
fallback; concordância de rota dos 17 não-loot com a P1/P2 da J1 (informativa);
latência Jev p50/p95 (comparar com P2 da J1: 247 / 286,55 ms).

**Regra de adoção:** adotável ⇔ 0 erro de fonte coberto **e** 0 erro de rota
coberto **e** 0 erro de alvo coberto **e** 0 escalada insegura **e** cobertura >
baseline. Entre adotáveis: maior cobertura; empate → guard ligado → τ_loot mais
próximo de 0,50. Nenhuma adotável ⇒ não adota; a J2 usa a política J1 aprovada.

**Para a J2 (se adotada):** orçamento inalterado (1 Jev + 1 CLASSIFY por caso,
≤ 100) e R9.7 acrescentada: nos casos FROZEN com `loot` coberto por B, fonte de B =
`loot_context` do CLASSIFY (A) no mesmo caso/réplica, 0 divergência; se o FROZEN
tiver oráculo de fonte, 0 erro.

## Resultados

_(preenchido após o run)_
