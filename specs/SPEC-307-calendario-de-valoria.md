# SPEC-307 — Calendário de Valoria: 7 meses, semana de 5 dias, data exibida

> **Status:** `approved` (aprovada pelo dono em 2026-10-24 na própria encomenda; escolhas de nome da §9 seguem o default recomendado até o dono trocar)
> **Criada:** 2026-10-24 · **Atualizada:** 2026-10-24
> **Origem:** decisão do dono de 24/10 (calendário próprio de Valoria, substituindo as 4 estações genéricas da SPEC-303)
> **Depende de:** SPEC-303 (`in-progress`; tem de estar `done` ou ser pousada junto, decisão D7), SPEC-302 (`done`: tick diário, `day_rng`, hooks `pre`)
> **Desbloqueia:** SPEC-305 (prazo de quest em data de Valoria), SPEC-304 (agenda de NPC por dia da semana, se quiser), entrada de Codex do calendário (autoria, fora daqui)
> **EXECUTOR_MODEL:** `Sonnet` (bounded: troca o modelo de tempo dentro do ponto único da 303) · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (bump de versão de um writer persistente, `world_sim.calendar`, com migração de save)
> **EVAL_AUTHORING_REQUIRED:** `false`

---

## 1. Contexto & Objetivo

A SPEC-303 deu a Valoria um ano de 4 estações de 14 dias (56 dias) sem semana e
sem mês, e manteve o relógio exibido como "Dia N · Período". O dono decidiu em
24/10 que Valoria tem **calendário próprio**: o ano tem **7 meses**, a semana tem
**5 dias**, e cada mês tem 4 semanas, ou seja, 20 dias. O ano fica com 140 dias.
**Cada mês carrega o seu clima**: 2 meses de frio, 2 de calor e 3 de transição.
Os meses substituem as estações genéricas como unidade de tempo. As estações
canônicas da 303 (`primavera/verao/outono/inverno`) continuam existindo **só como
chave interna** das tabelas de modulação (clima, pressão, encontro, passo), e cada
mês aponta para uma delas.

O jogador passa a ver a data no estilo **"3º dia de Vorrnak, Eco — Ano 1"** no
relógio do HUD e no contexto do narrador. O período do dia (Amanhecer…Noite)
continua. O tempo continua passando só em viagem e descanso, e o motor de mundo
continua rodando 1× por dia. A campanha continua sem duração fixa.

Esta spec **não cria mecânica nova**. Ela troca o modelo de datas dentro do ponto
único que a 303 criou (`services/world_calendar.py` + `world_sim.calendar`),
reposiciona as 14 festas aprovadas em mês+dia, migra saves e expõe a data. Tudo é
Python determinístico. A LLM não ganha chamada nova e só recebe a data pronta.

Os nomes (7 meses, 5 dias) são **autoria nova ancorada na lore**. Cada nome cita
a linha que o inspirou e traz uma alternativa para o dono escolher (§3.6, D1/D2).

### 1.1 Problemas com evidência

Caminhos com prefixo `[303]` são do worktree da SPEC-303
(`C:\Users\guilh\AppData\Local\Temp\claude\rpg-spec-303`). Os demais são da `main`
(worktree desta spec).

| # | Problema | Evidência |
|---|---|---|
| P1 | O relógio exibido é só "Dia N · Período", no HUD, nas notícias e no prompt | `world_utils.py:1538-1540` (`clock_label`); `web/src/components/PlayScreen.tsx:42`; `web/src/heardNews.ts:10` |
| P2 | O calendário da 303 é 4 estações × `SEASON_DAYS`, sem mês nem semana, por requisito | `[303] services/world_calendar.py:24` (`SEASONS`), `:65-97` (`create_calendar`/`season_at` com `season_days`); `[303] data/world/calendar.json:3` (`SEASON_DAYS: 14`); `[303] specs/SPEC-303-calendario-estacoes-festas.md:62-66` (R1: "Sem lua, sem semana") |
| P3 | As festas estão em `season` + `day_in_season ≤ 10` e o agendamento depende de `season_days` | `[303] data/world/festivals.json:2`, `:7`, `:14`…`:105`; `[303] services/world_calendar.py:200-216` (`festival_schedule`) |
| P4 | Uma versão nova do calendário seria **recriada do zero** pelo hook, o que muda a estação de um save no meio da campanha e viola o congelamento (303 R4) | `[303] services/world_calendar.py:371-373` (`if … cal.get("version") != CAL_VERSION: cal = create_calendar(...)`) |
| P5 | Os invariantes do playtest assumem estação de tamanho fixo e acusariam a migração como erro | `[303] playtest/invariants.py:2024` (usa `cal["season_days"]`); `:2009-2010` (`calendar.params_changed` dispara em qualquer diferença) |
| P6 | A lore fala em "noite de seis meses" / "inverno de seis meses" no norte; num ano de 7 meses isso seria quase o ano inteiro | `lore_nova/creatures.txt:64`; `lore_nova/items.txt:139` |
| P7 | O narrador recebe o tempo só por `clock_label(world)`, que não enxerga `world_sim` | `agents/storyteller.py:767`, `:771`, `:1117`; `services/ambient.py:52`; `agents/world_simulator.py:125` |
| P8 | A API só manda `day`/`period`, e o `_world_block` não recebe `world_sim` | `api.py:2839-2840`; chamada em `api.py:2182-2187`; `[303] api.py:2873`, `:2882-2892` (`season`) |

## 2. Requisitos

### Modelo de tempo

- **R1 — Ano de Valoria.** `MONTHS = 7`, `MONTH_DAYS = 20`, `WEEK_DAYS = 5`,
  `YEAR_DAYS = 140`, lidos de `data/world/calendar.json` (`constants`). Validação de
  dados (teste): `MONTH_DAYS % WEEK_DAYS == 0` e `MONTH_DAYS // WEEK_DAYS == 4`.
  `SEASON_DAYS` deixa de existir.
- **R2 — Mês carrega clima e estação.** Cada um dos 7 meses tem `{id, name, of,
  climate, season, lore_ref}`. `climate ∈ {"frio","calor","transicao"}`, com
  exatamente 2 `frio`, 2 `calor` e 3 `transicao` (teste). `season` é a chave
  canônica da 303 que as tabelas de modulação usam. Os meses de uma mesma
  `season` são contíguos, a ordem cíclica é `primavera → verao → outono →
  inverno`, e toda `season` tem ≥ 1 mês (teste). Proposta na §3.5: 1 mês de
  primavera, 2 de verão, 2 de outono, 2 de inverno.
