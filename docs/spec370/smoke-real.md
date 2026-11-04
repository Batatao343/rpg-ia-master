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

## Rodada 2 (04/11) — presença nascida pelo `day_hook`, viagem e custo `on` × `off`

Mesmo método (em processo, DeepSeek, `.env` copiado e apagado), sem nenhuma presença injetada. Roteiro fixo a partir de Brekmar: 8 × "descanso para me recuperar", "Viajo para Ophidia.", "exploro a área em volta", "continuo explorando". Rodado com as flags `on` e com `off`.

- **(a) Nascida pelo `day_hook`:** no dia 4 (Manhã), depois de 7 descansos, nasceu em Brekmar `mon_penhorado_do_poco` (`origem: dia`, região nova, `ativa`) e a cena já mostrou o 1º sinal (`marca`).
- **(b) Viagem entre regiões:** "Viajo para Ophidia." chegou em `ophidia`; a presença da região (`mon_ossada_de_pomes`, `origem: conversao`) nasceu **com 1 sinal já mostrado** (`marca`), sem combate, e depois ganhou `som` e `resto` nas duas ações seguintes. Ophidia ficou com 1 presença ativa; a de Brekmar seguiu ativa.
- **(c) Custo `on` × `off`:** 29 chamadas LLM nos dois, **idênticas turno a turno** (2,2,3,2,3,2,2,2,3,2,2); **0 chamada originada em `services/fauna.py`** (verificado pela pilha de chamada no hook de telemetria). Nesta trajetória não houve luta, então não há diferença de trajetória a explicar.

## Limites das rodadas

- Na rodada 1 a presença foi injetada (Skallgard e Ophidia); a rodada 2 cobre o nascimento real.
- Houve timeouts de transporte do DeepSeek na rodada 1, com queda para Groq em alguns nós; na rodada 2 todas as chamadas foram DeepSeek.
- Bloco com 0 token nos turnos sem sinal.
