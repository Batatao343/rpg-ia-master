# SPEC-372 — revisão sol (review)

> Nome do arquivo: `handoffs/SPEC-372-sol-review.md`.
> **Veredito:** `APPROVED_WITH_FOLLOWUPS` (rodada 2; rodada 1 em `3a92ece8` foi `CHANGES_REQUIRED`)
> **Revisor:** Opus (`claude-opus-5-5`, `spec-reviewer`, papel Sol técnico) · **Data:** 2026-11-03 · **Commit revisado:** `6ceaec6e` (rodada 1: `3a92ece8`)

## Escopo

`git diff main...spec-372` (commits `d72bbff7`, `5f5ccaa7`, `1306681c`, `bfa7d2d8`, `3a92ece8`):
`services/plot_threads.py` (estágio derivado), `services/fauna_tramas.py` (portão, puxão, nascimento,
rumor), `services/fauna_lint_tramas.py` (forma + E19–E22), ganchos em `services/fauna.py`,
`world_utils.py`, `agents/storyteller.py`, `services/rumors.py`, `config/flags.yaml`,
`data/world/fauna_config.json`, `playtest/invariants.py`, `scripts/fauna/build.py` e os testes
`tests/test_spec372_*`. Integridade de eval: `git diff d72bbff7..HEAD -- scripts/fauna/eval_tramas.py
tests/test_spec372_eval.py evals/` vazio. As ligações em si estão em `SPEC-372-independent-review.md`.

## O que confere

- **Flag `off` byte-idêntica.** `fauna_tramas.factor/apply_gate/open_pool/birth/rumor_adjust` saem
  cedo com `mode() != "on"` ou sem estágios; `stages_for` devolve `None` e `region_stages` `{}`; o
  `day_hook` não consome sorteio novo; `trama_id` só é escrito com a flag `on`. Golden da 360
  (`test_spec360_flags_off`) e T7 (relatório de NA da 360 igual a `docs/spec360/eval-nova_arcadia.md`)
  verdes.
- **Requisitos da flag (R12/D9).** `mode()` devolve `off` sem `RPG_FAUNA=on` ou `RPG_PLOT_THREADS=on`,
  com `log_event` uma vez por processo (`fauna_tramas.py:21-33`); testado em `test_spec372_flags_off`.
- **Portão no fallback legado e nos migrantes (R8).** `apply_gate` roda por último em
  `_weighted_pool` (`world_utils.py:1178-1181`), depois do `if sum(eco_weights) > 0` e do migrante; o
  ramo legado sem `bestiary_knowledge`/`projection` usa `open_pool` (`world_utils.py:986-991`) quando
  recebe estágios. Round-robin por turno continua determinístico sobre o pool filtrado.
- **Determinismo.** Nenhum `random` novo; `plot_stages` não muta (teste `test_plot_stage_nao_muta_estado`
  e conferido em save real); `reached` preserva a ordem do autor, então `trama:<id>` é estável.
- **`plot_stage` contra save real.** Save `fd3082fd…` (sem rumor/quest): 7 tramas `dormente`, estado
  intacto (dump JSON igual antes/depois). Mutando a cópia: rumor da trama percebido + quest
  `investigar_rumor` `active` → `investigada`; a mesma quest `failed` → `tocada` (R2); evento
  `secret_revealed` com `target_id: npc_valerius` → `revelada` (via `SECRET_ENTITY_IDS` →
  `pacto_valerius`).
- **Save/load de `trama_id`.** `persistence.load_game_state` passa por `normalize_fauna_sim`, que
  preserva `trama_id` (`fauna.py:197-198`); conferido com um round-trip `save_game_state` →
  `load_game_state` (teste temporário, removido). Save antigo sem a chave carrega igual.