- **R3 — Semana.** 5 dias da semana `{id, name, lore_ref}`. O dia da semana é
  `(day_of_month - 1) mod 5`. Como `MONTH_DAYS` é múltiplo de 5, o 1º de todo mês
  cai sempre no mesmo dia da semana (teste). O dia da semana **não tem efeito
  mecânico** (sem dia de mercado nem de descanso).
- **R4 — Função pura.** `date_at(cal, day) -> CalendarDate` devolve
  `{year, month_index, month_id, day_of_month, weekday_index, weekday_id, season,
  climate, day_of_year, day_in_season, season_len}` só a partir dos parâmetros
  persistidos e de `world_clock.day`. Mesma entrada, mesma saída, sem `random`
  global (teste por AST, como na 303). `season_at(cal, day)` continua existindo
  com a mesma assinatura e o mesmo dict de saída (`season`, `day_in_season`,
  `year`, `day_of_year`), agora derivado de `date_at`, para os consumidores da 303
  não mudarem.
- **R5 — Relógio absoluto intocado.** `world_clock = {day, period}` continua sendo
  a única fonte de tempo e o único writer continua sendo `advance_clock`
  (`world_utils.py:64-73`). A data é sempre **derivada**, nunca gravada como
  verdade. O formato do save do relógio não muda.
- **R6 — Início semeado com virada cedo garantida (herda 303 R3).**
  `create_calendar(game_id, anchor_day)` usa `day_rng(game_id, anchor_day,
  "calendar")`: `s = rng.randrange(4)` escolhe um dos 4 meses que **fecham uma
  estação** (os meses `m` com `season(m) != season(m+1)`; na proposta, índices
  0, 2, 4, 6) e `k = rng.randint(FIRST_TURN_MIN, FIRST_TURN_MAX)` (4..8). O
  `epoch_offset` faz o jogo começar `k` dias antes do fim desse mês. Assim a
  primeira **troca de mês e de estação** acontece em `anchor_day + k` (teste: 200
  `game_id` × anchors 1, 7, 33). A ordem de chamadas do `rng` é a mesma da 303, então
  o mesmo `game_id` começa na mesma estação canônica nas duas versões.
- **R7 — Congelamento (herda 303 R4).** `world_sim.calendar` v2 =
  `{version: 2, month_days, months, week_days, epoch_offset, year_offset,
  anchor_day, first_turn_day, migrated_from?}` é gravado na criação ou na
  migração e **nunca** recalculado. Mudar `MONTH_DAYS` no JSON não muda a data de
  saves existentes (teste com monkeypatch). Versão desconhecida ou maior que 2 é
  tratada como neutra (sem data, sem modulação) e logada, **nunca** recriada.
- **R8 — Rótulos regionais de estação continuam.** `labels` por região da 303
  (`skallgard` "Dia Longo"/"Noite Longa", `deserto_zhur` "Estação do Vidro")
  continuam indexados pela `season` canônica. Com a proposta da §3.5, a Noite
  Longa de Skallgard cobre os meses 4–7 (80 de 140 dias, 57 % do ano) e o Dia
  Longo cobre os meses 1–3 (teste do rótulo por mês).

### Festas

- **R9 — Catálogo em mês+dia.** `data/world/festivals.json` troca `season` e
  `day_in_season` por `month` (id de mês) e `day_of_month` (1..20). Os outros
  campos (`id`, `name`, `location_ids`, `duration_days`, `label`, `effects`,
  `lore_refs`, `review`) não mudam. Validação (teste): `month` existe,
  `1 ≤ day_of_month ≤ MONTH_DAYS`, `duration_days ≥ 1`.
- **R10 — Sentido preservado.** As 14 festas aprovadas são reposicionadas pela
  tabela da §3.7. Regra padrão: posição proporcional dentro da mesma estação,
  `dia_na_estacao_novo = floor((d - 1) × L / 14) + 1`, onde `L` é o tamanho da
  estação no calendário novo. Desvios temáticos ficam listados na tabela. Teste:
  para cada festa, `month.season` é igual à `season` que ela tinha na 303 (tabela
  congelada no teste). Festa de inverno cai em mês de frio.
- **R11 — Agendamento.** `festival_schedule(cal, game_id, year)` calcula
  `start_day` a partir de `month_index × MONTH_DAYS + day_of_month - 1`,
  `epoch_offset` e `year_offset`. `festa_id = sha256(game_id|festival_id|year)[:16]`
  sem mudança, com `year` = ano exibido (R14). Todo o resto das festas da 303
  (R15–R19: estado `festa` por evento, crise vence festa, anúncio 2 dias antes,
  efeitos) fica como está. Teste S4 de 2 anos: cada festa ocorre ou é cancelada
  exatamente 1× por ano.

### Exibição

- **R12 — `date_label`.** `date_label(cal, day) -> str` devolve
  `"{d}º dia {of}, {weekday} — Ano {year}"`, por exemplo
  `"3º dia de Vorrnak, Eco — Ano 1"` ou `"12º dia do Céu Vermelho, Maré — Ano 2"`.
  O campo `of` do mês carrega a preposição certa ("de", "do", "da", "dos").
  O ordinal é sempre `º`. Teste com tabela de 6 casos, incluindo o 1º e o 20º.
- **R13 — `clock_label`.** `world_utils.clock_label(world, calendar=None)`:
  - com `calendar` v2 válido e modo `on`: `"{date_label} · {period}"`;
  - sem `calendar`, usa `world["date"]` se `world["date"]["day"] ==
    world_clock.day` (vista fresca);
  - nos demais casos (modo `off`/`shadow`, sem calendário, vista velha), o texto
    legado `"Dia N · {period}"`, byte a byte (teste).
  Os chamadores que têm o `state` (`agents/storyteller.py:767`, `:771`, `:1117`,
  `agents/world_simulator.py:125`) passam `state["world_sim"]["calendar"]`.
  `services/ambient.py:52` usa a vista `world["date"]`.
- **R14 — Ano.** `year = (day - 1 + epoch_offset) // YEAR_DAYS + 1 + year_offset
  + (YEAR_BASE - 1)`, sempre ≥ 1 e nunca decrescente (teste). `YEAR_BASE` vem do
  JSON (default 1, D4). O ano é só rótulo, sem mecânica.
- **R15 — Vista `world["date"]`.** O hook diário da 303 (`calendar_day_hook`) e o
  `init_new_game` gravam `world["date"] = DateView` junto com `world["season"]`,
  nos mesmos pontos e só no modo `on`. Eles são o único writer.
