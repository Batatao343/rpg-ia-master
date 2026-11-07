# SPEC-398 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-11-07 · **Commit revisado:** `bf07dc99`

## Escopo

Revisei o diff `main...spec-398` (5 commits: `3bd74aa5` R1/R2, `e0c57280` R3, `0b55eece` R4,
`7c3d9db2` R5 e `bf07dc99` §6). Arquivos: `services/hand_contract.py`, `api_presenters.py`
(merge da mão), `services/outcome_reason.py`, `agents/combat.py`, `services/encounter_manifest.py`,
`services/combat_targeting.py`, `web/src/combat/{deck.ts,TargetChip.tsx}`,
`web/src/combatOutcome.ts`, `CombatOutcomePanel.tsx`, `types.ts` e os testes novos ou alterados.
Ficou fora o R6 (driver do smoke e smoke no staging): é do coordenador depois do pouso e não está
no diff.

O que confirmei no source:
- **Reação via `reaction_card_id` (SPEC-355/328) não quebrou.** O `ReactionPrompt` lê
  `combat.cards`, não `pilhas.mao`. O motor (`conflict_orchestrator.py:1063-1075`, `reaction_gate`)
  exige `tipo == "reacao"`, a carta na mão e Fôlego, e nada disso olha `jogavel`. Jogar a Reação em
  `jogadas` já era recusado ("não é uma Carta ativa", `conflict_turn.py:397`), então
  `jogavel:false` só alinha a vista ao motor. As fixtures do e2e com `reacao` são de `combat.cards`.
- **Nenhuma sugestão gera 409.** Para reação, `valid_targets: []`. Para ativa, a lista vem de
  `hand_card_targeting`, a mesma regra de `check_declared_target`.
- **`not_playable_from_hand` fora de `INVALID_REASONS` é coerente.** O motivo é só da vista e nunca
  volta como motivo de 409. O tipo `HandCard.invalid_reason` é `string`.
- **R3.** `mark()` roda antes de `_finish_encounter`, que copia o meta (`dict(combat_meta)`).
  `normalize_combat` no load é aditivo, então a chave sobrevive ao save/load, e save antigo sem a
  chave sai sem `outcome_reason` em `result_view`. Combate novo recria o meta do zero
  (`agents/combat.py:3040`), então não sobra motivo velho, e `result_view` ainda é amarrado ao
  `receipt_id`. A narração usa o mesmo predicado de antes (equivalente). `agents/combat.py` caiu de
  3948 para 3946 linhas. O caminho de fecho antecipado (`agents/combat.py:2473`, vitória sem
  inimigos) não chama `mark`, e está certo assim.
- **R5.** Procurar agora mira quem tem `hidden_from` com o herói (inclui `approx_from`), atacar
  escondido segue `target_hidden`, e o 409 de Procurar usa a mesma função
  (`check_declared_target` → `basic_action_targeting`). O flanco (SPEC-285) não foi tocado.
