# Gate de latência intraturno R28/R29 — 2026-08-28

## Resultado

O fan-out de `campaign_manager` + `dm_router` **não foi promovido**. O gate
controlado R28 aprovou a implementação, mas o gate pareado com DeepSeek real
reprovou latência, cauda e custo/request. O rollback previsto foi aplicado:
`RPG_TURN_EXECUTION=sequential` voltou a ser o default; `concurrent` permanece
somente como opt-in experimental.

As otimizações que não disputam geração LLM foram mantidas: compartilhamento de
embedding quando os índices são compatíveis, leituras independentes
lore/sessão/NPC com ordem estável e limites por processo. `ainvoke` delega ao
caminho síncrono via `to_thread`; cancelar a coroutine não cancela HTTP já em
andamento. Não é uma implementação async nativa.

## R28 — controlado, sem provider

Comando:

```text
uv run python scripts/benchmark_turn_pipeline.py --repetitions 12
```

- serial mediana: 140,97 ms;
- concorrente mediana: 81,55 ms;
- redução: 42,1% (gate mínimo: 30%);
- requests de provider: 0;
- resultado: aprovado.

## R29 — DeepSeek real pareado

Artefato bruto gitignored:
`playtest_runs/latency-r29-20260828-162232.json`.

Foram executados 18 turnos: três repetições por modo em três coortes, alternando
a ordem sequencial/concorrente. Preflight CLASSIFY/FAST/SMART passou no DeepSeek.
O custo estimado foi US$ 0,014280 em 51 requests, abaixo dos tetos de US$ 0,10 e
180 requests.

| Coorte | Mediana sequencial | Mediana concorrente | Variação |
|---|---:|---:|---:|
| replan | 20.711,82 ms | 39.927,96 ms | -92,8% |
| travel | 10.358,88 ms | 11.293,85 ms | -9,0% |
| archive_due | 11.477,95 ms | 10.835,78 ms | +5,6% |

O p95 agregado passou de 21.863,38 ms para 40.068,19 ms. O modo concorrente
também fez 26 requests/US$ 0,007280 contra 25/US$ 0,007000 no sequencial, após
duas falhas de conexão no ramo concorrente exigirem trabalho adicional. Os
contratos mecânicos permaneceram válidos, mas R29 exige simultaneamente redução
de mediana, p95 não degradado, zero terminal e nenhum aumento de requests/custo.

## Decisão

O resultado é compatível com contenção/cauda do provider sob chamadas
simultâneas, mas a amostra não isolou a causa nem prova esse comportamento para
outros providers. Nessa configuração, SMART e CLASSIFY concorrentes não
atingiram os gates de latência/custo. Uma promoção futura exige nova medição de
capacidade e novo R29 com os mesmos limites. Memória e finalização canônica
continuam inline; não há worker/outbox de derivados entregue por esta spec.

Gate local posterior: suíte offline completa verde e `infra_local` 13/13.
