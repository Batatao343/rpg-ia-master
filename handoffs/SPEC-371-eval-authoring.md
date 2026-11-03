# SPEC-371 · eval authoring: correção do bot `leitor` da arena

Autor do eval (independente do executor de produto), 03/11. Nenhum código de produto foi tocado.

## Bug (harness)

`scripts/fauna/arena_saber.py:125` (commit `f75f88d2`) testava as Cartas de reação com
`cards.can_use_card`, que por design só responde por Cartas `ativa`
(`services/cards.py:660-663`: reações entram por gatilho). Toda reação era recusada e a única
defesa do `leitor` era Guardar, que gasta a Ação.

Evidência no source:
- o herói da arena tem reação preparada em 3 das 5 Posturas (nível 3, `docs/spec285/arena_lethality.py:84` via `playtest.runner._build_initial_state`):
  Devoto `dev_ombro_porta` (`ao_inimigo_engajar`), Sangromante `san_esquiva` (`ao_ser_atacado`),
  Corruptor `cor_membrana` (`ao_ser_alvo_distancia`); Arcanista e Médico não têm nenhuma;
  `can_use_card` = False nas três;
- o motor aceita a reação do jogador via `TurnDeclaration.reaction_card_id`
  (`services/conflict_orchestrator.py:2770-2773`) e a dispara na janela de reação
  (`:1064-1101`: preparada, `reaction_gate`, `gatilho_matches`, `use_card`), sem gastar a Ação;
- bug secundário: o harness mantinha um só `state` na luta e o orquestrador grava a escolha em
  `state["_player_reaction_card_id"]` (`:2773`), então a reação ficaria armada nas rodadas
  seguintes. No produto a escolha é transitória: `agents/combat.py:2663-2666` cria `round_state`
  novo a cada rodada e `:3237` zera `player_reaction_card_id`.
- reuso: nenhum bot existente usa reações (`docs/spec285`, `docs/spec332`, `docs/spec358/arena_v2.py`,
  `scripts/cards/sim.py` tratam `reacao` como não jogável).

## O que mudou (commit `bff04051`)

- `reacao_disponivel(player, cid)`: espelho puro da economia que `cards.use_card` cobra de uma
  reação preparada (preparada, frequência livre, Entropia suficiente); substitui `can_use_card`
  no `leitor_decl`.
- `fight`: `state = {"player": player}` a cada rodada, como `agents/combat.py`.
- 2 testes novos em `tests/test_spec371_eval.py` (escolhe a reação; cai para Guardar sem ela).

## O que NÃO mudou

Limiares E1–E4, nível, população (26 criaturas), Posturas (5), seeds (20), denominadores,
métricas, agregação, veredito, política do bot (reação preparada > Guardar, mesmo gatilho
`_triggers`), flags.

## Resultado (mesma configuração, 2600 pares, 705 s)

| Métrica | Antes (`f75f88d2`) | Depois | Limiar |
|---|---|---|---|
| E1 | 34,4 % OK | 34,4 % OK | ≥ 30 % |
| E2 | −25,59 pp FALHA | −12,85 pp FALHA | ≥ +3 pp |
| E3 | 0,999× (213) FALHA | 0,928× (321) FALHA | ≤ 0,92× |
| E4 | 55,2 % / −47,0 pp FALHA | 59,6 % / −31,0 pp FALHA | ≤ 92 % e ≥ −2 pp |
| E5 | verde | verde | byte-idêntico |

E2 por Postura (revelados): Sangromante +6,5 pp; Corruptor +1,6; Devoto −5,7; Arcanista −21,9;
Médico −35,5. As Posturas sem reação preparada (Arcanista, Médico) seguem caindo para Guardar,
e o Devoto (gatilho `ao_inimigo_engajar`, raro depois do 1º engajamento) quase não a dispara.

## Parecer

A hipótese do executor estava certa em parte: havia bug do harness, e corrigido ele vira E2
positivo onde o herói tem uma resposta barata. O que ainda reprova não é bug de harness. É a
política congelada do bot (Guardar quando não há reação) somada ao conteúdo: Arcanista e Médico
não têm reação preparada contra a assinatura. Continua a decisão do dono da §9 (a) dar ao herói
uma resposta barata ao golpe conhecido, ou (b) uma nova spec de avaliador com outra política
defensiva (por exemplo, não Guardar sem reação). Nenhuma das duas cabe a este autor sem nova
aprovação, porque mudam a política do bot.