- **Telemetria** só com ids (`creature`, `thread`, `stage`); sem texto, segredo ou nome de NPC.
- **Sem LLM novo**, sem `with_structured_output` novo; guard de FallbackLLM não se aplica.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `agents/storyteller.py:1780`, `world_utils.py:1909`, `world_utils.py:1474-1482` | **O tipo `track` não tem portão (R7 o exige; T1 só mede o caminho do avaliador).** Em jogo, o rastro chama `resolve_track` → `pick_encounter_enemy(loc, danger, turn, theme=…)` sem `trama_stages`, no ramo legado `pool[turn % len]`. Sonda com as 4 flags `on` e todas as tramas dormentes: as **8** criaturas ligadas saem desse sorteio em `na_anel_lama/ferro/dourado`. Depois, `_fauna.track_signal` (`fauna.py:645`) grava `bestiary_knowledge` (registro de rumor) e **cria presença** da criatura escondida no local atual, sem `trama_id` e fora de R10; essa presença passa a decidir o próximo encontro via `ptheme`/`_presence_entry` (`world_utils.py:1321`, `:1396`, `:1474`), que devolve a criatura da presença sem olhar o portão. Ou seja: o rastro reabre o combate com a criatura que o portão escondeu. | `resolve_track(..., trama_stages=None)` repassa a `pick_encounter_enemy`; o storyteller passa `_fauna.fauna_tramas.stages_for(state, world)` (o mesmo valor do `check_encounter`). Defesa em profundidade: `_presence_entry` e o cálculo de `ptheme` ignoram presença cuja criatura tem `gate_closed`. Teste `test_track_respeita_portao` de verdade, chamando `resolve_track` (o `test_open_pool_respeita_portao` atual só testa o helper). |
| P2-1 | P2 | `encounter_budget.py:151`, `services/rumor_adoption.py:632` | Outros sorteios sem portão: o reforço "atraído pelo tumulto" (ramo legado) e o encontro de rumor adotado de tipo ≠ `criatura_avistada`. A §9 registra como fora de escopo, mas R7 fala em "sorteio de encontro" sem exceção. Impacto menor (reforço no meio do combate; rumor adotado). | Follow-up: os dois recebem `trama_stages` (o `state` está à mão em ambos), ou registrar a exceção em R7. |
| P2-2 | P2 | `services/plot_threads.py:470` | `revelada` é inalcançável para 6 das 7 tramas de NA: `accepted_secret_ids` só converte `target_id` em segredo pelos 4 ids de `SECRET_ENTITY_IDS`; `corpos`, `praga`, `aco_lembra`, `barril`, `elaryin` nunca aparecem. Sem efeito hoje (nenhuma ligação usa `desde: revelada`), mas R1/T8 prometem o estágio. | Follow-up: mapear esses segredos em `SECRET_ENTITY_IDS` (ou derivar dos `segredo_doc_id` do catálogo da 350), ou documentar em R1 que `revelada` só vale para segredos com entidade. |
| P2-3 | P2 | `services/plot_threads.py:464` | `knowledge_source == "met"` como alternativa a `known_by_player` é frágil: `npc_layers.ensure_npc_fields` põe `knowledge_source="met"` por default e `reputation.py:1043-1044` cria o lojista com `known_by_player=False` depois disso. Nenhuma âncora de porta de NA é lojista hoje, então sem efeito. | Usar `known_by_player is True` como critério (é o que todo o resto do jogo usa, `npc_world.py:303`), ou `met` **e** `known_by_player` não-falso. |
| P2-4 | P2 | `services/rumors.py:253-258` | Com o `avistamento` dormente zerado, `own_avist` cai e a massa dos avistamentos falsos de região vizinha muda (quando `own_avist` chega a 0 o alvo vira `len(adj)`). Comportamento coerente com D7, mas não documentado e sem teste. | Registrar na §9 ou cobrir em `test_spec372_rumor`. |
| P2-5 | P2 | spec §R15/§R16/§Etapa 5/§R14 | Evidências declaradas ausentes no HEAD: `docs/spec372/eval-tramas-nova_arcadia.md` (relatório) não existe; playtest `explorador` 50 turnos com as 4 flags (R16) não registrado; teste de contagem de `invoke` `on`×`off` numa campanha MockLLM (Etapa 5, `test_spec372_flags_off`) não existe; `trama_puxao` fora da telemetria (desvio registrado, sem decisão do coordenador); round-trip de save com `trama_id` sem teste versionado. Bloqueiam o `done`, não esta revisão. | Executor: publicar o relatório, rodar o playtest e registrar na §9, acrescentar os dois testes; coordenador decide sobre `trama_puxao`. |
| P2-6 | P2 | `services/fauna.py:519` | `chosen` começa em `cands[-1]`; se o acúmulo em ponto flutuante não passar de `pick*total`, a última candidata é escolhida mesmo com peso 0 (inclusive uma atrás do portão; `birth` então devolve `([], "")` e o dia é pulado, ou, se não for ligada, nasce). Pré-existente e raríssimo. | Escolher a última candidata com peso > 0. |
| P2-7 | P2 | `services/fauna.py`, `services/fauna_lint.py`, `world_utils.py`, `data/world/fauna.json`, `evals/protected-paths.txt` | **Conflito com a SPEC-370:** `git merge-tree HEAD spec-370` acusa conflito de conteúdo nesses 5 arquivos (`day_hook` e `_add_presence` em `fauna.py`, `_e1_entry` em `fauna_lint.py`, bloco do migrante em `_weighted_pool`). Semântico: a 370 cria `PRESENCAS_POR_NO` no `day_hook`, que se combina com o recorte de locais da trama (R10) e pode deixar `locais` vazio mais vezes; a 370 regenera `docs/spec360/eval-nova_arcadia.md`, que é o baseline do T7. | Quem pousar depois: rebase, resolver à mão o código, `build.py` para `fauna.json` (nunca à mão), união em `protected-paths.txt`, e **rodar de novo** `eval_tramas.py` (T2/T3/T4 mudam com a 370) e o T7 contra o baseline novo. |

