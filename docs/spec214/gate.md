# SPEC-214 — Gate de entrada (R1 / P1)

**Data:** 2026-10-16 · **Decisão:** `NO_GO` (gate não atingido no baseline offline; reavaliar com baseline real)

Nenhum código de produto foi escrito. A spec permanece `draft`.

## Limiar (P1, default da spec)

`NO_GO` se, no perfil `typical`, **`context_share < 10 %`** **e** **`p95(context) < 400 ms`**,
com `context_share = p50(phase_ms.context) / p50(ttlt_server_ms)`.

## Execução

HEAD `0bbd742` (inclui a SPEC-213: arquivista com projeções adiadas), código sem alterações.
`--mode scaled --scale 1.0`: a latência injetada dos LLMs é dormida em tempo real (escala 1),
então TTLT tem a magnitude do perfil e a fase `context` é medida em relógio de parede
(no modo `virtual` o relógio só avança nas chamadas LLM e `context` sai sempre 0, ver
`docs/spec200/README.md`).

```
uv run python scripts/latency_baseline.py run --journeys all --reps 10 --seed 214 --profile typical   --mode scaled --scale 1.0
uv run python scripts/latency_baseline.py run --journeys all --reps 10 --seed 214 --profile slow-tail --mode scaled --scale 1.0
```

Run IDs `spec214-gate-typical-scaled1` e `spec214-gate-slow-tail-scaled1` (fora do repo,
`latency_runs` gitignored). `summary.json` sha256: `typical` `639d0636…e11e`,
`slow-tail` `79e45b4a…0a62` (modo scaled mede relógio de parede: não é byte-determinístico).

## Resultados (ms, 110 turnos medidos por perfil)

| Perfil | context p50 | context p95 | context max | TTLT p50 | TTLT p95 | context_share (p50/p50) | mediana da razão por turno |
|---|---|---|---|---|---|---|---|
| `typical` | 9 | 36 | 119 | 6388 | 8254 | **0,14 %** | 0,19 % |
| `slow-tail` | 5 | 12 | 33 | 6620 | 18015 | **0,08 %** | 0,10 % |

`share` da fase no `summary.json` (soma por fase / soma total): `typical` 0,25 %, `slow-tail` 0,08 %.

Por jornada (`typical`, context p50 / p95 · TTLT p50 / p95):

| Jornada | n | context p50 | context p95 | TTLT p50 | TTLT p95 | share p50 |
|---|---|---|---|---|---|---|
| J1 story | 30 | 17 | 26 | 3182 | 7404 | 0,53 % |
| J2 combat start | 20 | 7 | 25 | 6639 | 13674 | 0,11 % |
| J3 npc dialogue | 20 | 13 | 115 | 3275 | 7623 | 0,40 % |
| J4 loot shop | 20 | 0 | 0 | 7232 | 8115 | 0,00 % |
| J5 travel replan | 10 | 5 | 35 | 6625 | 7193 | 0,08 % |
| J6 first turn | 10 | 4 | 8 | 3281 | 7036 | 0,12 % |

Fases dominantes (`typical`, share): narrator 56 %, archivist 36 % (SMART do arquivista nos turnos
em que dispara), router 4,6 %, context 0,25 %.

## Leitura

* As duas condições de `NO_GO` valem com folga de ~2 ordens de grandeza nos dois perfis
  (share ≪ 10 %, p95 ≪ 400 ms), em todas as jornadas.
* **Limitação principal:** o baseline offline usa embeddings desligados/efêmeros
  (`playtest.runner._offline_embeddings`) — a fase `context` não inclui a chamada HTTP de embedding
  (Jina) nem a busca FAISS real de lore. Em produção, `context` = 1 embedding da query + buscas
  paralelas; ainda não há medição real dessa fase (a SPEC-200 não executou o experimento `--real`).
  Para o gate virar `GO` com TTLT ~6,4 s, `context` real precisaria passar de ~640 ms no p50 ou
  400 ms no p95. Referência auxiliar: o R28 da SPEC-143 (`docs/playtests/latencia-turno-r29-2026-08-28.md`)
  mediu o pipeline de leituras sem provider em ~141 ms serial / ~82 ms concorrente.
* Custo de embedding/turno (`usage_events`, SPEC-182) não medido offline (sem embeddings reais).
* **Reavaliar** quando existir baseline real da SPEC-200 (`--real`, autorização do dono) com
  `phase_ms.context` incluindo embedding de rede.
