# SPEC-307: calibração e evidência

Simulador: `docs/spec302/world_engine_sim.py --calendar on|off [--s303] --days N --seeds M`
(MockLLM/offline). Ano de Valoria = 7 meses × 20 dias = 140 dias.

## S1 — C1/C3–C6 da SPEC-302 (120 dias × 60 seeds)

| | nova_arcadia | brekmar | pradaria_ruinas | pantano_melancolia | C4 mundo máx |
|---|---|---|---|---|---|
| calendário `off` (303) | 10 | 15 | 10 | 11,5 | 62,5 % |
| calendário `on`, 7 meses (307) | 10 | 15 | 10 | 11 | 62,5 % |

C1 continua em [10, 15]; C3, C5 e C6 fecham. Com 20 seeds o brekmar oscila para 16 tanto
com o calendário `on` quanto `off` (ruído de amostra, não do calendário).

## S2–S4

- S2 (120 d × 60 seeds): 0 crises de fome/praga extras vindas só da estação.
- S3: 100 % das seeds com a 1ª virada de mês e de estação em `anchor+4..+8`
  (offsets vistos: 4, 5, 6, 7, 8).
- S4 (**280 dias** = 2 anos × 20 seeds): cada (festa, ano) ocorre ou é cancelada 1×
  (560 pares). Cancelamento: dia_da_fundacao 42,5 %, noite_do_silencio 27,5 %,
  dia_da_estaca 30 %, procissao_de_vaelorn 15 %, dia_do_levante 15 %, cancoes_de_pedra
  12,5 %, dia_da_simbiose 12,5 %, demais ≤ 10 %. (Sem meta; o dono olha.)
- Horizonte de 280 dias: C1 sai de [10, 15] (nova_arcadia/pradaria 8) e C4 sobe a 72 %,
  **igual com o calendário `off`** (8/15/8/10,5; 72,1 %). É efeito do horizonte da
  simulação da SPEC-302 (calibrada para 120 dias), não do calendário. Nenhum offset de
  pressão foi alterado (`pressure_offsets` intactos).

## R27 — letalidade (playtest `combate`, MockLLM, seeds 21–32 × 200 turnos, nível 5)

12 campanhas: 0 erros de turno. 11 com 0 violações; a seed 26 tem 1 `combat.no_progress`
(M5). **Isso não vem da 307:** a mesma seed dá 1 violação no código da SPEC-303 (calendário
`on`) e 0 com `RPG_CALENDAR=off`; o clima sazonal muda o caminho do RNG de uma campanha de
200 turnos que passa só 2 dias no relógio. Pendente para o coordenador/dono: decidir se o
M5 da SPEC-285 exige corrigir a 303 (correção no multiplicador de clima, nunca no combate).
M1 e M2 não foram recomputados (a matriz SPEC-056 completa fica para o pouso).

## Smoke real (§6) — NÃO executado

Sem chave/teto nesta execução. Pendente: `playtest run --profile explorador --turns 15
--real --max-cost 0.25 --seed 31` com `RPG_CALENDAR=on`, leitura humana de 5 narrações
(nenhum mês/dia fora de Valoria), save sintético v1 com descanso 3×, e sessão manual no
staging.
