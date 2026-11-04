# SPEC-382 — revisão sol (independent-review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 / papel Sol (spec-reviewer) · **Data:** 2026-11-04 · **Commit revisado:** `7c880a02` (branch `spec-382`, base `3cd58353`, 55 commits)

## Escopo

Revisei as Etapas 1 (golden), 2 (`storyteller_node`) e 4 (`_combat_node`): `agents/storyteller.py`,
`agents/combat.py`, `tests/spec382_node_*.py`, `tests/test_spec382_node_golden.py`, o fixture,
`tests/size_budget.json` e o "Registro de execução" da spec (desvios 1–8).
Ficou fora: a Etapa 3 (`_run_round`, não feita por causa do W1/`spec-373`), a Etapa 5 (W2 A/B de
evals/playtest, smoke §6, `docs/spec382/equivalence.md`), que são do coordenador, e a
verificação do golden commit a commit (conferi só o HEAD e a base).

### Prova estática de equivalência (o que sustenta o veredito)

O golden não executa parte das linhas (desvio 5). Por isso não fiquei só nele e fiz três verificações
por AST, com scripts one-shot no scratchpad:

1. **Re-inline:** reconstruí o nó substituindo cada chamada `_story_*(t)`/`_combat_*(t)` pelo corpo
   do helper, troquei `t.x` por `x` e `_fm_view(t)` por `_fm_view()`, e desconsiderei imports,
   docstrings e anotações. Depois comparei o `ast.unparse` com o nó da base `3cd58353`.
   **O diff é vazio nos dois nós**, com três exceções esperadas: (a) o envelope
   `_early = …; if _early is not None: return _early` das 3 recusas antecipadas, em que o helper
   termina em `return None` fora do `if`, como no fluxo antigo; (b) as closures `_fm_view`/`_fm_apply`,
   que agora são funções de módulo com corpo idêntico (`t.factions = value` no lugar do `nonlocal`);
   (c) os aliases do desvio 3. Com isso ficam provados, também nas linhas que o golden não cobre
   (fauna, `rumor_adoption.commit`, abandono, `death_pending` no deck on, `manifest_from_legacy`,
   `expire_pending`/`grant_after_conflict` etc.): a ordem dos efeitos, o aninhamento, a cobertura
   de cada `try/except` (R6: o `try` principal do storyteller envolve só os 8 helpers do caminho feliz,
   e o `except` só tem o `_log_event` e o `return _story_exception_fallback(t)`) e a ausência de `finally` novo.
2. **Escopo (symtable):** nenhum helper lê como global, nem deixa indefinido, um nome que era local do
   nó antigo (só `_fm_*`, que agora são de módulo de propósito). Os locais que se repetem entre
   helpers (`_saber_logs`, `killer`, `card_piles`, `em`, `_lq`, `exc`…) são imports, variáveis de laço
   ou temporários atribuídos antes do uso em cada helper, sem risco de `UnboundLocalError`.
3. **Campos × locais:** em nenhum helper novo um campo de `_StoryTurn`/`_CombatTurn` é rebindado
   como local. Nenhum campo é lido sem nunca ter sido escrito, e nenhum é declarado sem uso. Os únicos
   aliases são `combat.py:3350` e `combat.py:3438`: são snapshots só de leitura e o campo não é
   rebindado depois deles dentro do helper.

Não há `nonlocal` em `storyteller.py`. Nenhum nome de módulo foi removido ou renomeado (R7), e nenhuma
função pré-existente mudou de corpo, nem `_advance_reinforcements`/`_plan_reinforcements` (D7). Os
únicos imports novos no topo são `dataclass`/`Any` (R8). `evals/`, `services/` e `playtest/` não
foram tocados.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `tests/spec382_node_golden.py:55`, `agents/combat.py:2440` | **O golden é menos sensível do que a spec supõe.** Fiz duas mutações em cópias no scratchpad: trocar a ordem de `_combat_close_round_meta(t)` e `_combat_close_round_log(t)` **passou nos 53 casos**, embora `meta` acrescente linhas a `status_logs` antes de `log` normalizá-las e gravar o `mech_log`. Tirar `_story_world_pulse(t)` (`storyteller.py:1404`) só foi pego por 1 caso (`campaign_explorador_off`). Além disso, `sort_keys=True` esconde a ordem de inserção das chaves, e `_HEX_RE` (l.26) também mascara strings só com dígitos de 8 ou mais caracteres. Nesta série a equivalência fica provada pela verificação estática acima. Para a Etapa 3 o oráculo precisa ser mais forte. | Antes da Etapa 3, junto com os ≥ 6 casos de `run_round` que já estão previstos: um caso com deck `on` e `card_status` ativo, com `status_logs` não vazio no fim da rodada; e uma mutação de controle (trocar duas fases) que tem de falhar. O fixture não muda, os casos novos entram como golden novo. Registrar este resultado no `SPEC-382-equivalence.md`. |
| P3-1 | P3 | `agents/combat.py:3350`, `agents/combat.py:3438` | Desvio 3: os aliases `is_simulation = t.is_simulation` e `combat_over, is_simulation = …` existem só para satisfazer o literal de `tests/test_spec371_saber.py:214-216`. Não mudam o comportamento, porque o campo não é rebindado depois do alias. **Aceitável** sob o W3. | Follow-up fora desta spec: trocar o `getsource` da 371 por um teste de comportamento e depois tirar os aliases. |
| P3-2 | P3 | `storyteller.py:2520` (93 l.), `combat.py:3381` (92 l.), `combat.py:2535` (89 l.) e outros 17 helpers entre 61 e 85 l. | Ficam acima das 60 linhas por função nova do AGENTS.md, mas dentro do R1 da spec (≤ 220) e do teto de 100 que o executor adotou. Exceção consciente da spec, não é bloqueio. | Nenhuma nesta spec. O follow-up "nós em pacote" pode fatiar mais. |
| P3-3 | P3 | `combat.py:2452-2458`, `2506-2512`, `3014-3023` | O bloco `party_mod.backfill_party` + `enemy_refs` + `scene_tr` aparece 3 vezes. O re-inline mostra que a duplicação **já existia** no corpo antigo, então não foi introduzida aqui. | Follow-up de limpeza (outra spec; muda o caminho e precisa de oráculo próprio). |
| P3-4 | P3 | `storyteller.py:1254-1286`, `combat.py:2251-2320` | Com os campos default `None`, um caminho que antes levantaria `UnboundLocalError` agora leria `None`. Conferi que `_story_exception_fallback` só lê campos atribuídos antes do `try` e que `chase_state`/`decl` só são lidos sob a mesma condição que os define. Não há mudança nos caminhos que funcionam. | Nenhuma. Fica registrado como risco residual. |

