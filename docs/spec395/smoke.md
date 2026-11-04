# SPEC-395 §6 - smoke de integracao (04/11/2026)

Ambiente: `uvicorn api:app` local (porta 8039, perfil `legacy`), `RPG_ENEMY_DECKS=on RPG_ENEMY_INTENT=on RPG_CARD_DECK=on RPG_FORCE_MOCK=1`, sem chave, sem `.env`. `/game/state` com `simulated: true`. Corruptor L5 em Nova Arcadia. Servidor encerrado por PID (`taskkill /T /F`); `saves/` nao commitado.

**Edicao de save (declarada).** O router do MockLLM nao resolve o alvo para o bestiario (o hint vira generico e o scanner mock devolve "Lobo Sombrio"), e o router zera `combat_encounter_hint` a cada turno. Por isso, em cada jogo: (1) `/game/new` + uma acao "Ataco a criatura" abre um combate mock; (2) um script fora do repo chama o proprio `agents.combat._spawn_v4_enemies` (com `combat_encounter_hint.enemy_id` = a criatura), pos a vitalidade em 30 % (3/10 e 5/16, abaixo do limiar `muito_ferido` <= 0,35), refez `combat.scene` (`_prepare_scene`) e `combat.encounter` (`build_manifest`) e gravou no save. Dai em diante tudo roda pelo `/game/action` normal (`action_kind` "pass" com texto "Aguardo" nas rodadas 1-3, "attack" a partir da 4; as rodadas de Cartas nao chamam LLM).

| Criatura | game_id | Rodadas | Acao do inimigo | Fecho |
|---|---|---|---|---|
| `mon_portao_que_morde` (abissal, Elite, 3/10) | `8836056a-d5b1-4782-8ba4-33d5e30e1504` | 9 | Atacou com `Folha de Ferro` em todas as rodadas a partir da 2 (a 1 foi sem log), incluindo a "Ultima Acao"; nenhuma linha de fuga/recuo no `mech_log` | `outcome: victory`, `final_status: morto`, loot reclamado, sem erro |
| `mon_lacrador_de_saidas` (abissal flexivel, 5/16) | `0b621a0a-286a-4825-b295-505b356909cc` | 2 | Fugiu na rodada 2 (mensagem "cumpre o que o pressagio anunciava") | `outcome: victory`, `final_status: fugiu` |

Tentativas anteriores descartadas: com a cena nao refeita o `round` ficava em 0; e com o inimigo a 20-30 % o primeiro "attack" o matava na rodada 1 (por isso as rodadas 1-3 sao "pass"). Numa execucao intermediaria o jogador morreu na rodada 11 (`defeat`) com o Portao atacando em todas as rodadas: o combate tambem fecha sem erro.

Resultado: D1 confirmado em jogo (portao nunca foge ferido; lacrador abissal `flexivel` ainda foge). Nenhum bug encontrado.