- **R16 — API.** `_world_block` recebe `world_sim` (chamada em `api.py:2182`) e
  ganha `date: {label, day_of_month, month, month_id, weekday, year, climate} |
  null`, calculado de forma **pura** a partir de `world_sim.calendar` (v2, ou v1
  convertido em memória pela R19, sem gravar). Fica `null` fora do modo `on` ou
  sem calendário. Cada item de `news` ganha `date_label` (mesma função, com o
  `day` do item; vazio sem calendário). Não sai pela API: `epoch_offset`,
  `year_offset`, o catálogo de festas nem `closed_in` (teste herdado da 303 R22,
  estendido).
- **R17 — Web.** `PlayScreen.tsx:42` mostra `w.date.label + " · " + w.period` se
  `w.date` existir; senão o texto atual. `heardNews.ts:10` usa `item.date_label`
  quando houver. `types.ts` ganha `date` e `season` no tipo do mundo. Se o
  local atual tiver rótulo regional próprio (Skallgard, Zhur), o chip
  ` · Noite Longa` aparece depois do período (D8).
- **R18 — Narrador.** A linha `Momento:` do storyteller, do world_simulator e do
  `<AMBIENTE>` passa a trazer a data nova (R13). O prompt do storyteller ganha uma
  frase fixa: "Use só os nomes de mês e de dia de Valoria que aparecem em
  Momento; não invente datas nem meses de outro mundo." A linha `Estação:` da 303
  (`[303] agents/storyteller.py:563-572`) continua. Nenhuma chamada LLM nova:
  teste com contador do MockLLM igual com calendário `on`/`off` numa ação que vira
  o dia (herda 303 R21).

### Migração e compatibilidade

- **R19 — Migração v1 → v2 sem salto de estação.** `migrate_calendar(cal_v1,
  game_id, day) -> CalendarParams` (pura), com `day` = dia sendo virado:
  1. `s, d = season_at_v1(cal_v1, day)` (estação e dia na estação, 1..14);
  2. `doy_novo = inicio_v2(s) + floor((d - 1) × L_v2(s) / 14)`;
  3. `epoch_offset = (doy_novo - (day - 1)) mod 140`;
  4. `year_offset = ano_v1(day) - ano_v2_bruto(day)` (o ano exibido continua o
     mesmo);
  5. mantém `anchor_day` e `first_turn_day`, grava `migrated_from: 1`.
  Teste: para 56 dias × 3 `epoch_offset` v1, a `season` em `day` é igual antes e
  depois, e o ano exibido é igual. O hook troca a recriação de
  `[303] services/world_calendar.py:371-373` por esta migração.
- **R20 — Festas na migração.** Registros `ativa` mantêm `end_day` (absoluto). Os
  `anunciada` são descartados e o agendamento v2 recalcula o ano. Nenhuma festa
  ocorre 2× no mesmo ano por causa da migração: o agendamento pula `festa_id` que
  já tem registro (teste: festa v1 encerrada no ano 1, migração, ano 1 v2 não a
  repete).
- **R21 — Save sem calendário.** Save de antes da 303, ou com o motor ligado depois:
  cria v2 direto (herda 303 R5: `anchor_day` = dia do primeiro tick menos 1, sem
  simulação retroativa). Até o primeiro dia virado, o HUD mostra o rótulo legado
  e a API manda `date: null`. Teste de round-trip save/load com v1, com v2 e
  sem calendário.
- **R22 — Rollout.** Mesmos modos da 303 R25 (`RPG_WORLD_ENGINE` × `RPG_CALENDAR`).
  Em `off` nada muda, inclusive o rótulo legado. Em `shadow` calcula a data v2,
  loga `world.calendar` com `month_id`/`weekday_id` e não grava `world["date"]`.
  Não há flag nova.
- **R23 — Independência do herói (herda 303 R26).** Nenhuma função nova lê nível,
  ficha, inventário, ouro ou party (teste igual ao da 303).

### Playtest e calibração

- **R24 — Invariantes.** `calendar.params_changed` aceita exatamente uma mudança
  v1 → v2 com `migrated_from: 1`; qualquer outra mudança continua `error`.
  `calendar.season_regressed` usa o menor tamanho de estação v2 (20) no lugar de
  `cal["season_days"]` (`[303] playtest/invariants.py:2024`). Novos:
  `calendar.date_regressed` (`error`: a data andou para trás com o dia avançando)
  e `calendar.date_stale` (`warning`: `world["date"]["day"] != world_clock.day`
  depois de um tick).
- **R25 — Telemetria.** O log `world.calendar` (303 R27) ganha `month_id`,
  `day_of_month`, `weekday_id` e `year`. A seção "Mundo" do `playtest report`
  ganha "meses vistos por campanha".
- **R26 — Recalibração.** Com estações de 20–40 dias (antes 14), rodar de novo
  S1–S3 da 303 (`docs/spec302/world_engine_sim.py --calendar on`, 120 dias × 20
  seeds) e S4 com **280 dias** (2 anos de 140). Metas iguais às da 303: C1–C6 da
  302 fechadas, 0 crise vinda só da estação, 100 % das seeds com a 1ª virada em
  `anchor+4..+8`. Se S1/S2 falharem por inverno mais longo, ajustar os offsets de
  pressão da 303 (`[303] data/world/calendar.json:19-25`), nunca o motor. Tabela
  em `docs/spec307/README.md`.
- **R27 — Letalidade.** Repetir a medição da 303 R29 (mesmo comando, MockLLM,
  autorizada por esta spec): M1/M2/M5 da SPEC-285 continuam valendo com o
  inverno passando de 25 % para 28,6 % do ano.

### Fora de escopo

- Mecânica por dia da semana (mercado, descanso, culto) ou por mês além da
  `season` canônica. Sem lua nem fase lunar (decisão da 303 mantida).
- Mudar as tabelas de modulação da 303 (`weather_mult`, `pressure_offsets`,
  `encounter_mult`, `passes`) além do ajuste de calibração da R26.
- Nomes de mês por região ou por povo (os anões contando diferente, por exemplo):
  o calendário é um só, comum a Valoria.
- Era exibida ("Ano N da Era 7") e contagem histórica do ano: a lore não fixa
  quantos anos tem a Era 7 (`lore_nova/timeline_completa.txt:416-420`). Só
  `YEAR_BASE` (D4).
- Escrever o calendário no Codex/`lore_nova/` (entrada de lore, a correção de
  "seis meses" da P6): outra tarefa, por `docs/guias/AUTORIA.md`, depois da
  escolha de nomes (D1/D2/D6).
