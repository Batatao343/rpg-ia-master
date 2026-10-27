# Medição A/B 316–319 no staging — 2026-10-27

Pedido do dono: "mede tudo para garantir que realmente fica mais rápido".

**Protocolo.** Staging Vercel (`0640bff`, DeepSeek), mesmo roteiro de 15 turnos por sessão
(6 cena, 3 NPC novo, 2 conversa com NPC, 2 viagem de região, 2 descanso com virada de dia), think 6 s.
Quatro sessões intercaladas com redeploy entre elas: OFF1 → ON1 → OFF2 → ON2 (60 turnos).

- **OFF** (comportamento anterior): `RPG_EARLY_NARRATIVE=off`, `RPG_TOKEN_STREAM=off`, `RPG_LLM_HEDGE_MS=0`,
  `RPG_NPC_TWO_PHASE=off`, `RPG_REPLAN_AFTER=off`, `RPG_DAY_DIGEST=llm`, `RPG_ARCHIVE_POLICY=legacy`.
- **ON**: preset `scripts/staging/staging_flags.json` (hedge já `0`, decisão do dono 27/10).
- Limitação: cache de índice e prefetch de contexto (SPEC-317) não têm flag no `vercel_env.py` e ficam
  ligados nos dois braços → o A/B **subestima** o ganho total.
- "sem fila" = tempo medido a partir do `ack` do SSE (desconta a espera de cold start do Vercel antes da função).

## Cliente (60 turnos, 0 erros, checks de integridade verdes nas 4 sessões)

| Métrica | OFF1 | OFF2 | ON1 | ON2 |
|---|---|---|---|---|
| 1ª narração na tela p50 | 11,36 s | 8,24 s | **2,66 s** | **2,60 s** |
| 1ª narração na tela p95 | 26,13 s | 15,49 s | 11,75 s | 9,75 s |
| narração completa (`done`) p50 | 11,36 s | 8,24 s | 6,18 s | 6,14 s |
| estado final (`state`, input libera) p50 | 11,36 s | 8,24 s | 9,77 s | 11,36 s |
| estado final p95 | 26,13 s | 15,49 s | 16,99 s | 17,10 s |
| estado final média | 14,48 s | 9,34 s | 10,10 s | 10,99 s |
| cold start (ack > 5 s) | 1 | 0 | 1 | 0 |

1ª narração (sem fila), mediana por tipo de turno — OFF (1/2) → ON (1/2):

| Tipo | OFF | ON |
|---|---|---|
| cena | 7,26 / 7,13 s | 2,13 / 2,19 s |
| NPC novo | 8,62 / 5,11 s | 2,39 / 4,47 s |
| conversa com NPC | 15,51 / 10,35 s | 7,62 / 9,21 s |
| descanso (vira o dia) | 17,72 / 14,14 s | 4,14 / 2,36 s |
| viagem de região | 24,26 / 11,01 s | 2,18 / 2,28 s |

## Servidor (logs Vercel)

| | OFF1 | OFF2 | ON1 | ON2 |
|---|---|---|---|---|
| TTFMC servidor p50 / p95 | 10,8 / 24,9 s | 8,0 / 15,3 s | 2,4 / 6,2 s | 2,4 / 7,5 s |
| chamadas SMART por turno | 0,77 | 0,60 | 0,47 | 0,71 |
| custo por turno (US$) | 0,0044 | 0,0033 | 0,0033 | 0,0038 |
| `sse.token_replace` | — | — | 0 | 0 |
| entregas antecipadas | 0/13 | 0/15 | 15/15 | 14/14 |

## Conclusão

- **O que o jogador vê ficou muito mais rápido:** 1ª narração p50 de 8,2–11,4 s para 2,6 s (−70 %), p95 de
  15,5–26,1 s para 9,8–11,8 s; narração completa p50 de 8,2–11,4 s para 6,1 s. Ganho em todos os tipos de
  turno; maior em viagem e descanso.
- **O turno inteiro (estado final / input liberado) NÃO ficou mais rápido:** p50 8,2–11,4 s (OFF) × 9,8–11,4 s
  (ON); p95 15,5–26,1 × 17,0–17,1; média 9,3–14,5 × 10,1–11,0. Empate dentro do ruído. O trabalho pós-narração
  (arquivista, commit) continua no mesmo request; só deixou de bloquear a leitura.
- **SMART por turno** com `lean`: 0,47 e 0,71 (média 0,59) — meta ≤ 0,45 da SPEC-318 **não atingida**; custo
  por turno igual entre braços.
- Zero `replace`, zero erro, integridade (turn_count, canonical_version, jobs/memória sem duplicata, crônica
  no reload) verde nos 60 turnos.
