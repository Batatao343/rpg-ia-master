# SPEC-382 — revisão independente (spec `draft`, antes da aprovação)

> **Veredito:** `CHANGES_REQUIRED` (para a spec; em termos de risco: **SAFE-WITH-CHANGES**)
> **Revisor:** Opus (spec-reviewer), só leitura + sondas · **Data:** 2026-11-03 · **Commit revisado:** `main` `b278f6af` (spec em `specs/SPEC-382-refactor-nos-grandes-agentes.md`)
>
> Nota de nome: este arquivo ocupa `handoffs/SPEC-382-independent-review.md`, o mesmo nome que a §5
> da spec reserva para a revisão Sol do **código**. Essa revisão futura deve usar
> `handoffs/SPEC-382-sol-independent-review.md` (aceito por `scripts/check_handoff_names.py`), e a §5
> precisa ser ajustada.

## Escopo

A spec inteira (§1–§8), contra o source da `main` de 03/11 e as branches abertas. Verifiquei os fatos
[F]/[H] com `ast`/`grep`, rodei 8 testes focados e uma sonda de determinismo do MockLLM. Não revisei
código implementado (ainda não existe). Também li a auditoria §6/§6.5 e cruzei com as specs 371, 374,
376, 377, 378, 379 e 384.

## Fatos conferidos