- Datas na crônica, no memorial e no `event_log` (continuam por dia/turno).
- Prazo de quest em data (SPEC-305 consome esta spec, não o contrário).
- Mexer em `advance_clock`, em `PERIODS` ou na quantidade de tempo gasta por
  viagem e descanso.

## 3. Design técnico

### 3.1 Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `docs/spec307/README.md` | Tabelas da recalibração (R26), letalidade (R27), registro do smoke |
| `tests/test_spec307_calendar.py` | R1–R8, R12–R14 |
| `tests/test_spec307_festivals.py` | R9–R11, R20 |
| `tests/test_spec307_migration.py` | R19–R21 |
| `tests/test_spec307_display_api.py` | R13, R15–R18, R22 |
| `tests/test_spec307_playtest.py` | R24–R25 |

### 3.2 Arquivos alterados

- `services/world_calendar.py` (da 303, ponto único de data): `CAL_VERSION = 2`;
  `months()`, `weekdays()`, `create_calendar` v2, `date_at`, `date_label`,
  `date_view`, `migrate_calendar`; `season_at` reescrita sobre `date_at`;
  `festival_schedule` por mês+dia; `calendar_day_hook` migra (em vez de recriar)
  e grava `world["date"]`; `init_new_game` grava `world["date"]`.
- `data/world/calendar.json`: `constants` sem `SEASON_DAYS`, com `MONTH_DAYS`,
  `WEEK_DAYS`, `YEAR_BASE`; blocos `months` e `weekdays` (§3.5). `labels`,
  `weather_mult`, `pressure_offsets`, `encounter_mult` e `passes` ficam.
- `data/world/festivals.json`: `month` + `day_of_month` (§3.7); `_doc`
  atualizado.
- `world_utils.py:1538-1540`: `clock_label(world, calendar=None)` (R13).
- `agents/storyteller.py` (`:767`, `:771`, `:1117` na `main`): passa o
  calendário; frase de datas no prompt (R18).
- `agents/world_simulator.py:125`: passa o calendário.
- `services/ambient.py:52`: sem mudança de assinatura (usa `world["date"]`).
- `api.py`: `_world_block(..., world_sim=None)` com `date` e `date_label` nas
  notícias; chamada em `:2182-2187` passa `state.get("world_sim")`.
- `state.py`: `CalendarParams` v2, `CalendarDate`, `DateView`;
  `WorldState.date: DateView` (aditiva).
- `web/src/components/PlayScreen.tsx:42`, `web/src/heardNews.ts:10`,
  `web/src/types.ts` (tipo do mundo): R17.
- `playtest/invariants.py` (`[303] :2005-2033`), `playtest/telemetry.py`,
  `playtest/report.py`: R24–R25.
- `docs/spec302/world_engine_sim.py`: horizonte configurável para S4 de 280 dias.
- Testes da 303 que afirmam "sem semana" (`test_four_seasons_fixed_order_no_other_cycles`)
  e `test_params_frozen_when_constant_changes` (monkeypatch de `SEASON_DAYS`):
  atualizar para o modelo v2 no mesmo commit, com nota de que a decisão do dono
  de 24/10 substitui a 303 R1. Não são caminhos de eval protegidos.

### 3.3 Schemas (`state.py`)

```python
Climate = Literal["frio", "calor", "transicao"]


class CalendarParams(TypedDict, total=False):
    version: int  # 2
    month_days: int  # 20, congelado
    months: int  # 7, congelado
    week_days: int  # 5, congelado
    epoch_offset: int  # 0..139
    year_offset: int  # 0 em jogo novo; ajuste da migração v1 (R19), pode ser negativo
    anchor_day: int
    first_turn_day: int
    migrated_from: int  # 1, só quando veio da 303


class CalendarDate(TypedDict):
    year: int  # exibido (R14)
    month_index: int  # 0..6
    month_id: str
    day_of_month: int  # 1..20
    weekday_index: int  # 0..4
    weekday_id: str
    season: Season  # chave canônica da 303
    climate: Climate
    day_of_year: int  # 0..139
    day_in_season: int  # 1..season_len
    season_len: int  # 20 ou 40 na proposta


class DateView(TypedDict):  # world["date"] e API (sem day_of_year/epoch)
    day: int  # world_clock.day a que a vista se refere (frescor, R13)
    label: str  # "3º dia de Vorrnak, Eco — Ano 1"
    day_of_month: int
    month: str  # nome exibido
    month_id: str
    weekday: str
    year: int
    climate: Climate
```

`SeasonView` (`world["season"]`) continua igual. `day_in_season` passa a ir de 1
até `season_len`.

### 3.4 Assinaturas e algoritmo

```python
# services/world_calendar.py
CAL_VERSION = 2
def months() -> list[dict]                                   # do JSON, ordem do ano
def weekdays() -> list[dict]
def create_calendar(game_id: str, anchor_day: int) -> CalendarParams        # R6
def date_at(cal: CalendarParams, day: int) -> CalendarDate                  # R4
def season_at(cal: CalendarParams, day: int) -> dict                        # compat 303
def date_label(cal: CalendarParams, day: int) -> str                        # R12
def date_view(cal: CalendarParams, day: int) -> DateView                    # R15/R16
def migrate_calendar(cal_v1: dict, game_id: str, day: int) -> CalendarParams  # R19
def calendar_for_read(sim: dict | None, day: int) -> CalendarParams | None  # v2, ou v1 convertido em memória (API)

# world_utils.py
def clock_label(world: dict, calendar: dict | None = None) -> str           # R13
```

`create_calendar` v2:

```
MD = MONTH_DAYS; YD = MONTHS * MD
closers = [m for m in range(MONTHS) if season(m) != season((m + 1) % MONTHS)]   # [0, 2, 4, 6]
rng = day_rng(game_id, anchor_day, "calendar")
m   = closers[rng.randrange(4)]
k   = rng.randint(FIRST_TURN_MIN, FIRST_TURN_MAX)
doy_anchor   = (m + 1) * MD - k
epoch_offset = (doy_anchor - (anchor_day - 1)) mod YD
```

`date_at`: `t = day - 1 + epoch_offset`; `day_of_year = t mod YD`;
`month_index = day_of_year // MD`; `day_of_month = day_of_year mod MD + 1`;
`weekday_index = (day_of_month - 1) mod WEEK_DAYS`; `year = t // YD + 1 +
year_offset + YEAR_BASE - 1`; `season`/`climate` do mês; `day_in_season` e
`season_len` pela soma dos meses contíguos da mesma `season`.

