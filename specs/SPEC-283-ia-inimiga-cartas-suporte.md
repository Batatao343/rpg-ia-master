# SPEC-283 — IA inimiga usa as Cartas de suporte do bestiário

> **Status:** `approved` (dono autorizou em 19/10 tudo que não exige ação externa dele — onda 19/10)
> **Criada:** 2026-10-19 · **Atualizada:** 2026-10-19
> **Origem:** follow-up 1 da revisão Astra da SPEC-275 ([handoff](../handoffs/SPEC-275-ASTRA-review.md), achado R2)
> **Depende de:** SPEC-275 (`done`), SPEC-232 (`done`)
> **Desbloqueia:** SPEC-285 (letalidade pós-232/275), que usa a medição de letalidade antes/depois registrada aqui
> **EXECUTOR_MODEL:** `Opus` · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true`, porque toca a IA tática do motor de conflito
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Das 40 Cartas do bestiário (`data/cards/bestiario.json`), 9 são de suporte. Oito
são ativas:

- `bst_postura_muralha` e `bst_osso_costa` (`protecao`);
- `bst_roubar_calor` (`buff_defesa`);
- `bst_furia_final` e `bst_noite_skallgard` (`buff_dano`);
- `bst_coro_colmeia` (`buff_acerto`);
- `bst_carregar_ruina` e `bst_poeira_pradaria` (`reposicionar`).

A nona é a reação `bst_defesa_instintiva`, que já roda pela janela de Reação. Essas
Cartas aparecem em 29 criaturas.

Antes da SPEC-275, `_enemy_offensive_card` devolvia essas Cartas mirando o jogador,
e elas eram sempre recusadas. A SPEC-275 R1 tirou as Cartas de suporte do caminho
ofensivo para fechar o impasse eterno. O resultado é que **a IA inimiga nunca usa
essas Cartas**: o conteúdo está nas fichas, mas fica inerte.

Objetivo: a IA tática passa a usar Carta de suporte **no próprio ator ou num
aliado do lado inimigo**, quando o estado da cena justifica. Exemplos: proteger um
aliado em perigo, reforçar-se antes de atacar, fechar distância. O alvo é validado
em Python. O uso respeita custo, frequência e Entropia. A Carta nunca mira o
jogador nem um aliado dele. Tudo é determinístico, sem RNG novo e sem LLM
(princípio "mecânica é Python").

## 2. Requisitos

- **R1 — Escolha determinística.** Nova função `_enemy_support_card(...)` em
  `services/conflict_orchestrator.py`. Ela devolve `(card_id, target_id, direction)`
  ou `None` e decide só pelo estado da cena (`derive_tactical_scene_state`) e pela
  ficha do ator. A mesma entrada dá a mesma saída, e nenhum RNG é consumido.
- **R2 — Regras por família de efeito.** Vale a primeira regra que casar, nesta
  ordem:
  1. **Defensiva** (`protecao`, `buff_defesa`). O alvo é o aliado em perigo
     (`_ally_danger_target`). Sem aliado em perigo, o alvo é o próprio ator, desde
     que ele esteja com `vitalidade_baixa` ou com Vitalidade ≤ 50%.
  2. **Ofensiva** (`buff_dano`, `buff_acerto`, `vantagem`). Na ação tática `support`
     com aliado disponível (`_ally_available_target`), o alvo é esse aliado. Na ação
     `attack` com alvo hostil existente, o alvo é o próprio ator (reforço antes de
     atacar).
  3. **Movimento** (`reposicionar`). O alvo é o próprio ator, na direção
     `aproximar`, só na ação `attack` e com o ator fora da Distância `proximo`.
  4. **Sem repetição.** A Carta não é escolhida se o alvo já tem uma condição ativa
     vinda dela (`source == card_id`). Isso impede loop de reforço.
- **R3 — Precedência.** A escolha da Carta de suporte vem depois de
  `flee`/`surrender`/sem alvo e antes das manobras táticas sem Carta. Ela nunca
  passa na frente de `stabilize`: aliado em Estado Terminal tem prioridade. Com
  `_forced_attack` (quebra de impasse da SPEC-275 R5), nenhuma Carta de suporte é
  escolhida.
- **R4 — Lado validado em Python.** O `target_id` é sempre o próprio ator ou um id
  vivo e disponível de `_same_side_ids`. Na resolução,
  `_invalid_target_reason(support=True)` continua recusando alvo hostil, coberto pelo
  fallback da SPEC-275 R3. Nenhuma combinação de estado faz a Carta mirar o jogador
  ou um aliado dele.
- **R5 — Economia.** O uso passa por `cards.can_use_enemy_card(..., "ativa")` e
  `cards.use_enemy_card`, que cobram Entropia e frequência. Uma Carta gasta não é
  escolhida de novo enquanto o contador estiver esgotado. Inimigo não declara Ruptura
  (`use_enemy_card` não tem essa variante), e isso continua assim.
- **R6 — Sem janela de Reação para suporte.** Uma Carta de suporte que mira o
  próprio ator ou o mesmo lado não abre a janela de Reação do lado oposto. Ela não é
  um ataque declarado, e o jogador não pode gastar Reação contra um reforço.
- **R7 — Narração pt-BR.** O log narrável do uso é uma frase em pt-BR, com nomes e
  sem ids ("X usa Carta" ou "X usa Carta em Y"). O `reposicionar` deixa de pôr o token
  técnico `id -> proximo (pre)` na prosa. A telemetria estruturada vai em
  `out["enemy_support_cards"]`, no formato
  `{event: "enemy_support_card", actor_id, card_id, target_id, kind}`.
- **R8 — O impasse continua fechado.** `playtest run --profile combate --turns 200`
  nas seeds 21, 22 e 23 termina com 0 `combat.no_progress` e 0 erro.
- **R9 — Medição de letalidade.** A spec registra, antes e depois, a taxa de morte
  do jogador por combate no playtest mock `combate` de 200 turnos, nas mesmas seeds
  (§8). A SPEC-285 usa esse número.

### Fora de escopo

- Rebalancear números das Cartas (valor, custo, frequência). Isso fica com a
  SPEC-285 / SPEC-049.
- Carta de suporte que mira o jogador (debuff) e Cartas novas de bestiário.
- Carta de suporte como reação. `bst_defesa_instintiva` continua pela janela de
  Reação existente.
- IA de NPC aliado do jogador (controlado pela party).

## 3. Design técnico

- **`services/conflict_orchestrator.py`**
  - Constantes `_ENEMY_DEFENSIVE_SUPPORT`, `_ENEMY_OFFENSIVE_SUPPORT` e
    `_ENEMY_MOVE_SUPPORT`.
  - Nova função
    `_enemy_support_card(scene, actor, actor_id, actors_by_id, sides, canonical, action_key) -> tuple[str, str, str | None] | None`
    (R1/R2/R4/R5).
  - `enemy_declaration`: depois do `if target is None: pass`, chama
    `_enemy_support_card`, desde que não haja `forced_attack` e
    `action_key != "stabilize"`. Se ela devolver uma Carta, a declaração é
    `TurnStep(kind="card", card_id, target_id, direction)` (R3).
  - `_resolve_actor_turn`:
    - não abre `_open_reaction_window` quando o passo é Carta de suporte com alvo do
      mesmo lado (R6);
    - depois de `resolve_turn`, registra a telemetria e a frase pt-BR (R7) para cada
      Carta de suporte inimiga usada.
- **`services/conflict_turn.py`**
  - Em `_resolve_support_card`, o log de `reposicionar` usa o nome do alvo e a nova
    Distância em pt-BR, no lugar de `cs.move_distance().log`.
- **Schema:** nenhum campo novo persistido. `out["enemy_support_cards"]` só existe
  durante a rodada. Saves antigos não são afetados.

## 4. Plano passo a passo

### Etapa 1 — Testes (`tests/test_spec283_enemy_support_cards.py`)
- Escolha da Carta e do alvo:
  - `test_defensive_card_protects_ally_in_danger`: aliado com Vitalidade ≤ 50% faz
    `postura_muralha` mirar o aliado, e a rodada aplica `protection` nele.
  - `test_defensive_card_on_self_when_badly_wounded`: sem aliado, o inimigo ferido se
    protege.
  - `test_defensive_card_not_used_when_healthy`: inimigo saudável e sem aliado em
    perigo não escolhe a Carta.
  - `test_offensive_buff_on_self_before_attack`: `noite_skallgard` mira o próprio
    ator, cobra Entropia e aplica a condição `damage`.
  - `test_offensive_buff_on_available_ally_for_support_action`: um `lider_matilha`
    com aliado manda `coro_colmeia` para o aliado.
  - `test_reposition_closes_distance_only_when_far`: distante dá `aproximar`; em
    `proximo`, a Carta não é escolhida.
- Restrições:
  - `test_support_card_never_targets_player_side`: varre os estados
    (ferido/saudável, com aliado/sem aliado, cada Carta) e confirma que o alvo está
    sempre no lado inimigo.
  - `test_support_card_respects_frequency_and_entropy`: Carta gasta ou sem Entropia
    não é escolhida, e o inimigo ataca.
  - `test_no_repeat_while_condition_active`.
  - `test_forced_attack_skips_support_cards` (R3 / SPEC-275 R5).
  - `test_stabilize_precedes_support_card`.
  - `test_support_card_does_not_open_reaction_window` (R6).
  - `test_support_card_log_is_ptbr_without_ids` (R7), junto com a telemetria
    estruturada.
  - `test_choice_is_deterministic` (R1).
- Adaptar
  `test_spec275_stalemate.py::test_enemy_declaration_falls_to_basic_attack_without_offensive_card`:
  com `buff_acerto` disponível, o inimigo agora se reforça. O invariante da SPEC-275
  continua valendo: nenhuma Carta de suporte mira o jogador.

### Etapa 2 — Implementação (R1–R7)

### Etapa 3 — Playtest em 3 seeds, medição de letalidade (R8/R9) e revisão independente

## 5. Critérios de aceite

- [ ] R1–R7 cobertos por testes verdes
- [ ] `playtest run --profile combate --turns 200` nas seeds 21/22/23: 0 `combat.no_progress`, 0 erro
- [ ] Medição de letalidade antes/depois registrada (§8)
- [ ] Suíte completa verde, exceto `test_project_index` stale (esperado até o rebuild no pouso)
- [ ] Saves antigos continuam carregando (nenhum campo novo persistido)
- [ ] Revisão independente Opus (`handoffs/SPEC-283-review.md`)
- [ ] Smoke real DeepSeek com ≤ 10 turnos de combate (§6)

## 6. Smoke test com LLM real

A narração muda: a rodada ganha linhas novas em pt-BR no log. O smoke curto com
DeepSeek roda um combate contra uma criatura com Carta de suporte e confere dois
pontos:

1. A Carta de suporte aparece na prosa como ação coerente da criatura.
2. A narração não mostra id técnico nem token (`enemy_support_card`, `-> proximo`).

## 7. Riscos & compatibilidade

- **Letalidade:** o reforço gasta o turno do inimigo e atrasa o 1º ataque, mas os
  ataques seguintes ficam mais fortes. A proteção alonga as lutas. O efeito líquido
  é medido em §8 e encaminhado à SPEC-285.
- **Impasse:** quase todas as Cartas de suporte do bestiário têm frequência `cena`.
  A exceção é `poeira_pradaria` (`turno`), que só dispara fora de `proximo` e
  converge. `_forced_attack` desliga o suporte, e a regra 4 de R2 impede repetir o
  reforço.
- **Saves antigos:** nada é persistido. Um save no meio do combate segue com o mesmo
  estado.

## 8. Evidência

(preenchido na execução)
