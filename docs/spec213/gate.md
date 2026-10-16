# SPEC-213 — Gate de entrada (§0 / P1)

**Data:** 2026-10-16 · **Decisão:** `GO` (gate atingido no baseline offline; amostra real inexistente)

## Limiar (P1, default da spec)

Aprovar se a parte movível do arquivista representar **≥ 15 % do p50 de `ttlt_server_ms`**
**ou** **≥ 1,5 s no p95**, nos turnos em que `_should_archive` disparou.

## Fórmula

```
movable_ms = phase_ms.archivist − archivist_validate_ms     (campos da linha rpg.turn, SPEC-200 R4/R5)
turno "disparou" ⇔ llm_by_phase.archivist ≥ 1                 (o SMART do arquivista só roda se _should_archive)
```

`process_pending_events` **não** é separado pela SPEC-200: fica dentro de `phase_ms.archivist`, então
`movable_ms` é um **limite superior** (declarado). No modo `virtual` o relógio só avança nas chamadas LLM
injetadas, logo `archivist_validate_ms = 0` e `process_pending_events` contribui 0 — na prática
`movable_ms` = latência injetada da chamada SMART do arquivista, que é exatamente o derivado.

## Execução

Mesmo comando/seed da SPEC-200 (`docs/spec200/README.md`), HEAD `8cd12ee`, código sem alterações:

```
uv run python scripts/latency_baseline.py run --journeys all --reps 30 --seed 200 --profile typical   --mode virtual
uv run python scripts/latency_baseline.py run --journeys all --reps 30 --seed 200 --profile slow-tail --mode virtual
```

| Perfil | N total | N disparou | movable p50 | movable p95 | TTLT p50 (disparou) | TTLT p95 (disparou) | movable p50 / TTLT p50 |
|---|---|---|---|---|---|---|---|
| `typical` | 330 | 171 | 4040 ms | 4735 ms | 6823 ms | 8130 ms | **59,2 %** |
| `slow-tail` | 330 | 171 | 4186 ms | 16927 ms | 7262 ms | 20905 ms | **57,6 %** |

Mediana da razão por turno: 58,4 % nos dois perfis. `archivist_validate_ms` máximo = 0 (virtual).
`summary.json` (sha256): `typical` `df83ac4a…d754`, `slow-tail` `4d8e1efc…b850` (determinístico; uma 2ª
execução com o código da SPEC-213 em modo `inline` reproduziu os mesmos hashes byte a byte).

## Leitura

* As duas condições do limiar passam com folga nos dois perfis (≥ 15 % e ≥ 1,5 s p95).
* **Amostra real:** a SPEC-200 não executou o experimento com provider real (P5, sem autorização de
  custo). O gate é decidido só pelo baseline offline, que mede a **estrutura** do turno com latência
  injetada, não rede real. Reavaliar com a amostra real quando ela existir.
* Ressalva: em produção o narrador pode dominar mais do que a injeção sugere; o ganho absoluto real
  só é conhecido com o smoke real opt-in da §6.
