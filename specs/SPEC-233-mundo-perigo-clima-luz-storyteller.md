# SPEC-233 — Mundo: perigo efetivo, controle dinâmico, luz em masmorra, clima/reforços e exceção do storyteller

> **Status:** `done`
> **Criada:** 2026-10-15 · **Atualizada:** 2026-10-15
> **Depende de:** nenhuma · SPEC-052 weather-global-vivo, SPEC-053 itens-vivos-e-luz, SPEC-020 fase-6.4-encontros-sistemicos e SPEC-090 modo-simulacao-combate `done` são corrigidas (ordem final 2026-10-15)
> **Desbloqueia:** SPEC-210, SPEC-212 (ordem final 2026-10-15)
> **Origem:** auditoria de bugs 2026-10-15 — achados BUG-06-04, 06-09, 06-10, 06-14, 06-15, 06-16, 06-17, 01-10, 01-05, 01-06/07-03 (`achados/06-mundo.md`, `01-grafo-turno.md`, `07-api-frontend.md`)
> **EXECUTOR_MODEL:** `Terra` (≡ Sonnet)
> **REVIEW_MODEL:** `Sol` (≡ Opus em contexto separado) · **REVIEW_REQUIRED:** `false` — mecânica determinística de mundo, sem mudança de schema
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

Fatos reproduzidos/lidos no HEAD `d6af933` (subagente da área 06 executou scripts offline; orquestrador conferiu os
trechos):

- [F] **Perigo efetivo ignorado na chegada** — `world_utils.apply_travel` (`:168`) grava `danger_level = dest["danger"]`
  (base) ignorando `danger_overrides` (`_effective_danger`, `:531`); `recovery_rest_safe`, `detection_check`,
  `roll_encounter_type`, armadilhas e clima global leem `danger_level`. Repro: override 4 em `na_anel_dourado` (base 1)
  → `danger_level 1`, descanso "seguro" de early-game num local que a ascensão tornou perigo 4.
- [F] **Clamp de perigo** — `agents/world_simulator.py:66-78` `max(1, min(4, cur+shift))`: local com `danger 0` (existe
  no mapa) e `shift=-1` → 1 (sobe); drift sem decaimento nem piso por tipo (cidade pode virar 4 em 3 descansos).
- [F] **Luz nunca escura em masmorra** — `world_utils.py:792,888-909`: escuro = noite OU tag `dark`; nenhum nó tem
  `dark` e as masmorras (`pm_cripta_afogada`, `ae_camara_seca`, `ma_forja_profunda`) têm `abrigo` ⇒ `sheltered` ⇒
  nunca escuro. Tocha/lanterna (+22 itens da SPEC-053) são inúteis onde deveriam importar.
- [F] **Controle dinâmico nunca desativado** — `services/graph_resolver.py:107-114` filtra `disabled_ids` só nas edges
  base; `dynamic_edges` (`dyn_*`) são apendadas sem filtro embora `rule_engine.disable_controls_edges` e
  `location_control_changed` registrem ids `dyn_*` em `disabled_edges`. Repro: controlador segue `mao_sombria` após
  desativar a edge.
- [F] **`encounter_eff_danger` grudado** — `world_utils.py:745-746` grava a flag sempre que passa do cooldown mesmo
  retornando `None`; consumo único em `agents/combat.py:227` → próximo combate deliberado usa o orçamento de outro
  local/nível.
- [F] **Reforços prometidos somem** — `_pop_active_alert` consome o alerta (`:581-593,749-755`) e o storyteller (`:428-430`)
  suprime por dedupe (`hint == last_encounter_id` no mesmo local).
- [F] **Duração do clima por chamada** — `advance_weather` decrementa `periods_left` 1× por chamada (`:840-844`), não por
  período avançado; descanso bloqueado por clima avança relógio 1 e fações 2 (`storyteller.py:367`).
- [F] **Exceção no storyteller descarta mecânica aplicada** — `agents/storyteller.py:1017-1028` devolve só `messages`
  (e `world` se `dest`): `rested_player`, relógio do descanso, `discovery_player`, armadilha e `factions` somem, mas o
  texto (nota interna em 3ª pessoa) diz "O jogador DESCANSOU… recuperou parte das forças". `looted_locations` já
  mutado in-place → baú consumido sem entrega.
- [F] **Laboratório de combate encerrado vira campanha** — `main.py:63-71,122-134` e `api.py:3319-3339`: com
  `combat_simulation.enabled` e `combat.active=False`, a próxima ação passa por router/NPC/RAG/arquivista reais. Repro
  via API: `xp 0→150`, local "Arena do Véu"→"Brekmar", memória gravada no RAG (SPEC-090 só isolava no cliente).

