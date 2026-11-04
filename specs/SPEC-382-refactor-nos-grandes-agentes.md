# SPEC-382 — Refatoração pura dos nós grandes: `storyteller_node`, `_combat_node` e `_run_round` em fases nomeadas no mesmo módulo

> **Status:** `in-progress` (Etapas 0-parcial, 1, 2 e 4 executadas em 04/11; Etapa 3 pendente por W1 da `spec-373`; Etapa 5 pendente). Aprovada em 04/11 ( coordenador, autonomia do dono na onda: "vai executando o que puder"; D1 = não (follow-up), D2 = 378 já `done`, D3 = aceitar, D4 = aceitar, D5 = smoke local, D6 = já aplicada pela SPEC-387 (guard da 363 com gate de branch), D7 = SPEC-384 D3 é **não**: Etapa 4 preserva `_advance_reinforcements`. Etapa 3 espera a `spec-373` (W1: `services/conflict_orchestrator.py`))
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-04
> **Origem:** auditoria de qualidade de 03/11 (`docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md`
> §4.2 itens 1–2, §5 letra F, §6 regras W1–W8, §6.3 ordem 7)
> **Depende de:** por etapa (§4):
> - Etapa 1 (golden): `mock_llm.py` livre no W1 (a SPEC-374 o edita agora) e helpers de teste
>   importados pelo golden livres (a SPEC-379 R4.4 pode mexer neles).
> - Etapa 3 (`_run_round`): **D6** decidida (guard da 363) **e** SPEC-377 item 3 (`_alive`/declarações,
>   `conflict_orchestrator.py:694,2750`, muda comportamento de propósito) pousada ou descartada.
> - Etapa 4 (combate): SPEC-371 **pousada** (edita `agents/combat.py` e `playtest/*` agora) **e**
>   SPEC-384 D3 decidida (apaga `_advance_reinforcements`, chamado em `combat.py:2732`, dentro de
>   `_combat_resolve_round`/`_combat_aftermath`).
> - SPEC-378 (helpers comuns) **recomendada antes** de tudo: mexe em `_last_human_text`, `_fold` e nos
>   guards `isinstance` destes mesmos arquivos (auditoria §4.2 itens 3 e 6). Ver D2.
> **Desbloqueia:** SPEC-384 D4 (tirar o caminho de combate sem tabuleiro fica localizado em
> `_combat_narrate`/`_combat_resolve_round`); follow-up futuro "nós em pacote" (fora de escopo).
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`
> **Tipo:** refatoração pura (W2/W3). Nenhum comportamento muda.

Rótulos: **[F]** fato verificado no source em 03/11 (arquivo:linha) · **[H]** hipótese a confirmar na
execução · **[D]** decisão do dono (§8).

---

## 1. Contexto & Objetivo

Três funções concentram boa parte da lógica de turno e passaram do tamanho em que uma sessão de IA
consegue ler e alterar com segurança:

- [F] `storyteller_node`: `agents/storyteller.py:1173-2720` = **1.548 linhas** (a função vai até o fim
  do arquivo). Tem 2 closures que reatribuem variáveis do nó (`_fm_view`/`_fm_apply`, l.1239-1254, com
  `nonlocal factions, intel` em l.1243), mais 2 closures locais menores (`_describe_track` l.1772,
  `_stream_view` l.2140), 3 saídas antecipadas (l.1176, l.1216, l.1738) e um `try` que cobre **toda** a
  chamada à LLM e a aplicação do `StoryUpdate` (l.2122-2652) com um `except` de 66 linhas que remonta
  o turno mecânico a partir das variáveis locais (l.2654-2720).
- [F] `_combat_node`: `agents/combat.py:2206-3215` = **1.010 linhas** (a auditoria contou 1.012 até a
  linha em branco 3217). Sem closures; ~60 variáveis locais compartilhadas entre preparação, rodada,
  narração e montagem do resultado; 5 saídas antecipadas (l.2209, 2234, 2267, 2415, 2455).
- [F] `_run_round`: `services/conflict_orchestrator.py:2517-2999` = **483 linhas**, com **7 closures
  de 1º nível** que compartilham estado mutável da rodada (`_next_intent` l.2623, `_frustrate` l.2629,
  `_spend_taunt` l.2651, `_taunt_same_round` l.2667 com `swap` aninhado l.2699, `_enemy_decl` l.2716,
  `_enemy_decl_inner` l.2726 com `late` aninhado l.2727, `_tf_acted` l.2864). `_enemy_decl` chama
  `_enemy_decl_inner` por nome antes de ele ser definido (ligação tardia); `acted` (lido por
  `_tf_acted`) só nasce em l.2862. Sem `nonlocal`. Só 2 saídas: l.2581 (recusa) e l.2999.

O objetivo é transformar cada uma num **orquestrador curto** que chama helpers privados nomeados por
fase, **sem mudar nenhum efeito**: mesmo dict parcial de `GameState` devolvido, mesma ordem de mutação,
mesmos eventos de observabilidade na mesma ordem, mesmos pontos de captura de exceção. O ganho é
legibilidade e revisão: cada fase passa a caber num `Read` e ganha nome.

**Decisão de desenho crítica (justificada em §3.1): os helpers ficam no MESMO módulo.** A auditoria
(§4.2 item 1) sugeria `time_passage.py`/`context.py`/`apply_update.py` e `start.py`/`round.py`/
`finish.py`; isso foi descartado já no §6.1 da própria auditoria ("extrair **no mesmo arquivo**
(preserva monkeypatch)") e esta spec confirma com contagem.

Princípio: "Mecânica é Python" e "cada agente retorna dict parcial" (`AGENTS.md` § Convenções) seguem
intactos; esta spec só reorganiza código.

## 2. Requisitos

Todos verificáveis pelo oráculo da §3.4 (golden novo + W2).

- **R1 — Orquestradores curtos.** Ao fim: `storyteller_node` ≤ 250 linhas, `_combat_node` ≤ 250
  linhas, `_run_round` ≤ 150 linhas (medidas por `ast`: `end_lineno - lineno + 1`). Nenhum helper novo
  passa de 220 linhas.
- **R2 — Helpers por fase, mesmo módulo.** Cada helper novo é função privada (prefixo `_`) definida no
  mesmo arquivo do nó: `agents/storyteller.py`, `agents/combat.py`, `services/conflict_orchestrator.py`.
  Nenhum arquivo `.py` novo de produto.
- **R3 — Closures viram parâmetros explícitos.** `_fm_view`/`_fm_apply` (storyteller) e as 7 closures
  de 1º nível de `_run_round` saem do corpo do nó e passam a receber o estado compartilhado por parâmetro (objeto de
  contexto privado, §3.2). As closures pequenas que não reatribuem nada do nó (`_describe_track`,
  `_stream_view`, `late`, `swap`) podem ficar como closures dentro do helper que as usa.
- **R4 — Retorno idêntico.** Para todo caso do golden (§3.4), o dict devolvido por `storyteller_node`,
  `combat_node`/`_combat_node` e `run_round`/`_run_round` é igual ao de antes após normalização
  (mesmas chaves, mesmos valores, mesmo conteúdo de mensagens, mesma ordem nas listas).
- **R5 — Ordem dos efeitos preservada.** Para todo caso do golden, a sequência de eventos de
  observabilidade é idêntica: chamadas a `_log_event` (categoria, nome, campos), `log_fallback`
  (nó, motivo), `log_intent_guard`, `mechanics_trace.record_step` (tipo, ator, motivo) e
  `logger.info` de `pressagio_frustrado`. Mutação in-place de `world`, `player`, `combat_meta`, `scene`,
  `out` e dos atores acontece na mesma ordem relativa (provado pela igualdade do estado final e dos
  logs mecânicos, que dependem da ordem).
- **R6 — Escopo de exceção preservado.** Todo `try/except` existente continua cobrindo exatamente as
  mesmas instruções. Em particular, o `try` principal do storyteller (l.2122-2652) continua no
  orquestrador e envolve as chamadas aos helpers que substituem aquele bloco, e só elas; o fallback do
  `except` (l.2654-2720) enxerga os mesmos valores (inclusive o que helpers já tinham mutado antes da
  exceção). Nenhum `except` novo é criado; nenhum é alargado ou estreitado.
- **R7 — Nomes estáveis.** Nenhum nome de módulo hoje existente é removido ou renomeado (o teste
  `tests/test_spec361_integracao.py` faz `setattr(combat, "_combat_node", …)`; outros patcham
  `_narrate`, `_spawn_v4_enemies`, `_finish_encounter`, `_parse_turn_declaration`, `_fast_text`,
  `_canonical_enemy_id`, `_OUTCOME_BUDGET_S`, `_narrate_world`, `_guard_mediation_secret`, `_log_event`,
  `get_llm`, `check_encounter`, `simulate_world`, `find_travel_destination`, `build_context_pack`,
  `generate_new_npc`, `generate_new_enemy`). Os helpers novos chamam esses nomes pelo global do módulo,
  como hoje.
- **R8 — Imports locais ficam locais.** Todo `from X import Y` hoje dentro do corpo do nó continua
  dentro de função, executado no mesmo ponto do fluxo (pode migrar para o helper que contém aquele
  trecho). Nada sobe para o topo do módulo.
- **R9 — Testes intocados.** Nenhum arquivo de teste existente muda (W3). A única adição em `tests/` é
  o golden da Etapa 1. Se algum teste existente exigir mudança, a etapa para e é reportada (não é pura).
  **Única exceção possível:** [F] `tests/test_spec363_golden_guard.py:23-25`
  (`test_engine_modules_untouched_by_spec363`) faz `git diff --quiet main -- services/conflict_orchestrator.py`
  **sem gate de branch**; qualquer branch que mude o orquestrador falha nele, inclusive na suíte do pouso.
  A Etapa 3 só acontece com a decisão **D6** do dono, aplicada num commit `test:` próprio antes dela.
- **R10 — Um commit por extração** (W4), cada um revertível sozinho com `git revert <sha>`, com o
  golden e os testes de escopo verdes em cada commit.
- **R11 — W2 completo** antes (baseline A, Etapa 0) e depois (B, Etapa 5): suíte completa verde;
  `evals compare --current B --baseline A` sem diferença. O **oráculo A/B real é o golden** (§3.4):
  `playtest run --all --turns 10` (`--seed 0` e `--seed 1`, mesma contagem de violações e mesmo
  desfecho) e `playtest.invariants.check_reproducibility()` → `True` entram só como **sanidade**, porque
  comparam o código consigo mesmo ou só contagens e não pegam mudança de ordem do RNG. Além disso, o
  hash do `last_mech_log` e da sequência de `record_step` por campanha é gravado em A e comparado em B.
- **R12 — Travas de texto-fonte.** Testes que leem o código como texto continuam verdes sem mudança:
  - [F] `tests/test_spec297_review_fixes.py:186` faz `inspect.getsource(st.storyteller_node)` e exige
    `[m for m in messages if isinstance(m, HumanMessage)][-3:]` **dentro do nó** (hoje
    `agents/storyteller.py:2378`): essa linha (`_recent_player_inputs`) **fica no orquestrador**, com a
    variável local chamada `messages`, e o valor é passado ao helper.
  - [F] Leem o módulo inteiro (sobrevivem porque o código fica no mesmo arquivo, desde que o texto
    não mude): `tests/test_spec304_review.py:216-219` (`if k != "npcs"` presente e
    `updates.update(sim_updates)\n` ausente), `tests/test_spec303_passes.py:84`
    (`world_calendar.CROSSING_NOTE`), `tests/test_spec298_faccao_eventos.py:78-80` (`_POS_CUES`/
    `_revert_reputation` ausentes).
  - Antes de cada etapa: `git grep -n "getsource\|read_text" tests` e confirmar que nenhum alvo novo
    aponta para os 3 arquivos.

### Fora de escopo

- Mover qualquer helper para arquivo/pacote novo (`agents/storyteller/…`, `agents/combat/…`). Fica
  como follow-up, que exige reexports e migração dos alvos de patch (§3.1).
- `npc_actor_node` (`agents/npc.py:861-1639`, ~779 linhas) e `_archive_node`
  (`agents/archivist.py:587-1252`, ~666 linhas): passam do limite de 480, mas a auditoria não os
  mapeou, têm 109 `monkeypatch.setattr` próprios em 32 arquivos e o W6 pede uma refatoração por vez.
  Ver **D1**.
- Qualquer mudança de comportamento, inclusive "bug óbvio" visto de passagem: vai para nota no
  hand-back (o ex.: SPEC-377 cuida das divergências conhecidas).
- Os helpers da SPEC-378 (`invoke_structured`, `text.fold`, `env.env_choice`): se a 378 não tiver pousado,
  esta spec **não** os antecipa.
- Remover o caminho de combate sem tabuleiro (`board_on` falso) ou o modo `shadow`: é a SPEC-384 N.
- Editar `playtest/*`, `evals/` protegido, goldens existentes (`tests/fixtures/spec330_legacy_golden.json`,
  `router_off_golden.json`, `spec358_sim_v1_golden.json`, `spec360_flags_off_golden.json`; são
  vigiados por `tests/test_spec353_golden_guard.py`, `test_spec363_golden_guard.py`,
  `test_spec364_golden_guard.py`).
- Ruff/format em massa nos três arquivos (só o código movido segue o format atual).

## 3. Design técnico

### 3.1 Por que no mesmo módulo (contagem de 03/11)

[F] Os testes trocam atributos **do módulo do nó** com `monkeypatch.setattr(<alias>, "<nome>", …)`:

| Módulo | Aliases usados nos testes | `setattr` | Arquivos |
|---|---|---|---|
| `agents.storyteller` | `stt`, `st`, `st_mod`, `storyteller` | 93 | ~45 |
| `agents.combat` | `combat`, `cbt`, `cbt2`, `combat_agent`, `combat_mod`, `ac` | 86 | ~40 |
| (soma dos dois) | | **179** | **74** |
| `services.conflict_orchestrator` | `orch` | 31 | 18 |

(Contagem por `Grep` de `setattr\(\s*(alias)\s*,` em `tests/`; nenhum patch usa caminho em string
`"agents.storyteller.x"` nem `unittest.mock.patch`. A auditoria citou ~196 em 46 arquivos; a diferença
é de método de contagem, a conclusão é a mesma.) Nomes mais patchados: `get_llm` (≈60 no storyteller),
`generate_new_npc`, `check_encounter`, `simulate_world`, `_narrate`, `generate_new_enemy`,
`_log_event`, `_finish_encounter`.

Um helper em `agents/storyteller/apply_update.py` que fizesse `from agents.storyteller import get_llm`
(ou `from llm_setup import get_llm`) teria **o próprio** binding: `setattr(stt, "get_llm", fake)` não o
alcançaria, o teste passaria a chamar o LLM real/mock em vez do fake e poderia continuar verde por
acaso (MockLLM devolve Pydantic válido). É o pior modo de falha: patch inócuo silencioso. O mesmo vale
para atributos de dados de módulo, como `monkeypatch.setattr(npc, "NPC_DB_FILE", …)`
([F] `tests/test_runtime_cache.py:82`). No mesmo módulo, todo helper resolve o nome pelo global na hora
da chamada e os 210 patches seguem efetivos sem tocar em teste (R9).

### 3.2 Estado compartilhado: objeto de contexto privado por nó

[F] As fases leem e **reatribuem** as mesmas variáveis (storyteller: `world` em l.1279/1280/1342/1374/
1817/1822, `factions`/`intel` via `nonlocal` em l.1243, `state` em l.1368, `turn_bl` em 6 lugares;
combate: `enemies` l.2292/2373, `combat_meta` l.2323/2351/2414/3039/3053, `player` l.2793). Passar e
devolver tuplas de 15-25 valores entre helpers é onde a extração erra. Por isso:

- `agents/storyteller.py`: `@dataclass class _StoryTurn` (privada, sem `slots` para facilitar o diff)
  com os campos mutáveis do turno: `state`, `messages`, `last_user_input`, `world`, `world_before`,
  `factions`, `intel`, `law_resolved`, `dest`, `travel_periods`, `closed_pass`, `discovered_routes`,
  `world_tick`, `sim_updates`, `faction_events`, `discovery_events`, `discovery_player`,
  `rested_player`, `reward_player_before`, `turn_bl`, `travel_note`, `rest_note`, `faction_note`,
  `world_note`, `weather_note`, `fm_events`, `fm_post_notes`, `fm_extra`, `perceived_items`,
  `wq_quests`, `wq_events`, `wq_created`, `wq_changed`, `extra_engine_events`, `rumor_nothing`,
  `rumor_find`, `scene_npcs`, `scene_state`, `travel_needs_replan`, `replan_cause`, `track_bk`,
  `fauna_sign_shown`, `fauna_day`, `ll` (luz). A lista final é a que o executor confirmar ao extrair;
  campo que só uma fase usa fica local da fase.
  - `_fm_view(t: _StoryTurn) -> dict` e `_fm_apply(t: _StoryTurn, result) -> str` substituem as
    closures com o mesmo corpo (`t.factions = value` no lugar do `nonlocal`).
- `agents/combat.py`: `@dataclass class _CombatTurn` com os ~60 locais (player, enemies, combat_meta,
  scene, allies, scene_tr, party, actors_by_id, sides, active, intent, declaration, flags de fuga,
  `chase_state`, `out`, logs, `world`, `world_out`, desfecho, XP, narrativa…). `chase_state` e `decl`,
  hoje só definidos em alguns ramos (l.2563/2586, l.2599-2621), viram campos com default `None`: hoje
  só são lidos sob a mesma condição que os define (l.2722), então o default não muda nada.
- `services/conflict_orchestrator.py`: `class _RoundIntents` (privada) com `frozen`, `intent_mode`,
  `intent_cursor`, `taunt_spend`, `acted`, e referências a `scene`, `actors_by_id`, `sides`, `out`,
  `rng`, `scene_state`; as 7 closures viram métodos (`next_intent`, `frustrate`, `spend_taunt`,
  `taunt_same_round`, `enemy_decl`, `enemy_decl_inner`, `tf_acted`) com o mesmo corpo; `enemy_decl`
  chama `self.enemy_decl_inner`. `swap` e `late` continuam aninhadas. `acted` é criado no mesmo ponto
  de hoje (l.2862) e atribuído ao objeto ali (`intents.acted = acted`, mesma identidade do `set` que o
  laço muta); antes disso o campo é `None` e nenhum método o lê (hoje só `_tf_acted` o lê, dentro do laço).

Regra de identidade: o objeto de contexto guarda **as mesmas referências** que os locais guardavam
(nada de `deepcopy`/`dict(...)` novo). Comparações por identidade que existem hoje dependem disso:
[F] `turn_bl is not state.get("turn_baseline")` (storyteller l.1705, 2629, 2698) e
`_bl is not state.get("turn_baseline")` (combate l.3102).

### 3.3 Mapa de fases (alvo; nomes podem ser ajustados no plano, não a fronteira)

**`storyteller_node`** (orquestrador mantém: guarda de `messages` vazio l.1174-1176, montagem do
`_StoryTurn`, `llm = get_llm(temperature=0.7)` l.1905, o `try/except` principal e os `return`).

| Helper | Faixa atual | Observação |
|---|---|---|
| `_story_travel_refusal(t)` → `dict \| None` | 1199-1220 | saída antecipada; `try/except (ImportError, AttributeError)` l.1204-1209 vai junto |
| `_story_time_passage(t)` | 1221-1360 | viagem/descanso, `_world_tick`, fações off-screen, achado de exploração; `try` l.1269-1278 junto |
| `_story_world_tick_effects(t)` | 1361-1408 | `state_patch` (rebind de `t.state`, l.1368), percepção, crônica; `try` l.1397-1406 |
| `_story_membership_and_quests(t)` | 1409-1473 | SPEC-301 rivais/ascensão, quests de mundo, cache de boato; `try` l.1450-1461 |
| `_story_scene_and_replan(t)` | 1474-1497 | reset de cena, `travel_needs_replan`, `world_replan_cause` + `_log_event` |
| `_story_encounter(t)` → `dict \| None` | 1501-1833 | devolve o dict de COMBAT START (hoje `return updates` l.1738) ou `None`; subdividir em `_story_roll_encounter` (1508-1619), `_story_combat_start(t, enc, …)` (1662-1738) e `_story_noncombat_encounter` (1740-1807); o pulso do mundo com `try` l.1809-1833 fica no `_story_encounter` |
| `_story_context_blocks(t)` | 1835-2025 | `build_context_pack`, blocos de ambiente/fama/elenco/companheiro/lei/fauna; os 3 `try` (l.1982, 1994, 2014) vão junto |
| `_story_system_message(t, blocks)` → `SystemMessage` | 2026-2116 | f-strings do prompt copiadas byte a byte (SPEC-317 `compose_prompt`) |
| dentro do `try`: `_story_narrate(t, llm, sys)` → `StoryUpdate` | 2123-2179 | `narrate_structured` + guard `isinstance(update, StoryUpdate)` (l.2169-2179) intacto |
| dentro do `try`: `_story_guard_narrative(t, update)` | 2181-2278 | pré-validação, quarentena, sanitização, mediação |
| dentro do `try`: `_story_engine_proposals(t, update)` | 2280-2332 | `faction_deed`, `apply_claims` (com seu `try` l.2313-2321), `membership_action` via `_fm_apply` |
| dentro do `try`: `_story_beat_and_npcs(t, update, recent_player_inputs)` | 2334-2401 | XP de beat, `campaign_plan`, `introduced_npcs`/`npcs_left_scene`. **Exceção (R12):** l.2377-2379 (`_recent_player_inputs = tuple(... [m for m in messages if isinstance(m, HumanMessage)][-3:])`) fica no orquestrador, dentro do `try`, no mesmo ponto relativo, e entra como parâmetro |
| dentro do `try`: `_story_assemble_updates(t, update)` → `dict` | 2403-2652 | itens narrados (2433-2513 pode virar `_story_narrated_items`), recibo, eventos, quests, rumores, `archive_low` |
| no `except`: `_story_exception_fallback(t)` → `dict` | 2655-2720 | o `except Exception as e:` e o `_log_event("storyteller", "failed", …)` ficam no orquestrador; só o corpo da montagem do fallback vira helper |

Texto que precisa sobreviver byte a byte no módulo (R12): `if k != "npcs"` (l.1708),
`world_calendar.CROSSING_NOTE` (l.1333), a list comprehension de l.2378.

**`_combat_node`** — faixas na numeração **pré-371** da `main` de 03/11; a 371 desloca até ~+30
linhas (blocos em ≈2314, ≈2695, ≈2782) e a Etapa 4.0 refaz esta tabela. (O wrapper `combat_node` l.2185-2203, com `mechanics_trace.scope()` e o
`ContextVar` da SPEC-361, não muda; todos os helpers rodam dentro desse escopo porque são chamados por
`_combat_node`).

| Helper | Faixa atual |
|---|---|
| `_combat_turn_from_state(state)` → `_CombatTurn` | 2207-2231 (guarda `messages` vazio fica no orquestrador) |
| `_combat_unconscious_refusal(t)` / `_combat_freetext_refusal(t)` → `dict \| None` | 2233-2250 / 2252-2275 |
| `_combat_prepare_encounter(t)` | 2281-2375 (spawn, cena, manifesto, pilhas, presságio de cena; ramo `else` de reconciliação junto) |
| `_combat_no_active_result(t)` → `dict \| None` | 2377-2428 |
| `_combat_assemble_sides(t)` | 2430-2451 (`_board_opening_result` l.2454-2473 continua chamado do orquestrador; já é helper e precedente desta spec) |
| `_combat_flee_request(t)` | 2474-2516 |
| `_combat_environment(t)` | 2517-2558 (clima, luz, iniciativa, surpresa) |
| `_combat_resolve_round(t)` | 2559-2723 (fuga, declaração, `orch.run_round`, `_canonical_player_action`) |
| `_combat_aftermath(t)` | 2725-2796 (espelho de vitais, Cicatriz, mortos/derrubados, XP; rebind de `t.player` l.2793) |
| `_combat_narrate(t)` | 2798-2906 (ramos `board_on`/queda/simulação/narração) |
| `_combat_close_round_meta(t)` | 2908-3057 (presságio seguinte com seu `try` l.2921-2943, pilhas, mech_log, registro do tabuleiro, fim do encontro) |
| `_combat_build_result(t)` → `dict` | 3058-3215 (resultado, quests, crônica, eventos de morte, fuga com viagem) |

**`_run_round`** (orquestrador mantém a assinatura, `rng = rng or random.Random()`,
`declarations = dict(...)` e os `return out`; `run_round` e seu `fx.bind/unbind` l.2501-2514 não mudam).

| Helper | Faixa atual |
|---|---|
| `_round_new_out(actors_by_id)` → `dict` | 2539-2563 |
| `_round_refusal(...)` → `bool` (o orquestrador faz `return out`) | 2564-2581 |
| `_round_scene_start(...)` | 2582-2608 (marcadores, `advance_tactical_state`, impasse, Cartas de Cena, fases de chefe, promessas) |
| `_RoundIntents(...)` + `freeze()` | 2609-2621 e closures 2623-2763 (+ `_tf_acted` 2864; `acted` ligado em 2862) |
| `_round_start_of_round(...)` → `(player, player_id, player_decl)` | 2765-2828 |
| `_round_sequence(...)` → `(seq, side_actors)` | 2830-2860 |
| `_round_actor_loop(...)` | 2861-2936 |
| `_round_end(...)` | 2938-2998 |

### 3.4 Oráculo: golden de nós (novo, Etapa 1) + W2

- **Arquivos novos (só teste):** `tests/spec382_node_golden.py` (gera casos, normaliza, captura
  eventos), `tests/test_spec382_node_golden.py` (compara), `tests/fixtures/spec382_node_golden.json`
  (gravado **uma vez**, na Etapa 1, sobre o código ainda intacto; `SPEC382_REGEN=1` regrava e só vale
  nessa etapa).
- **Casos diretos** (estado de entrada fixo, MockLLM, `random.seed(…)` fixo por caso), reutilizando os
  construtores que os testes já têm (`tests/spec304_helpers.py`, `tests/spec325_helpers.py`,
  `tests/spec325_chase_helpers.py`, `tests/prompt_capture.py`) em vez de inventar estado:
  - storyteller (≥ 12): ação livre; viagem para vizinho sem encontro; viagem com encontro de combate
    (`check_encounter` patchado para devolver um encontro fixo, como já fazem
    `tests/test_audit_reward_contracts.py`/`test_world_event_proof.py`); viagem com armadilha mortal;
    rastro; encontro social; descanso; descanso bloqueado por clima; destino impossível (recusa
    l.1216); `get_llm` devolvendo `FallbackLLM` (guard l.2170); exceção dentro do `try` (fake que
    levanta em `narrate_structured`, para exercitar o `except` l.2654); proposta de evento inválida
    (quarentena l.2216); item narrado único já reclamado; jogador com `faction_membership`.
  - combate (≥ 10), com `RPG_CARD_DECK` `off` e `on`: inconsciente; texto livre com tabuleiro aberto;
    COMBAT START com spawn; abertura do tabuleiro (`_board_opening_result`); rodada comum; sem inimigo
    ativo; fuga com sucesso com destino; fuga recusada por condição; morte do jogador; vitória com
    quest `cacar_criatura`; simulação.
  - `_run_round` (≥ 6), além do `spec330_legacy_golden.json` que já existe: recusa de item; presságio
    `on` congelado; `shadow`; Provocação na mesma rodada (`_taunt_same_round`); ações extras de chefe;
    Interromper (`interrompido_por`).
  - **stream (≥ 2):** com `services.narrative_sink.bind(coletor)` e o modo de stream ligado, um turno de
    história (`narrate_structured` com `stream=_stream_ok`/`finalize=_stream_view`, l.2130-2166) e um
    desfecho de combate (`narrate_text`, combate l.1786/1878), gravando a lista ordenada de chunks
    emitidos. Sem isso o caminho do stream fica fora do oráculo.
  - **fauna (≥ 1, só na Etapa 4.0):** combate com `RPG_FAUNA` ligado (ramo de saber de fauna que a
    SPEC-371 acrescenta).
- **Casos de campanha:** fingerprint no formato de `tests/test_spec360_flags_off.py:27-52` para os 4
  perfis vitais (`explorador`, `combate`, `diplomatico`, `secret_rusher`), 10 turnos, `seed=0`, com
  `RPG_CARD_DECK` `off` e `on`, mais hash do estado final inteiro normalizado, do `last_mech_log` e da
  sequência de `record_step`. **Byte-idêntico**: o golden da 360 (30 turnos) já prova que é viável.
- **O que se grava por caso:** hash e (em falha) diff legível de:
  - (a) dict devolvido normalizado (mensagens → `(tipo, content)`, `sort_keys`, `default=str`);
  - (b) estado de entrada **após** a chamada (pega mutação in-place, inclusive de objetos aninhados
    como o `world` mutado em l.1599/1621 antes do rebind);
  - (c) eventos de observabilidade capturados **no sink**, não por binding: `caplog.set_level(DEBUG)`
    nos loggers `rpg.*`, gravando `(logger, level, msg, extras ordenados)`. `log_event` sempre passa por
    `logging.getLogger(f"rpg.{area}")` (`observability/telemetry.py:136`); isso cobre
    `_log_event` de storyteller, combate e orquestrador, `log_fallback` importado no topo por serviços,
    e `logging.getLogger("rpg.conflict")` (`conflict_orchestrator.py:2402`, `pressagio_frustrado`).
    Mais o patch em `services.mechanics_trace.record_step` (tipo, ator, motivo);
  - (d) lista ordenada de arquivos criados/alterados no `tmp_path` isolado pelo conftest (nome + sha do
    conteúdo): pega escritas de `npc_database.json`/bestiário por `generate_new_npc` e
    `_sync_enemy_knowledge(load_persisted=True)` (`combat.py:754-776`).
- **Determinismo:** o `rng` do combate é o módulo `random` **global** (`combat.py:2518`), e o MockLLM
  também consome `random` global (`mock_llm.py`); é uma fita única, e qualquer troca na ordem das
  chamadas (fala × rolagem × spawn) muda o resultado, o que o golden precisa pegar. Por isso:
  `random.seed(...)` **por caso**; casos parametrizados, cada um com isolamento próprio de cache/
  `tmp_path`; `_OUTCOME_BUDGET_S` (`combat.py:2017`, 6 s, thread com `copy_context`) fixado alto nos
  casos (monkeypatch de atributo do módulo, já usado em `tests/test_spec353_misc.py`), para que
  lentidão da máquina não dispare o fallback de orçamento e consuma `random` noutra ordem.
- **Estabilidade (Etapa 1, antes do commit):** rodar o golden em 3 processos (`PYTHONHASHSEED=0`, `1`,
  `random`) e 1× com `-n 2`; campo instável (uuid, timestamp, latência) vai para uma lista `VOLATILE`
  explícita **nessa etapa**. Depois da Etapa 1 a lista e o fixture não mudam (W3). Degradar um caso de
  campanha para a parte estável só com evidência de instabilidade anotada no handoff.
- **Cobertura das faixas (Etapa 1):** `pytest-cov` não está instalado; um script one-shot com o `trace`
  da stdlib (ou `sys.monitoring`), só sobre o golden, lista as linhas **não executadas** de cada uma
  das 3 funções. Cada faixa das tabelas da §3.3 precisa de ≥ 1 linha executada; ramo relevante sem
  cobertura (ex.: `beat_completed`, que o MockLLM sorteia em ~30 %) ⇒ caso novo com seed que o dispare,
  ou a extração daquela faixa espera. As linhas não cobertas ficam anotadas no handoff.
- **W2** (auditoria §6.2) roda em A (Etapa 0) e B (Etapa 5): suíte completa (coordenador), evals das 12
  suítes do `eval-gates.yml` com `--seed 7` + `evals compare` sem diferença; playtest
  `--all --turns 10` (`--seed 0` e `--seed 1`) e `check_reproducibility()` como sanidade (R11).

### 3.5 Arquivos

- **Alterados (produto):** `agents/storyteller.py`, `agents/combat.py`,
  `services/conflict_orchestrator.py` (só reorganização interna; R2/R7/R8).
- **Novos (teste):** os 3 da §3.4. Evidência de A/B em `handoffs/SPEC-382-equivalence.md` (tabela de
  violações/desfechos por perfil e seed, saída do `evals compare`).
- **Não tocados:** `playtest/*`, `evals/*`, testes existentes (exceto o commit da D6, se aprovada),
  goldens existentes, `main.py`, `state.py`, `mock_llm.py`.

## 4. Plano passo a passo

Antes de **cada** etapa: W1 **revisada** (auditoria §6.2), com as três fontes: (1) branches vivas
(commit à frente da `main` e com commit nos últimos 7 dias); (2) mudanças não commitadas em todos os
worktrees, inclusive o checkout principal; (3) arquivos de specs `in-progress` que trabalham direto na
`main` (§3 delas + `git log --since=2.days --name-only main`). Interseção não vazia ⇒ a etapa espera.
A lista de arquivos de **toda** etapa inclui, além do arquivo de produto da etapa, os que invalidam o
fixture: `mock_llm.py`, `tests/spec304_helpers.py`, `tests/spec325_helpers.py`,
`tests/spec325_chase_helpers.py`, `tests/prompt_capture.py`, `playtest/runner.py`. Também antes de
cada etapa: `git grep -n "getsource\|read_text" tests` (R12). W6: só esta spec de refatoração em voo;
RAM < 3 GB ⇒ não dispara. Testes de escopo com no máximo `-n 2`; a suíte completa é do coordenador.

**Regra de rebase:** se o golden quebrar depois de um rebase sobre a `main`, a etapa **para** e quem
pousou no meio é investigado (vale para qualquer spec, não só a 378). O fixture não é regravado para
"acompanhar"; a única regravação permitida é a da Etapa 4.0.

### Etapa 0 — Baseline A e travas

1. W1 para `agents/storyteller.py`, `services/conflict_orchestrator.py`, `agents/combat.py` e a lista
   comum acima. [F] No W1 do revisor em 03/11: `spec-371` toca `agents/combat.py` e
   `playtest/{invariants,runner,telemetry}.py`; `spec-374` toca `mock_llm.py`; `spec-214` toca
   `playtest/latency_llm.py` (branch parada pela regra de 7 dias, a listar para o dono arquivar).
2. Rodar W2-A e gravar em `handoffs/SPEC-382-equivalence.md`, inclusive o hash de `last_mech_log` e da
   sequência de `record_step` por campanha.
3. Registrar o SHA da `main` usado como A.

### Etapa 1 — Golden de nós (antes de qualquer extração; `mock_llm.py` e helpers de teste livres no W1)

1. **Testes:** `tests/test_spec382_node_golden.py::test_storyteller_cases`,
   `::test_combat_cases`, `::test_run_round_cases`, `::test_stream_cases`,
   `::test_campaign_fingerprints` assertam igualdade com o fixture (casos parametrizados, seed por
   caso).
2. **Implementação:** só os arquivos de teste da §3.4; código de produto intocado.
3. **Verificação:** verde no código intacto em 3 processos (`PYTHONHASHSEED=0`, `1`, `random`) e 1×
   com `-n 2`; relatório de cobertura por faixa (`trace` da stdlib) anotado no handoff, com toda faixa
   da §3.3 coberta. Commit único `test: add SPEC-382 node golden`.

### Etapa 2 — `storyteller_node` (W1 livre)

Um commit por linha; após cada uma: golden + `tests/test_fase26.py tests/test_fase33.py
tests/test_grounding_boundaries.py tests/test_npc_two_phase.py tests/test_spec301_*.py
tests/test_spec309_*.py tests/test_spec311_*.py tests/test_spec315_*.py tests/test_spec360_*.py
tests/test_stream_structured.py tests/test_streaming.py tests/test_mediation_secret.py` verdes.

1. `_StoryTurn` + `_fm_view(t)`/`_fm_apply(t, r)` (closures saem; nó passa a usar `t.`).
2. `_story_travel_refusal`.
3. `_story_time_passage` + `_story_world_tick_effects`.
4. `_story_membership_and_quests` + `_story_scene_and_replan`.
5. `_story_encounter` (+ 3 sub-helpers).
6. `_story_context_blocks` + `_story_system_message` (prompt byte a byte: o golden captura o
   `SystemMessage` via o fake de LLM de `tests/prompt_capture.py`).
7. Helpers de dentro do `try` (`_story_narrate`, `_story_guard_narrative`, `_story_engine_proposals`,
   `_story_beat_and_npcs`, `_story_assemble_updates`), um commit cada.
8. `_story_exception_fallback`.

### Etapa 3 — `_run_round` (W1 livre + D6 aplicada + SPEC-377 item 3 pousado ou descartado)

0. Aplicar a D6 num commit `test:` próprio (gate de branch em
   `tests/test_spec363_golden_guard.py::test_engine_modules_untouched_by_spec363`, no padrão de
   `tests/test_spec364_golden_guard.py:30-36`, ou apagar o teste, conforme o dono). Sem D6 a Etapa 3
   não começa.

Após cada linha: golden + `tests/test_card_effects_grammar.py` (usa `spec330_legacy_golden.json`) +
`tests/test_spec339_duracao_condicoes.py tests/test_spec346_mech_log.py tests/test_enemy_intent_node.py
tests/test_spec355_*.py tests/test_spec295_chefe_no_topo.py tests/test_spec353_golden_guard.py
tests/test_spec363_golden_guard.py tests/test_spec364_golden_guard.py`.

1. `_RoundIntents` (7 closures → métodos; `acted` ligado em l.2862).
2. `_round_new_out` + `_round_refusal` + `_round_scene_start`.
3. `_round_start_of_round` + `_round_sequence`.
4. `_round_actor_loop`.
5. `_round_end`.

### Etapa 4 — `_combat_node` (só depois da SPEC-371 pousada + SPEC-384 D3 decidida + W1 livre + golden reconferido)

0. Se a 371 (ou a 384 D3) mudou `combat.py`/`playtest/*` depois da Etapa 1, o golden de combate e de
   campanha foi gravado sobre código antigo: **regravar só os casos de combate/campanha** sobre a
   `main` atual, num commit próprio `test: refresh SPEC-382 combat golden after SPEC-371`, acrescentar
   o caso com `RPG_FAUNA` ligado, **refazer a tabela de faixas de `_combat_node` da §3.3** sobre essa
   `main` (atualizando a spec no mesmo commit) e refazer o relatório de cobertura por faixa. Anotar no
   handoff. É a única regravação permitida.
1. `_CombatTurn` + `_combat_turn_from_state`.
2. `_combat_unconscious_refusal` + `_combat_freetext_refusal` + `_combat_no_active_result`.
3. `_combat_prepare_encounter`.
4. `_combat_assemble_sides` + `_combat_flee_request` + `_combat_environment`.
5. `_combat_resolve_round`.
6. `_combat_aftermath`.
7. `_combat_narrate`.
8. `_combat_close_round_meta`.
9. `_combat_build_result`.

Após cada linha: golden + `tests/test_spec325_*.py tests/test_spec346_*.py tests/test_spec353_*.py
tests/test_spec363_*.py tests/test_spec364_*.py tests/test_encounter_manifest.py
tests/test_api_jogadas.py tests/test_spec361_integracao.py tests/test_combat_lifecycle.py`.

### Etapa 5 — Fechamento

1. Medir R1 por `ast` (comando one-shot no hand-back, não teste permanente).
2. W2-B e comparação com A no `handoffs/SPEC-382-equivalence.md`.
3. `git diff main -- tests/` mostra só os 3 arquivos novos (R9).
4. Revisão independente (W7): o revisor Sol refaz W2 em pelo menos 1 item e lê o diff de cada commit
   procurando os riscos da §7.
5. Smoke real §6.

## 5. Critérios de aceite

- [ ] R1: `storyteller_node` ≤ 250, `_combat_node` ≤ 250, `_run_round` ≤ 150 linhas; nenhum helper novo > 220
- [ ] R2/R7/R8: nenhum `.py` novo de produto; nenhum nome existente removido; nenhum import local promovido ao topo
- [ ] R3: sem `nonlocal` em `storyteller.py`; sem as 7 closures de 1º nível dentro de `_run_round`
- [ ] R4/R5: `tests/test_spec382_node_golden.py` verde em **todos** os commits da série (provado commit a commit no handoff), estável em 3 processos e com `-n 2`, com toda faixa da §3.3 coberta
- [ ] R6: revisor confirma, por commit, que o `try` principal do storyteller cobre o mesmo bloco e o fallback lê os mesmos valores
- [ ] R9: nenhum teste existente alterado, salvo o commit da D6 (se o dono aprovar)
- [ ] R10: um commit por extração; cada um revertível sozinho
- [ ] R11: W2 A = B (evals sem diferença; hashes de `last_mech_log`/`record_step` iguais); sanidade: violações/desfechos iguais em `--seed 0` e `--seed 1` e `check_reproducibility()` `True`
- [ ] R12: `test_spec297_review_fixes`, `test_spec304_review`, `test_spec303_passes`, `test_spec298_faccao_eventos` verdes sem mudança
- [ ] `uv run pytest` verde (suíte completa offline, coordenador)
- [ ] Guard de FallbackLLM preservado (`isinstance(update, StoryUpdate)` segue antes de qualquer acesso a campo)
- [ ] Saves antigos continuam carregando (nada de schema muda; coberto pela suíte)
- [ ] Smoke §6 com LLM real executado e anotado
- [ ] Revisão independente Sol do código aprovada (`handoffs/SPEC-382-sol-independent-review.md`; o
      `handoffs/SPEC-382-independent-review.md` é a revisão desta spec, de 03/11)

## 6. Smoke test com LLM real

Local, `RPG_FORCE_MOCK` desligado, ROUTES padrão (DeepSeek primário), ~10–20 requisições, depois da
Etapa 5:

1. Jogo novo; 1 turno de história com **viagem** para local vizinho (ex.: "viajo para <vizinho de
   `current_location_id`>"). Esperado: narração não vazia e sem `[SISTEMA]` de quarentena espúrio;
   `world.current_location_id` mudou; relógio avançou; nenhum `storyteller.failed` nem
   `log_fallback("storyteller", "structured_invalid")` no log; `mock=False` na telemetria.
2. Com `RPG_CARD_DECK=on`: 1 **combate de cartas completo** (abrir o tabuleiro por encontro ou
   `COMBAT START`, jogar rodadas pela UI ou API até o desfecho). Esperado: abertura narrada, rodadas sem
   chamada LLM (SPEC-346), `conflict_summary` presente no fim, narração de desfecho, `combat.active`
   falso, `next` coerente (`loot` em vitória), nenhum `combat.*failed` no log.
3. Anotar no handoff: provider/modelo por chamada, latência do turno, e que os campos do
   `StoryUpdate` real (`introduced_npcs`, `proposed_events`, `faction_impacts`) chegaram ao estado como
   antes (MockLLM esconde mapeamento de campo; é o motivo deste passo).

## 7. Riscos & compatibilidade

- **Patch inócuo** (o maior risco, §3.1): mitigado por R2/R7/R8. Sinal de alerta na revisão: qualquer
  `from agents.storyteller import`/`from agents.combat import` novo dentro de produto, ou nome global
  copiado para variável local antes de ser chamado (ex.: `llm_fn = get_llm` no topo de um helper).
- **Ordem de mutação**: `world` é mutado in-place (`world["last_encounter_turn"]` l.1599/1621) e
  reatribuído (l.1279, 1817); `scene_state` captura o `world` da hora (l.1479, refeito em l.1840);
  `t.state` é reatribuído pelo `state_patch` (l.1368) e as fases seguintes, inclusive `_fm_view` e o
  fallback (l.2673, 2691), leem o estado já patchado. No combate, `player` é substituído por
  `grant_xp` (l.2793) enquanto `actors_by_id[_PLAYER_ID]` (l.2446) continua apontando para o dict antigo
  e `_compose_board_narrative` recebe os dois (l.2996-3006). O objeto de contexto precisa guardar
  exatamente essas referências; o golden (b) captura a mutação do estado de entrada.
- **Exceções em escopo diferente**: o `except` do storyteller remonta o turno com `sim_updates`,
  `fm_extra`, `fm_events`, `factions`, `world` e `turn_bl_pre_llm` (l.2654-2720). Hoje, se
  `_fm_apply` rodou dentro do `try` (l.2328) e algo depois levantou, o fallback vê `factions`/`fm_extra`
  já atualizados. Se o helper devolvesse os valores só no sucesso, o fallback veria os antigos: por isso
  as fases mutam o `_StoryTurn` in-place, na mesma ordem. Os 11 `try` internos (l.1204, 1269, 1397,
  1450, 1512, 1809, 1982, 1994, 2014, 2313; combate l.2921) migram inteiros com o trecho que envolvem;
  nenhum helper ganha `try` próprio em volta de código que hoje está fora dele.
- **Variáveis locais compartilhadas e ramos**: `chase_state`/`decl` só existem em alguns ramos do
  combate; `_track_entry` e `_describe_track` vivem só no ramo de rastro; `turn_bl` é comparado por
  identidade (§3.2). Default `None` e campos do contexto preservam isso; nada de cópia defensiva.
- **Ordem de eventos de observabilidade**: [F] há testes que capturam `_log_event` e asseveram a lista
  (`tests/test_spec311_planner.py`, `test_spec346_outcome.py`, `test_spec346_spawn_hint.py`,
  `test_spec353_agent.py`, `test_spec325_abandon.py`); `combat.mechanics`/`summary` dependem da ordem do
  `record_step` (SPEC-251, `combat_node` l.2192-2194). O golden (c) cobre.
- **Ordem de import**: imports locais com efeito colateral (ex.: `services.fauna` l.1506,
  `services.faction_membership` l.1233) rodam na mesma ordem relativa (R8).
- **Conflito com sessões paralelas**: W1 revisada por etapa (§4), incluindo `mock_llm.py`, helpers de
  teste e `playtest/runner.py`. Specs que mudam **comportamento** nos mesmos trechos: 377 item 3
  (`_alive`/declarações no `_run_round`) trava a Etapa 3; 384 D3 (`_advance_reinforcements`) e 371
  travam a Etapa 4; 374 (`mock_llm.py`) e 379 R4.4 (helpers de teste) travam a Etapa 1. Golden quebrou
  depois de rebase ⇒ a etapa para (regra geral da §4).
- **Guards de outras specs**: `tests/test_spec363_golden_guard.py:23-25` não tem gate de branch e
  reprova qualquer diff do orquestrador (D6); os guards 353/364/367 só comparam goldens ou têm gate de
  branch e não travam esta spec.
- **Testes que leem código como texto** (R12): mover a linha 2378 para um helper quebraria
  `test_spec297_review_fixes.py:186`; ela fica no orquestrador.
- **Saves antigos**: nenhum campo de `GameState` muda; sem risco de round-trip.
- **MockLLM / FallbackLLM**: guard de `StoryUpdate` (l.2169-2179) e caminho de exceção entram como
  casos do golden.
- **Quota/latência**: zero chamada LLM nova; custo extra de uma chamada de função por fase é
  desprezível. [H] O objeto de contexto não muda latência mensurável (a SPEC-316/319 mede o turno; o
  revisor pode conferir no playtest W2 que o tempo por turno não subiu além do ruído).

## 8. Decisões do dono

- **D1 — `npc_actor_node` (779 linhas) e `_archive_node` (666 linhas) entram?** Recomendação: **não
  nesta spec**; abrir follow-up `refactor-nos-npc-arquivista` com o mesmo método depois que esta pousar
  (109 patches próprios em 32 arquivos; W6 pede uma refatoração por vez).
- **D2 — Ordem em relação à SPEC-378.** Recomendação: storyteller e `_run_round` (Etapas 2–3) podem
  começar antes da 378 se ela estiver parada, porque W1 protege o conflito; o combate (Etapa 4) espera
  a 371 de qualquer jeito. Alternativa conservadora: esperar a 378 inteira antes de começar.
- **D3 — Objeto de contexto (`_StoryTurn`/`_CombatTurn`/`_RoundIntents`) em vez de tuplas.**
  Recomendação: aceitar (§3.2). Alternativa: parâmetros/tuplas explícitos, com orquestradores maiores
  (~350–400 linhas) e mais chance de erro de devolução.
- **D4 — Golden novo versionado em `tests/fixtures/spec382_node_golden.json`.** Recomendação: aceitar e
  apagá-lo numa spec futura (é andaime da refatoração); alternativa: manter como regressão permanente.
- **D5 — Smoke real §6** custa ~10–20 requisições no DeepSeek (centavos). Recomendação: rodar local, não
  no staging.
- **D6 — Exceção W3 para `tests/test_spec363_golden_guard.py::test_engine_modules_untouched_by_spec363`**
  (P0-1 da revisão). O teste faz `git diff --quiet main -- services/conflict_orchestrator.py
  services/conflict_turn.py` sem gate de branch e reprova a Etapa 3, e também a SPEC-377. Opções:
  (a) dar a ele o gate de branch `spec-363` (padrão de `test_spec364_golden_guard.py:30-36`), num commit
  `test:` próprio antes da Etapa 3 (a 363 consta `in-progress` no ESTADO de 02/11; o gate mantém a
  proteção enquanto a branch dela estiver checada); (b) apagá-lo (o golden da 330 continua protegido
  por `test_golden_files_have_no_diff_against_main` no mesmo arquivo e pelo guard da 353); (c) não
  fazer a Etapa 3. **Recomendação: (a)**, uma vez só, servindo também à 377. Quem aplica: o
  coordenador ou o executor da 382, com o dono de acordo, porque o teste é de outra spec.

## Resposta à revisão (`handoffs/SPEC-382-independent-review.md`, 03/11)

| ID | Resposta |
|---|---|
| P0-1 | **Aceito, depende do dono** → D6; R9 ganha a exceção nomeada; Etapa 3.0 aplica antes de qualquer extração do orquestrador. |
| P0-2 | **Aceito pelo desenho, sem exceção W3**: a linha 2378 fica no orquestrador (R12, §3.3); travas de texto dos testes 304/303/298 citadas; varredura `getsource\|read_text` antes de cada etapa. |
| P1-1 | **Aceito**: captura no sink (`caplog` `rpg.*`) + `record_step` (§3.4 c). |
| P1-2 | **Aceito**: ≥ 2 casos de stream com `narrative_sink.bind`. |
| P1-3 | **Aceito**: seed por caso, isolamento por caso, 3 processos + `-n 2`, `_OUTCOME_BUDGET_S` alto; campanha byte-idêntica, degradação só com evidência. |
| P1-4 | **Aceito**: playtest e `check_reproducibility()` rebaixados a sanidade (R11); hash de `last_mech_log`/`record_step` por campanha em A e B. |
| P1-5 | **Aceito**: cobertura por faixa via `trace` da stdlib na Etapa 1 (e de novo na 4.0). |
| P1-6 | **Aceito**: travas 377 item 3 (Etapa 3), 384 D3 (Etapa 4, D7), 374 e 379 (Etapa 1); lista comum do W1 com `mock_llm.py`, helpers de teste e `playtest/runner.py`; regra geral de rebase. |
| P2-1 | **Aceito**: 7 closures; `acted` ligado em l.2862; `enemy_decl` → `self.enemy_decl_inner`. |
| P2-2 | **Aceito**: Etapa 4.0 refaz a tabela de faixas sobre a `main` com a 371 e acrescenta caso com `RPG_FAUNA`. |
| P2-3 | **Aceito**: "SPEC-384 D4". |
| P2-4 | **Aceito**: arquivos do `tmp_path` (nome + sha) entram no golden (§3.4 d). |
| P2-5 | **Aceito**: revisão de código futura em `handoffs/SPEC-382-sol-independent-review.md`. |

Nenhum achado rejeitado. Ajuste factual em relação ao texto da revisão: na D6 (b) não afirmo que a 363
pousou, porque o ESTADO de 02/11 a lista como `in-progress`.
- **D7 — Ordem com a SPEC-384 D3** (apagar `_advance_reinforcements`). Recomendação: decidir a D3 antes
  da Etapa 4; se for "apagar", a 384 pousa antes e a Etapa 4.0 regrava o golden de combate sobre ela.

## Registro de execução (04/11, executor — Etapas 1, 2 e 4)

**Estado:** golden (Etapa 1) + `storyteller_node` (Etapa 2) + `_combat_node` (Etapa 4) prontos na branch `spec-382`
(rebaseada sobre `3cd58353`). **Etapa 3 (`_run_round`) NÃO executada**: a branch viva `spec-373` edita
`services/conflict_orchestrator.py` (W1). Antes dela: acrescentar ≥ 6 casos diretos de `run_round` ao golden
(§3.4) — o golden atual só cobre `run_round` indiretamente (combate e campanhas) — e pousar a D6 (gate de branch em
`test_spec363_golden_guard.py` **já existe**, SPEC-387). Etapa 5 (W2 A/B completo, revisão Sol, smoke) com o coordenador.

**Resultado (linhas por `ast`):** `storyteller_node` 1553 → 118; `_combat_node` 1037 → 125; nenhum helper novo > 100
linhas (maior: `_story_system_message` 93, `_combat_aftermath` 92). Arquivos: `agents/storyteller.py` 2725 → 3020,
`agents/combat.py` 3731 → 3957 (inevitável pelo R2: mesmo módulo; baseline de `tests/size_budget.json` atualizada
só nessas 4 linhas, em commit próprio com o motivo).

**Desvios (registrados, sem mudança de comportamento):**
1. *Contexto de turno único.* `_StoryTurn` (108 campos) e `_CombatTurn` (66) guardam **todos** os locais usados por
   mais de uma fase (inclusive `update`, `llm`, `sys`, `narrative_text`, `out`, `result`); os helpers recebem só `(t)`,
   sem os parâmetros extras da §3.3 (`update`, `llm`, `recent_player_inputs`). Loop-vars e temporários de uma fase só
   ficam locais. Identidade preservada (`turn_bl is not state.get("turn_baseline")` verde pelo golden).
2. *Fronteiras de helper (§3.3 superada).* Teto de 100 linhas por função nova (gate `size_budget`) em vez de 220:
   storyteller — `_story_travel_refusal`, `_story_travel_passage`, `_story_rest_passage`, `_story_world_tick_effects`,
   `_story_membership_and_quests`, `_story_scene_and_replan`, `_story_roll_encounter` (+`_story_fauna_to_signal`),
   `_story_encounter_kind`, `_story_combat_start`, `_story_noncombat_encounter`, `_story_world_pulse`,
   `_story_context_blocks`, `_story_prompt_blocks`, `_story_prompt_scene_blocks`, `_story_system_message`,
   `_story_narrate`, `_story_guard_narrative` (+`_story_prevalidate_events`), `_story_engine_proposals`,
   `_story_beat_and_npcs`, `_story_assemble_{base,items,events,quests}`, `_story_exception_fallback`;
   combate — `_combat_unconscious_refusal`, `_combat_freetext_refusal`, `_combat_open_scene`, `_combat_no_active_result`,
   `_combat_assemble_sides`, `_combat_flee_request`, `_combat_environment`, `_combat_attempt_flee`,
   `_combat_declare_turn`, `_combat_prepare_round`, `_combat_run_round`, `_combat_aftermath`,
   `_combat_outcome_summary`, `_combat_narrate`, `_combat_close_round_{meta,log}`, `_combat_close_encounter`,
   `_combat_result_{base,quests,events}`. `llm = get_llm(...)` fica no orquestrador no mesmo ponto; o `try/except`
   principal e o `return _story_exception_fallback(t)` também (R6). `_fm_view/_fm_apply` viraram funções de módulo `(t, …)`.
3. *Texto-fonte.* `test_spec371_saber` exige os literais `if not is_simulation and _fauna_saber.active()` e
   `if combat_over and not is_simulation and _fauna_saber.active()` (não listados no R12): os dois helpers mantêm
   aliases locais (`is_simulation = t.is_simulation`). O `getsource` do nó que a R12 previa já virou teste de
   comportamento (SPEC-379 R6a). `travel_intent` e `world_before` foram promovidos a campos num commit próprio
   (a divisão viagem/descanso os cruza).
4. *Golden.* `tests/test_spec382_node_golden.py` (+ `spec382_node_golden.py`, `spec382_node_cases.py`, fixture): 17 casos
   diretos de `storyteller_node`, 25 de combate (12 cenários × `RPG_CARD_DECK` off/on + texto livre `on`), 3 de stream
   (`narrative_sink.bind`), 8 campanhas de **30** turnos (4 perfis × deck off/on; `seed=0`) com hash do estado final,
   `last_mech_log` e `record_step`. Partes hasheadas: retorno, estado de entrada pós-chamada, eventos `rpg.*` +
   `record_step`, arquivos em `tmp_path`. Normalização: ids hex (uuid) e `llm.mock_selected` (uma vez por processo).
   Estável em 3 `PYTHONHASHSEED`, `-n 2` e depois de outros testes (commit de correção do harness, sem regravar o
   fixture). Fixture gravado 1× e **nunca regravado**; Etapa 4.0 dispensada (a 371 já estava na `main`; rebase sobre
   a 393 não alterou nenhum hash).
5. *Cobertura por faixa* (`sys.monitoring`, só o golden): `storyteller_node` 473/629 stmts (75 %), `_combat_node`
   374/475 (79 %); toda faixa tem ≥ 1 linha executada. **Não cobertos** (extraídos sem prova do golden, só pelos testes
   de escopo): storyteller — caça/sinal de fauna (`hunt_hint`, `track_signal`, `fauna_to_signal` com `_fnote`),
   `rumor_adoption.commit`, `advance_factions` (motor desligado), `on_faction_defeated`/ascensão, `death_pending` por
   armadilha, `companion_voice_ack`, `archive_low`, item repetido/único reclamado, recusa de item narrado,
   `world_replan` por causa; combate — `manifest_from_legacy`, `card_rewards.expire_pending`/`grant_after_conflict`,
   `_normalize_extra_play`, `chase_state` por condição, absorção/`finish_combat` do saber de fauna, reflexo de aliados
   de cena, `death_pending` (coberto só no ramo off), eventos de abandono (`choices["events"]`). Revisor: prefira ler
   o diff desses trechos.
6. *Evidência por commit.* Golden (53 casos) verde em **cada** commit da série; escopo da Etapa 2 (1013 testes) e da
   Etapa 4 (1267 testes) verdes no HEAD. Não rodei a suíte completa nem W2 A/B (coordenador).
7. *D7.* `_advance_reinforcements` e `_plan_reinforcements` ficaram como estavam.
8. *W1 (04/11):* `spec-373` (conflict_orchestrator, dados de cartas; worktree sujo), `spec-359`, `spec-383-etapa4-wip` (web):
   sem interseção com `agents/storyteller.py`/`agents/combat.py`; `spec-393` mexia em `combat._narrate_outcome` e já pousou
   (rebase feito).
