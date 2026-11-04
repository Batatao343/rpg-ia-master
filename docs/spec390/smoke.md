# Smoke local (LLM real): SPEC-390 §6

Feito em 04/11/2026 pelo agente de smoke local, na `main` (`93a7a480`). Cópia `git archive` fora do OneDrive, `web/dist` gerado dela, `.env` copiado (nenhum valor impresso), perfil `legacy`, API `:8780` com o preset `scripts/staging/staging_flags.json` + `RPG_CREATURE_ART=on`. Saves de `seed_save` (MockLLM) com `smoke_body` (`tests/fixtures/spec368_seed.py`). API morta por PID e cópia apagada no fim.

## Tabela item → resultado

| Item | Resultado | Evidência |
|---|---|---|
| 1 `13 voto` | **ok**. Mensagem e `/game/history`: "Goblin, provocado por você, muda de alvo." O nome do herói ("Hv") aparece 0 vezes na mensagem e nas entradas do histórico (varredura nos 3 saves da cópia: 13 entradas, 0 nome do herói, 0 ids, 0 hex de 24). O ramo "resiste à sua provocação" não ocorreu nesta rodada (o Goblin não resistiu), então não foi exercitado. | `r-v.json`, scan |
| 2 `14 entrega` | **ok**. "Entrego a prova da caça ao contratante" fechou a quest: `turn_outcome.quests_completed = [{"id": "q368", "title": "Caça"}]`, `source: "quest"`, +200 XP, +20 ouro. O título é "Caça", não o id (o achado 2 do smoke da 389 está resolvido). Rota NPC, 1 de 1 tentativa. | `r-e.json` |
| 3 `13 armadura` | **ok**. "Você está provocado por Soldado." (herói como vítima, com o nome do inimigo). A linha de provocação do herói não traz mais "dele mira" (achado 4 da 389 resolvido). 0 chamadas LLM. | `r-a.json` |

## LLM, custo

- Turnos com LLM: 1 (item 2: classify + FAST + SMART, 3 chamadas, todas DeepSeek, `llm_attempt_outcomes: success 3`, 0 queda para fallback). Itens 1 e 3 são rodadas de combate sem LLM (0 chamadas).
- Provider/modelo: DeepSeek em tudo. Custo estimado: **~US$ 0,0028** (item 2: classify 0,0003, FAST 0,0021, SMART 0,0004). 0 retrato pago. Latência do turno NPC: 10,7 s.

## Achados

Nenhum bloqueante. Observação: o ramo "resiste à sua provocação" (R1) só tem cobertura de teste, não de smoke real; o Goblin da seed não resistiu.
