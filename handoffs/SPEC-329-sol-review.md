# SPEC-329 — revisão sol (review)

> **Veredito:** `APPROVED` (re-revisão de `35810655`; a 1ª rodada, sobre `2000cbe5`, foi `CHANGES_REQUIRED`)
> **Revisor:** Sol (Opus) · **Data:** 2026-10-27 · **Commit revisado:** `2000cbe5` → `35810655`

## Escopo

Branch `spec-329`, diff `main...2000cbe5`: `services/enemy_intent.py` (novo),
`data/combat/pressagio_sinais.json` (novo), `services/conflict_orchestrator.py` (`run_round`),
`agents/combat.py` (congelar o presságio no fim da rodada), `api.py` (`_combat_block`),
`tests/test_enemy_intent.py` e §5/§5.1 da spec. Não revisei: o texto do catálogo de sinais
(é do dono) nem a medição da arena (não reproduzi o `shadow` de 11,7 %).

Pontos que o coordenador pediu para olhar:

- **(b) `off` igual ao anterior, byte a byte: OK.** Com `off`, `frozen` fica `None` e
  `_enemy_decl` chama `enemy_declaration` com os mesmos argumentos de antes. Os ramos de
  frustração exigem `intent_mode == "on"`, o nó só passa `pressagios` quando `active()`, e a
  API só mostra `pressagios_publicos` com `active()`. O único efeito novo no nó é
  `combat_meta.pop("pressagios"/"pressagios_publicos")`, que não faz nada se as chaves não
  existem. O `import` local de `enemy_intent` não tem efeito colateral. O teste
  `test_off_keeps_old_behavior_without_new_keys` cobre isso, e
  `test_shadow_measures_without_changing_outcome` confirma que `shadow` produz os mesmos logs
  e o mesmo HP que `off`.
- **(c) Determinismo e efeito colateral: parcial.** O rng bifurcado (`_fork_rng`, estado
  copiado) não consome o rng principal (testado). A ficha do próprio inimigo é copiada, inclusive
  `enemy_card_usage` com deepcopy, e `_forced_attack`/`surrendered` não vazam (testado). **Mas**
  `_taunt_target` muta o ator que **provocou**, que não está no sandbox (ver P1-2).
- **(d) Save de combate em curso sem `pressagios`: OK no orquestrador.** Com `on` e
  `pressagios=None`, `run_round` calcula o presságio no início da rodada e o executa
  (`test_on_without_saved_pressagios_computes_at_round_start`). Se a flag mudar de `on` para
  `off`/`shadow`, o nó remove as chaves antigas. O conteúdo é JSON-safe: `TurnDeclaration`
  só tem str/None/dict. Falta o round-trip pelo nó/persistência (P1-1).
