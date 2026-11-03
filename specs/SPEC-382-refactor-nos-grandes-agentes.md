# SPEC-382 — Refatoração pura dos nós grandes: `storyteller_node`, `_combat_node` e `_run_round` em fases nomeadas no mesmo módulo

> **Status:** `draft`
> **Criada:** 2026-11-03 · **Atualizada:** 2026-11-03
> **Origem:** auditoria de qualidade de 03/11 (`docs/auditorias/auditoria-qualidade-codigo-2026-11-03.md`
> §4.2 itens 1–2, §5 letra F, §6 regras W1–W8, §6.3 ordem 7)
> **Depende de:** SPEC-371 **pousada** (só para a parte de combate, Etapas 4.x: ela edita
> `agents/combat.py` e `playtest/*` agora). SPEC-378 (helpers comuns) **recomendada antes**: ela
> mexe em `_last_human_text`, `_fold` e nos guards `isinstance` destes mesmos arquivos (§4.2 itens 3 e 6).
> **Desbloqueia:** SPEC-384 item N (tirar o caminho de combate sem tabuleiro fica localizado em
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
- [F] `_run_round`: `services/conflict_orchestrator.py:2517-2999` = **483 linhas**, com 6 closures que
  compartilham estado mutável da rodada (`_next_intent` l.2623, `_frustrate` l.2629, `_spend_taunt`
  l.2651, `_taunt_same_round` l.2667 com `swap` aninhado l.2699, `_enemy_decl`/`_enemy_decl_inner`
  l.2716/2726 com `late` aninhado l.2727, `_tf_acted` l.2864).

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
- **R3 — Closures viram parâmetros explícitos.** `_fm_view`/`_fm_apply` (storyteller) e as 6 closures
  de `_run_round` saem do corpo do nó e passam a receber o estado compartilhado por parâmetro (objeto de
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
- **R10 — Um commit por extração** (W4), cada um revertível sozinho com `git revert <sha>`, com o
  golden e os testes de escopo verdes em cada commit.
- **R11 — W2 completo** antes (baseline A, Etapa 0) e depois (B, Etapa 5): suíte completa verde;
  `evals compare --current B --baseline A` sem diferença; `playtest run --all --turns 10` com
  `--seed 0` e `--seed 1` com mesma contagem de violações por perfil e mesmo desfecho
  (vivo/morto/turnos); `playtest.invariants.check_reproducibility()` → `True`.

### Fora de escopo

- Mover qualquer helper para arquivo/pacote novo (`agents/storyteller/…`, `agents/combat/…`). Fica
  como follow-up, que exige reexports e migração dos alvos de patch (§3.1).
- `npc_actor_node` (`agents/npc.py:861-1639`, ~779 linhas) e `_archive_node`
  (`agents/archivist.py:587-1252`, ~666 linhas): passam do limite de 480, mas a auditoria não os
  mapeou, têm 109 `monkeypatch.setattr` próprios em 32 arquivos e o W6 pede uma refatoração por vez.
  Ver **D1**.
- Qualquer mudança de comportamento, inclusive "bug óbvio" visto de passagem: vai para nota no
  hand-back (o ex.: SPEC-377 cuida das divergências conhecidas).
- Os helpers da SPEC-378 (`invoke_structured`, `text.fold`, `flags.mode`): se a 378 não tiver pousado,
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
  `rng`, `scene_state`; as 6 closures viram métodos (`next_intent`, `frustrate`, `spend_taunt`,
  `taunt_same_round`, `enemy_decl`, `tf_acted`) com o mesmo corpo. `swap` e `late` continuam aninhadas.

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
| dentro do `try`: `_story_beat_and_npcs(t, update)` | 2334-2401 | XP de beat, `campaign_plan`, `introduced_npcs`/`npcs_left_scene` |
| dentro do `try`: `_story_assemble_updates(t, update)` → `dict` | 2403-2652 | itens narrados (2433-2513 pode virar `_story_narrated_items`), recibo, eventos, quests, rumores, `archive_low` |
| no `except`: `_story_exception_fallback(t)` → `dict` | 2655-2720 | o `except Exception as e:` e o `_log_event("storyteller", "failed", …)` ficam no orquestrador; só o corpo da montagem do fallback vira helper |

**`_combat_node`** (o wrapper `combat_node` l.2185-2203, com `mechanics_trace.scope()` e o
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
| `_RoundIntents(...)` + `freeze()` | 2609-2621 e closures 2623-2763 |
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
- **Casos de campanha:** fingerprint no formato de `tests/test_spec360_flags_off.py:27-52` para os 4
  perfis vitais (`explorador`, `combate`, `diplomatico`, `secret_rusher`), 10 turnos, `seed=0`, com
  `RPG_CARD_DECK` `off` e `on`, mais hash do estado final inteiro normalizado.
- **O que se grava por caso:** hash e (em falha) diff legível de: (a) dict devolvido normalizado
  (mensagens → `(tipo, content)`, `sort_keys`, `default=str`); (b) estado de entrada **após** a
  chamada (pega mutação in-place); (c) sequência ordenada de eventos capturados por patch em
  `agents.storyteller._log_event`, `agents.combat._log_event`, `observability.telemetry.log_fallback`,
  `services.intent_guard.log_intent_guard` e `services.mechanics_trace.record_step`.
- **Estabilidade:** na Etapa 1 o teste roda 2× seguidas e 1× com `-p no:randomly`/ordem diferente
  antes do commit; campo instável (uuid, timestamp, latência) vai para uma lista `VOLATILE` explícita
  **nessa etapa**. Depois da Etapa 1 a lista e o fixture não mudam (W3). [H] Os caches globais de
  conteúdo gerado (`playtest/invariants.py:1763`) podem tornar os casos de campanha não byte-estáveis
  entre execuções; se isso acontecer, os casos de campanha passam a comparar só a parte estável
  (turnos/rota/local/vitalidade/ouro/nível/flags de combate), decidido e registrado na Etapa 1.
- **W2** (auditoria §6.2) roda em A (Etapa 0) e B (Etapa 5): suíte completa (coordenador), evals das 12
  suítes do `eval-gates.yml` com `--seed 7` + `evals compare` sem diferença, `playtest run --all
  --turns 10` com `--seed 0` e `--seed 1`, `check_reproducibility()`.

### 3.5 Arquivos

- **Alterados (produto):** `agents/storyteller.py`, `agents/combat.py`,
  `services/conflict_orchestrator.py` (só reorganização interna; R2/R7/R8).
- **Novos (teste):** os 3 da §3.4. Evidência de A/B em `handoffs/SPEC-382-equivalence.md` (tabela de
  violações/desfechos por perfil e seed, saída do `evals compare`).
- **Não tocados:** `playtest/*`, `evals/*`, testes existentes, goldens existentes, `main.py`, `state.py`.

## 4. Plano passo a passo

Antes de **cada** etapa: W1 (auditoria §6.2) com a lista de arquivos da etapa; interseção não vazia ⇒
a etapa espera. W6: só esta spec de refatoração em voo; RAM < 3 GB ⇒ não dispara. Testes de escopo com
no máximo `-n 2`; a suíte completa é do coordenador.

### Etapa 0 — Baseline A e travas

1. W1 para `agents/storyteller.py`, `services/conflict_orchestrator.py` e `agents/combat.py`. [H] Em
   03/11 só `combat.py` estava quente (SPEC-371, auditoria §6.3); storyteller e orquestrador estavam
   livres. Confirmar com o comando do W1 no dia.
2. Rodar W2-A e gravar em `handoffs/SPEC-382-equivalence.md`.
3. Registrar o SHA da `main` usado como A.

### Etapa 1 — Golden de nós (antes de qualquer extração)

1. **Testes:** `tests/test_spec382_node_golden.py::test_storyteller_cases`,
   `::test_combat_cases`, `::test_run_round_cases`, `::test_campaign_fingerprints` assertam igualdade
   com o fixture; `::test_golden_is_stable` roda 2 casos 2× e asserta hashes iguais.
2. **Implementação:** só os arquivos de teste da §3.4; código de produto intocado.
3. **Verificação:** verde no código intacto, 2× seguidas. Commit único `test: add SPEC-382 node golden`.

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

### Etapa 3 — `_run_round` (W1 livre)

Após cada linha: golden + `tests/test_card_effects_grammar.py` (usa `spec330_legacy_golden.json`) +
`tests/test_spec339_duracao_condicoes.py tests/test_spec346_mech_log.py tests/test_enemy_intent_node.py
tests/test_spec355_*.py tests/test_spec295_chefe_no_topo.py`.

1. `_RoundIntents` (6 closures → métodos).
2. `_round_new_out` + `_round_refusal` + `_round_scene_start`.
3. `_round_start_of_round` + `_round_sequence`.
4. `_round_actor_loop`.
5. `_round_end`.

### Etapa 4 — `_combat_node` (só depois da SPEC-371 pousada + W1 livre + golden reconferido)

0. Se a 371 mudou `combat.py`/`playtest/*` depois da Etapa 1, o golden de combate e de campanha foi
   gravado sobre código antigo: **regravar só os casos de combate/campanha** sobre a `main` com a 371,
   num commit próprio `test: refresh SPEC-382 combat golden after SPEC-371`, antes de qualquer
   extração de combate, e anotar no handoff. É a única regravação permitida.
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
- [ ] R3: sem `nonlocal` em `storyteller.py`; sem as 6 closures dentro de `_run_round`
- [ ] R4/R5: `tests/test_spec382_node_golden.py` verde em **todos** os commits da série (provado commit a commit no handoff)
- [ ] R6: revisor confirma, por commit, que o `try` principal do storyteller cobre o mesmo bloco e o fallback lê os mesmos valores
- [ ] R9: nenhum teste existente alterado
- [ ] R10: um commit por extração; cada um revertível sozinho
- [ ] R11: W2 A = B (evals sem diferença; violações/desfechos iguais em `--seed 0` e `--seed 1`; `check_reproducibility()` `True`)
- [ ] `uv run pytest` verde (suíte completa offline, coordenador)
- [ ] Guard de FallbackLLM preservado (`isinstance(update, StoryUpdate)` segue antes de qualquer acesso a campo)
- [ ] Saves antigos continuam carregando (nada de schema muda; coberto pela suíte)
- [ ] Smoke §6 com LLM real executado e anotado
- [ ] Revisão independente Sol aprovada (`handoffs/SPEC-382-independent-review.md`)

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
- **Conflito com sessões paralelas**: W1 por etapa; combate só após a 371; se a 378 pousar no meio,
  rebase antes da próxima etapa e regolden **não** é permitido para storyteller/orquestrador (a 378 é
  "só cópias equivalentes"; se o golden quebrar após o rebase, quem quebrou foi a 378 e a etapa para).
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
