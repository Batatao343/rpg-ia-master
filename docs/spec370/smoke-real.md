# SPEC-370 — smoke real §6 (04/11/2026)

Em processo (sem uvicorn), `app.invoke` real, DeepSeek primário (`deepseek-v4-flash`; houve timeouts de transporte e queda para Groq em alguns nós), `RPG_FAUNA=on`, `RPG_FAUNA_SINAIS=on`, `RPG_WORLD_ENGINE=on`. Save descartável (nível 3, `game_id` aleatório). Script fora do repo; o `.env` foi copiado só durante a rodada e apagado. A presença foi **injetada** (criatura `cedo` não-BOSS do território do nó, 0 sinal, período dentro do `horario`), `danger_overrides` = 4. Prompt do narrador capturado por um wrapper de `get_llm` do storyteller.

## Skallgard (`sk_fortaleza_vorr`, criatura `enemy_guerreiro_bjorn`) — passou

| Turno | Ação | Chamadas LLM | `<SINAIS_NA_CENA>` no prompt | Resultado |
|---|---|---|---|---|
| 1 | "fico observando" | 3 (deepseek) | sim | 1 sinal novo (`rastro`), sem combate; a narração traz o vestígio (sulcos na pedra, cheiro de piche) e **não** contém "Bjorn" nem "guerreiro" |
| 2 | "sigo o rastro" | 4 (deepseek) | não | combate (`always_combat`, surpresa do jogador, frase de aproximação); presença vira `encontrada` |

`bestiary_knowledge.enemy_guerreiro_bjorn.sinais_vistos = ["rastro"]` = tipos mostrados. Uma rodada anterior (mesmo roteiro, ainda com a cena em Nova Arcádia por herança de histórico) e uma intermediária com queda para Groq deram o mesmo comportamento.

## Ophidia (`ophidia`, criatura `mon_arpeu_de_bracos`, presença nova sem sinal) — passou

| Turno | Ação | Chamadas | `<SINAIS_NA_CENA>` | Resultado |
|---|---|---|---|---|
| 1 | "exploro a área em volta" | 4 | sim | sinal `resto`, sem combate, sem nome |
| 2 | "avanço com cuidado pelo caminho" | 4 | sim | sinal `rastro` (cabo arrastado aparece na narração), sem combate |
| 3 | "continuo explorando" | 2 | não | sem combate |
| 4 | "sigo o rastro" | 3 | não | combate com a aproximação; só aqui o nome aparece |

`sinais_vistos = ["resto", "rastro"]`. Presenças ativas em Ophidia no fim: 0 (a única virou `encontrada`; `region_cap("ophidia") == 1` está em `tests/test_spec370_caps.py`). Nenhum combate antes do primeiro sinal.

## Limites desta rodada

- Presença injetada, não nascida pelo `day_hook`; a conversão de presença nova de Ophidia (decisão do dono) está provada por `tests/test_spec370_solo.py` e pelo eval (M1 0,9845).
- Passos 6 (viagem Skallgard→Ophidia pelo mapa) e 7 (custo `on` × `off` do mesmo roteiro com telemetria) não foram feitos nesta rodada: o custo observado foi 2 a 4 chamadas por turno, e o turno da caça custou um início de combate comum (4).
- Bloco com 0 token nos turnos sem sinal (turnos 3 e 4 de Ophidia, 2 de Skallgard).
