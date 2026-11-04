# SPEC-397 — revisão sol (review)

> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus 5.5 / Sol (spec-reviewer) · **Data:** 2026-11-04 · **Commit revisado:** `e67f7873`

## Escopo

Branch `spec-397`, `main...spec-397` (851cf6ec, 4d87e3bb, e67f7873): `scripts/cards/draft.py`,
`services/card_rewards.py`, `services/opening_ambush.py` (novo), `agents/combat.py` (2 linhas),
testes `tests/test_card_draft.py`, `tests/test_card_smoke_edges.py`, `tests/test_spec346_vigilia.py`,
spec §4/§7. Fora: o smoke real do §5 (não executado, fica com o coordenador) e a suíte completa.

## Conferência por requisito

- **R1** ok. `aceitas[: max(n, 0)]` vem depois de triagem, reparo e `_ajustar_orcamento`; `entregues`
  sai do lote já cortado. Teste com 6 cartas para `n=4`.
- **R2** ok. Enum `sorted(card_lint.FREQUENCIAS)` no schema (`json_schema_extra`, parse tolerante) e a
  triagem rejeita valor fora do vocabulário, que cai em `rejeitadas` e no reparo. Os guards do
  FallbackLLM em `draft.py:261` e `:393` estão intactos.
- **R3** ok. `opening_ambush.with_ambush` devolve o mesmo objeto `narrative` quando o motivo não é
  `ambush`/`ambush_negated_vigilia`, então a abertura sem emboscada fica byte-idêntica. `player_ambush`,
  `player_attack` e `neutral` não ganham frase. `agents/combat.py` tem 3957 linhas antes e depois. Os
  testes passam por `_combat_node` com MockLLM, não pelo HTTP como a spec pedia; o desvio está
  declarado no §7 (P3-1).
- **R4** ok. A conclusão se sustenta: o teste confirma `serra_cirurgica` em
  `inventory.equipped_items` do Médico de Campo recém-criado.
- **R5** o bug é real e a correção tira o sintoma: o teste novo **falha contra o
  `card_rewards.py` da `main`** (`_has_vigilia` False; conferido trocando o módulo) e passa na
  branch. Mas a correção quebra o invariante da Preparação (P1-1).
- **R6** ok no que dá para ver agora. Não mudou nada em `evals/`, `web/`, golden, `sim.py` nem
  contracts. `test_size_budget` e `test_no_silent_except` passam, ruff está limpo e
  `dup_helpers` não acusa nada. A suíte completa fica para o pouso.

### Efeito colateral em outras passivas (pedido do coordenador)

As passivas estáticas e de gatilho **não mudam**: `combat_mechanics.learned_passives` e
`card_effects._passive_listeners` já leem `known_cards`. Só duas coisas mudam:

1. `_has_vigilia` passa a ver as 5 passivas com `buff_iniciativa` ganhas por recompensa:
   `arc_imp_remendo`, `arc_equacao_persistente`, `dev_zel_vigilia`, `cor1_tro_faro_do_abismo` e
   `san_conta_memorizada`. Isso é coerente com a SPEC-355 R17.
2. Com o baralho existente, uma passiva **deixa de entrar no `deck`**. Na `main`, a sonda mostra
   `baralho`, com a passiva dentro do deck e podendo ir para a mão. É uma melhora, coerente com
   `_DECK_TIPOS`.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `services/card_rewards.py:298-302`; `services/cards.py:422-429` (`set_prepared`); `web/src/components/tabs/CombatDeckTab.tsx:46-48,57` | A passiva é anexada a `prepared_cards` **acima do limite do nível**, mas `set_prepared` e o cabeçalho e bloqueio do Acervo continuam contando todo `prepared_cards`. Reproduzido pela API: Corruptor novo, espólio da Faro, `prepared_cards` = 5 com `slots` = 4 e `_cards_block` com 5 `prepared`. Nesse estado, `set_prepared(st, mesma_lista)` responde "Máximo 4 Cartas preparadas neste nível.", a UI mostra "Preparação 5/4" e bloqueia preparar qualquer Carta. Para reorganizar, o jogador precisa largar uma ativa, e daí em diante a passiva **ocupa** um slot, o oposto do que o §7 afirma. Acontece com o baralho `off` e também com o baralho `on` antes de existir um `deck` no herói (herói novo que compra na loja antes do 1º conflito), porque `_deck_mode_on` exige `player.deck`. | Escolher um modelo e aplicá-lo nos três pontos. **(a)** Preferido, por ser menor e já ser a regra de `learned_passives`: não mexer em `prepared_cards`. `_has_vigilia` (`agents/combat.py:1936`) passa a varrer também as passivas de `known_cards`, trocando a lista da iteração sem aumentar linhas. `_add_to_deck` e `acervo_reason` só tiram a passiva do deck e do slot (destino `acervo` sem motivo, ou um destino novo `permanente`). **(b)** Manter a passiva em `prepared_cards` e excluir `tipo == "passiva"` da contagem em `set_prepared`, no ramo sem baralho de `_add_to_deck`/`acervo_reason` e no `preparedIds.length` do `CombatDeckTab` (`isPreparable`). Em qualquer caso, adicionar um teste de regressão: nível 1 com 4 Preparadas recebe a passiva, `len` de slots ocupados ≤ limite e `set_prepared(lista atual)` passa. |
