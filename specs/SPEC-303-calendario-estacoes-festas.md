# SPEC-303 — Calendário: estações, passos de montanha e festas da lore

> **Status:** `in-progress` (implementada em 2026-10-24; aguarda revisão independente Opus)
> **Criada:** 2026-10-23 · **Atualizada:** 2026-10-23
> **Origem:** `docs/mundo-vivo/VISAO.md` (§"A. Mundo autônomo" → Calendário; §Calibração → duração da campanha; Regra de ouro) e SPEC-302 §9 (filha **302-B**)
> **Depende de:** SPEC-302 (`approved`; precisa estar `done` no marco M2: hooks diários, `world_sim`, estado `festa`, digest/percepção, `world.news`), SPEC-215 (`done`, propagação), SPEC-233 (`done`, perigo efetivo), SPEC-285 (`done`, metas de letalidade que não podem regredir)
> **Desbloqueia:** 302-D (quests de mundo podem ancorar prazo em festa/estação), frente D (luz da "Noite Longa" em Skallgard, overlay de neve)
> **EXECUTOR_MODEL:** `Sonnet` (bounded sobre os hooks da 302) · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (writer persistente novo em `world_sim.calendar`, payload novo de `location_state_changed`, mexe em clima/viagem/encontro)
> **EVAL_AUTHORING_REQUIRED:** `false` (calibração estende o simulador determinístico da SPEC-302)

---

## 1. Contexto & Objetivo

Valoria não tem tempo cíclico. O relógio é só `{day, period}` e avança em viagem
e descanso; nada no motor sabe se é inverno, e o clima é uma cadeia de Markov fixa
por região que se comporta igual no dia 3 e no dia 300. A lore descreve um norte
com "noite de seis meses" e "inverno de seis meses", passagens de montanha que
"deslizamentos redesenham", um deserto que queima e um pântano que cresce "a cada
ano", mas o jogo não expressa nada disso. Também não há festa ou data: a única
data citada como costume ("Noite do Silêncio") não tem definição, e a lore diz
explicitamente que o herói da guerra "não tem feriado".

Esta spec cria o **calendário**: um ano de 4 estações com duração em dias,
**derivado de forma determinística** do `game_id` e do dia em que o mundo vivo
ligou, sem lua e sem dia de mercado (decisão do dono). A estação **modula**
sistemas que já existem, sem criar mecânica paralela:

- **clima** — multiplica pesos de transição de `data/weather.json`;
- **viagem** — o passo de montanha para Skallgard fecha no inverno;
- **encontros** — redistribui pesos entre criaturas do mesmo porte, sem mexer no
  gatilho nem no perigo;
- **pressões** — desloca a *baseline* de deriva das pressões da SPEC-302 (fome no
  inverno do norte e no verão de Zhur, praga na cheia do pântano).

E cria **festas e datas** (lista proposta, derivada da lore, para o dono revisar),
que viram o estado de local `festa`, reservado pela SPEC-302 R16 para esta spec.

Princípios: mecânica em Python e determinística; a LLM só narra e não ganha
chamada nova; regra de ouro (o jogador só sabe da festa que viu ou ouviu); o
mundo não escala com o herói; a campanha não tem duração fixa, então o calendário
**garante uma virada de estação cedo** em todo jogo, em vez de assumir quantos
dias o jogador vai jogar.

### 1.1 Problemas com evidência

| # | Problema | Evidência |
|---|---|---|
| P1 | Não há calendário: o relógio é `{day, period}` e nada deriva estação dele | `world_utils.py:11` (`PERIODS`), `:64-73` (`advance_clock`); `docs/mundo-vivo/VISAO.md:17-18` ("Não há calendário") |
| P2 | O clima é uma cadeia fixa por região, igual o ano inteiro | `data/weather.json:25-58` (skallgard/zhur/montanhas), `:2-12` (default); `world_utils.py:1178-1204` (`_advance_weather_once` usa os pesos crus em `:1200-1201`) |
| P3 | A lore pede ciclo sazonal forte no norte e não há nenhum | `lore_nova/creatures.txt:64` ("noite de seis meses"); `lore_nova/items.txt:139` ("inverno de seis meses"); `lore_nova/daily_life.txt:201` ("quota da estação"), `:213` ("quantos invernos faltam") |
| P4 | O frio do norte e o calor de Zhur são condição do Abismo, não clima: a estação **modula**, não cria nem desliga | `lore_nova/timeline_completa.txt:160`; `data/world_map.json:398` (`lore_seed` de Skallgard) |
| P5 | Skallgard só tem uma saída para fora da região, pelas Montanhas Afiadas: um bloqueio duro no inverno prende o jogador | `data/world_map.json:392-397` (conexões de `skallgard`), `:605-618` (`montanhas_afiadas`, tag `passagens`, `travel_times.skallgard = 2`) |
| P6 | A viagem não lê rotas bloqueadas, e `route_blocked`/`route_cleared` não têm dono por motivo: um `route_cleared` sazonal apagaria o bloqueio de um cerco (SPEC-302 R19) no mesmo par | `services/event_processor.py:181-188` (dedupe por par), `:207-213` (clear por par, sem motivo); SPEC-302 §2 Fora de escopo ("o `world_utils` não lê `blocked_routes`") |
| P7 | A lore não tem festa datada. Há só candidatos: um costume citado sem definição, uma procissão espectral "em noites específicas", eras com marcos | `lore_nova/npcs.txt:88` ("não há feriado"); `lore_nova/daily_life.txt:137` ("Noite do Silêncio. Ninguém abre."); `lore_nova/creatures.txt:492` (procissão de Vaelorn); `lore_nova/timeline_completa.txt:218`, `:318`, `:340`, `:368`, `:432` |
| P8 | A duração da campanha varia por jogador; um ano longo com início fixo faria campanhas curtas nunca verem estação mudar | `docs/mundo-vivo/VISAO.md:187-189`; SPEC-302 R32 (o playtest mede dias por perfil, ainda sem número) |

## 2. Requisitos

### Calendário

- **R1 — Ano e estações.** O ano tem 4 estações, em ordem fixa
  `primavera → verao → outono → inverno`, cada uma com `SEASON_DAYS` dias
  (`[BALANCEAR]`, recomendação 14 — decisão D1). `YEAR_DAYS = 4 × SEASON_DAYS`.
  Sem lua, sem semana, sem dia de mercado (teste: o módulo não define nenhum
  ciclo além de ano/estação).
- **R2 — Função pura.** `season_at(cal, day) -> SeasonInfo` devolve
  `{season, day_in_season, year, day_of_year}` só a partir dos parâmetros
  persistidos do calendário e do dia. Mesma entrada, mesma saída. Sem `random`
  global (teste por AST, como na SPEC-302 R3).
