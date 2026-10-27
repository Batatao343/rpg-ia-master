# SPEC-328 — revisão sol (review)

> **Veredito (re-revisão, `a0556a29`):** `APPROVED_WITH_FOLLOWUPS`: aprovado para pouso com `RPG_CARD_DECK=off`. R-1 (semântica do Pacto) e R-2 (Presságio rerolado na recusa) bloqueiam `on`.
> Veredito da 1ª passada (`79c391ea`): `CHANGES_REQUIRED`.
> **Revisor:** Opus / Sol · **Data:** 2026-10-27 · **Commit revisado:** `79c391ea` → `a0556a29` (rebase em `main` `8bd4f384`, SPEC-329 incluída)

## Escopo

`git diff main...HEAD` da branch `spec-328`: `services/card_piles.py`,
`services/card_deck_round.py`, `services/cards.py`, `services/conflict_orchestrator.py`,
`services/conflict_turn.py`, `services/content_validator.py`, `agents/combat.py`, `api.py`,
`data/cards/basicas.json`, os 4 testes novos, a arena (`docs/spec328/`) e o §5b da spec.
Na re-revisão, também o delta `597aeab7..a0556a29` e a resolução do rebase com a SPEC-329.
Fora do escopo: front (SPEC-334), jornadas e2e (autoria separada), suíte completa.

Pontos pedidos pelo coordenador (1ª passada):

- **(a) `off` byte a byte:** o motor, a narração e o save ficam iguais. `deck_mode()` devolve `""`
  sem `_piles`; `refusal`/`shadow`/`reaction_gate`/`reaction_commit` viram no-op; o nó só cria
  `pilhas` com flag != `off`; `use_card` só aceita `deck` com a flag `on`;
  `TurnDeclaration.jogadas` vazio não muda `acao` e o playtest serializa com `exclude_defaults`.
  `all_cards()` passa a ter 15 básicas, mas nenhum consumidor em `off` muda: `cards_for_class`
  as exclui, a subclasse vem de `subclasse` (vazia nas básicas) e o MockLLM acha `arc_vazao` antes
  de `bas_arc_vazao` pela ordem dos arquivos. A única exceção era o schema CLASSIFY (P1-1), já resolvida.
- **(b) save/load:** `persistence` grava `combat` inteiro e `normalize_combat`/`_rewrite_refs` não
  tocam `pilhas`. O replay por `seed:embaralhos` está certo. Testes reais foram adicionados na
  correção (P2-4). Combate antigo sem `pilhas` está coberto.
- **(c) recusa sem efeito colateral:** OK no motor. `plan_plays` trabalha numa `deepcopy`; a recusa
  retorna em `run_round` antes de `reset_card_usage`, `reset_entropy_turn`, `tick_boiler` e do `rng`;
  o nó devolve a rodada e não chama `begin_round`. **Exceção** no nó, herdada da 329: o Presságio é
  recalculado (R-2).
- **(d) Pacto via `on_channel`** era bug (P1-2). A nova semântica está em R-1.
- **(e) determinismo:** OK. A semente é `crc32(game_id:epoch:action_count)` e cada embaralho usa
  `Random(f"{seed}:{n}")` com `n` persistido. O RNG global do combate fica intocado.
- **(f)** `test_log_event_registry.py` e `test_no_silent_except.py` passam. O único `except`
  novo (`card_deck_round.py:76`) faz `logger.debug(..., exc_info=True)` e não é silencioso.
- **(g) arena:** ver Pendências.

Sem segredo em log, sem mudança em `evals/`. O guard de FallbackLLM no parser está presente e testado.

## Achados

