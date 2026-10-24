# SPEC-303: calibração

Simulador: `docs/spec302/world_engine_sim.py --calendar on|off [--s303]` (120 dias).

## S1 — C1 da SPEC-302 com estações (60 seeds)

| | nova_arcadia | brekmar | pradaria_ruinas | pantano_melancolia | C4 mundo máx |
|---|---|---|---|---|---|
| calendário `off` | 10 | 15 | 10 | 11,5 | 62,5 % |
| calendário `on` | 10 | 15 | 10 | 11 | 59,2 % |

C1 continua em [10, 15]; C3, C5 e C6 fecham.

## S2–S4 (20 seeds)

- S2: 0 crises de fome/praga extras vindas só da estação (surtos e causas desligados).
- S3: 100 % das seeds com a 1ª virada em `anchor+4..+8` (offsets vistos: 4, 5, 6, 7, 8).
- S4: cada (festa, ano) ocorre ou é cancelada 1× (592 pares observados).

Taxa de cancelamento por festa: dia_da_fundacao 27,5 %, noite_do_silencio 23,9 %,
dia_da_estaca 21,7 %, noite_dos_nomes 17,4 %, procissao_de_vaelorn 12,2 %,
cancoes_de_pedra 9,5 %, dia_do_levante 9,5 %, fim_do_ceu_vermelho 7,3 %,
rito_da_memoria 2,5 %, demais 0 %. (Sem meta; o dono olha.)

## Pendente (coordenador)

R29 (letalidade M1/M2/M5 SPEC-285 com playtest 12 seeds x 200 turnos) e smoke real §6 não foram
executados aqui (custo/tempo). Revisão independente Opus pendente.