- **R3 — Início semeado com virada cedo garantida.** Na criação do calendário,
  `day_rng(game_id, anchor_day, "calendar")` sorteia a estação inicial (uniforme
  entre as 4) e `k ∈ [FIRST_TURN_MIN, FIRST_TURN_MAX]` (4..8). O `epoch_offset` é
  calculado para que a **primeira virada de estação aconteça em
  `anchor_day + k`**. Assim toda campanha, curta ou longa, vê ao menos uma
  troca de estação na primeira semana de jogo, sem assumir duração (P8).
- **R4 — Congelamento.** Os parâmetros (`season_days`, `epoch_offset`,
  `anchor_day`, `version`) são gravados em `world_sim.calendar` na criação e
  **nunca** recalculados: mudar `SEASON_DAYS` no código não muda a estação de
  saves existentes (teste).
- **R5 — Âncora.** Jogo novo: `anchor_day = 1`, criado no fluxo de novo jogo
  (`world_engine.ensure_world_sim(state, 1)` logo após o `game_id` existir).
  Save antigo: `anchor_day = world_sim.enabled_from_day` da migração da SPEC-302
  R29, sem simulação retroativa. Antes do calendário existir, toda leitura de
  estação devolve `None` e todos os modificadores são neutros.
- **R6 — Perfis regionais de nome.** O `season` canônico é global; o **rótulo**
  exibido vem de `data/world/calendar.json` por região (decisão D2). Proposta:
  default "Primavera/Verão/Outono/Inverno"; `skallgard` "Dia Longo" (primavera e
  verão) e "Noite Longa" (outono e inverno), o que dá a noite de seis meses da
  lore (P3); `deserto_zhur` "Estação do Vidro" no verão.
- **R7 — Hook `pre`.** O calendário roda como hook `pre` do tick diário da
  SPEC-302 (§3.4, passo 1), com `order` 10. Por dia `d`, nesta ordem: calcula a
  estação; se mudou, emite digest `estacao`; atualiza `world["season"]`; devolve
  os deslocamentos de baseline do dia (R12); abre, cancela e encerra festas
  (R15–R19). Idempotente pelo `last_ticked_day` da 302 (teste de replay).

### Clima

- **R8 — Multiplicadores de transição.** `_advance_weather_once` multiplica cada
  peso de transição por `weather_mult[region][season][estado_destino]` (default
  1,0), arredonda e clampa em ≥ 0. Se a soma der 0, usa os pesos crus. A estação
  vem de `world["season"]["id"]`, sem plumbing novo nos chamadores
  (`apply_travel`, `apply_rest`). Regiões sem tabela em `weather.json` usam o
  perfil `default`. Tabela proposta na §3.5.
- **R9 — Sem estado novo de clima.** Esta spec não adiciona nem remove estados de
  `weather.json` e não muda `weather_effects` (os efeitos continuam leitura do
  estado atual). Não torna o clima determinístico (fora de escopo, herdado da
  302).

### Viagem — passos de montanha

- **R10 — Passos sazonais como leitura.** `data/world/calendar.json` lista os
  passos (`{id, a, b, closed_in: [season…]}`). Proposta: um passo,
  `montanhas_afiadas ↔ skallgard`, fechado no `inverno`. O fechamento é
  **derivado** da estação (como o clima: leitura, nunca condição gravada) e
  **não** usa `route_blocked`/`route_cleared` (P6).
