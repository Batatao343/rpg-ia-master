# SPEC-382 — golden reforçado antes da Etapa 3 (Sol P2-1)

Base: `main` `0fdb2a85`. Atende `handoffs/SPEC-382-sol-independent-review.md` P2-1: o golden de nós
não pegava a troca de fases (`_combat_close_round_meta` × `_combat_close_round_log` passava nos 53
casos). O código de produto não foi tocado. Só mudaram `tests/` e `docs/spec382/`.

## O que mudou no oráculo

| Peça | Mudança |
|---|---|
| `tests/spec382_round_cases.py` (novo) | 13 casos: 12 diretos de `run_round` (§3.4) e 1 de nó com status. Os de `run_round` cobrem `off` com morte e fim do conflito, item recusado, Presságio `on` (cumprido, frustrado por atordoamento, 2ª rodada calculada no início), `shadow`, Provocação na mesma rodada, Provocação em quem já agiu (`taunt_frozen_acted`), chefe com ação extra e decks `on` (fases, promessas, prenúncio), chefe com 2 presságios, Interromper por atordoamento (`interrompido_por`), Interromper por queda (extra `incapaz`), Baralho `on` (várias jogadas, recusa, `end_round`) e Cartas de Cena em 3 rodadas. O caso de nó, `combat_status_cards_on`, roda com Baralho `on` e `RPG_CARD_REWARDS=on`: tem 5 rodadas resolvidas e `status_logs` não vazio (Sussurro, Dor Surda). |
| `tests/spec382_phase_spy.py` (novo) | Espião transparente de 51 colaboradores de módulo do `_run_round`: os globais do orquestrador e as funções de `scene_cards`, `enemy_decks`, `enemy_intent`, `card_effects`, `combat_mechanics`, `cards`, `card_deck_round` e `death_flow`. Grava `[nome, args leves]` em ordem, e o `out` entra como `out#<n logs>`. Como são globais consultados na hora da chamada, o espião continua valendo dentro dos helpers que a Etapa 3 extrair. |
| `Recorder(strict=True)` | Acrescenta duas partes: `calls`, a sequência de fases, e `order`, a ordem de inserção das chaves do resultado e de todo dict de rodada, que o `sort_keys` escondia. Vale para os 25 casos de combate e os 13 novos. |
| As 5 partes antigas | Não mudaram de formato. Comparei o fixture novo com `0fdb2a85` nos 53 casos antigos × 5 partes: **0 hashes mudaram**. O fixture só ganhou chaves. |

**Estabilidade:** rodei com `PYTHONHASHSEED` `0`, `1` e `random`, e também com `-n 2`: 66/66 verdes.
Na 1ª versão, `order` serializava o estado inteiro sem `sort_keys` e dependia do hash seed: o
`modifiers` nasce de `frozenset` (`conflict_scene._TACTICAL_MODIFIERS`). Por isso `order` ficou
restrito a resultado e dicts de rodada.

## Mutações de controle (cópias no scratchpad; worktree intacto)

Carreguei cada mutação com o plugin `mutplug` (`-p`, que troca o módulo em `sys.modules` antes dos
imports) e rodei os 66 casos em série. Para reproduzir, use `docs/spec382/golden-etapa3-mutants/`
(`make.py` gera as cópias, `run.sh` roda e `score.py` compara). Controles: sem plugin, 0 falhas; cópia
idêntica pelo plugin, 0 falhas.

Legenda das colunas: **Golden novo** é quantos dos 66 casos reprovam. **Golden antigo** é quantos
dos 53 casos antigos reprovam pelas 5 partes antigas, ou seja, o que o golden de `0fdb2a85` teria
visto.

| Mutação (plausível na extração) | Golden novo | Partes | Golden antigo |
|---|---|---|---|
| M1 `_stalemate_guard` antes de `advance_tactical_state` | **reprova** (33) | calls | 0 (passaria) |
| M2 fase de chefe depois do Presságio (e sem `phase_changed`) | **reprova** (33) | calls | 0 |
| M3 `inicio_rodada` dos atores depois da mecânica de classe | **reprova** (33) | calls | 0 |
| M4 pular `acted.add` (helper extraído sem o bind) | **reprova** (5) | calls, order, result, state, trace | 0 |
| M5 `_tf_acted` devolve um set novo (closure ligada ao `acted` errado) | **reprova** (1: `round_taunt_after_acted`) | calls, result, state, trace | 0 |
| M6 `_enemy_decl` ligado cedo (antes do tick e do atordoamento) | **reprova** (33) | todas | 0 |
| M7 `_spend_taunt` depois de `_note_turn_records` | **reprova** (1: `round_taunt_same_round`) | calls | 0 |
| M8 `resolve_terminals` antes de `_resolve_last_stands` | **reprova** (33) | todas | 1 |
| M9 `fim_rodada` das Cartas antes da colheita de Entropia/Abismo | **reprova** (33) | calls | 0 |
| M10 `apply_phases` de fim antes de `close_promises` | **reprova** (33) | calls | 0 |
| M11 Cartas de Cena de fim depois dos terminais | **reprova** (1: `round_scene_cards`) | calls | 0 |
| M12 ação extra sem `declare_extra` (perde o R12 da 373) | **reprova** (2) | calls | 0 |
| M13 `_deck.shadow` antes da recusa do Baralho | **reprova** (34) | calls | 0* |
| C1 (controle Sol) `_combat_close_round_log` antes de `_meta` no nó | **reprova** (1: `combat_status_cards_on`) | result, state | 0 |

São 14 de 14 mutações reprovadas. O golden antigo pegava só 1 delas (M8).

\* Numa das execuções do M13, `campaign_explorador_off.events` também divergiu, e não pela mutação:
o `_HEX_RE` só mascara hex com pelo menos 1 dígito, e um uuid saiu `deaeffdf`, só com letras. Ver os
achados.

## Achados que exigem decisão

1. **Flake raro no golden antigo (W3).** O `_HEX_RE` (`tests/spec382_node_golden.py:26`) exige um
   dígito, então um `event_id` uuid de 8 hex só com letras escapa da máscara. A chance é de ~0,04 %
   por id, e o caso `campaign_explorador_off` tem vários. Para corrigir, a regex ou a lista
   `VOLATILE` teriam de mudar, o que mexe nas partes antigas e o W3 congela. Fica para o
   coordenador decidir. Uma opção é mascarar `event_id` por chave, com o fixture regravado e a prova
   de igualdade das outras partes.
2. **Os casos de nó `*_on` antigos não resolviam nenhuma rodada.** Sem `combat_declaration`, o texto
   livre com o tabuleiro aberto é recusado. Isso explica por que o C1 passava. O
   `combat_status_cards_on` novo cobre esse caminho, e os antigos não mudaram (W3).
3. **Sensibilidade do `calls`.** A parte reprova qualquer mudança de ordem ou de argumento leve nas
   chamadas espionadas. Numa refatoração pura isso é o esperado. Se a Etapa 3 precisar trocar um
   colaborador de propósito, por exemplo chamar um global por outro caminho, é desvio de spec, e não
   regravação do golden.