Exemplo de migração (R19): v1 no dia 30 em `inverno`, `d = 5`. Na proposta o
inverno é `doy 100..139` (`L = 40`): `doy_novo = 100 + floor(4 × 40 / 14) = 111`,
ou seja, "12º dia de Vorrnak".

### 3.5 `data/world/calendar.json` (trecho novo)

```json
{
  "constants": {"MONTH_DAYS": 20, "WEEK_DAYS": 5, "YEAR_BASE": 1,
                "FIRST_TURN_MIN": 4, "FIRST_TURN_MAX": 8,
                "PASS_EXTRA_PERIODS": 2, "FESTIVAL_HERALD_DAYS": 2},
  "months": [
    {"id": "morrakh",  "name": "Morrakh",  "of": "de Morrakh",  "climate": "transicao", "season": "primavera", "lore_ref": "timeline_completa.txt:338"},
    {"id": "vaelith",  "name": "Vaelith",  "of": "de Vaelith",  "climate": "calor",     "season": "verao",     "lore_ref": "timeline_completa.txt:334"},
    {"id": "malagor",  "name": "Malagor",  "of": "de Malagor",  "climate": "calor",     "season": "verao",     "lore_ref": "timeline_completa.txt:326"},
    {"id": "solveth",  "name": "Solveth",  "of": "de Solveth",  "climate": "transicao", "season": "outono",    "lore_ref": "timeline_completa.txt:330"},
    {"id": "orrakh",   "name": "Orrakh",   "of": "de Orrakh",   "climate": "transicao", "season": "outono",    "lore_ref": "timeline_completa.txt:336"},
    {"id": "vorrnak",  "name": "Vorrnak",  "of": "de Vorrnak",  "climate": "frio",      "season": "inverno",   "lore_ref": "timeline_completa.txt:328"},
    {"id": "thessrak", "name": "Thessrak", "of": "de Thessrak", "climate": "frio",      "season": "inverno",   "lore_ref": "timeline_completa.txt:332"}
  ],
  "weekdays": [
    {"id": "pedra", "name": "Pedra", "lore_ref": "timeline_completa.txt:36"},
    {"id": "geada", "name": "Geada", "lore_ref": "timeline_completa.txt:42"},
    {"id": "mare",  "name": "Maré",  "lore_ref": "timeline_completa.txt:38"},
    {"id": "eco",   "name": "Eco",   "lore_ref": "timeline_completa.txt:44"},
    {"id": "serra", "name": "Serra", "lore_ref": "timeline_completa.txt:40"}
  ]
}
```

Distribuição de dias por estação canônica: primavera 20 (14 %), verão 40 (29 %),
outono 40 (29 %), inverno 40 (29 %). Na 303 eram 25 % cada.

### 3.6 Nomes propostos, inspiração e alternativa (D1/D2)

**Meses: os Sete do Monte.** A lore diz que "Sete dragões emergiram do Monte da
Perdição" na Era 6 (`lore_nova/timeline_completa.txt:326`). São 7 meses para 7
dragões, e o povo conta o ano pelo que cada um trouxe. Cada dragão foi escolhido
pelo clima que o seu trecho evoca. Todas as fichas de Codex dos sete são
`visibility: public` (`data/codex/npcs/npc_{malagor,vorrnak,solveth,thessrak,vaelith,orrakh,morrakh}.md:12`),
então os nomes não vazam segredo. A alternativa de cada mês é um nome
descritivo, também tirado da lore, para quem preferir que o povo não nomeie o
tempo por monstros.

| # | Clima / estação | Proposto | Inspiração | Alternativa | Inspiração da alternativa |
|---|---|---|---|---|---|
| 1 | transição / primavera (degelo, cheia, praga) | **Morrakh** | Dragão das feridas que não fecham; o contágio "por contato, por fluidos, por ar" e a Praga de Ferro (`timeline_completa.txt:338`). Casa com a praga de primavera da 303 (`[303] data/world/calendar.json:23`) | **Cheia** ("da Cheia") | "Não é cheia. É crescimento. A lama está viva" (`rumors.txt:73`); a pradaria que virou pântano (`timeline_completa.txt:366`) |
| 2 | calor / verão | **Vaelith** | Areia negra, foi para o Deserto de Zhur; miragens pelo vidro (`timeline_completa.txt:334`) | **Vidro** ("do Vidro") | Zhur "queima em compensação" ao gelo do norte (`timeline_completa.txt:160`); o deserto de vidro (`:46`, `:334`) |
| 3 | calor / verão (auge) | **Malagor** | O maior dos sete; ferrugem negra, cidades e pradarias "reduzidas a cinza" (`timeline_completa.txt:326`, `:344`) | **Céu Vermelho** ("do Céu Vermelho") | "o céu que permaneceu cor de sangue durante toda a duração do conflito" (`timeline_completa.txt:368`) |
| 4 | transição / outono (névoa) | **Solveth** | "Corpo de névoa densa e ácida"; o ar pesado, "as bordas das coisas … imprecisas" (`timeline_completa.txt:330`) | **Cinza** ("da Cinza") | Pradarias "reduzidas a cinza" na guerra (`timeline_completa.txt:344`); os Cinzéus (`races.txt:204`) |
| 5 | transição / outono (colheita, mar parado) | **Orrakh** | O peso de tudo; "quando o mar fica anormalmente calmo … estão sobre ele" (`timeline_completa.txt:336`) | **Corvos** ("dos Corvos") | A Guilda dos Corvos contando os mortos da guerra "por gerações" (`timeline_completa.txt:366`; `factions.txt:77`) |
| 6 | frio / inverno | **Vorrnak** | "Translúcido como gelo sujo"; onde passava, "o som … desaparecia completamente"; foi para o extremo norte (`timeline_completa.txt:328`) | **Ermo** ("do Ermo") | O Ermo Branco, "gelo eterno que não é apenas clima mas condição do próprio Abismo" (`timeline_completa.txt:160`) |
| 7 | frio / inverno (fundo) | **Thessrak** | O das dezenas de bocas, selado no mar leste sob Aethelgard; os Afogados são quem o ouviu (`timeline_completa.txt:332`) | **Chama Negra** ("da Chama Negra") | O Farol que emite anti-luz no ponto mais ao norte (`timeline_completa.txt:16`, `:164`) |

**Dias da semana: as quatro bordas e a pedra.** "Valoria não é redonda. É uma
pedra plana flutuando no nada … Tem quatro bordas" (`timeline_completa.txt:36`).
A semana gira em volta do mundo: começa na pedra (o centro) e passa pelas
bordas norte, leste, sul e oeste.