- **R11 — Travessia de inverno (decisão D4, opção recomendada a).** Viajar por
  um passo fechado **é permitido** e custa `PASS_EXTRA_PERIODS` (2,
  `[BALANCEAR]`) a mais em `travel_cost`; ao chegar, o clima do destino é forçado
  ao estado de neve da região (`nevasca`). O storyteller recebe uma nota
  determinística ("O passo está fechado pela neve; a travessia leva o dia
  inteiro."), que vira fato para o narrador. Nunca há recusa, então não há
  softlock em Skallgard (P5).
- **R11b — Comércio (decisão D5).** Com D5 = sim, `economy.is_reachable` trata o
  passo fechado como par bloqueado (une `seasonal_closed_pairs(state)` a
  `_blocked_pairs`). Skallgard fica sem abastecimento externo no inverno (preço
  ×`SCARCE_MULT` de `services/economy.py:118` nos bens de fora), coerente com
  `lore_nova/items.txt:139`.

### Pressões

- **R12 — Deslocamento de baseline, não delta.** O hook devolve
  `baseline_offsets[region][pressure]` do dia, a partir da tabela por
  `(região, estação)` da §3.5. A SPEC-302 usa `baseline + offset` como alvo da
  deriva (R7c dela) **só nesse dia**. A estação muda o ponto de equilíbrio, não
  soma pressão acumulada.
- **R13 — Estação sozinha não abre crise.** Validação de dados (teste):
  `baseline + offset ≤ SINAL` para toda região, estação e pressão. Simulador: com
  as causas por evento desligadas, 0 crises em 120 dias × 20 seeds; a estação só
  produz sinais.
- **R14 — Sem slot de crise.** O calendário **não** chama
  `request_crisis_slot`: festa não é crise e a estação só move baseline. (Ajuste
  de texto da SPEC-302 R15, que cita o calendário como usuário do slot.)

### Encontros

- **R14b — Pesos sazonais.** No caminho ponderado de `pick_encounter_enemy`
  (`world_utils.py:937-943`), o peso de cada criatura é multiplicado por
  `encounter_mult[region][season][enemy_id]` (default 1,0). Não muda o gatilho
  (`check_encounter`), o perigo, o porte (`tier`) nem o caminho legado sem
  `projection` (`:914-915`). Todo `enemy_id` da tabela existe em
  `data/bestiary.json`, não é BOSS e tem a região em `regions` (teste).

### Festas e datas

- **R15 — Catálogo.** `data/world/festivals.json` lista festas com `{id, name,
  location_ids, season, day_in_season, duration_days, label, effects?,
  lore_refs, review}`. `day_in_season ≤ 10` (válido com qualquer `SEASON_DAYS ≥
  10`). `location_ids` só não-interiores (o interior herda pelo `parent_id`,
  SPEC-302 R16). Lista proposta na §3.6, toda com `review: "dono"` até a
  aprovação (D3).
- **R16 — Festa = estado `festa` via evento.** No dia de início, cada local da
  festa recebe `location_state_changed` (`source="engine"`) com
  `payload={state:"festa", previous:"", severity:1, cause:"calendario",
  festival_id, crisis_id:<festa_id>}`. `festa_id =
  sha256(game_id|festival_id|year)[:16]`. No fim (`start + duration_days`), o
  evento de volta (`state:""`) só é emitido se o local **ainda** estiver em
  `festa` com o mesmo `festa_id`.
- **R17 — Crise vence festa.** A festa não começa num local com qualquer estado
  (cerco, escassez, praga, ocupado, ruína, corrompido) nem numa região com crise
  anunciada ou ativa da SPEC-302. Nesse caso ela é **cancelada naquele ano**:
  gera digest `festa_cancelada` (visibilidade regional), sem evento. Se uma crise
  abre durante a festa, o estado da crise sobrescreve (um estado por local) e o
  fim da festa não emite nada (R16).
- **R18 — Efeitos.** `location_effects` (SPEC-302 R19) usa o efeito de `festa`
  de `data/world/location_states.json`, com override por festival
  (`festivals.json.effects`: `price_mult`, `restock_mult`, `merchant_closed`).
  `public_label` usa o `label` da festa ("em festa", "em silêncio", "em luto").
  Festa não muda perigo (`danger_delta` 0) nem pressão.
- **R19 — Anúncio (telegrafado).** `FESTIVAL_HERALD_DAYS` (2) antes do início,
  o hook gera digest `festa_proxima` com visibilidade regional. Não é
  `GameEvent`.

### Percepção, narração e API (regra de ouro)

- **R20 — Percepção.** Todos os itens novos passam pelo filtro da SPEC-302 R23:
  - `estacao` tem visibilidade nova `global`: a estação é visível de qualquer
    lugar (céu e frio). É o único tipo com essa visibilidade (teste);
  - `festa_proxima`, `festa_cancelada` e `passo` (fechou/abriu) são `regional`;
  - início de `festa` é testemunho local/regional e se propaga como rumor pela
    SPEC-215, porque é `location_state_changed` (já em `SUBJECT_PARAMS` pela 302
    R27);
  - **ninguém sabe de festa em região distante sem ter ouvido** (teste: jogador
    em `nova_arcadia`, festa em `skallgard`, SPEC-215 `off` → nenhum item).
- **R21 — Sem chamada LLM nova.** Os itens entram no digest que a 302 já narra
  (≤ 1 chamada por ação que vira dia, R26 dela). O contexto do storyteller ganha
  uma linha determinística com o rótulo regional da estação ("Estação: Noite
  Longa"). Nenhum campo vindo da LLM altera calendário, festa ou passo.
- **R22 — API.** `_world_block` (`api.py:2792-2836`) ganha `season: {id,
  label} | null` (rótulo regional do local atual). A festa aparece só pelo
  `location_state` do local atual (302 R31). Passos e calendário de festas
  **não** saem pela API (teste: nenhuma resposta contém `festivals`,
  `epoch_offset` ou `closed_in`).
- **R23 — Notícias.** Os itens percebidos vão para `world.news` com texto de
  template (302 R25). Templates em `data/world/signals.json` (§3.7); nenhum
  nomeia fação.

### Persistência, rollout, telemetria, calibração

- **R24 — Saves.** `world_sim.calendar` e `world_sim.festivals` são chaves
  aditivas, sem bump de `SCHEMA_VERSION`. `world["season"]` é aditiva. O
  round-trip save/load preserva os três. Save sem calendário carrega e liga no
  próximo dia virado (R5).
- **R25 — Rollout.** Modo efetivo = `off` se `RPG_WORLD_ENGINE=off` ou
  `RPG_CALENDAR=off`; `shadow` se qualquer um for `shadow`; senão `on`
  (`RPG_CALENDAR` ausente = `on`).
  - `off`: nenhum efeito, nenhuma chave nova escrita;
  - `shadow`: calcula e grava em `world_sim_shadow.calendar`, loga
    `world.calendar`, sem efeito em clima, viagem, encontro, pressão, evento ou
    API;
  - `on`: tudo ligado.
- **R26 — Independência do herói.** Nenhuma função do calendário lê nível,
  ficha, inventário, ouro ou party (teste igual ao R5 da 302). A posição do
  jogador só afeta percepção.
- **R27 — Telemetria e playtest.** Log JSON `world.calendar` por tick com
  `{day, season, changed, festas_started, festas_cancelled, passes_closed,
  mode}`. A seção "Mundo" do `playtest report` (302 R32) ganha: estações vistas
  por campanha, viradas, festas percebidas e canceladas, travessias de inverno.
  Invariantes novos: `calendar.festa_over_crisis` (error: estado `festa` gravado
  em local que tinha crise), `calendar.season_regressed` (error: a estação andou
  para trás entre dois ticks), `calendar.params_changed` (error:
  `world_sim.calendar` mudou depois de criado).
- **R28 — Calibração.** O simulador da SPEC-302 (`docs/spec302/world_engine_sim.py`)
  ganha `--calendar on`, 120 dias × 20 seeds:
  - **S1** — C1–C6 da SPEC-302 continuam fechadas (C1 é a meta que vence, decisão
    D4 do dono na 302);
  - **S2** — 0 crises vindas só da estação (R13);
  - **S3** — 100 % das seeds têm a primeira virada entre `anchor+4` e `anchor+8`;
  - **S4** — cada festa ocorre ou é cancelada exatamente 1× por ano por seed; a
    taxa de cancelamento por festa entra na tabela (sem meta; o dono olha).
  Tabela em `docs/spec303/README.md`.
- **R29 — Letalidade.** Playtest `combate` seeds 21–32 × 200 turnos (MockLLM),
  matriz SPEC-056 e `--start-level 5`, com calendário `on`: M1 (≤ 0,564), M2
  (mediana da 1ª queda ≥ 20) e M5 (0 `combat.no_progress`) da SPEC-285 continuam
  valendo. Se a nevasca/miasma sazonal piorar algo, a correção é no
  multiplicador de clima, nunca no combate.

### Fora de escopo

- Lua, fases lunares, semana, dia de mercado (decisão do dono). Inclui a "maré
  baixa extrema uma vez por mês" de Aethelgard (`lore_nova/timeline_completa.txt:106`),
  que pressupõe ciclo mensal (D8).
- Ano/era exibido ao jogador ("Ano N da Era 7"): `year` é só interno.
- Luz: a "Noite Longa" de Skallgard escurecer todos os períodos ao relento
  (`world_utils.py:1238-1278`) fica para a frente D. Overlays de neve na UI e
  rótulo de estação no HUD também (a API só expõe o campo).
- Estações mexendo em **perigo**, **gatilho** de encontro, porte de criatura ou
  `danger_delta`. Só pesos dentro do mesmo porte (R14b).
- Novos estados de clima, clima determinístico, efeitos de calor em Zhur além do
  clima e da fome.
- Bloqueio duro de passo (só se o dono escolher D4 = b/c; aí vira emenda).
- Quests de festa (torneio, concurso), NPCs com agenda de festa, preços por
  estação fora da `festa`/escassez: 302-C/302-D ou spec futura.
- Festa como crise ou usando `request_crisis_slot` (R14).
- Mudar `route_blocked`/`route_cleared` para ter dono por motivo (P6): registrado,
  não resolvido aqui (os passos não usam esses eventos).
- Editar `lore_nova/`/Codex para registrar as festas: só depois da aprovação do
  dono (D3), por `docs/guias/AUTORIA.md`, em outra tarefa.

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/world_calendar.py` | Puro: `create_calendar`, `season_at`, `season_label`, `baseline_offsets`, `weather_multipliers`, `encounter_multipliers`, `seasonal_closed_pairs`, `pass_between`, `festival_schedule`, `calendar_day_hook` (o hook `pre`), `mode` (R25) |
| `data/world/calendar.json` | Constantes, rótulos regionais, multiplicadores de clima/encontro, offsets de pressão, passos |
| `data/world/festivals.json` | Catálogo de festas (proposta para revisão do dono) |
| `docs/spec303/README.md` | Tabelas S1–S4, letalidade antes/depois, registro do smoke |
| `tests/test_spec303_*.py` | Ver §4 |

### 3.2 Arquivos alterados

- `services/world_engine.py` (SPEC-302): `ensure_world_sim` cria
  `world_sim.calendar` (R3–R5); `register_day_hook("calendar",
  calendar_day_hook, stage="pre", order=10)`; a deriva de pressão aceita
  `baseline_offsets` do `DayHookResult`; `WorldTickResult.world` leva
  `world["season"]`.
- `services/world_pressures.py` (302): `drift(value, baseline + offset)`.
- `services/world_perception.py` (302): visibilidade `global`; kinds novos
  `estacao`, `festa_proxima`, `festa_cancelada`, `passo`.
- `services/location_states.py` (302): `location_effects`/`public_label` leem o
  override do festival por `festival_id` da linha.
- `services/world_validators.py`: `location_state_changed` aceita
  `cause="calendario"` **só** com `state ∈ {"festa", ""}` e `festival_id`
  existente no catálogo.
- `state.py`: `LocationStateRow.festival_id: str`; `WorldSimState.calendar:
  CalendarParams`, `WorldSimState.festivals: list[FestivalRecord]`;
  `WorldState.season: SeasonView`; `DigestItem.kind` com os 4 kinds novos.
- `world_utils.py`:
  - `_advance_weather_once` (`:1197-1203`): aplica `weather_multipliers` (R8);
  - `travel_cost` (`:191-210`): `+ PASS_EXTRA_PERIODS` se o par está fechado
    (R11);
  - `apply_travel` (`:213-242`): força `nevasca` na chegada por passo fechado;
  - `pick_encounter_enemy` (`:937-943`): `encounter_multipliers` (R14b).
- `agents/storyteller.py` (`:532-543`): nota determinística da travessia (R11)
  e a linha de estação no contexto (R21).
- `services/economy.py` (`:121-125`): com D5 = sim, `_blocked_pairs` recebe os
  pares sazonais (via `state`/`world` passados pelo chamador; sem ler o herói).
- `api.py` (`_world_block`, `:2792-2836`): `season` (R22).
- Fluxo de novo jogo (`api.py` `/game/new` e `game_engine.py`, onde
  `world_utils.starting_world` é chamado e o `game_id` já existe):
  `ensure_world_sim(state, 1)` (R5).
- `data/world/signals.json` (302): templates da §3.7.
- `playtest/invariants.py`, `playtest/telemetry.py`, `playtest/report.py`:
  R27.
- `docs/spec302/world_engine_sim.py`: flag `--calendar` (R28).

### 3.3 Schemas (`state.py`)

```python
Season = Literal["primavera", "verao", "outono", "inverno"]


class CalendarParams(TypedDict):
    version: int  # 1
    season_days: int  # congelado na criação (R4)
    epoch_offset: int  # 0..YEAR_DAYS-1
    anchor_day: int  # 1 em jogo novo; enabled_from_day em save migrado
    first_turn_day: int  # anchor_day + k (auditoria do R3)


class FestivalRecord(TypedDict, total=False):
    festa_id: str  # sha256(game_id|festival_id|year)[:16]
    festival_id: str
    year: int
    start_day: int
    end_day: int
    status: Literal["anunciada", "ativa", "encerrada", "cancelada"]
    location_ids: list[str]  # locais que receberam o estado


class SeasonView(TypedDict):  # world["season"]
    id: Season
    label: str  # rótulo regional do local atual
    day_in_season: int


class SeasonInfo(TypedDict):
    season: Season
    day_in_season: int  # 1..season_days
    year: int  # interno
    day_of_year: int  # 0..YEAR_DAYS-1
```

`world_sim.festivals` guarda as anunciadas/ativas mais as últimas 20 encerradas
ou canceladas (anel).

### 3.4 Assinaturas e algoritmo

```python
# services/world_calendar.py
SEASONS: tuple[Season, ...] = ("primavera", "verao", "outono", "inverno")
def mode() -> Literal["off", "shadow", "on"]                               # R25
def create_calendar(game_id: str, anchor_day: int) -> CalendarParams      # R3
def season_at(cal: CalendarParams, day: int) -> SeasonInfo                # R2
def season_label(cal: CalendarParams, day: int, region_id: str) -> str    # R6
def baseline_offsets(season: Season) -> dict[str, dict[str, int]]         # R12
def weather_multipliers(region_id: str, season: Season | None) -> dict[str, float]
def encounter_multipliers(region_id: str, season: Season | None) -> dict[str, float]
def seasonal_closed_pairs(world: dict) -> set[frozenset[str]]             # R10/R11b
def pass_between(a: str, b: str) -> dict | None
def festival_schedule(cal: CalendarParams, game_id: str, year: int) -> list[FestivalRecord]
def calendar_day_hook(ctx: "DayContext") -> "DayHookResult"               # R7
```

`create_calendar` (R3):

```
rng = day_rng(game_id, anchor_day, "calendar")
s0  = rng.randrange(4)
k   = rng.randint(FIRST_TURN_MIN, FIRST_TURN_MAX)          # 4..8
doy_anchor   = s0 * SD + (SD - k)                           # faltam k dias p/ virar
epoch_offset = (doy_anchor - (anchor_day - 1)) mod YEAR_DAYS
```

`season_at`: `t = day - 1 + epoch_offset`; `day_of_year = t mod YEAR_DAYS`;
`year = t // YEAR_DAYS + 1`; `season = SEASONS[day_of_year // SD]`;
`day_in_season = day_of_year mod SD + 1`. Teste: com `anchor_day` qualquer, a
estação muda exatamente em `anchor_day + k`.

O hook usa o contrato `DayContext`/`DayHookResult` da SPEC-302 §3.4. Esta spec
precisa destes campos (se a 302 pousar com nomes diferentes, alinhar aqui no
mesmo commit):

```python
DayContext:    day, game_id, sim (world_sim), world, projection (cópia local), rng, region_ids
DayHookResult: baseline_offsets: dict[str, dict[str, int]]
               pending_events: list[dict]      # propostas source="engine"
               digest: list[DigestItem]
               world_patch: dict               # {"season": SeasonView}
               sim_patch: dict                 # {"festivals": [...]}
```

### 3.5 `data/world/calendar.json` (proposta; valores `[BALANCEAR]`)

```json
{
  "constants": {"SEASON_DAYS": 14, "FIRST_TURN_MIN": 4, "FIRST_TURN_MAX": 8,
                "PASS_EXTRA_PERIODS": 2, "FESTIVAL_HERALD_DAYS": 2},
  "labels": {
    "default":      {"primavera": "Primavera", "verao": "Verão", "outono": "Outono", "inverno": "Inverno"},
    "skallgard":    {"primavera": "Dia Longo", "verao": "Dia Longo", "outono": "Noite Longa", "inverno": "Noite Longa"},
    "deserto_zhur": {"verao": "Estação do Vidro"}
  },
  "weather_mult": {
    "default":            {"verao": {"chuva": 0.5, "limpo": 1.3}, "outono": {"chuva": 1.5, "nublado": 1.2},
                           "inverno": {"chuva": 1.3, "nublado": 1.3}},
    "skallgard":          {"primavera": {"nevasca": 0.7}, "verao": {"nevasca": 0.5},
                           "outono": {"nevasca": 1.5}, "inverno": {"nevasca": 2.0}},
    "montanhas_afiadas":  {"verao": {"nevasca": 0.5}, "inverno": {"nevasca": 2.0}},
    "deserto_zhur":       {"verao": {"vendaval": 1.5}, "inverno": {"vendaval": 0.7}},
    "pantano_melancolia": {"primavera": {"miasma": 1.3}}
  },
  "pressure_offsets": {
    "inverno":   {"skallgard": {"fome": 15}, "montanhas_afiadas": {"fome": 10},
                  "nova_arcadia": {"fome": 5}, "pradaria_ruinas": {"fome": 5}},
    "verao":     {"deserto_zhur": {"fome": 10}},
    "primavera": {"pantano_melancolia": {"praga": 10}, "selva_xylos": {"praga": 5}},
    "outono":    {}
  },
  "encounter_mult": {
    "skallgard":         {"inverno": {"enemy_lobo_invernal": 1.5, "enemy_yeti": 1.5}},
    "montanhas_afiadas": {"inverno": {"enemy_yeti": 1.5}, "verao": {"enemy_wyvern_jovem": 1.5}},
    "deserto_zhur":      {"verao": {"enemy_verme_areia_jovem": 1.5, "enemy_escorpiao_cristal": 1.3}},
    "selva_xylos":       {"primavera": {"enemy_hospedeiro_fungico": 1.3}}
  },
  "passes": [
    {"id": "passo_skallgard", "a": "montanhas_afiadas", "b": "skallgard", "closed_in": ["inverno"]}
  ]
}
```

Checagens de dados (testes): com as baselines da SPEC-302 §3.5,
`skallgard.fome 25 + 15 = 40 ≤ SINAL (40)`, `montanhas_afiadas.fome 20 + 10 =
30`, `deserto_zhur.fome 30 + 10 = 40`, `pantano_melancolia.praga 30 + 10 = 40`.
Nenhuma passa de `SINAL` (R13). Todo par de `passes` é uma `connection` real do
mapa (`data/world_map.json:392-397`, `:605-610`). Todo `enemy_id` existe e tem a
região (`data/bestiary.json`: `enemy_lobo_invernal` `:1012/:1040`, `enemy_yeti`
`:3651/:3677`, `enemy_wyvern_jovem` `:3740/:3766`, `enemy_verme_areia_jovem`
`:3307/:3333`, `enemy_escorpiao_cristal` `:514/:546`,
`enemy_hospedeiro_fungico` `:726/:758`).

### 3.6 `data/world/festivals.json` (proposta para o dono, D3)

Todas com `"review": "dono"`. A lore não tem nenhuma festa datada (P7). As datas
abaixo são **autoria nova** ancorada nos trechos citados; o nome e a origem são
sugestão.

| id | Nome | Local(is) | Quando | Dias | Rótulo / efeito | Âncora na lore |
|---|---|---|---|---|---|---|
| `dia_da_fundacao` | Dia da Fundação | `nova_arcadia`, `na_anel_dourado`, `na_anel_ferro`, `na_anel_lama` | verão, dia 7 | 2 | "em festa"; efeito padrão de `festa` (preço ×1,1, estoque ×1,2) | Nascimento de Nova Arcádia na Era 6 (`timeline_completa.txt:318`, `:432`). A cidade celebra Valerius e o Código; o herói da guerra segue **sem** feriado (`npcs.txt:88`, `timeline_completa.txt:440`), ironia útil para template |
| `noite_do_silencio` | Noite do Silêncio | `nova_arcadia`, `na_anel_dourado`, `na_anel_ferro`, `na_anel_lama` | inverno, dia 1 | 1 | "em silêncio"; `merchant_closed: true`, `restock_mult: 0`, preço ×1,0 | O costume existe e fecha o comércio (`daily_life.txt:137`, "Ninguém abre"). Origem proposta: a noite em que as sombras se soltaram dos corpos (`timeline_completa.txt:340`); o dono confirma se é o "Dia sem Sombra" do título da Era 5 (`:218`) |
| `procissao_de_vaelorn` | Procissão dos Antigos | `pr_vaelorn` | outono, dia 5 | 1 | "em vigília"; preço ×1,0 | Procissão espectral que "repete um festival de uma era perdida" em "noites específicas" (`creatures.txt:492`); os elfos vivos assistem em silêncio |
| `noite_dos_nomes` | Noite dos Nomes | `skallgard` (o `sk_salao_do_jarl` herda) | outono, dia 1 (início da Noite Longa) | 1 | "em luto"; preço ×1,0 | Parede dos Mortos e a conta do tempo "em nomes novos na pedra" (`daily_life.txt:201`; `factions.txt:160`); "quota da estação" (`daily_life.txt:201`) |
| `fim_do_ceu_vermelho` *(mais especulativa)* | Dia do Céu Limpo | `brekmar` | primavera, dia 3 | 1 | "em festa"; efeito padrão | Fim da Guerra do Céu Vermelho (`timeline_completa.txt:368`). Os Filhos da Chama Azul a veem como erro (`factions.txt:62`); só sinal de flavor, sem mecânica de fação |

Ficaram de fora: o festival do herói (a lore nega, `npcs.txt:88`) e a maré baixa
mensal de Aethelgard (ciclo mensal; D8). Os ritos sem data (Batismo de Fogo
`factions.txt:64`, rito de passagem de Skallgard `factions.txt:160`) não são
festas públicas.

### 3.7 Templates (`data/world/signals.json`, trecho)

```json
{
  "estacao.inicio.inverno":   {"visibility": "global",   "text": "O frio chegou de vez; o vapor da respiração não se desfaz mais no ar."},
  "estacao.inicio.noite_longa": {"visibility": "global", "text": "No norte, o sol não volta a nascer por meses; começa a Noite Longa."},
  "passo.fechou":            {"visibility": "regional", "text": "A neve fechou o passo para {local}; quem atravessar agora gasta o dia inteiro na travessia."},
  "passo.abriu":             {"visibility": "regional", "text": "O passo para {local} voltou a ser trilha; as caravanas sobem de novo."},
  "festa.proxima":           {"visibility": "regional", "text": "Em {local} já se fala do {festa}, daqui a poucos dias."},
  "festa.inicio":            {"visibility": "local",    "text": "{local} está {rotulo}: é o {festa}."},
  "festa.cancelada":         {"visibility": "regional", "text": "Não haverá {festa} em {local} este ano; ninguém tem cabeça para isso agora."}
}
```

`estacao.inicio.noite_longa` só é escolhido quando o jogador está em
`skallgard` (rótulo regional); fora dela vale o template da estação canônica.

## 4. Plano passo a passo

Pré-condição: SPEC-302 `done` (M2). Um marco só, com `/spec-land` próprio.

### Etapa 0 — Contrato com a 302 e baseline

1. Ler o `DayContext`/`DayHookResult` pousado pela 302 e alinhar a §3.4 aqui
   (mesmo commit, se mudar).
2. Ownership: `world_sim.calendar`/`festivals` têm dono único em
   `services/world_engine.py` (o hook devolve patches, o engine grava);
   `location_states` segue escrito só por `event_processor.apply_event`.
3. Baseline: repetir as medições da Etapa 8 da 302 (letalidade + `--all
   --turns 50` com dias por perfil) com calendário `off`. Guardar em
   `docs/spec303/README.md`.

### Etapa 1 — Calendário puro

1. **Testes** (`tests/test_spec303_calendar.py`):
   - `test_four_seasons_fixed_order_no_other_cycles` (R1);
   - `test_season_at_is_pure_and_deterministic` (R2);
   - `test_no_global_random_in_calendar_module` (AST);
   - `test_first_turn_between_4_and_8_days_after_anchor` (R3; 200 `game_id`s ×
     anchors 1, 7, 33);
   - `test_start_season_distribution_covers_all_four` (R3);
   - `test_params_frozen_when_constant_changes` (R4: monkeypatch `SEASON_DAYS`);
   - `test_new_game_anchor_is_day_1` e
     `test_legacy_save_anchor_is_enabled_from_day_no_retroactive` (R5);
   - `test_season_none_before_calendar_exists` (R5);
   - `test_regional_labels_skallgard_noite_longa` (R6);
   - `test_calendar_independent_of_player` (R26).
2. **Implementação:** `services/world_calendar.py` (criação, `season_at`,
   rótulos, modo), `data/world/calendar.json`, `ensure_world_sim` + fluxo de
   novo jogo, `state.py`.

### Etapa 2 — Hook diário, estação e pressão

1. **Testes** (`tests/test_spec303_hook.py`):
   - `test_hook_registered_pre_order_10`;
   - `test_world_season_updated_each_tick`;
   - `test_season_change_emits_one_digest_item` (e nenhum nos outros dias);
   - `test_replay_same_day_no_duplicate_items` (R7, idempotência);
   - `test_baseline_offset_moves_equilibrium_not_accumulates` (R12: 60 dias de
     inverno sem causas → `skallgard.fome` estabiliza em 40 ± ruído);
   - `test_offsets_never_exceed_sinal` (R13, validação de dados);
   - `test_calendar_never_requests_crisis_slot` (R14);
   - `test_shadow_writes_only_shadow_key` e `test_off_writes_nothing` (R25).
2. **Implementação:** `calendar_day_hook` (estação + offsets), integração em
   `world_engine`/`world_pressures`.

### Etapa 3 — Clima e encontros

1. **Testes** (`tests/test_spec303_weather_encounters.py`):
   - `test_weather_mult_applied_with_injected_rng` (skallgard inverno: frequência
     de `nevasca` em 2.000 transições com rng fixo > verão);
   - `test_weather_zero_sum_falls_back_to_raw`;
   - `test_default_profile_for_regions_without_table`;
   - `test_weather_neutral_when_season_none_or_mode_off`;
   - `test_encounter_mult_only_in_weighted_path` (caminho legado sem
     `projection` idêntico);
   - `test_encounter_mult_never_changes_tier_or_trigger`;
   - `test_encounter_ids_exist_have_region_not_boss`.
2. **Implementação:** `_advance_weather_once`, `pick_encounter_enemy`.

### Etapa 4 — Passos de montanha

1. **Testes** (`tests/test_spec303_passes.py`):
   - `test_pass_pairs_are_real_connections`;
   - `test_pass_closed_only_in_listed_seasons`;
   - `test_winter_crossing_costs_extra_periods` (`travel_cost` +2; também no
     sentido `skallgard → montanhas_afiadas`);
   - `test_winter_crossing_forces_snow_on_arrival`;
   - `test_winter_crossing_never_refused` (anti-softlock P5: em `skallgard` no
     inverno, `find_travel_destination` acha `montanhas_afiadas` e o storyteller
     não recusa);
   - `test_crossing_note_is_deterministic_fact`;
   - `test_closed_pass_counts_as_blocked_for_trade` (D5 = sim) e
     `test_route_events_untouched_by_season` (P6: nenhum
     `route_blocked`/`route_cleared` emitido pelo calendário);
   - `test_pass_digest_regional_on_close_and_open`.
2. **Implementação:** `seasonal_closed_pairs`, `travel_cost`/`apply_travel`,
   nota no storyteller, `economy._blocked_pairs`.

### Etapa 5 — Festas

1. **Testes** (`tests/test_spec303_festivals.py`):
   - `test_catalog_valid` (ids únicos, locais não-interiores e existentes,
     `day_in_season ≤ 10`, `review` presente);
   - `test_festa_starts_and_ends_via_location_state_changed`;
   - `test_festa_id_deterministic_per_year`;
   - `test_interior_inherits_festa` (`sk_salao_do_jarl`);
   - `test_festa_cancelled_when_location_has_crisis_state` e
     `test_festa_cancelled_when_region_has_announced_crisis` (R17);
   - `test_crisis_during_festa_overwrites_and_end_is_noop` (R16/R17);
   - `test_validator_accepts_calendario_cause_only_for_festa`;
   - `test_llm_proposal_of_festa_rejected` (engine-only, 302 R28);
   - `test_noite_do_silencio_closes_merchants` (override de efeito, R18);
   - `test_festa_label_in_public_label`;
   - `test_herald_two_days_before` (R19);
   - `test_one_occurrence_or_cancel_per_year` (S4, 3 anos).
2. **Implementação:** `data/world/festivals.json`, `festival_schedule`, parte
   de festas do hook, override em `location_states`, validator.

### Etapa 6 — Percepção, narração e API

1. **Testes** (`tests/test_spec303_perception_api.py`):
   - `test_season_item_global_visibility_only_type`;
   - `test_far_festival_invisible_without_propagation` (SPEC-215 `off`);
   - `test_far_festival_heard_via_location_heard` (SPEC-215 `on`);
   - `test_templates_never_name_factions`;
   - `test_storyteller_context_has_season_line_no_extra_llm_call` (contador no
     MockLLM igual com calendário `on`/`off` numa ação que vira dia);
   - `test_api_world_block_has_season_only` (sem `festivals`, `epoch_offset`,
     `closed_in`);
   - `test_save_load_roundtrip_calendar_festivals_season` (R24).
2. **Implementação:** visibilidade `global` e kinds no `world_perception`,
   linha de contexto no storyteller, `_world_block`, templates.

### Etapa 7 — Playtest, calibração e letalidade

1. **Testes:** `tests/test_spec303_playtest.py`:
   `test_invariants_festa_over_crisis_and_season_regressed` (estado sintético),
   `test_report_world_section_has_seasons_and_festas`;
   `tests/test_spec303_calibration.py` (rápido, 60 dias × 3 seeds): S2 e S3
   sempre valem.
2. **Implementação:** invariantes, telemetria e relatório (R27); `--calendar`
   no simulador; rodar S1–S4 (120 × 20) e R29; ajustar `[BALANCEAR]` até
   fechar; registrar em `docs/spec303/README.md` e na §8.
3. Ruff nos arquivos tocados. Suíte completa (`-n auto`) 1× no pouso.

## 5. Critérios de aceite

- [ ] R1–R7: calendário puro, seeded, congelado, com virada em 4–8 dias, rótulos
      regionais, hook `pre` idempotente
- [ ] R8–R9: clima modulado pela estação, sem estado novo
- [ ] R10–R11b: passo de Skallgard fechado no inverno como travessia cara, sem
      softlock; comércio conforme D5; nenhum `route_*` emitido
- [ ] R12–R14: offsets de baseline ≤ `SINAL`; estação sozinha não abre crise;
      sem slot de crise
- [ ] R14b: pesos sazonais de encontro só no caminho ponderado, sem mudar porte
      nem gatilho
- [ ] R15–R19: festas do catálogo aprovado (D3) via `location_state_changed`;
      crise vence festa; anúncio 2 dias antes; overrides de efeito
- [ ] R20–R23: percepção pela regra de ouro, sem chamada LLM nova, API só com
      `season`
- [ ] R24–R26: saves antigos carregam; `off`/`shadow`/`on`; independente do
      herói
- [ ] R27–R29: invariantes e relatório; S1–S4 fechadas; M1/M2/M5 da SPEC-285
      com calendário `on`
- [ ] Nenhum `with_structured_output` novo (guard de FallbackLLM não se aplica;
      a narração é a da 302)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Revisão independente Opus (`handoffs/SPEC-303-review.md`) sem P0/P1
- [ ] Smoke real (§6) executado e registrado

## 6. Smoke test com LLM real

Teto do dono: US$ 3/dia, só campanhas curtas. Pré-requisito:
`RPG_WORLD_ENGINE=on`, `RPG_CALENDAR=on`, `RPG_NPC_KNOWLEDGE=on`, DeepSeek nas
`ROUTES`. O MockLLM não mostra se a narração respeita a estação e a regra de
ouro; por isso este passo é obrigatório.

1. `uv run python -m playtest run --profile explorador --turns 25 --real --max-cost 0.40 --seed 31`
   com start em `skallgard`. Assertar: `mock=False`; a virada de estação
   aparece no transcrito entre o 4º e o 8º dia; `/game/state` traz `season`
   com rótulo regional; o número de invokes do narrador diário é igual ao do
   mesmo run com `RPG_CALENDAR=off` (telemetria `set_llm_telemetry_hook`);
   0 violação `error`.
2. Save sintético em `montanhas_afiadas` no inverno (dia de inverno forçado via
   `epoch_offset` no fixture do playtest) e ação "viajar para Skallgard":
   travessia aceita, +2 períodos no relógio, nota da neve narrada, sem recusa.
3. Save sintético em `nova_arcadia` 2 dias antes do `dia_da_fundacao`, 3 ações
   de descanso: anúncio, depois "em festa" no `location_state`, depois o fim. A
   narração cita a festa só depois do anúncio/testemunho. Leitura humana de 5
   trechos: nenhuma festa de outra região citada sem rumor; nenhuma fação
   nomeada.
4. Staging (depois do pouso): `RPG_CALENDAR=shadow` primeiro, 1 sessão manual de
   ~10 ações com descanso, conferir `world.calendar` nos logs sem mudança
   visível; depois do OK do dono, `on` e repetir.

Custo esperado: ≤ US$ 0,80 no total. Estourou o teto: parar e registrar.

## 7. Riscos & compatibilidade

- **Saves antigos:** calendário nasce na migração da 302 (R29 dela), com
  `anchor_day` = dia atual e sem retroativo. Antes do primeiro dia virado, tudo
  neutro e `season: null` na API. Chaves aditivas, sem bump de schema.
- **Mudança de balanceamento em dados:** `SEASON_DAYS` é congelado por save
  (R4), então ajuste futuro só vale para jogos novos. Isso é intencional.
- **Letalidade (SPEC-285):** mais nevasca (−1 de ataque, −3 de percepção) no
  inverno do norte e mais miasma (bloqueia descanso ao relento) na primavera do
  pântano podem piorar M1/M2. Mitigação: medir na Etapa 7 e reduzir o
  multiplicador; o descanso em local com tag de abrigo continua imune
  (`world_utils.py:1312-1319`).
- **Skallgard no inverno:** travessia cara + escassez (D5) + fome alta + nevasca
  é o momento mais duro do jogo. Sem softlock (R11), mas um jogador de nível
  baixo pode sofrer. Se R29 falhar só por isso, reduzir `PASS_EXTRA_PERIODS`
  ou o offset de fome antes de mexer em qualquer outra coisa.
- **Festa x crise:** a regra "crise vence" (R17) e o fim condicionado ao
  `festa_id` (R16) evitam apagar estado de crise. Invariante
  `calendar.festa_over_crisis` cobre regressão.
- **Onisciência:** a estação é o único item `global`. Calendário de festas e
  passos não saem pela API. O jogador só sabe de festa distante por rumor.
- **Lore inventada:** toda festa é autoria nova marcada `review: "dono"`. Nada
  entra no Codex/RAG nesta spec, então o narrador não "conhece" as festas além do
  template percebido.
- **MockLLM/FallbackLLM:** sem `with_structured_output` novo. O calendário é
  Python puro, e a suíte offline exercita tudo.
- **Quota/latência:** zero chamada LLM nova; O(12 regiões + |festas|) por dia.
- **Rollback:** `RPG_CALENDAR=off` desliga só o calendário; as chaves ficam
  inertes.

## 8. Evidência

Calibração e pendências: `docs/spec303/README.md`.

**Desvios do contrato real da SPEC-302 (alinhados no código):**

- `DayContext` real = `{game_id, day, sim, projection, world, factions, rng}` (sem `region_ids`).
  `DayHookResult` real = `{pressure_deltas, events, digest}` + novo campo `baseline_offsets`
  (R12). O hook **muta `ctx.sim`/`ctx.world` in place** (calendário, `festivals`,
  `world["season"]`) em vez de devolver `world_patch`/`sim_patch`; o engine passou a
  confirmar `pre.events` (antes só lia deltas) e a juntar `pre.digest`. Hooks que lançam são
  isolados (`log_fallback world_engine.day_hook_failed`).
- Modo `shadow` do calendário grava em `world_sim.calendar_shadow` (não em
  `world_sim_shadow.calendar`); só calcula e loga `world.calendar`. Festas só existem em `on`.
- Save de 302 sem calendário: ancora em `day - 1` do primeiro tick (= `enabled_from_day`
  na migração). `init_new_game` ancora no dia 1 em `/game/new`, `game_engine` e playtest.
- `pick_crisis_target` trata local em `festa` como elegível (crise vence festa, R17).
- D5: o preço ×1,8 vale (`supply_factor` com `extra_blocked`), mas a prateleira de
  `economy` NÃO esconde bens por passo sazonal (só por `route_blocked`), para não zerar
  Skallgard no inverno.
- D3: 14 festas (5 propostas + 9 novas, uma por região restante), `lore_refs` arquivo:linha,
  todas `review: "dono"`; teste valida que as linhas existem.

## 9. Decisões do dono

- **D1 — Duração da estação.** Recomendado: `SEASON_DAYS = 14` (ano de 56
  dias), mais a virada garantida em 4–8 dias (R3). Racional: uma estação ≈ um
  ciclo de crise perceptível (10–15 dias, VISAO) e uma campanha de 30 dias vê 2–3
  estações. Alternativas: 10 (ano de 40) ou 20 (ano de 80). Rever quando a seção
  "Mundo" da 302 medir dias por perfil.
- **D2 — Nomes das estações.** Recomendado: nomes comuns no default, e "Dia
  Longo"/"Noite Longa" em Skallgard e "Estação do Vidro" em Zhur (§3.5).
  Alternativa: nomes próprios de Valoria para todas (exige autoria).
- **D3 — Festas.** Aprovar, vetar ou renomear cada uma das 5 da §3.6. Em
  especial: (a) se a Noite do Silêncio é o aniversário das sombras soltas
  (`timeline_completa.txt:340`) e/ou o "Dia sem Sombra" da Era 5 (`:218`); (b) se
  `fim_do_ceu_vermelho` entra.
- **D4 — Passo fechado.** (a) **recomendado**: travessia permitida e cara (+2
  períodos, neve na chegada); (b) bloqueio duro com recusa (exige exceção
  anti-softlock para quem já está em Skallgard); (c) fecha só enquanto o clima
  local estiver em `nevasca`.
- **D5 — O passo fechado isola o comércio de Skallgard no inverno** (preço ×1,8
  nos bens de fora). Recomendado: **sim** (lore: carne curada é a "base da
  sobrevivência no inverno de seis meses").
- **D6 — Offsets de pressão e multiplicadores de clima/encontro (§3.5).**
  Revisão de coerência com a lore; os números são `[BALANCEAR]`.
- **D7 — Noite do Silêncio fecha todo mercador de Nova Arcádia por 1 dia.**
  Recomendado: **sim** (a lore diz "Ninguém abre").
- **D8 — Maré baixa mensal de Aethelgard** (`timeline_completa.txt:106`).
  Recomendado: fora (é ciclo mensal, próximo de lua). Alternativa: virar data
  "uma vez por estação" numa spec futura.


## Decisões do dono (2026-10-23)

Todas as decisões abertas seguem o **default recomendado pelo autor**, exceto/explicitando:

- D1: estação de 14 dias.
- D3 (amplia a proposta): ~14 festas no total, distribuídas para que cada região tenha ao menos 1 (12 regiões), todas ancoradas na lore (grep, citação arquivo:linha) e marcadas `review: "dono"` — o dono edita texto/datas depois. As 5 propostas entram; o executor autora as demais na Etapa de dados.

## 10. Evidência e desvios da implementação (2026-10-24)

Desvios do contrato real da 302 (alinhados aqui):
- `DayContext`/`DayHookResult` pousados não têm `region_ids`, `baseline_offsets`, `world_patch` nem `sim_patch`. Adicionei só `DayHookResult.baseline_offsets` (mesclado em `_run_hooks`); o hook muta `ctx.sim` (`calendar`, `festivals`) e `ctx.world["season"]` direto, e o engine passou a commitar `pre.events` e anexar `pre.digest`. `_run_hooks` agora isola falha de hook com `log_fallback`.
- Shadow grava em `world_sim["calendar_shadow"]` (não em `world_sim_shadow.calendar`) e não rastreia festas.
- `anchor_day` de save sem calendário = `day - 1` do primeiro tick (equivale a `enabled_from_day` na migração).
- `pick_crisis_target` trata local em `festa` como elegível (crise vence festa). `economy.supply_factor` só encarece (×1,8); a prateleira não esconde bens por passo sazonal.
- Ponto único de data: `services/world_calendar.py` + `world_sim.calendar` (qualquer calendário próprio futuro troca nomenclatura/duração ali).
- 14 festas cobrindo as 12 regiões, `review: "dono"`, com `lore_refs` arquivo:linha (testadas).

Calibração (60 seeds × 120 dias): C1 off = 10/15/10/11,5; on = 10/15/10/11 (dentro de [10,15]); C3/C5 true, C6 vazio. 20 seeds: S2 sem crise extra, S3 ok (viradas em +4..+8), S4 ok. Taxas de cancelamento por festa: 0 a 27,5 % (dia_da_fundacao 27,5 %, noite_do_silencio 23,9 %, dia_da_estaca 21,7 %). Letalidade R29 (playtest 12 seeds × 200) e smoke real §6 NÃO executados: pendentes para o coordenador.