## Correções aplicadas

Nenhuma (revisão).

## Pendências

- P1-1 antes do pouso (executor Terra), com reteste do T1 e do playtest.
- P2-1, P2-2, P2-3: follow-up técnico (pode ir na onda 2 de tramas).
- P2-5: fecha os critérios de aceite da spec.
- P2-7: ordem de pouso 370/372 decidida pelo coordenador.

## Comandos rodados

```text
git diff d72bbff7..HEAD -- scripts/fauna/eval_tramas.py tests/test_spec372_eval.py evals/ → vazio (avaliador intocado)
pytest -n 2 tests/test_spec372_*.py test_spec360_* test_spec350_* test_spec351_* test_flag_registry.py test_spec371_flags_off.py → verde (1 skip)
py.sh -c "pick_encounter_enemy(node, d, turn) sem trama_stages, 4 flags on" → as 8 ligadas sorteadas nos 3 anéis (P1-1)
py.sh -c "plot_stages no save fd3082fd + mutações" → dormente; active→investigada; failed→tocada; secret npc_valerius→revelada
pytest (teste temporário) save_game_state/load_game_state com trama_id → PASSED (arquivo removido)
git merge-tree --write-tree --name-only HEAD spec-370 → conflito em 5 arquivos
scripts/dev/dup_helpers.py / size_budget.py → não existem neste worktree (não rodados)
```

## Rodada 2 (`16956de5`, `6ceaec6e`, sem rebase sobre a 370)

**P1-1 fechado.** O rastro em jogo agora passa pelo portão. O storyteller passa
`stages_for(state, world)` para `resolve_track` (`agents/storyteller.py:1787`), que repassa os
estágios a `pick_encounter_enemy` (`world_utils.py:1918-1920`). No ramo legado, `open_pool` tira do
pool quem está atrás do portão. `_fauna_presence` (`world_utils.py:1464-1479`) devolve `None` quando
a presença é de criatura com `gate_closed`, então `ptheme`, `_presence_entry` e `_fauna_encounter`
deixam de usá-la. `test_track_respeita_portao` chama `resolve_track` com estágios dormentes e
confere que o `bestiary_knowledge` não registra a criatura. A asserção vale porque `record_rumor`
grava em `bk[creature_id]`. `test_presenca_atras_do_portao_nao_decide_encontro` cobre a presença.

