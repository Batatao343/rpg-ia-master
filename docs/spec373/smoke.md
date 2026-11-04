# SPEC-373 §6 — smoke real (04/11/2026)

Ambiente: `uvicorn api:app` local (porta 8037, perfil `legacy`), `RPG_ENEMY_DECKS=on RPG_ENEMY_INTENT=on RPG_CARD_DECK=on RPG_SCENE_CARDS=on RPG_CARD_REWARDS=on RPG_COMBAT_OBJECTS=on`, chave real do `.env` (rotas DeepSeek primário). Todo `/game/state` devolveu `simulated: false` (`mock=False`); `llm_mode: routes`. 3 jogos, cerca de 18 requests de ação (as rodadas do conflito não chamam LLM). Servidor encerrado por PID (`taskkill /T /F`), `.env` removido do worktree.

Provider por chamada (log `turn`, `llm_providers`): só o turno que abre o combate (router CLASSIFY + narrações FAST) e o turno que fecha o combate chamam LLM, sempre `deepseek`, 0 falhas, 0 fallbacks.

| Jogo | game_id | Turnos com LLM (provider) |
|---|---|---|
| A (Corruptor L5, Montanhas Afiadas) | `fa04d14a-4bc3-4417-b753-1bd03c56ac96` | t2 abertura: 3 chamadas deepseek; t9 desfecho (morte): 1 chamada deepseek; t3–t8 rodadas: 0 LLM |
| B (Corruptor L5, Nova Arcádia) | `78e84c66-3aa6-4a73-a84e-e817fa86199f` | t2 abertura: 2 chamadas deepseek; t3 rodada: 0 LLM |
| C (Arcanista Cinzento L5, Nova Arcádia) | `e29325bd-475a-47ee-bc73-8ca9a8d6d55a` | t2 abertura: 2 chamadas deepseek; t3 rodada: 0 LLM |

A criação do jogo (`/game/new`, prólogo) não gera linha `turn` no log; o prólogo veio com texto real e `simulated: false`.

## Item 1 — Chefe da esteira em jogo (OK) — jogo A

Ação "Ataco o Peso dos Vencidos" em `montanhas_afiadas` abriu combate com `mon_peso_dos_vencidos` (`categoria: chefe`; o spawn criou 2 instâncias `_1` e `_2`, ver observações). Baralho montado (save, `enemies[].cartas`):

- `_1`: `cri_peso_dos_vencidos_punho_do_orc`, `_soco_de_cima`, `_patas_de_goblin` (3 próprias) + `bst_defesa_instintiva` + `inf_predador_apice_olhar_de_fome` (1 de família).
- `_2`: as 3 próprias + `bst_defesa_instintiva` + `inf_predador_apice_olhar_de_fome` + `inf_predador_apice_rugido_que_dobra` (2 de família).
- As assinaturas de família de `predador_apice` são `inf_predador_apice_sentenca_do_apice` e `_dilacerar`: nenhuma está no baralho. A assinatura em jogo é a própria (`tactical_profile.assinatura.carta = cri_peso_dos_vencidos_soco_de_cima`, `a_cada_n: 3`).
- Telegrafo: em `/game/state` `combat.pressagios_publicos[].prenuncio`, na rodada anterior ao golpe: "O Orc de Peso dos Vencidos 1 ergue os dois punhos, e todas as mãos de baixo se fincam no chão ao mesmo tempo." (promessa gravada em `combat.scene.prenuncios` com `rnd` seguinte). O `Soco de Cima` foi jogado nas rodadas 3 e 6 (`a_cada_n: 3`), conforme o mech_log ("Peso dos Vencidos 1 · Soco de Cima → Você"). Só vi o texto do prenúncio no save/estado depois da rodada 4, não registrei a captura da rodada 2.
- Facção: este chefe não tem Carta de facção sorteada (`bst_defesa_instintiva` é genérica do bestiário, não de facção); a parte "mais facção" do baralho não foi exercitada neste chefe.

## Item 2 — Duas ações e fase (OK) — jogo A