| P3-1 | P3 | `tests/test_spec346_vigilia.py:70-90` | O R3 pedia o teste "pela API real com as duas seeds do smoke", mas ele vai por `_combat_node`. O desvio está declarado no §7. | Aceitável. O smoke do §5 (itens 2a e 2b) cobre o caminho real; registrar em `docs/spec397/smoke.md`. |
| P3-2 | P3 | `services/card_piles.py:123-127` (`deactivate_deck`) | Se a passiva chega com o baralho ativo e a flag volta a `off`, `prepared_cards_pre_deck` restaura a lista antiga e a passiva sai de `prepared_cards`. A Vigília se perde. Com a correção (a), isso deixa de existir. | Resolver junto com o P1-1. Se ficar com (b), anexar as passivas conhecidas ao restaurar. |
| P3-3 | P3 | `scripts/cards/draft.py:282` | O corte descarta em silêncio as aprovadas que passam de `n`. | Opcional: contar as excedentes em `rejeitadas` (motivo "excedeu n") ou num campo `cortadas`. |

## Correções aplicadas

Nenhuma ainda (o revisor só escreve este handoff).

## Pendências

- Smoke real do §5, com o coordenador.
- R6 ainda não está marcado: suíte completa no pouso.

## Comandos rodados

```text
bash scripts/dev/pt.sh test_card_draft test_card_smoke_edges test_spec346_vigilia test_card_rewards test_card_shop test_card_shop_api test_card_quest_rewards test_card_acervo_reparo test_spec363_rewards_shop test_spec368_discard test_forge test_spec347_forge_reasons test_size_budget test_no_silent_except --basetemp=.../btR397 → 167 passed
pytest tests/test_card_smoke_edges.py com services.card_rewards da main injetado → R5 FAILED (_has_vigilia False): o teste prova o bug
sonda _add_to_deck (main x branch): deck on main=baralho (passiva no deck) / branch=preparadas; deck off main=acervo / branch=preparadas com 5/4
sonda API: Corruptor + espólio Faro → prepared 5, slots 4, set_prepared(mesma lista) = "Máximo 4 Cartas preparadas neste nível."
dup_helpers.py --diff main...HEAD → nenhuma função duplicada
ruff check (arquivos alterados) → All checks passed
wc -l agents/combat.py main/branch → 3957/3957
```

## Rodada 2

> **Veredito:** `APPROVED_WITH_FOLLOWUPS` · **Commit revisado:** `46b58705` · 2026-11-04

O commit aplica a opção (a) do P1-1. A passiva ganha por recompensa fica só em `known_cards`:
`_add_to_deck` devolve `acervo` e `acervo_reason` devolve `None`. `_has_vigilia` delega para o novo
`services/initiative_cards.has_initiative_card`.

- **P1-1 fechado.** Sonda pela API (Corruptor novo, espólio da Faro): `prepared_cards` fica 4 com
  `slots` 4, `_cards_block` marca 4 `prepared` (a UI mostra 4/4), `set_prepared(lista atual)` passa e
  a Faro não entra no `deck`. Os testes novos cobrem 4/4 com `set_prepared`, o baralho `on` sem
  `deck` e `deactivate_deck`.
- **Equivalência.** `has_initiative_card` repete o laço antigo sobre `deck` + `prepared_cards`
  (Vigília por id ou `buff_iniciativa`) e acrescenta só as passivas de `known_cards`.
  `test_spec355_emboscada`, `test_spec346_vigilia`, `test_card_acervo_reparo`, `test_spec369_regua`
  e `test_spec363_rare_scenarios` passam.
- **`agents/combat.py`** foi de 3957 para 3948 linhas.
- **P3-2 fechado.** `deactivate_deck` não tira mais o efeito: o teste cobre.
- **P3-3 fechado.** O aviso conta as aprovadas descartadas além de `n`.
- **P3-1** segue aceito como desvio declarado, coberto pelo smoke do §5.

### Follow-ups (P3, não bloqueiam)

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P3-4 | P3 | `services/initiative_cards.py:26-28` | **Mudança de regra.** Uma passiva de iniciativa **conhecida** agora anula a emboscada sem estar preparada e sem custo de slot. Antes, a decisão da SPEC-346 e o texto da R17 da SPEC-355 diziam "baralho/preparadas". Valem as 5 passivas: `dev_zel_vigilia`, `arc_imp_remendo`, `arc_equacao_persistente`, `san_conta_memorizada` e `cor1_tro_faro_do_abismo`. Isso é coerente com `learned_passives`, mas um herói que só conhece a Carta, sem prepará-la (o "Carta fora" do item 2b do smoke da 369, se lá ela continuava em `known_cards`), passa a não ser emboscado. | Registrar a regra no §6 da 397 como decisão e atualizar a frase das specs 346/355. No smoke do §5, o item 2b precisa remover a Carta também de `known_cards`. |
| P3-5 | P3 | `agents/combat.py:1926` e `services/initiative_cards.py:11` | `VIGILIA_CARD_ID` está duplicado. | `combat.py` deve importar a constante do módulo novo (sem crescer), ou deixar o comentário "espelho". |
| P3-6 | P3 | `web/src/cardRewards.ts:58` | Uma passiva recebida aparece como "só para o Acervo", mas ela já vale sem preparar, então o texto engana. | Opcional: `acervo_reason` devolve um motivo `passiva_permanente`, com o rótulo "vale sempre, sem ocupar Preparação". |

### Comandos rodados (rodada 2)

```text
bash scripts/dev/pt.sh (16 arquivos: draft, smoke_edges, 346_vigilia, 355_emboscada, acervo_reparo, 369_regua, 363_rare_scenarios, rewards, shop, shop_api, quest_rewards, 363_rewards_shop, 368_discard, 373_cartas, size_budget, no_silent_except) --basetemp=.../btR397 → 198 passed
sonda API Corruptor + espólio Faro → prepared 4, slots 4, ui prepared 4, set_prepared(mesma lista) ok
ruff check (alterados) → All checks passed · dup_helpers --diff main...HEAD → nada duplicado
wc -l agents/combat.py → 3948 (main 3957)
```