| # | Proposto | Inspiração | Alternativa | Inspiração da alternativa |
|---|---|---|---|---|
| 1 | **Pedra** | O mundo é "uma pedra plana" (`timeline_completa.txt:36`) | **Chão** | "onde o chão simplesmente para" (`timeline_completa.txt:42`) |
| 2 | **Geada** | Borda norte, fria (`timeline_completa.txt:42`), depois o Ermo Branco (`:160`) | **Farol** | O Farol da Chama Negra "no ponto mais ao norte do mundo" (`timeline_completa.txt:16`) |
| 3 | **Maré** | A leste "o oceano termina numa borda invisível" (`timeline_completa.txt:38`) | **Orla** | Mesma linha (a borda do mar) |
| 4 | **Eco** | "o vazio sul tem som — não vento, não eco" (`timeline_completa.txt:44`) | **Sem-Nome** | "algo que não tem nome em nenhuma língua" (`timeline_completa.txt:44`) |
| 5 | **Serra** | A oeste "uma cadeia de montanhas marca o fim da terra" (`timeline_completa.txt:40`) | **Cume** | "Quem as escala alto o suficiente encontra o universo do lado de fora" (`timeline_completa.txt:40`) |

Exemplos de data com os nomes propostos: "1º dia de Morrakh, Pedra — Ano 1"
(início do ano), "13º dia de Malagor, Maré — Ano 1", "20º dia de Thessrak, Serra
— Ano 2" (último dia do ano). Com as alternativas: "3º dia do Céu Vermelho, Maré
— Ano 1".

### 3.7 Reposicionamento das 14 festas (`[303] data/world/festivals.json`)

`L` = tamanho da estação no calendário novo (primavera 20, demais 40).
"Proporcional" aplica a R10. "Proposto" é o valor que vai para o JSON.

| id | 303: estação, dia/14, duração | Proporcional (dia na estação) | **Proposto** | Nota |
|---|---|---|---|---|
| `dia_da_fundacao` | verão 7, 2 d | 18 → 18º de Vaelith | **18–19 de Vaelith** | — |
| `noite_do_silencio` | inverno 1, 1 d | 1 → 1º de Vorrnak | **1º de Vorrnak** | Vorrnak apagava o som (`timeline_completa.txt:328`) |
| `procissao_de_vaelorn` | outono 5, 1 d | 12 → 12º de Solveth | **12º de Solveth** | procissão espectral no mês da névoa |
| `noite_dos_nomes` | outono 1, 1 d | 1 → 1º de Solveth | **1º de Solveth** | abre a Noite Longa de Skallgard |
| `fim_do_ceu_vermelho` | primavera 3, 1 d | 3 → 3º de Morrakh | **3º de Morrakh** | — |
| `dia_da_estaca` | outono 2, 1 d | 3 → 3º de Solveth | **3º de Solveth** | — |
| `rito_da_memoria` | verão 8, 1 d | 21 → 1º de Malagor | **1º de Malagor** | — |
| `colheita_do_po_de_sonho` | outono 8, 2 d | 21 → 1º de Orrakh | **1–2 de Orrakh** | — |
| `dia_da_simbiose` | primavera 6, 2 d | 8 → 8º de Morrakh | **8–9 de Morrakh** | — |
| `vigilia_dos_afogados` | inverno 6, 1 d | 15 → 15º de Vorrnak | **6º de Thessrak** (desvio, D5) | Aethelgard: Thessrak foi selado nas câmaras submersas e os Afogados são quem o ouviu (`timeline_completa.txt:332`). Continua no inverno |
| `noite_das_cores_erradas` | verão 10, 1 d | 26 → 6º de Malagor | **6º de Malagor** | — |
| `colheita_das_carcacas` | outono 9, 2 d | 23 → 3º de Orrakh | **3–4 de Orrakh** | Costa Negra no mês do mar parado (`timeline_completa.txt:336`) |
| `dia_do_levante` | primavera 9, 1 d | 12 → 12º de Morrakh | **12º de Morrakh** | — |
| `cancoes_de_pedra` | inverno 4, 1 d | 9 → 9º de Vorrnak | **9º de Vorrnak** | — |

Nenhum local tem duas festas no mesmo dia (teste). O anúncio de 2 dias antes
(303 R19) pode cair no mês anterior. Exemplo: `noite_dos_nomes` é anunciada no
19º de Malagor.

### 3.8 Migração dos campos da SPEC-303

| Campo/símbolo da 303 | Destino na 307 |
|---|---|
| `constants.SEASON_DAYS` (`[303] data/world/calendar.json:3`) | removido; `MONTH_DAYS`, `WEEK_DAYS`, `YEAR_BASE` |
| `CalendarParams.season_days` (v1) | `month_days`/`months`/`week_days` (v2); v1 lido só por `migrate_calendar` |
| `SEASONS` (`[303] services/world_calendar.py:24`) | mantido como chaves canônicas; a estação vem de `months()[i].season` |
| `season_at` (`:86-97`) | mantida (assinatura e saída iguais), derivada de `date_at` |
| `season_view` / `world["season"]` | mantidos; `day_in_season` 1..`season_len` |
| `labels` regionais ("Noite Longa", "Estação do Vidro") | mantidos por `season`. Noite Longa = meses 4–7, Dia Longo = 1–3, Estação do Vidro = Vaelith+Malagor |
| `festivals.json` `season` + `day_in_season` | `month` + `day_of_month` (§3.7) |
| `festival_schedule` (`:200-216`) | por mês+dia, com `year_offset` |
| recriação por versão (`:371-373`) | `migrate_calendar` (R19) |
| `invariants.py:2024` (`season_days`) | menor estação v2 (R24) |
| `weather_mult`, `pressure_offsets`, `encounter_mult`, `passes` | sem mudança de chave; só recalibração (R26) |

## 4. Plano passo a passo

Pré-condição: SPEC-303 implementada (worktree `rpg-spec-303`). Ordem de pouso:
D7. Um marco só, com `/spec-land` próprio.

### Etapa 0 — Base

1. Ler o `world_calendar.py` pousado pela 303 e alinhar a §3.4/§3.8 se os nomes
   mudaram (mesmo commit).
2. Ownership: `world_sim.calendar` e `world["date"]`/`world["season"]` têm um
   único writer, `services/world_calendar.py`, chamado só pelo hook e pelo
   `init_new_game`. A API só lê.

### Etapa 1 — Calendário v2 puro

