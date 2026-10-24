# SPEC-304 — calibração do mundo de NPCs

`npc_world_sim.py` roda o motor real (sem LLM) por N dias × N seeds com um elenco sintético de 60
NPCs: os 21 líderes de fação, os 36 `npc_mv_*` e 3 companheiros (Brunna, Skek, Odrin) deixados
esperando em `ma_saidas_baixas` (perigo 3) por 10 dias, a partir do dia 6 (depois da calma
inicial de 5 dias do diretor). O jogador fica em `nova_arcadia`, só percebe e nunca intervém: é o
pior caso de letalidade.

```
bash scripts/dev/py.sh docs/spec304/npc_world_sim.py --seeds 40 --days 120
```

## Resultado (40 seeds × 120 dias)

| Meta | Alvo | Medido |
|---|---|---|
| N1 percebíveis por 20 dias (mediana) | ≥ 1 | 1,0 |
| N2 mortes por 15 dias (mediana) | ≤ 1 | 0,94 |
| N2 ≥ 1 morte em 120 dias | sim | 100 % das seeds |
| N3 mortes de líder em 120 dias (máx.) | ≤ 2 | 2 |
| N3 nunca 2 mortes de líder em 30 dias | sim | sim (intervalo calibrado em 60) |
| N4 P(perigo \| companheiro, perigo 3, 10 dias) | 0,25–0,60 | 0,28 |
| N4 P(morte \| perigo maior, telegrama percebido, sem intervenção) | 0,30–0,50 | 0,44 |
| N5 mortes em local com perigo ≤ 2 e sem estado de crise | 0 | 0 |
| N6 mortes sem telegrama ≥ `TELEGRAPH_MIN_DAYS` / maior sem percepção | 0 | 0 |
| N7 crises ativas simultâneas (orçamento da SPEC-302) | ≤ 2 | 2 |

## Constantes calibradas (`data/world/npc_world.json`)

| Constante | Spec | Calibrada | Por quê |
|---|---|---|---|
| `BASE_HAZARD` (perigo 3 / 4) | 0,02 / 0,05 | 0,06 / 0,10 | N4 (companheiro largado) |
| `HOME_MULT` (em casa, entre os seus) | — | 0,05 | 23 de 35 locais têm perigo ≥ 3: sem isso o elenco inteiro vive em perigo e o teto de 3 saturaria |
| `ROLE_MULT` líderes | 0,5 / 1,0 | 0,5 / 1,0 | N1 |
| `fate_weights.emboscada.morto` | 3 | 6 | N4 (P(morte \| percebido)) |
| `LEADER_DEATH_GAP_DAYS` | 30 | 60 | N3: ≤ 2 mortes de líder em 120 dias |

Mecânica nova não prevista na spec: perigo maior sem vaga do diretor na data do prazo (ou sem
telegrama percebido) **estende** o prazo até `MAX_EXTENSION_DAYS` antes de excluir `morto` do
sorteio (R17 já previa a extensão por falta de percepção; a falta de vaga usa o mesmo mecanismo).

## Baseline e prova de não regressão (R32)

- `--all --turns 50` com `RPG_WORLD_ENGINE=on RPG_NPC_WORLD=on` (MockLLM): 16 perfis,
  0 erro, 0 violação `error` (a spec cita 14; hoje são 16 perfis).
- Letalidade (perfil `combate`, 200 turnos, seeds 21 e 22, MockLLM): `RPG_NPC_WORLD=off` e `on` dão
  0 mortes do jogador e 0 quedas em ambos; a spec não toca o combate.