- `acoes_por_rodada: 2`. Em toda rodada a 2ª ação do chefe aparece após "<chefe> age de novo" no registro como ataque básico sem nome de Carta ("Peso dos Vencidos 1 → Você · 2d10 ..."), nunca Carta de família.
- Troca de fase a ≤ 60 % no `_1` (22 -> 14 -> 11 de 22): narração da fase na mensagem da rodada 5 ("Peso dos Vencidos 1 se ancora nas patas de baixo, e os Goblins mortos seguram o Orc no alto."); na rodada seguinte o chefe joga a Carta própria da fase, `Monte Firme` (`cri_peso_dos_vencidos_monte_firme`, `baralho_extra`).
- A ação extra seguiu básica mesmo na fase nova (o ramo "extra com Carta própria da fase" não apareceu).
- Desfecho: o jogador (Corruptor L5, 18 Vitalidade) morreu na rodada 7 (`outcome: death`, narração de fim de combate com 1 chamada deepseek).

## Item 3 — Criatura da 332 (OK) — jogo B

"Ataco o Bandido" em `nova_arcadia` -> `enemy_bandido_1` (sem `cartas_autorais`, `_deck332`) + `enemy_iniciado_chama_azul_2`. Baralho do Bandido: `bst_pancada_esmagadora`, `bst_defesa_instintiva` (genéricas) + 3 de família (`inf_bruto_pancada_de_tronco`, `inf_bruto_agarrar_e_atirar`, `inf_bruto_rugido_de_guerra`), dentro de 3–5. Iniciado: 3 genéricas + 4 da família `conjurador` + 3 de facção (`inf_fac_filhos_chama_azul_*`). Nota: a §6.3 cita `enemy_gargula_ferro`, que hoje (349) é a "Rã de Lótus" com 2 Cartas autorais, então não serve como exemplo "sem autorais"; usei o Bandido.

## Item 4 — Carta `cartas-373` no painel (OK, com ressalva) — jogo B

`inf_bruto_agarrar_e_atirar` (origem `cartas-373`, `data/cards/inimigos/bruto.json`) estava no baralho do Bandido e foi jogada na rodada 1 ("Bandido ataca Você com Agarrar e Atirar: acerto crítico — 10 de dano"). Em `/game/state` `enemies[].revealed_cards = [{"id": "inf_bruto_agarrar_e_atirar", "name": "Agarrar e Atirar"}]`; o painel (`Hud.tsx`, `Arena.tsx`) mostra "Cartas vistas: Agarrar e Atirar". A descrição da Carta ("Agarra pela roupa e atira o alvo contra a ruína mais próxima, como quem joga um fardo.") não tem número, mas `revealed_cards` expõe só `id` e `name`; não abri a UI, então a descrição renderizada no painel não foi verificada.

## Item 5 — Parte C (OK; emboscada N/A) — jogos B e C

- **Mão Adiantada (jogo B).** Não há caminho de API para dar a Carta a um Corruptor de `biologia` (é do tronco, tier 3, fora do baralho inicial), então **injetei `cor1_tro_mao_adiantada` na `mao` e em `known_cards`/`prepared_cards` do save** (caminho determinístico; o motor jogou a Carta normalmente por `/game/action`). Resultado: "Você ganha a condição Mão Adiantada"; no save `active_conditions`: `{"name": "Mão Adiantada", "duration": 1, "source": "cor1_tro_mao_adiantada", "stat": "initiative", "delta": 2}`. Texto na mão: "+2 de Iniciativa.", custo Fôlego 1.
- **bomba_estopim v2 (jogo C).** Mesma injeção (`arc1_imp_bomba_estopim` na `mao`; a subclasse do jogo era `calibrado`, não `improvisador`). Na mão: custo Fôlego **2** (era 1), texto "Causa 5 de dano (4 da Carta + 1 de bônus). Causa 2 ...". Resolução: 4 de dano no alvo (10 -> 5 com a área) e o 2º inimigo 10 -> 9; confirma o número novo (área 2) do R20. Não testei com o improvisador de verdade.
- Emboscada (`buff_iniciativa` anula): N/A (P2-6, SPEC-369).

## Observações para o coordenador (não consertei)

1. "Ataco o Peso dos Vencidos" gerou 2 instâncias do mesmo chefe numa luta de nível 5; a §6.1 espera um. Vale juntar às ressalvas do chefe `unico`.
2. Corruptor L5 (18 Vitalidade) morre em 7 rodadas contra 2 chefes; não é bug da 373.
3. Os saves do smoke ficaram em `saves/` do worktree (ignorado pelo git).