1. **Testes** (`tests/test_spec307_calendar.py`):
   - `test_year_is_7_months_of_20_days_week_of_5` (R1);
   - `test_months_climate_two_cold_two_hot_three_transition` (R2);
   - `test_season_months_contiguous_cyclic_order` (R2);
   - `test_first_of_every_month_same_weekday` (R3);
   - `test_date_at_pure_deterministic_and_no_global_random` (R4, AST);
   - `test_season_at_compat_shape_unchanged` (R4);
   - `test_first_turn_month_and_season_between_4_and_8_days` (R6, 200 ids × anchors 1/7/33);
   - `test_same_game_id_same_start_season_as_v1` (R6);
   - `test_params_frozen_when_month_days_changes` (R7);
   - `test_unknown_version_neutral_never_recreated` (R7);
   - `test_skallgard_noite_longa_months_4_to_7` (R8);
   - `test_date_label_format_table` (R12: 1º, 3º, 20º, preposições "de/do/da/dos");
   - `test_year_monotonic_and_year_base` (R14);
   - `test_calendar_independent_of_player` (R23).
2. **Implementação:** `services/world_calendar.py` (v2), `data/world/calendar.json`,
   `state.py`. Atualizar os 2 testes da 303 citados na §3.2.

### Etapa 2 — Festas

1. **Testes** (`tests/test_spec307_festivals.py`):
   - `test_catalog_month_day_valid` (R9);
   - `test_each_festival_keeps_303_season` (R10, tabela congelada);
   - `test_winter_festivals_in_cold_months`;
   - `test_proportional_rule_matches_table_except_listed_deviations` (R10);
   - `test_no_location_two_festivals_same_day`;
   - `test_schedule_two_years_once_or_cancel` (R11/S4).
2. **Implementação:** `festivals.json`, `festival_schedule`.

### Etapa 3 — Migração

1. **Testes** (`tests/test_spec307_migration.py`):
   - `test_migrate_v1_preserves_season_and_year_on_day` (R19, 56 dias × 3 offsets);
   - `test_hook_migrates_instead_of_recreating` (P4);
   - `test_active_festa_kept_announced_rescheduled` (R20);
   - `test_no_festival_twice_same_year_after_migration` (R20);
   - `test_save_without_calendar_creates_v2_next_tick` (R21);
   - `test_save_load_roundtrip_v1_v2_none` (R21).
2. **Implementação:** `migrate_calendar`, `calendar_for_read`, troca no hook.

### Etapa 4 — Exibição, narrador e API

1. **Testes** (`tests/test_spec307_display_api.py`):
   - `test_clock_label_legacy_byte_identical_off_shadow_none` (R13/R22);
   - `test_clock_label_with_calendar_on` (R13);
   - `test_clock_label_stale_view_falls_back` (R13);
   - `test_world_date_written_by_hook_and_init_only_on` (R15);
   - `test_api_world_block_date_and_news_date_label` (R16);
   - `test_api_never_leaks_epoch_year_offset_catalog` (R16);
   - `test_api_v1_calendar_read_converted_without_write` (R16);
   - `test_storyteller_prompt_has_date_and_no_invent_rule` (R18);
   - `test_no_extra_llm_call_on_day_turn` (R18).
2. **Implementação:** `clock_label`, chamadores, `_world_block`, prompt.
3. **Web:** `PlayScreen.tsx`, `heardNews.ts`, `types.ts`. `npm run build` e o e2e
   do relógio, se existir; senão um teste de unidade do formatador.

### Etapa 5 — Playtest e calibração

1. **Testes** (`tests/test_spec307_playtest.py`):
   `test_params_changed_allows_single_v1_to_v2`,
   `test_season_regressed_uses_v2_lengths`,
   `test_date_regressed_and_stale` (estado sintético),
   `test_report_has_months_seen`.
2. **Implementação:** R24–R25; horizonte de 280 dias no simulador; rodar R26 e
   R27; ajustar só `pressure_offsets` se preciso; registrar em
   `docs/spec307/README.md`.
3. Ruff nos arquivos tocados. Suíte completa (`-n auto`) 1× no pouso.

## 5. Critérios de aceite

- [ ] R1–R8: ano de 7 × 20 dias, semana de 5, mês com clima (2/2/3), estações
      contíguas, virada em 4–8 dias, parâmetros congelados, rótulos regionais
- [ ] R9–R11: 14 festas em mês+dia, estação da 303 preservada, desvio da Vigília
      conforme D5, S4 em 2 anos
- [ ] R12–R18: data "Nº dia de <Mês>, <Dia> — Ano N" no HUD, nas notícias e no
      narrador; legado byte a byte em `off`/`shadow`; sem chamada LLM nova
- [ ] R19–R22: migração v1 → v2 sem salto de estação nem de ano; saves v1/v2/sem
      calendário carregam; modos `off`/`shadow`/`on`
- [ ] R24–R27: invariantes, telemetria, recalibração S1–S4 e letalidade M1/M2/M5
      registradas em `docs/spec307/README.md`
- [ ] Nenhum `with_structured_output` novo (o guard de FallbackLLM não se aplica)
- [ ] `uv run pytest` verde (suíte completa offline)
- [ ] Revisão independente Opus (`handoffs/SPEC-307-review.md`) sem P0/P1
- [ ] Smoke real (§6) executado e registrado

## 6. Smoke test com LLM real

Não há chamada nova, mas o narrador passa a receber nomes de mês e de dia que a
LLM nunca viu. O MockLLM não mostra se ela respeita esses nomes ou inventa
"janeiro", "segunda-feira" ou outra data. Pré-requisito: `RPG_WORLD_ENGINE=on`,
`RPG_CALENDAR=on`, DeepSeek nas `ROUTES`. Teto: US$ 0,50.

1. `uv run python -m playtest run --profile explorador --turns 15 --real --max-cost 0.25 --seed 31`:
   `mock=False`; o transcrito tem ≥ 2 dias virados; o `Momento:` do prompt e o
   `/game/state` (`world.date.label`) batem com o `world_clock.day`; a troca de
   mês acontece entre o 4º e o 8º dia; 0 violação `error`.
2. Leitura humana de 5 narrações que citam tempo: nenhum mês, dia da semana ou
   ano fora do calendário de Valoria; nenhuma data inventada.
3. Save sintético com calendário v1 (gerado pela 303) a 2 dias da
   `noite_do_silencio`: carregar, descansar 3×. A migração mantém a estação, o
   anúncio aparece, "em silêncio" entra no 1º de Vorrnak e a narração usa a data
   nova.