| Afirmação da spec | Resultado |
|---|---|
| `storyteller_node` 1173-2720 = 1548 l.; closures `_fm_view` 1239 / `_fm_apply` 1242 com `nonlocal factions, intel` 1243; `_describe_track` 1772; `_stream_view` 2140 | **Confere** (ast) |
| Saídas antecipadas do storyteller em 1176/1216/1738 | **Confere** (os `return` em 1240/1254/1777/2143 são das closures) |
| `try` 2122 com `except Exception` 2654-2720 que remonta o turno | **Confere**. Todos os 26 nomes que o `except` lê são atribuídos **incondicionalmente** antes de 2122 (ast), e nenhum é reatribuído dentro do `try` (só `_k/_v/e`). A única reatribuição de `factions/intel` dentro do `try` vem do `nonlocal` de `_fm_apply` (2328). Então R6 + "mutar `_StoryTurn` in-place" é a mitigação certa. Com dataclass com defaults não existe `UnboundLocalError` hoje que viraria silêncio. |
| Os 11 `try` internos (1204, 1269, 1397, 1450, 1512, 1809, 1982, 1994, 2014, 2313; combate 2921) | **Confere** |
| `state` reatribuído por `state_patch` (1368); `_fm_view` lê `state`/`world`/`factions` com ligação tardia (variáveis reatribuídas depois da definição da closure) | **Confere**. Esse é o ponto mais frágil do storyteller: qualquer leitura de `state` que depois de 1368 fique como parâmetro do helper (e não `t.state`) passa a ler o estado **sem** o patch. |
| `turn_bl is not state.get("turn_baseline")` (1705/2629/2698); `_bl is not …` combate 3102 | **Confere** |
| `_combat_node` 2206-3215 = 1010 l., sem closures, saídas em 2209/2234/2267/2415/2455 | **Confere** na `main`. **Na `spec-371` as faixas andam até ~+30 linhas** (+3 imports/blocos em 2314, 2695, 2782). |
| `player` reatribuído por `grant_xp` (2793) enquanto `actors_by_id[_PLAYER_ID]` (2446) segue apontando para o dict antigo; os dois vão para `_compose_board_narrative` (2996-3006) | **Confere** |
| `chase_state`/`decl` só lidos sob a mesma condição | **Confere** (2563-2722) |
| `_run_round` 2517-2999 = 483 l., "6 closures" | **Parcial**: são **7** closures de 1º nível (`_enemy_decl` e `_enemy_decl_inner` são irmãs, não aninhadas; `_enemy_decl` chama `_enemy_decl_inner` por nome **antes** de ele ser definido, ligação tardia), mais `swap`/`late` aninhadas. Não há `nonlocal`. Nenhuma variável livre das closures é reatribuída depois da definição, então o `_RoundIntents` com referências é seguro. `acted` nasce em 2862, **depois** do bloco 2609-2621 em que a spec monta o `_RoundIntents`. |
| `_run_round` com "saídas antecipadas" | Só 2581 (recusa) e 2999. Os outros 19 `return` são das closures. |
| `tests/test_spec361_integracao.py:171` patcha `_combat_node` | **Confere** |
| `rng` do combate | [F] `agents/combat.py:2518` `rng = random` (módulo **global**). O dano lê `random` global (`check_reproducibility`, docstring). O MockLLM também consome `random` global (`mock_llm.py:239-797`). Então a ordem de consumo é uma única fita: qualquer troca na ordem de chamadas (fala do LLM × rolagem × spawn) muda o combate. O golden pega isso se semear por caso. |
| MockLLM determinístico? | Sonda: `random.seed(0)` + 5× `StoryUpdate` isolado deu o **mesmo hash** em 6 processos (`PYTHONHASHSEED` 0/1/2/3/random/random). A não-determinância medida pelo revisor da 385 (4 formas em 5 runs) vem de não semear e/ou do estado de processo (caches, ordem). O golden de campanha da 360 (`test_spec360_flags_off`, 30 turnos) é **byte-idêntico** e passou aqui. Ou seja, golden byte-estável com MockLLM é viável **se** semear por caso e isolar caches. |

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P0-1 | P0 | `tests/test_spec363_golden_guard.py:23-25` | `test_engine_modules_untouched_by_spec363` faz `git diff --quiet main -- services/conflict_orchestrator.py` **sem gate de branch**. Em qualquer branch que mude o orquestrador (Etapa 3) ele **falha**, inclusive na suíte completa do pouso, que roda na branch depois do `wt.sh sync`. A R9/W3 proíbe mexer nele, então a Etapa 3 não consegue ficar verde. A spec só cita os guards 353/363/364 como "vigias de golden". | Declarar na spec: (a) uma exceção W3 explícita, aprovada pelo dono, para dar a esse teste um gate de branch `spec-363` (como a 364/367 já fazem), num commit `test:` próprio **antes** da Etapa 3, ou para apagá-lo; ou (b) a Etapa 3 não acontece. Pela regra, o executor precisa saber antes. A 377 (que também toca o orquestrador) cai no mesmo teste, e convém resolver uma vez só. |
| P0-2 | P0 | `tests/test_spec297_review_fixes.py:186` | `inspect.getsource(st.storyteller_node)` asserta que o texto `[m for m in messages if isinstance(m, HumanMessage)][-3:]` está **dentro de `storyteller_node`**. A expressão está em `agents/storyteller.py:2378`, na faixa do `_story_beat_and_npcs` (2334-2401). Extrair como planejado quebra o teste, e R9 proíbe ajustá-lo. | Na §3.3, fixar que a linha 2378 (`_recent_player_inputs`) fica no orquestrador e é passada ao helper, ou declarar a exceção W3. Acrescentar à Etapa 2 uma varredura `git grep -n "getsource\|read_text" tests` contra os 3 arquivos. Outros dois testes leem o arquivo inteiro (`test_spec304_review.py:216`, `test_spec303_passes.py:84`, `test_spec298_faccao_eventos.py:78`) e não quebram, porque o código fica no mesmo módulo. Precisam ser citados como travas: o texto `updates.update({k: v for k, v in sim_updates.items() if k != "npcs"})` tem de sobreviver byte a byte. |
| P1-1 | P1 | spec §3.4 (c) | A captura de eventos patcha `agents.storyteller._log_event` e `agents.combat._log_event`, mas **não** `services.conflict_orchestrator._log_event` (`:31`) nem o `logger = logging.getLogger("rpg.conflict")` (`:2402`, `pressagio_frustrado`), que a R5 exige. Também perde eventos de serviços que fazem `from observability.telemetry import log_fallback` no topo. | Capturar no **sink**: `caplog.set_level(DEBUG)` em `rpg.*`, gravando `(logger, level, msg, extras ordenados)`. `log_event` sempre passa por `logging.getLogger(f"rpg.{area}")` (`observability/telemetry.py:136`). Manter o patch de `record_step`. Isso cobre R5 inteira sem depender de binding. |
| P1-2 | P1 | spec §3.4 | Nenhum caso exercita o **stream** (`narrative_sink` ligado): o `stream=_stream_ok`/`finalize=_stream_view` do storyteller (2131-2166) e o `narrate_text` do combate (1786/1878). Com sink desligado o caminho do stream é morto no golden, e um `_stream_view` que capture `_gold_now`/`_aberturas` errado passa. | Adicionar ≥ 2 casos com `narrative_sink.bind(coletor)` + modo de stream ligado, gravando a lista de chunks emitidos (storyteller e desfecho de combate). |
| P1-3 | P1 | spec §3.4 "Estabilidade", §7 | O [H] de "degradar campanha para a parte estável" enfraquece o oráculo sem necessidade: a 360 já prova campanha byte-idêntica. O `test_golden_is_stable` (2 casos 2× no mesmo processo) não pega instabilidade entre processos, nem por `PYTHONHASHSEED` (iteração de `set` de str), nem por xdist. | Exigir: `random.seed` por caso **e** casos parametrizados (um `tmp_path`/isolamento de cache por caso). Na Etapa 1, rodar o golden em 3 processos (`PYTHONHASHSEED=0`, `1`, `random`) e 1× com `-n 2`. Só depois disso a lista `VOLATILE` fecha. Degradar a campanha só com evidência anotada no handoff. Fixar `_OUTCOME_BUDGET_S` (6 s, thread com `copy_context`, `combat.py:1836-1860`) num valor alto nos casos, para que lentidão da máquina não dispare o fallback de orçamento e consuma `random` noutra ordem. |
| P1-4 | P1 | spec §2 R11, §3.4 W2 | `check_reproducibility()` (`playtest/invariants.py:1763`) compara 2 execuções do **mesmo** código. É `True` antes e depois mesmo se a refatoração mudar a ordem do RNG, ou seja, não serve como oráculo A/B. O playtest W2 compara só contagem de violações e desfecho, e também não pega divergência. | Rebaixar os dois a "sanidade" na spec. O oráculo A/B real é o golden (com o reforço da campanha byte-idêntica, P1-3). Opcional: gravar o hash do `mech_log` e da sequência de `record_step` por campanha no `SPEC-382-equivalence.md` de A e comparar em B. |
| P1-5 | P1 | spec §3.4, §5 | Não há medida de que o golden cobre os ramos que serão movidos. "≥ 12/≥ 10/≥ 6 casos" é contagem, não cobertura. Muitos ramos dependem do `random` do MockLLM (`beat_completed` 30 %, `chronicle_entry` 45 %…). `coverage`/`pytest-cov` **não** estão instalados (sonda). | Na Etapa 1, rodar um script one-shot com o `trace` da stdlib (ou `sys.monitoring`) só sobre o golden, listar as linhas **não executadas** de cada uma das 3 funções, anotá-las no handoff e exigir que **cada faixa da tabela §3.3** tenha ≥ 1 linha executada. Faixa sem cobertura ⇒ caso novo (seed escolhida para disparar o ramo) ou a extração daquela faixa espera. |
| P1-6 | P1 | spec cabeçalho "Depende de", §7 | Faltam travas com specs que mudam **comportamento** nos mesmos trechos: **377** item 3 muda `_alive`/declarações dentro de `_run_round` (`conflict_orchestrator.py:694,2750`; "muda comportamento de propósito"). Se pousar depois da Etapa 1, o golden do `_run_round` quebra, e a spec só permite regravar combate/campanha. **384 D3** apaga `_advance_reinforcements` (chamada ≈2732, dentro de `_combat_resolve_round`) e mexe em `playtest/*`. **374** edita `mock_llm.py` agora (W1: `spec-374: mock_llm.py`; só o caminho de criatura gerada, flag off). **379** pode mexer nos helpers de teste que o golden importa (`spec304_helpers`, `prompt_capture`; R4.4). | Cabeçalho: "Etapa 3 depende de SPEC-377 item 3 pousado (ou descartado)". Etapa 4: "espera 371 **e** 384 D3 decidido". Golden gravado só depois de `mock_llm.py` livre no W1. Incluir `mock_llm.py`, `tests/spec304_helpers.py`, `tests/spec325_helpers.py`, `tests/spec325_chase_helpers.py`, `tests/prompt_capture.py` e `playtest/runner.py` na lista do W1 de **toda** etapa, porque mudança neles invalida o fixture. Regra geral no lugar da exceção só para a 378: golden quebrou depois de rebase ⇒ a etapa para, e quem pousou é investigado. |
| P2-1 | P2 | spec §3.3 `_run_round` | Contagem "6 closures" e "sem as 6 closures" (§5 R3). `acted` é criado em 2862, depois do ponto onde a spec monta o `_RoundIntents`. `_enemy_decl` → `_enemy_decl_inner` é ligação tardia por nome. | Corrigir para 7 e citar `acted` como campo atribuído depois (`intents.acted = acted` no ponto 2862, com a mesma identidade), e `_enemy_decl` chamando `self.enemy_decl_inner`. |
| P2-2 | P2 | spec §3.3/§4 Etapa 4 | Todas as faixas de `_combat_node` estão na numeração **pré-371**. A 371 acrescenta o saber de fauna em 3 pontos, inclusive com `bk_changed`/`logs` dentro da faixa `_combat_resolve_round` e `_combat_aftermath`. | Na Etapa 4.0, além de regravar, refazer a tabela de faixas sobre a `main` com a 371 e incluir ≥ 1 caso de combate com `RPG_FAUNA` ligado (o ramo `_fauna_saber.active()`), senão o código novo da 371 é extraído sem oráculo. |
| P2-3 | P2 | spec §1 "Desbloqueia" | Cita "SPEC-384 item N", mas a 384 numera por D. O caminho sem tabuleiro é a **D4** (`SPEC-384:29, 210`). | Trocar por "SPEC-384 D4". |
| P2-4 | P2 | spec §3.4 (b) | "Estado de entrada após a chamada" só pega mutação do dict raiz passado. Mutação de objetos aninhados reaproveitados (ex.: `world` de entrada mutado em 1599/1621 antes do rebind) aparece, mas o golden não vê efeitos fora do estado: `npc_database.json`/bestiário escritos por `generate_new_npc`/`_sync_enemy_knowledge(load_persisted=True)` (`combat.py:754-776`), caches de módulo. | Gravar também, por caso, a lista ordenada de arquivos criados ou alterados no `tmp_path` isolado pelo conftest (nome + sha do conteúdo). |
| P2-5 | P2 | spec §5 | O critério de revisão aponta para o nome deste arquivo. | Ver nota no topo. |

