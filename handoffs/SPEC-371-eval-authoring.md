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

---

## 2ª correção (03/11, commit `6c32b683`): uso `turno` lido antes do reset da rodada

Bug: o `leitor` decide ANTES de `run_round`, e `run_round` zera o uso `turno` no início da
rodada (`services/conflict_orchestrator.py:2804`, `cards.reset_card_usage(state, "turno")`) antes
da janela de reação (`:1064-1101`). `reacao_disponivel` lia o `used_this_turn` da rodada
anterior, então uma reação `turno` usada (ex.: `san_esquiva`) parecia gasta, e o bot caía no
Guardar uma rodada sim, outra não. A Entropia não é tocada nesse reset (`cm.reset_entropy_turn`
só zera `_entropy_trigger_turn`).

Mudou: `reacao_disponivel` ignora os contadores do cascade `turno` (`cards._RESET_CASCADE`);
`cena`/descanso e Entropia seguem valendo. Teste novo
`test_reacao_por_turno_volta_na_rodada_seguinte` (`turno` volta; `dev_ombro_porta`, `cena`, não).
Não mudou: limiares, população, seeds, denominadores, métricas, veredito e a política `_triggers`.

Observação de política (decisão do dono, não alterada): `_triggers` defende sempre que a linha
pública tem `contra_jogo` (ou o golpe estimado ≥ 30 % da Vitalidade), sem checar se o gatilho da
reação preparada casa com o golpe (ex.: `cor_membrana` só reage a ataque à distância). Sem reação
disponível, isso troca o ataque por Guardar.

### Arena (mesma configuração, 2600 pares, 739 s; com as reações iniciais de `87ec4837`/`8d11c4a9`)

| Métrica | `8d11c4a9` (antes desta correção) | `6c32b683` | Limiar |
|---|---|---|---|
| E1 | 34,4 % OK | 34,4 % OK | ≥ 30 % |
| E2 | +3,69 pp OK | +10,06 pp OK | ≥ +3 pp |
| E3 | 0,895× (416) OK | 0,842× (438) OK | ≤ 0,92× |
| E4 | 65,3 % / −19,0 pp FALHA | 67,5 % / −3,0 pp FALHA | ≤ 92 % e ≥ −2 pp |
| E5 | verde | verde | byte-idêntico |

E2 por Postura: Devoto +18,0; Médico +12,1; Arcanista +10,3; Sangromante +10,2; Corruptor +1,6.
Piores criaturas (−3,0 pp cada; 100 pares, ou seja 3 lutas):
`enemy_elemental_fogo_poluido` (Devoto −5, Médico −10, demais 0) e `mon_lencol_de_chamine`
(Arcanista −5, Médico −10, demais 0). E4 reprova só pela parte "pior criatura": −3 pp contra o
teto de −2 pp, dentro do ruído de 20 seeds por célula; a vitória agregada (67,5 %) passa.

---

## 3. Desvio do E4 aceito pelo dono (03/11)

O dono aceitou o E4 em −3,0 pp contra o limite de −2 pp (registrado na §9, commit `7fbc5af3`).
Em `tests/test_spec371_eval.py`, só o caso `test_arena_a_luta_ensina[E4]` virou
`xfail(strict=True)` com essa razão. O strict faz o teste acusar (XPASS → falha) se um dia o E4
passar, para a marca ser retirada. Não mudaram: o limiar `E4_MAX_PIOR_PP = 2.0`, o veredito
gravado no relatório (E4 = FALHA), `scripts/fauna/arena_saber.py`, nem os casos E1–E3.
