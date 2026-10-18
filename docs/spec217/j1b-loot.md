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

**Run** `SPEC-238-J1b-20261018T130603Z` (DEV, produto `bc9f8ca` = commit do
pré-registro, árvore limpa). **30/30 chamadas Jev**, 0 CLASSIFY, 0 erro de provider,
`max_retries=0`, modelo `jev-1.13.0`; uso 26.156 tokens de entrada / 3.666 de saída;
custo real `unavailable`. Ledger: J1 60 + J1b 30 = **90/190** (reserva US$ 0,90).

| Política (sobre as mesmas 30 respostas) | Cobertura | Loot cobertos | Erros rota/alvo/fonte cob. | Escalada insegura | Fallback |
|---|---:|---:|---:|---:|---|
| Baseline J1 `plain+target+guard@0.50` (loot ⇒ CLASSIFY) | 15/30 | 0/13 | 0 / 0 / — | 0 | loot 13, abst. 1, alvo n/repr. 1 |
| **`+lootsrc+lguard@0.50` (adotada)** | **28/30** | **13/13** | **0 / 0 / 0** | **0** | abst. 1, alvo n/repr. 1 |
| demais 17 variantes da grade (guard on/off × τ_loot 0,50…0,90) | 28/30 | 13/13 | 0 / 0 / 0 | 0 | idem |

- Fonte do loot: 13/13 corretas (TREASURE 5, SHOP 5, CRAFT 3), confiança da fonte
  1,00 em todas; rota `loot` com confiança 0,96–1,00. O guard nunca disparou.
- Não-loot (17): rota igual à da P1 da J1 em **17/17**, alvo igual em **12/12**;
  `loot_source` respondeu `none` em 17/17 (0,79–1,00). Nenhuma regressão de rota.
- Latência Jev p50 **261,5 ms** / p95 **306,2 ms** (P2 da J1 sem a pergunta extra:
  247 / 286,55 ms) — a pergunta extra custa ~15–20 ms.
- Cobertura projetada no DEV inteiro (52 elegíveis): 35 da J1 + 13 loot = **48/52
  (92 %)**, antes 35/52 (67 %). Projeção assume não-loot inalterado (17/17
  concordaram na amostra).

**Decisão (regra pré-registrada):** todas as 18 variantes adotáveis e empatadas;
desempate guard ligado → τ_loot 0,50 ⇒ **adotada `plain+target+guard@0.50+lootsrc+lguard@0.50`**.
Congelada em `evals/experiments/spec238_loot.py` (`FROZEN_J1B_POLICY`), digest
`sha256:1f6a5982d5b72c36c9bc67ddfaf3723eea19753ebe7cc0a713454247e61d70f0`
(superado pela emenda Astra: `sha256:75635c8994f8a421989653e1383052017feccde024ceaab731da69e739ef2247`, features de local desligadas na J2 — a requisição J2
é byte a byte a medida nas 30 chamadas DEV)
(inclui o digest J1 `80225d16…10f5`, a pergunta de fonte, o guard e o código das
features; teste `test_frozen_j1b_digest_matches_code`). Revisão Astra pendente:
[handoffs/SPEC-238-for-Astra.md](../../handoffs/SPEC-238-for-Astra.md).

**Artifacts** (gitignored, `evals/runs/jev-router-ab/spec238-j1b/20261018T130603Z/`;
cópia no scratchpad da sessão), summary reproduzido offline com hash idêntico
(`python -m evals.experiments.spec238_loot --phase summarize --run-dir <dir>`):

| Arquivo | SHA-256 |
|---|---|
| raw.json | `b5a3a6d05a4189a28a9a767d6997fd1ce595a86528d2844562220916808f23bf` |
| summary.json | `e884fb7b9838563d17484bf556fa1a6da1ea8b95aa2131322fdf90d119c5d13a` |
| ledger.json (após J1b) | `eb67f1047cfa0da066ef66ecc4d1fc3c3acd910ecae714eed34a7b3250543627` |

**Limitações:** DEV pequeno e já visto; no DEV o local é sempre desconhecido, então
`merchant_here`/`craft_station` não foram exercitados (o guard decidiu só por verbo);
o DEV não discrimina guard on/off nem τ_loot. A confirmação é a J2 (3 casos loot no
FROZEN) com a R9.7.