Objetivo: um único perigo efetivo por local; luz coerente com o mapa; controle do grafo respeita desativações;
flags one-shot realmente one-shot; clima por período; storyteller nunca narra mecânica que não aplicou; laboratório
isolado também no servidor.

## 2. Requisitos

- **R1** — [R] `apply_travel`/`ensure_world` gravam `danger_level = _effective_danger(world, dest_id)`; todo leitor de
  `world["danger_level"]` passa a usar `effective_danger(world)` (helper único). Teste de reprodução: override 4 →
  `danger_level == 4`, `recovery_rest_safe == False`.
- **R2** — [R] `world_simulator._apply_danger_shift`: clamp `[max(0, base-1), min(4, base+1)]` por local (drift ±1 em
  torno do base), decaimento de 1 em direção ao base a cada 10 turnos sem novo shift, shift positivo ignorado em locais
  com tag `abrigo|cidade`. Teste: base 0 + shift −1 → 0; cidade base 1 + 3 shifts +1 → 2.
- **R3** — [R] Luz: `is_dark_location(loc)` = tag `dark` OU `masmorra` OU `caverna` OU `subterraneo`; `dark` tem
  precedência sobre `abrigo` (abrigo protege do clima, não ilumina). Teste: `pm_cripta_afogada` de dia sem tocha →
  `light_level == "escuro"`, com tocha → `"iluminado"`.
- **R4** — [R] `graph_resolver.resolve_edges`: `disabled_ids` filtra `base + dynamic`. Teste de reprodução:
  `dyn_abc` desativada → `get_current_controller == None`/próximo válido.
- **R5** — [R] `encounter_eff_danger` só é gravado quando `check_encounter` devolve um encontro de combate; o storyteller
  limpa a flag quando o resultado é `None`/não-combate. Teste: local seguro → `None` e flag ausente.
- **R6** — [R] Alerta de reforço só é consumido quando o encontro é efetivado; `reason in {"reinforcements",
  "controlled"}` não sofre dedupe por `last_encounter_id`. Teste: `register_flee_alert` → voltar ao local → encontro
  `reinforcements` ocorre 1× e o alerta some depois.
- **R7** — [R] `advance_weather(world, *, steps: int)` ticka `steps` vezes (viagem de 3 períodos consome 3 de duração);
  fações avançam pelo delta real do relógio (`advance_factions(factions, steps)`), inclusive no descanso bloqueado.
  Teste: Tempestade de Éter (4) + viagem de 3 → `periods_left == 1`.
- **R8** — [R] `storyteller` `except Exception` devolve TODA mecânica já aplicada (`player` = `rested_player`/
  `discovery_player`, `world`, `factions`, `pending_world_events`) e converte a nota interna em texto diegético de 2ª
  pessoa; se a mecânica NÃO foi aplicada, a mensagem não a promete. Teste de reprodução: provider levanta durante
  descanso → Vitalidade e relógio avançam; texto em 2ª pessoa sem "O jogador DESCANSOU".
- **R9** — [R] Laboratório de combate: `main.py` (gate de START) e `api._execute_action`/`/game/equip`/`/game/levelup`
  recusam ação quando `combat_simulation.enabled and not combat.active` (409 `simulation_finished`; grafo → `END` com
  mensagem). Teste de reprodução: vitória no simulador → `POST /game/action "Viajo para Brekmar"` → 409, `xp 0`,
  `archivist_last_run` inalterado, nada em `data/saves_memory/`.

### Fora de escopo

- Parsers de viagem (spec `SPEC-229`); NPC em cena (spec `SPEC-230`); recompensas (spec `SPEC-226`).
- `blocked_routes` para o jogador (SPEC-017 decisão); mapa/viagem como turno (SPEC-210).
- Tabela de clima/efeitos (valores) — só duração/aplicação.

## 3. Design técnico

### Arquivos alterados

- `world_utils.py` — `effective_danger` helper (R1), `is_dark_location`/`light_level` (R3), `check_encounter` flag
  one-shot (R5), alertas (R6), `advance_weather(steps=)` (R7).
- `agents/world_simulator.py:66-78,120-138` — clamp/decaimento (R2); `state.py` `world.danger_overrides[loc] = {value,
  base, last_shift_turn}` (compatível: int legado = value).
