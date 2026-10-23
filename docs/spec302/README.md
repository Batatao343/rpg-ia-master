# SPEC-302 — calibração offline do motor de mundo

`world_engine_sim.py` roda o **mesmo** `services.world_engine.advance_days` (modo `on`,
sem LLM) por N dias × M seeds num estado sintético com herói inerte (R5), devolve os
eventos ao `event_log`/projection como o arquivista faria — validando cada um com
`validate_proposal` — e mede as metas C1–C6.

```bash
bash scripts/dev/py.sh docs/spec302/world_engine_sim.py --days 120 --seeds 20
```

## Resultado (120 dias × 20 seeds, constantes finais de `data/world/pressures.json`)

| Meta | Critério | Resultado |
|---|---|---|
| C1 crises perceptíveis (região ou adjacente) — mediana do intervalo entre inícios | ∈ [10, 15] dias | nova_arcadia **11** · brekmar **15** · pradaria_ruinas **10** · pantano_melancolia **13** |
| C2 itens testemunháveis (sinais, avisos, crises) na região — mediana do intervalo | ≤ 2 dias | **1** nas 4 regiões |
| C3 crises simultâneas ≤ `MAX_ACTIVE_CRISES` (2) | 100 % dos dias | **sim** |
| C4 dias com ≥ 1 crise ativa no mundo | ≤ 50 % | média **35,4 %** · p90 **41,7 %** · pior seed **52,5 %** (1 de 20) |
| C4 maior fração de dias em crise numa região | ≤ 35 % | **21,7 %** |
| C5 crises com aviso ≥ `MIN_WARNING_DAYS` (2) antes | 100 % | **sim** |
| C6 sem `ruina` permanente | toda ruína recupera ou tem pressão sustentando | **0 violações** |
| Eventos do motor rejeitados pelo validator | 0 | **0** |
| Tamanho de `world_sim` | < 40 KB | **35,7 KB** (repr) |

Decisão D4 do dono: **ritmo de crise vence** (C1) mantendo o teto de simultâneas (C3).
O pior seed de C4 (52,5 %) passa de 50 % em 2,5 pp; a média e o p90 ficam folgados. Para
reduzir sem mexer em C1, baixar `surge_p` ou subir `crisis_relief_per_day`.

## Constantes ajustadas (todas `[BALANCEAR]`)

- `crisis_relief_per_day` 6 → **14** (a resposta do mundo encerra a crise em ~3-5 dias);
- `surge_p` 0,0065 com pesos por região (`surge_weight`): regiões de partida/mais visitadas
  mais ativas (`nova_arcadia` 1,6 · `brekmar` 2,0 · `pradaria_ruinas` 1,5 ·
  `pantano_melancolia` 1,4 · vizinhas de `brekmar` 1,6) e as remotas bem menos;
- `signal_delta` 6 → **4**.
