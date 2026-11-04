# SPEC-372 — revisão sol (review)

> Nome do arquivo: `handoffs/SPEC-372-sol-review.md`.
> **Veredito:** `CHANGES_REQUIRED`
> **Revisor:** Opus (`claude-opus-5-5`, `spec-reviewer`, papel Sol técnico) · **Data:** 2026-11-03 · **Commit revisado:** `3a92ece8`

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