4. Staging, depois do pouso: 1 sessão manual de ~10 ações com descanso. O relógio
   do HUD mostra a data nova e as notícias trazem `date_label`.

Estourou o teto: parar e registrar.

## 7. Riscos & compatibilidade

- **Saves com calendário v1 (303):** migração pura (R19) que preserva estação e
  ano no dia do tick. Os ids de festa continuam por ano exibido, então não há
  repetição (R20). Até o primeiro tick, a API converte em memória (R16) e não
  grava nada.
- **Saves sem calendário:** iguais à 303 (liga no próximo dia virado), com rótulo
  legado até lá.
- **Rollback:** `RPG_CALENDAR=off` volta ao rótulo legado byte a byte. As chaves
  v2 ficam inertes. Um downgrade para o código da 303 recriaria o calendário v1
  pela `:371-373` dela; isso só é aceitável em rollback emergencial e fica
  documentado.
- **Balanceamento:** inverno, verão e outono passam de 14 para 40 dias seguidos, e
  a primavera de 14 para 20. Fome no inverno de Skallgard e o passo fechado duram
  quase 3× mais em dias corridos. Mitigação: R26/R27, ajustando só
  `pressure_offsets`/`PASS_EXTRA_PERIODS`.
- **Lore:** "seis meses" (P6) fica dissonante até a autoria corrigir (D6). Os
  nomes dos dragões são públicos no Codex, então não há spoiler. O Codex ainda não
  tem entrada do calendário, e o narrador só conhece o nome pela linha `Momento:`
  e pela regra de não inventar (R18).
- **Narração:** a LLM pode tratar "Malagor" como presença do dragão ("3º dia de
  Malagor" lido como ameaça). Mitigação: smoke §6.2. Se acontecer, a linha passa
  a dizer "mês de Malagor" só no prompt (ajuste de template, sem mudar o HUD).
- **MockLLM/FallbackLLM:** sem structured output novo. Tudo é Python puro e a
  suíte offline cobre.
- **Quota/latência:** zero chamada nova; O(7) por cálculo de data.

## 8. Evidência

A preencher na implementação: tabelas R26/R27 e o smoke em
`docs/spec307/README.md`.

## 9. Decisões do dono

### Dadas em 2026-10-24 (encomenda)

- Ano de 7 meses, semana de 5 dias, mês = 4 semanas = 20 dias, ano de 140 dias.
- Cada mês tem a sua estação: 2 de frio, 2 de calor, 3 de transição. Substitui
  as 4 estações genéricas de 14 dias da 303.
- As 14 festas aprovadas da 303 são reposicionadas mantendo o sentido.
- Exibição "3º dia de <Mês>, <Dia-da-semana> — Ano N" no HUD e no narrador. O
  período do dia continua.
- O tempo continua passando só em viagem e descanso, e o motor roda 1× por dia.
- Migração suave de saves. Mecânica em Python determinístico. Status `approved`.

### Escolhas abertas (o default recomendado vale até o dono trocar)

- **D1 — Nomes dos meses.** Default: os Sete do Monte (Morrakh, Vaelith, Malagor,
  Solveth, Orrakh, Vorrnak, Thessrak). Alternativa por mês na §3.6 (Cheia, Vidro,
  Céu Vermelho, Cinza, Corvos, Ermo, Chama Negra). Dá para misturar mês a mês.
- **D2 — Nomes dos dias.** Default: Pedra, Geada, Maré, Eco, Serra. Alternativas
  na §3.6 (Chão, Farol, Orla, Sem-Nome, Cume).
- **D3 — Quais são os 3 meses de transição.** Default: 1 de primavera (mês 1) e
  2 de outono (meses 4–5), o que dá Noite Longa de 57 % do ano em Skallgard.
  Alternativa: 2 de primavera e 1 de outono (Noite Longa de 43 %).
- **D4 — Ano exibido.** Default: `YEAR_BASE = 1` (toda campanha começa no Ano 1).
  Alternativa: um número fixo da Era 7 (o dono escolhe o ano; a lore não fixa,
  `timeline_completa.txt:416-420`).
- **D5 — Vigília dos Afogados.** Default: 6º de Thessrak (desvio temático, §3.7).
  Alternativa: 15º de Vorrnak (proporcional puro).
- **D6 — "Seis meses" na lore** (`creatures.txt:64`, `items.txt:139`). Default:
  numa tarefa de autoria, trocar por "metade do ano" (a Noite Longa da D3
  default tem 4 dos 7 meses). Alternativa: manter o texto como "conta antiga".
- **D7 — Ordem de pouso.** Default: aplicar a 307 no branch da 303 antes de a 303
  pousar, para nenhum save v1 existir fora do ambiente local (a migração R19 é
  implementada e testada do mesmo jeito). Alternativa: pousar a 303 primeiro e a
  307 depois.
- **D8 — Chip de estação regional no HUD.** Default: mostrar " · Noite Longa" /
  " · Estação do Vidro" só nas regiões que têm rótulo próprio. Alternativa: nunca
  mostrar (o mês já diz o clima).


## Decisões do dono (2026-10-24)

- **D1 meses:** "Os Sete do Monte" — Morrakh, Vaelith, Malagor, Solveth, Orrakh, Vorrnak, Thessrak.
- **D2 dias da semana (substitui a proposta):** **"Os Cinco Sinos"**, do Anel de Ferro, onde o sino é a única forma de
  saber a hora (`lore_nova/daily_life.txt:9`): **Sino de Ferro, Sino de Bronze, Sino de Cobre, Sino de Estanho, Sino Mudo**
  (o Sino Mudo é o dia em que ninguém trabalha). Forma curta para HUD: Ferro, Bronze, Cobre, Estanho, Mudo.
  Data exibida: "3º dia de Vorrnak, Sino de Cobre — Ano 112 da Era 7".
- **D3:** 1 mês de primavera + 2 de outono (recomendado).
- **D4 (substitui a proposta):** ano FIXO da Era 7, contado da fundação de Nova Arcádia: **Ano 112 da Era 7** no início de toda
  campanha (a timeline diz que os conselhos governaram "por décadas" antes de Valerius, `timeline_completa.txt:432`).
  Valor em dado curado (`data/world/calendar.json`), marcado `review: "dono"`.
- **D5–D8:** defaults recomendados (Vigília dos Afogados no 6º de Thessrak; "seis meses" da lore → "metade do ano" em tarefa
  de autoria; 307 aplicada no branch da 303 antes do pouso dela; chip de estação regional só onde há rótulo próprio).