### 1ª passada (`79c391ea`). O estado de cada um está em "Correções aplicadas".

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/combat.py:1147` | `extra_card_ids` entrava no schema CLASSIFY sempre, inclusive em `off`. | Campo só com `piles is not None`. |
| P1-2 | P1 | `services/card_deck_round.py:130` | O Pacto disparava `on_channel`, que só casa com o Arcanista: para ele o Pacto saía de graça e gastava o teto do gatilho; as outras Posturas não ganhavam Carga. | Consequência explícita e igual para as 5 Posturas. |
| P1-3 | P1 | `services/card_piles.py:113` + `agents/combat.py:1746` | `start_piles` → `migrate_deck` reescrevia `prepared_cards` na ficha, inclusive em `shadow` (viola R17), e deixava rollback sujo para `off`. | Shadow sem mutar a ficha; guardar a Preparação para o rollback. |
| P2-1 | P2 | `agents/combat.py:1094` | O atalho por nome casava substrings: "Vazão Controlada" → 2 cartas. | O nome mais longo vence. |
| P2-2 | P2 | `services/card_deck_round.py:97` | `reset_turn_budget` a cada jogada zerava a Guarda. | Guarda dura a rodada. |
| P2-3 | P2 | `services/card_deck_round.py:140` | O reembolso não desfazia o gatilho do Pacto. | Desfazer tudo. |
| P2-4 | P2 | `tests/test_round_multi_play.py:234` | O round-trip era só `json.dumps`. | Spawn real + `save/load` real + API. |
| P2-5 | P2 | `agents/combat.py:2072` | `last_player_action` mostrava só a 1ª jogada. | `plays` aditivo. |

### Re-revisão (`a0556a29`)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| R-1 | P1 (bloqueia `on`; decisão do dono) | `services/card_piles.py:269-279`, `_plan` `:263` | **O Pacto virou bônus.** No motor, Entropia é **combustível**: a ficha começa cheia (`ensure_combat_sheet`), `use_card` debita, `entropy_on_kill` é "colheita". Dar +2 Entropia por Fôlego emprestado é ganho, não custo. Probe com Entropia 8, ataque com 1 Fôlego emprestado: **as 5 Posturas terminam com 10 de Entropia e Carga +1**. Com o pool cheio (clamp), o Pacto custa só +1 Carga/rodada e dá 2 Fôlego, ou seja, Fôlego efetivo 5/rodada. O bot da arena não usa o Pacto, então a arena nem mede isso. O log ("o Abismo empresta, e cobra: +2 Entropia") apresenta ganho como cobrança. A R8 diz "pagar cada Fôlego faltante **com** 2 Entropia" e o §1 diz "pagar o Fôlego que falta com Entropia". | Voltar ao **débito** de 2 Entropia/Fôlego (exige Entropia no pool) e **manter** o +1 Carga 1×/rodada uniforme, que é a parte boa da correção. Se a intenção é mesmo "ganhar Entropia", isso precisa do dono (R8 é [D?]) e de uma passada de arena com bot que usa o Pacto. Testes: inverter o sinal em `test_pacto_*`. |
| R-2 | P1 (com 328 `on` **e** 329 `on`) | `agents/combat.py:2241-2252` (código da 329, pré-existente na `main`) | Na recusa (`deck_refused`, e também `chase_refusal`/item recusado, já na `main`), o nó remove e **recalcula** o Presságio com o `rng` global (`rng = random`, `:1922`). A recusa troca a intenção inimiga que o jogador já viu. Com a 328 `on`, recusar é trivial (mandar uma carta fora da mão), então dá para **rerolar o Presságio de graça**. | Com `out.get("action_refused")`, preservar `pressagios`/`pressagios_publicos`. Teste no nó: recusa mantém `pressagios` idêntico. Pode ir na 328 ou num bugfix da 329. |
| R-3 | P2 | `services/card_deck_round.py:150-155` | O reembolso restaura o snapshot de Entropia/Carga tirado **antes** de `_resolve_actor_turn`. Mudanças legítimas no meio (AoO ou reação inimiga que fere o herói → `on_damage_taken`) são apagadas junto. | Desfazer só os deltas do Pacto, não o snapshot inteiro. |
| R-4 | P2 | `agents/combat.py:1670` | O rollback `on → off` só acontece ao entrar no nó de combate. Fora de combate, com a flag já `off`, `api._cards_block`/`set_prepared` ainda veem as preparadas derivadas do baralho até o próximo conflito. | `deactivate_deck` também no load ou no `_cards_block` quando `mode()=="off"`. |
| R-5 | P2 | `tests/test_api_jogadas.py:284` | Asserção `a or b`, ver (3). | Endurecer. |

## Correções aplicadas

Commit `a0556a29`, conferido item a item:

| Achado | Estado | Observação |
|---|---|---|
| P1-1 | **resolvido** | `PlayerMoveDeck` só com pilhas (`agents/combat.py:1163`). O teste cobre os dois lados. Em `off` o schema é o da `main`. |
| P1-2 | resolvido como pedido, mas abre **R-1** | Sem `on_channel`; `apply_pact` é igual para as 5 Posturas, com +1 Carga 1×/rodada (`pacto_carga`). |
| P1-3 | **resolvido** | `start_piles` não toca a ficha (shadow limpo, testado). `activate_deck`/`deactivate_deck` com `prepared_cards_pre_deck`; `use_card` só aceita `deck` com `on`. Resto menor em R-4. |
| P2-1 | **resolvido** | Reconferido com o probe real: "uso Vazão Controlada" → `['arc_vazao']`. |
| P2-2 | **resolvido** | `_restore_guard` entre jogadas; gatilhos de classe já são limitados 1×/rodada. |
| P2-3 | resolvido, com ressalva R-3 | — |
| P2-4 | **resolvido** | Spawn real (`crc32(instance_id)`), `save_game_state`/`load_game_state` reais + mais uma rodada pelo nó, `/game/action` com `jogadas` via `TestClient`. |
| P2-5 | **resolvido** | `last_player_action.plays` só com > 1 jogada; testado pela API. |

### Pontos pedidos na re-revisão

**(1) Rebase com a SPEC-329.** Em `services/conflict_orchestrator.py`, o diff `main...HEAD` contém só os
ganchos da 328: `reaction_gate`/`reaction_commit`, `refusal`/`shadow` antes do `if refusal` e o desvio
`resolve_player_plays` no laço de ordem. O bloco do Presságio (`frozen`, `_next_intent`, `_frustrate`,
`_enemy_decl`) ficou intacto e é usado nas duas chamadas (`2160`, `2197`). Em `agents/combat.py`, nenhuma
linha da 329 mudou: `pressagios=` segue no `run_round` e o congelamento do próximo Presságio segue antes do
`begin_round`. As várias jogadas do jogador não consomem o cursor de intenção dos inimigos (o cursor é por
inimigo) e só frustram Presságios pelas regras normais (`still_possible`), o que é correto. Com as duas
flags em `off`, os ganchos são no-op e o comportamento é o da `main`. `test_enemy_intent*.py` passa.
A ressalva cross-spec está em R-2.

**(2) Pacto do Abismo.** A implementação é uniforme nas 5 Posturas e está testada, mas a semântica inverte o
custo (R-1).

**(3) Asserção `a or b`** (`tests/test_api_jogadas.py:284`). Na prática é inofensiva, mas não está correta.
Pela precedência, ela vale `(round_a == round_b == 2) or (a.active is False)`. O ramo `or` é morto: se o
combate acabasse, `pilhas` seria removido e a linha anterior (`a["combat"]["pilhas"]`) daria `KeyError`. O
teste então só passa com o conflito vivo, e as pilhas idênticas com e sem reload, sob a mesma semente
global, estão bem assertadas. **Basta para (b).** Follow-up R-5: `assert a["combat"]["active"] and
a["combat"]["round"] == b["combat"]["round"] == 2` e comparar também `player`/`enemies` de `a` e `b`. Hoje
uma divergência pós-reload fora das pilhas (Entropia, Vitalidade inimiga) passaria despercebida.

## Pendências

- **R-1 e R-2 antes de qualquer `on`.** O `shadow` da 328 não aplica o Pacto (R-1 não o afeta), e R-2
  só aparece com a 329 também `on`. R-3..R-5 podem ir junto.
- **Arena (g):** a causa principal é a economia de ações (quase tudo custa 1 Fôlego com Fôlego 3: ~3
  ações/rodada contra 1 do inimigo). O executor confirmou que `dano_base ≥ 5` não muda a arena, o que
  reforça: a alavanca é `FOLEGO_BASE`/custo do `attack` e das básicas, ou a pressão inimiga da 329. Com
  R-1 como está, o Pacto ainda acrescentaria até +2 Fôlego/rodada. Decisão do dono; não bloqueia `off`.
- A spec segue `in-progress` (critério da arena aberto; `on` só com a SPEC-334).

## Comandos rodados

```text
# 1ª passada (79c391ea)
pytest -n 2 (4 arquivos novos + log_event_registry + no_silent_except + 10 de regressão de cartas/combate) → 323 passed
probe: Pacto 1 Fôlego, Entropia 8 → Arcanista 8/Carga 1; Sangromante 6/0; Devoto 6/0
probe: "uso Vazão Controlada" (piles on) → ['arc_vazao', 'bas_arc_vazao']
# re-revisão (a0556a29)
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_card_piles.py tests/test_deck_migration.py tests/test_round_multi_play.py tests/test_api_jogadas.py tests/test_enemy_intent.py tests/test_enemy_intent_node.py tests/test_log_event_registry.py tests/test_no_silent_except.py tests/test_combat_simulator.py tests/test_conflito_cartas.py tests/test_mecanica_orfa.py tests/test_spec285_lethality.py tests/test_bug_combate_modificadores.py → 279 passed
probe: Pacto 1 Fôlego, Entropia 8 → Arcanista/Sangromante/Devoto: Entropia 10, Carga 1
probe: "uso Vazão Controlada" (piles on) → ['arc_vazao']
git diff main...HEAD -- services/conflict_orchestrator.py → só ganchos 328; bloco do Presságio intacto
```