- **(a) 1ª rodada sem presságio visível: não bloqueia, mas a spec precisa registrar isso.** O
  encontro é criado e a 1ª rodada é resolvida **no mesmo request** do nó de combate
  (`agents/combat.py:1667` → `run_round`). Pela arquitetura atual, não existe um momento
  "antes da escolha" na rodada 1, a não ser que se crie uma pausa pré-rodada (o que muda o
  fluxo do jogo). Hoje a rodada 1 em `on` decide no início da rodada, sem o jogador ver,
  como antes. Isso não piora nada em relação ao `off`, mas contraria a letra do R1 ("cada
  rodada"). Ver P2-1.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/combat.py:2128-2139`, `api.py:2897` | Esta mudança cria um **writer persistente novo**, `combat["pressagios"]`/`pressagios_publicos` no save, e nenhum teste passa pelo nó de combate ou pela persistência. Os 16 testes chamam só `forecast_round`/`run_round` direto. Ficam sem cobertura: (i) o nó grava o presságio no fim da rodada N e o **lê** na rodada N+1 (o caminho real do `on`); (ii) save→load (`persistence`) preserva o presságio e a rodada seguinte executa o mesmo; (iii) `_combat_block` expõe `pressagios_publicos` só com `on` e nunca `declaration`/`carta_id`; (iv) as chaves somem quando o combate termina. A regra do AGENTS.md ("round-trip save/load") não está cumprida. | Adicionar 1–2 testes de integração com MockLLM e `RPG_ENEMY_INTENT=on`: duas chamadas de `combat_node` com o state serializado/desserializado entre elas (`save_game_state`/`load_game_state` ou o serializer de persistência), conferindo `pressagios_cumpridos` na 2ª rodada e o bloco da API; e um teste com `off` provando que o `combat` persistido não ganha chaves novas. |
| P1-2 | P1 | `services/enemy_intent.py:176-184` × `services/conflict_orchestrator.py:296-305` | A previsão **tem efeito colateral** quando o inimigo está provocado. `_taunt_target` faz `source.setdefault("_last_class_mechanics", []).append({"kind": "special:taunt", ...})` no ator que provocou (o jogador ou um aliado), e esse ator vem de `actors_by_id` real, não do sandbox. No nó, a previsão roda **depois** de `run_round`. Como `player["_last_class_mechanics"]` é a mesma lista que `out["class_mechanics"]` (orchestrator:2072), o registro de mecânica de classe ganha uma entrada `special:taunt` falsa por rodada, e o playtest a lê (`playtest/runner.py:1637`). Isso contradiz a docstring ("sem efeito colateral") e o teste `test_forecast_has_no_side_effects`, que não cobre provocação. | No `forecast_round`, rodar `enemy_declaration` sobre um sandbox com uma cópia rasa de **todos** os atores (ou ao menos de quem tem `_last_class_mechanics`), ou fazer `_taunt_target` aceitar a opção de não registrar. Acrescentar um caso de provocação (`control: "taunt"`, `source_actor_id: "player"`) ao teste de efeito colateral. |
| P2-1 | P2 | spec §2 R1 / §5.1 (d) | O R1 diz "início de cada rodada, antes da escolha", mas a rodada 1 não tem presságio visível. A causa é estrutural (spawn e rodada 1 no mesmo request), não um esquecimento. O desvio está registrado só no §5.1. | Corrigir o texto do R1 ("a partir da 2ª rodada; na 1ª o presságio é calculado no início e executado, sem exibição") ou abrir um follow-up [D?] para o dono escolher entre uma pausa pré-rodada no spawn e aceitar a limitação. Não bloqueia o pouso com a flag `off`. |
| P2-2 | P2 | spec §5.1 / `services/conflict_orchestrator.py:1996-2004` | A calibração do `shadow` (11,7 %) compara uma previsão **do início da rodada** com a decisão tardia. Com `on` em produção, o presságio é congelado **no fim da rodada anterior** (nó, `combat.py:2133`). Por isso a medição deixa de fora o que acontece entre as duas: impasse/`_forced_attack`, ticks de DoT, inimigos novos que chegam pelo `reconcile_roster`, mudança de ficha fora do combate. A taxa real de "mudaria" com `on` pode ser maior. | Antes de passar para `on`, medir o `shadow` na arena com o mesmo momento de congelamento do `on` (fim da rodada anterior), ou registrar na spec que 11,7 % é um piso. |
| P2-3 | P2 | `services/conflict_orchestrator.py:2044-2047`, `agents/combat.py:1965` | R8: a narração recebe os presságios **frustrados**, como linha em `out["logs"]`, mas não recebe os **cumpridos**: `pressagios_cumpridos` fica no `out` e o nó não o usa. A narração do ataque acontece mesmo assim, mas a frase "presságio cumprido" não chega ao narrador. O §5 marca R1–R9 como `[x]` mesmo assim. | Passar os cumpridos ao contexto do narrador, por exemplo uma linha curta no log ("o presságio se cumpre"), ou desmarcar o R8 na spec e mandar para a SPEC-334. |
| P2-4 | P2 | `services/enemy_intent.py:301-324` | `still_possible` não verifica alcance (desvio §5.1 a). R5 cobre `atordoar`, mas `empurrao` não tem gancho (desvio §5.1 b). Os dois estão registrados. | Follow-up na SPEC-330 (keyword "Interromper"), que já é o gancho previsto. |
| P2-5 | P2 | `services/conflict_orchestrator.py:2147-2151` | Quando o jogador mata um inimigo antes do turno dele, o presságio desse inimigo é frustrado com motivo `incapaz` e a linha "O golpe de X morreu no ar." vai para o log do inimigo morto. Isso faz sentido (é o smoke §6.3), mas não há teste, e a linha aparece **depois** da linha de morte na mesma rodada. | Teste com o inimigo morto no meio da rodada, conferindo o motivo `incapaz` e a ordem das linhas. |

O que conferi e está correto: os valores do LLM não entram aqui (é tudo determinístico, sem
structured output, e o catálogo é estático). As chaves `{nome}`/`{alvo}` são as únicas usadas
no catálogo, então `format` não quebra. O `_forced_attack` (impasse da SPEC-275) cai na
decisão tardia, o que está certo. Se aparece um inimigo sem presságio congelado, ele decide
na hora (`_next_intent` devolve `None` e cai na decisão tardia). Em R7, o cursor por ator
consome o `idx` 0 na ação principal e o 1 em "age de novo". Nada em `evals/` foi alterado e
não há segredo em log. A falha da previsão no nó é capturada e só gera um warning (é
cosmética). A flag fica fora de `combat_flags.CAPS`, de propósito (§5.1).

## Correções aplicadas

P1-1 testes de nó+save/load+API em `tests/test_enemy_intent_node.py` (on e off); P1-2 sandbox raso de todos os atores + teste de provocação; P2-3 log de presságio cumprido; P2-5 teste `incapaz` com ordem das linhas; P2-1 R1 reescrito; P2-2/P2-4 follow-up na §5.1.

## Pendências

- Critério da arena com `on` (dano recebido cai, vitórias entre 40 e 80 %) continua aberto.
  A spec não pode ir para `done` antes disso, mesmo depois que P1-1 e P1-2 forem corrigidos.
- P2-1 (rodada 1) precisa de uma decisão do dono ou de um ajuste no texto do R1. P2-4 vai
  para a SPEC-330.
- Revisão do dono do catálogo `data/combat/pressagio_sinais.json` (§3 [D?]).

## Comandos rodados

```text
git diff main...HEAD --stat → 7 arquivos, +919/-9
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_enemy_intent.py tests/test_spec275_stalemate.py tests/test_tactical_archetypes_runtime.py → 56 passed
```

## Re-revisão (Sol, 2026-10-27, commit `35810655`)

**Veredito: `APPROVED`.** Revisei só o delta `2000cbe5..35810655`.

| ID | Status | Evidência |
|---|---|---|
| P1-1 | resolvido | Novo `tests/test_enemy_intent_node.py`. O teste `test_on_roundtrip_through_node_and_save` passa pelo `combat_node` real com save/load de verdade entre as rodadas (`_reload` usa `persistence._state_to_save_data` → JSON → `_raw_to_state`). Ele confere que a rodada N+1 recebe exatamente o `combat.pressagios` congelado e salvo, que a execução gera cumprido ou frustrado, que a visão pública não tem `declaration`/`carta_id`, e que `_combat_block` só mostra `pressagios_publicos` com a flag `on`. `test_off_save_has_no_new_keys` cobre o `off` no save. |
| P1-2 | resolvido | `services/enemy_intent.py:177-182` agora faz uma cópia rasa de **todos** os atores e copia a lista `_last_class_mechanics`. Como a provocação usa `setdefault`/`append`, tudo cai no sandbox. `test_forecast_taunt_does_not_touch_the_taunter` roda 12 seeds (com e sem o sorteio de provocação) e confere que `actors` fica igual por comparação profunda. |
| P2-3 | resolvido | `services/conflict_orchestrator.py:2048`: o presságio cumprido gera uma linha em `out["logs"]`, que chega ao narrador (`agents/combat.py:1965`). Só acontece no modo `on`. |
| P2-5 | resolvido | `test_frustrated_incapaz_when_enemy_dies_mid_round`: o motivo é `incapaz`, a frustração é do ator morto e a linha de frustração vem depois de "B é derrotado.". |
| P2-1 (R1) | resolvido no texto | O R1 agora diz "a partir da 2ª rodada" e explica por quê (o spawn e a 1ª rodada acontecem no mesmo request). A pausa antes da 1ª rodada foi mandada para a SPEC-328/334. O §5.1 (d) está consistente com isso. |
| P2-2, P2-4 | registrados como follow-up | O §5.1 registra que 11,7 % é um piso e manda alcance e `empurrao` para a SPEC-330. |

Pontos que continuam valendo (nenhum bloqueia o pouso com a flag em `off`):

- A spec segue sem `done`, porque o critério da arena com `on` está aberto.
- Antes de ligar `on`, é preciso medir o `shadow` com a previsão congelada no fim da rodada anterior (P2-2).
- O dono ainda precisa revisar o catálogo de sinais.

```text
bash scripts/dev/py.sh -m pytest -p no:cacheprovider -n 2 tests/test_enemy_intent.py tests/test_enemy_intent_node.py tests/test_spec275_stalemate.py tests/test_tactical_archetypes_runtime.py tests/test_encounter_lifecycle_reload.py → 70 passed
```