**Todos os chamadores de `pick_encounter_enemy`:**

| Chamador | Portão |
|---|---|
| `check_encounter`, ramos de ameaça e regional (`world_utils.py:1402`, `:1438`) | sim (rodada 1) |
| `resolve_track` (`:1918`) | sim (rodada 2) |
| `encounter_budget.fill_encounter` (`encounter_budget.py:158`, via `agents/combat.py:973`) | sim (rodada 2) |
| `rumor_adoption.encounter_hint` (`services/rumor_adoption.py:633`) | sim (rodada 2). `criatura_avistada` usa a entidade da semente, que antes do estágio tem peso 0 (R11) |
| `check_encounter`, ramo de facção dominante (`world_utils.py:1357`) | **não**, ver P2-8 |

**Com a flag `off`, os caminhos novos não mudam nada.**
- `stages_for` devolve `None`. Nesse caso `fill_encounter` nem passa o kwarg (`6ceaec6e`), e a
  chamada fica idêntica à anterior.
- `_weighted_pool` só aplica o portão com estágios não vazios. A troca de `fauna_on and
  trama_stages` por `trama_stages` só pesa com a flag `on`: é o que leva o portão ao sorteio sem
  fauna do `rumor_adoption`.
- `_fauna_presence` e `log_pull` saem cedo quando não há estágios.
- O `import fauna_tramas` que subiu em `pick_encounter_enemy` não tem efeito colateral.
- Única mudança fora da flag: no `day_hook`, a candidata padrão passou de `cands[-1]` para a
  última com peso > 0 (`services/fauna.py:519`). Isso só muda o resultado no caso de borda de
  ponto flutuante em que a regra antiga escolheria uma candidata de peso 0. O golden da 360 e o T7
  seguem idênticos.

**P2 da rodada 1:**
- P2-1: fechado.
- P2-2: follow-up registrado na §9.
- P2-3: fechado. `known is not False` exclui o lojista e mantém o `met` que o T8 congelado exige.
- P2-4: documentado na §9 (D7).
- P2-5: fechado. Saíram o relatório `docs/spec372/eval-tramas-nova_arcadia.md`, o playtest
  registrado na §9 e os testes de `invoke` `on`×`off`, `trama_puxao` e save/load com `trama_id`.
  O teste de save/load faz `normalize_fauna_sim` + JSON, que é o que `load_game_state` executa. O
  round-trip pela `persistence` já foi conferido na rodada 1.
- P2-6: fechado.
- P2-7: o conflito com a 370 continua, para o pouso.

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-8 | P2 | `world_utils.py:1357` | O ramo de facção dominante chama `pick_encounter_enemy(faction_id=…)` sem `trama_stages`. Facção sem combatente curado cai no pool regional sem portão; hoje só `poder_kahen` (Brekmar) está nesse caso. Sondei 19 facções × 3 anéis: com `poder_kahen`, as 8 criaturas ligadas saem. Só acontece em jogo se essa facção dominar um nó de NA, o que é improvável. | Passar `trama_stages=trama_stages` também nesta chamada (uma linha). |
| P2-9 | P2 | `tests/test_spec372_motor.py:307` | `test_encounter_budget_e_rumor_respeitam_portao` só exercita `fill_encounter`; `rumor_adoption.encounter_hint` com portão continua sem teste. | Acrescentar um caso com `encounter_hint` e estágios dormentes. |

```text
rg "pick_encounter_enemy(" (sem tests/specs) → 6 chamadores; 5 com portão
py.sh -c "pick_encounter_enemy(faction_id=f), 19 facções × 3 anéis" → só poder_kahen cai no pool sem portão (P2-8)
pytest -n 2 test_spec372_* test_spec360_* test_spec350_* test_spec351_* test_flag_registry test_spec315_* test_spec287_encounter_scale test_spec272_conflito_ligado test_fase64 test_spec289_ameaca_tematica → exit 0
```