## O que está bom (manter)

- Extrair no mesmo módulo: confirmado pelos 210 `setattr` e pelo modo de falha "patch inócuo".
- R6 (o `try` principal fica no orquestrador; o fallback lê `t.` mutado in-place) é exatamente o que
  a análise de ast mostra ser necessário.
- Etapa 4 atrás da 371 com uma única regravação, e um commit por extração.

## Pendências

Antes de `approved`: P0-1 e P0-2 (o dono decide a exceção W3 ou o desenho que evita), P1-1 a P1-6 na
spec. P2 pode entrar junto, com pouco esforço.

## Comandos rodados

```text
ast (end_lineno-lineno+1, closures, nonlocal, returns, tries) nos 3 nós → tamanhos/linhas conferem; 7 closures no _run_round
ast: leituras do except 2654 × atribuições antes/dentro do try → todas incondicionais antes de 2122; nenhum rebind no try
ast: variáveis livres das closures reatribuídas depois da def → só _fm_view (state/world/factions) e _enemy_decl→_enemy_decl_inner
W1 (for-each-ref, diff main...branch) → spec-371: agents/combat.py, playtest/{invariants,runner,telemetry}.py; spec-374: mock_llm.py; spec-214: playtest/latency_llm.py
git grep getsource/read_text em tests → test_spec297_review_fixes.py:186 (função), test_spec304_review/303_passes/298 (arquivo)
pytest -n 0 test_spec360_flags_off.py test_spec363_golden_guard.py test_spec297…::test_player_inputs… test_spec304_review…::test_encounter_path… → 8 passed (63,9 s)
sonda MockLLM StoryUpdate ×5, random.seed(0), 6 processos com PYTHONHASHSEED variado → mesmo hash a1954a03dfa4407e
find_spec coverage/pytest_cov → ambos ausentes
```