- `services/graph_resolver.py:107-114` — filtro nas dinâmicas (R4).
- `agents/storyteller.py:367,428-430,1017-1028` — fações por delta (R7), dedupe (R6), `except` (R8).
- `main.py:63-71,122-134`, `api.py:3319-3339` + equip/levelup — gate do laboratório (R9).
- `data/world_map.json` — opcional: tag `dark` explícita nos 3 interiores (R3 cobre por `masmorra` de qualquer modo).

## 4. Plano passo a passo

### Etapa 0 — Testes de reprodução (vermelhos no HEAD)
`tests/test_bug_mundo_perigo_luz_clima.py`: `test_travel_uses_effective_danger` (R1), `test_danger_shift_clamp_and_decay`
(R2), `test_dungeon_is_dark_without_torch` (R3), `test_disabled_dynamic_edge` (R4), `test_eff_danger_flag_one_shot` (R5),
`test_reinforcement_alert_not_deduped` (R6), `test_weather_duration_by_steps` (R7), `test_storyteller_exception_keeps_rest`
(R8), `test_finished_simulation_rejects_action` (R9).
### Etapa 1 — R1, R2, R4, R5 (perigo/controle/flags)
### Etapa 2 — R3, R6, R7 (luz/reforços/clima)
### Etapa 3 — R8, R9 (storyteller/laboratório)
### Etapa 4 — regressão `uv run pytest` + playtest offline `explorador`/`normal` 40 turnos: `danger_level ==
effective` em todo turno (invariante nova `world.danger_mismatch`, warning).

## 5. Critérios de aceite

- [x] 9 testes vermelhos → verdes; `tests/test_fase0.py`, `test_weather*.py`, `test_luz*.py`/`test_itens_vivos*.py`,
      `test_fase25.py`, `test_fase2*.py`, `test_combat_simulator.py` verdes ou diff justificado.
- [x] `uv run pytest` verde; playtest offline com run_id e invariante nova sem violação.
- [x] Saves antigos carregam (`danger_overrides` int legado aceito).
- [x] Guard de FallbackLLM: não se aplica.

## 6. Smoke test com LLM real

1. Entrar na Cripta Afogada de dia sem tocha → bloco de luz "escuro", percepção penalizada; acender tocha → normal.
2. Descansar com provider instável → se a narração diz que descansou, a Vitalidade subiu.
3. Simulador de combate: após vitória, enviar texto → 409 diegético, sem XP.

## 7. Riscos & compatibilidade

- R1 pode aumentar encontros em locais com override alto (comportamento correto) — observar `% combate` no playtest.
- R3 muda a dificuldade de masmorras (penalidade −3/−1 sem luz): coerente com SPEC-053; os 4 itens de luz passam a
  ter uso real.
- R9 altera o contrato do simulador para clientes de API: documentar no README do simulador.

## 8. Pontos de decisão do dono

- **D-A (decaimento do perigo):** 10 turnos (default) ou por dia do relógio.
- **D-B (luz em masmorra):** tag implícita por `masmorra` (default) ou só `dark` explícita no mapa (mais curadoria).

## 9. Evidência requerida

- `uv run pytest` completo; testes antes/depois; run_id do playtest com a invariante `world.danger_mismatch`.
- `docs/<spec>/README.md` com os scripts da área 06 transcritos e a repro da API do laboratório (área 07).

## 10. Implementação (2026-10-16)

- Defaults de decisão usados: **D-A** decaimento a cada 10 turnos (`world.danger_shift_turns`); **D-B** tag implícita
  (`masmorra|caverna|subterraneo|dark`, precedência sobre `abrigo`).
- Desvio: `danger_overrides` segue int (dict aceito na leitura); o carimbo do último shift mora em `danger_shift_turns`
  (sem mudança de `schema_version`). Shift negativo em base 1 agora vai a 0 (`max(0, base-1)`, literal da spec).
- `advance_weather(world, rng=None, *, steps=1)`; viagem/descanso chamam o tick por período. Fações do descanso
  bloqueado avançam 1 período. Gate do laboratório: `main.py` (START) + `api._reject_memorial` (409 `simulation_finished`,
  cobre action/equip/levelup/arte).
- Invariante `world.danger_mismatch` (warning) em `playtest/invariants.py`. Playtest offline 40t: explorador
  `20261016-023806-197930` e normal `20261016-023809-277698`, 0 violações.
- Testes alterados com justificativa: `test_world_sim`, `test_turn_pipeline_concurrency`, `test_conflict_summary_lifecycle`
  (cidade ignora shift +1 / piso passa a base-1).