- **R7.** Nada mudou em `evals/`, `web/e2e/`, `sim.py`, `scripts/` nem no golden. Golden 382,
  `size_budget`, `no_silent_except`, `log_event_registry` e `error_envelope` estão verdes. O alerta
  do `dup_helpers` sobre `mark` é colisão de nome (`observability/latency.py`), não helper duplicado.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/hand_contract.py:23`, `web/src/combat/deck.ts:67` | **Regressão visível nas cartas de status e maldição** (Ferimento/Cicatriz, `data/cards/status_e_maldicoes.json`: `tipo` `status`/`maldicao`, `injogavel`, palavra-chave `fardo`). Elas entram na mão (`card_rewards.py:273`, `STATUS_TIPOS`) e não são `ativa`/`utilitaria`, então `merge_row_targeting` grava `invalid_reason: "not_playable_from_hand"`. Com isso, `blockReason` troca "Fardo: pesa na mão, não se joga" por **"Reação: responde sozinha, não se joga da mão"**. Reproduzi: `sts_dor_surda` sai com `jogavel: False`, `invalid_reason: 'not_playable_from_hand'`. O `fardo_estilhaco` escapa só porque não está no catálogo (`get_card` → `None`). Isso aparece em todo combate com o herói ferido. | Em `merge_row_targeting`, sobrescrever só quando `not card_piles.is_fardo(card)` e `tipo in ("reacao", "passiva")` (ou deixar o `jogavel` que a vista já calculou para fardo). Em `deck.ts`, checar fardo antes do motivo do servidor. Teste em `tests/test_hand_contract.py` com `sts_dor_surda` na mão (deve continuar sem `not_playable_from_hand`, ou `blockReason` deve devolver `fardo`) e caso equivalente em `web/tests/deck-342-logic.test.mjs`. |
| P2-1 | P2 | `web/src/combat/TargetChip.tsx:67`, `:93`; `web/tests/spec345-components.test.mjs:35` | **R4: o texto "só cai com Ferimento Crítico" só vale para o Padrão.** No source (`conflict_orchestrator._check_terminal_inner:1609-1640`, `death_flow.py:42-84`): o **Lacaio** cai com **qualquer** Ferimento (`minion_defeated_by_wound`). O **Padrão** cai ao encher o último espaço Crítico. **Elite, Chefe e Nomeado** não caem com o Crítico: entram em Última Ação e Estado Terminal, e só morrem no dano seguinte (`last_stand_resolved`). O que vale para todos: com Vitalidade 0, todo dano que passa vira excedente e abre Ferimento (`conflict_damage.py:330-341`). O texto antigo ("o próximo golpe fere") estava certo. O novo é mais específico e erra em dois de três casos. | Texto genérico correto a partir do source: chip "de pé, sem Vitalidade"; fala/`title` "de pé, sem Vitalidade: cada golpe agora abre um Ferimento". Se quiser falar da queda, só por categoria vinda da vista (Lacaio: "o próximo Ferimento derruba"; Padrão: "cai quando os Ferimentos Críticos se esgotam"; Elite/Chefe: "resiste até a Última Ação"), e isso pede um campo público que hoje o chip não tem. Atualizar a regex do teste e o §6 da spec. |
| P2-2 | P2 | `web/src/combat/deck.ts:46` | **"Reação: responde sozinha" é falso para o herói.** A Reação do jogador só dispara se escolhida no `ReactionPrompt` ("Reação preparada para esta rodada"): sem `_player_reaction_card_id`, o motor cai em `_enemy_reaction_card(player)`, que só lê `cartas`/`enemy_cards` da ficha inimiga e devolve `None` para o herói. O texto também aparece para `passiva`, que não é Reação. | Por exemplo `nao_jogavel: "Não se joga da mão: escolha em Reação preparada para esta rodada"`. Para passiva, um motivo próprio ou um texto neutro ("Não se joga da mão"). Atualizar o `deepEqual` do `BLOCK_TEXT` (D-342-7). |
| P3-1 | P3 | `tests/test_outcome_reason.py` | Falta round-trip real de save/load do campo novo. O teste de "save antigo" só monta o dict à mão e chama `result_view`. Pela leitura, `normalize_combat` é aditivo e preserva o campo, mas o contrato (AGENTS.md, writer persistente) pede a prova. | Um teste `persistence` save → load com `combat.outcome_reason` e outro com save sem a chave, conferindo `result_view` depois do load. |
| P3-2 | P3 | `tests/test_hand_contract.py:39-52` | `test_every_suggested_target_is_accepted_by_engine` passa de forma trivial na reação (lista vazia) e não cobre o cenário que motivou a spec (inimigo escondido mais um visível) nem Procurar. | Parametrizar com 1 escondido + 1 visível (há `hp.add_second_enemy`/`hp.hide_enemy`) e incluir `basic_actions` (attack/engajar/procurar) no mesmo laço. |
| P3-3 | P3 | `services/combat_targeting.py:107-116` | Mudança de comportamento não registrada: com escondidos **e** visíveis ao mesmo tempo, Procurar num visível agora devolve 409 `no_valid_target`. Antes era aceito e gastava a Ação à toa. Parece correto, mas o §6 só fala do caso "todos escondidos". | Registrar no §6/§9 e cobrir com um assert no teste do R5. |
| P3-4 | P3 | `web/src/types.ts:471` | `outcome_reason` está na mesma linha de `outcome`, com comentário inline; destoa do resto da interface. | Linha própria. |

## Correções aplicadas

(nenhuma ainda; o executor preenche commit por item)

## Pendências

- R6 (driver em `docs/spec398/` e item 4 da 369 no staging): coordenador, depois do pouso e do
  deploy. A `Evidência` da spec ("smoke real no staging com driver corrigido") ainda não existe.
- R7 "suíte completa verde no pouso": coordenador (`/spec-land`).

## Comandos rodados

```text
git diff main...HEAD --stat → 17 arquivos, +274/-26; nada em evals/, web/e2e/, sim.py, golden
bash scripts/dev/pt.sh tests/test_hand_contract.py tests/test_outcome_reason.py tests/test_combat_targeting.py tests/test_spec363_hand_targets.py tests/test_spec364_409_play_index.py tests/test_spec364_hidden_view_contract.py tests/test_spec382_node_golden.py tests/test_tactical_archetypes_runtime.py tests/test_spec346_outcome.py tests/test_spec363_outcome_text.py tests/test_size_budget.py tests/test_no_silent_except.py tests/test_log_event_registry.py tests/test_error_envelope.py tests/test_spec364_golden_guard.py tests/test_spec363_golden_guard.py --basetemp=C:/Users/guilh/AppData/Local/Temp/btR398 → 247 passed, 2 skipped
cd web && npm test → 317 pass, 0 fail
cd web && npm run typecheck → ok
bash scripts/dev/py.sh scripts/dev/dup_helpers.py --diff main...HEAD → só colisão de nome `mark` (falso positivo)
script ad hoc (scratchpad) merge_row_targeting em sts_dor_surda → invalid_reason 'not_playable_from_hand' (confirma P1-1)
```