Sem P0/P1. Não há structured output novo: o guard `isinstance(update, StoryUpdate)` continua idêntico em
`_story_narrate`. Não há writer persistente novo, segredo em log nem `except` novo (o re-inline mostra
os mesmos handlers). O `dup_helpers` só acusa `_stream_view`, que é uma closure já existente movida
junto com o trecho. O `ruff check` e o `ruff format --check` passam nos 5 arquivos.

### Perguntas do coordenador

1. Equivalência nas linhas não cobertas: provada pelo re-inline por AST, com diff vazio. Não há early
   return perdido: todo `return` interno de helper é propagado pelo orquestrador (`_early`,
   `return _story_combat_start(t)`, `return _combat_no_active_result(t)`). Não há aliasing, `nonlocal`
   residual nem mudança de escopo de exceção.
2. O fixture só aparece em `21075595` (`git log -- tests/fixtures/spec382_node_golden.json`), e
   `89672f3b` mexe só no harness. Rodei o golden **no código da base** (`agents/` de `3cd58353`
   carregado à frente no `sys.path`): 53/53 verdes. No HEAD também passa (57 com o `size_budget`).
3. W3: `git diff 3cd58353...HEAD -- tests/` só remove 4 linhas, todas em `size_budget.json`. Nenhuma
   asserção mudou. O desvio 3 é aceitável (P3-1).
4. `_advance_reinforcements`/`_plan_reinforcements` têm o corpo idêntico ao da base. O `size_budget`
   tem só as 4 linhas: 2 arquivos sobem (+226/+295, inevitável pelo R2) e 2 funções descem
   (1037→125, 1553→118).

## Correções aplicadas

Nenhuma. A revisão é só leitura.

## Pendências

- P2-1: reforçar o golden antes da Etapa 3 (executor da Etapa 3, SPEC-382).
- Etapa 3 (`_run_round`) depois da `spec-373`. Etapa 5: W2 A/B, `SPEC-382-equivalence.md`, smoke §6
  e suíte completa (coordenador). A spec continua `in-progress`, corretamente.
- P3-1/P3-3: follow-ups em spec própria.

## Comandos rodados

```text
git log -- tests/fixtures/spec382_node_golden.json → só 21075595
AST re-inline (scratchpad/inline.py) storyteller_node e _combat_node vs 3cd58353 → diff vazio salvo envelopes _early, _fm_*, aliases do desvio 3
symtable (scratchpad/scope.py) + campos×locais (scratchpad/alias.py) → sem shadowing, indefinido nem alias mutável
pt.sh -n 0 tests/test_spec382_node_golden.py tests/test_size_budget.py → 57 passed
golden com agents/ da base 3cd58353 → 53 passed
mutante (swap close_round_meta/log) → 53 passed (não detectado: P2-1); mutante (sem _story_world_pulse) → 1 failed
pt.sh -n 0 test_spec371_saber, 297_review_fixes, 304_review, 303_passes, 298_faccao_eventos, 361_integracao, stream_structured, mediation_secret, combat_lifecycle, 346_mech_log → 226 passed
pt.sh -n 0 fase26, fase33, grounding_boundaries, npc_two_phase, spec301_*, 311_*, 315_*, 360_*, streaming, 325_*, 363_*, encounter_manifest → 1264 passed, 1 skipped
dup_helpers --diff 3cd58353...HEAD → só _stream_view (closure pré-existente movida)
ruff check / format --check (5 arquivos) → ok
```
