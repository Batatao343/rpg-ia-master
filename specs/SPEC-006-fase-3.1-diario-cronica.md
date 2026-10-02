# SPEC — Fase 3.1: Diário + Crônica melhorada (capítulos por arco)

> **Status:** `done` (smoke com LLM real executado 2026-07-03 — ver §6)
> **Criada:** 2026-07-03 · **Atualizada:** 2026-07-03
> **Depende de:** [SPEC-003-fase-2.6-structured-events.md](SPEC-003-fase-2.6-structured-events.md) (`done`),
> [SPEC-004-fase-2.7-rules-engine.md](SPEC-004-fase-2.7-rules-engine.md) (`done`)
> **Desbloqueia:** Fase 3.2 (codex revelável — âncora de descoberta), 3.3 (quest log),
> backlog "Melhorias da Crônica" (compressão, busca, download)

---

## 1. Contexto & Objetivo

A crônica hoje é `chronicle: List[str]` — lista flat de prosa de menestrel gerada pelo
LLM do archivist. Três problemas de clareza (Fase 3 = "jogador entende o mundo"):

1. **Eventos importantes podem NUNCA entrar na crônica.** O archivist roda com cadência
   (evento relevante OU ~10 turnos) e o LLM decide se escreve `chronicle_entry`. Morte de
   um líder de fação, mudança de controle de local, cascatas da rules engine — tudo isso
   já existe **estruturado e auditável** no `event_log` (2.6/2.7), mas a crônica que o
   jogador vê depende de o LLM lembrar de mencionar.
2. **Sem estrutura temporal.** Entradas não têm turno nem capítulo; após 50 turnos a aba
   Crônica é um paredão de texto sem "onde eu estava quando isso aconteceu".
3. **Trivial e importante se misturam.** O critério do ROADMAP: trivial fica na memória
   (narrative_summary/RAG), importante vai à crônica — hoje não há separação garantida.

Solução (princípio "LLM propõe, motor aplica" — ROADMAP § Princípios): **milestones
determinísticos** derivados do `event_log` (Python, zero LLM) + **prosa de menestrel**
(LLM, cor narrativa) organizados em **capítulos ancorados nos arcos** do campaign_manager.

## 2. Requisitos

- **R1** — `state.py` define `ChronicleEntry` (`text`, `turn`, `kind: "milestone"|"prose"`,
  `event_id` opcional) e `ChronicleChapter` (`title`, `started_turn`, `location`,
  `entries`). `GameState.chronicle` passa a ser `List[ChronicleChapter]`.
- **R2** — Todo `GameEvent` **aplicado** (validado pelo event_processor, incluindo cascata
  da rules engine) cujo `type` ∈ `CHRONICLE_EVENT_TYPES` gera uma entrada `milestone` no
  capítulo atual, **deterministicamente** (template Python, sem LLM), com `event_id` para
  auditoria e nome canônico (não id cru).
- **R3** — Evento rejeitado pelo validador ou de tipo fora de `CHRONICLE_EVENT_TYPES`
  NÃO gera milestone (trivial fica só em narrative_summary/RAG).
- **R4** — O archivist appenda `chronicle_entry` (quando o LLM escreve) como entrada
  `kind="prose"` no capítulo atual, com `turn` registrado.
- **R5** — `CampaignPlan` ganha `arc_title: str` (gerado no MESMO call do planner, campo
  novo no `CampaignPlanModel`). Replan que muda `arc_title` abre capítulo novo
  (`title=arc_title`, `started_turn`, `location`). Replan com mesmo título NÃO quebra
  capítulo (evita capítulo novo a cada 10 turnos).
- **R6** — Saves antigos (`chronicle` como `List[str]`) carregam sem crash: backfill em
  `load_game_state` converte para capítulo único `"Crônica da jornada"` com entradas
  `kind="prose"`, `turn=0`.
- **R7** — API expõe capítulos estruturados; frontend renderiza separador por capítulo
  (título + turno de início) e distingue visualmente milestone de prosa. Ordem: capítulo
  mais recente primeiro; dentro do capítulo, entrada mais recente primeiro.
- **R8** — Sem jogo iniciado por `/game/new` ou CLI, o primeiro capítulo existe desde o
  turno 0 (título derivado da região inicial — determinístico, sem LLM).

### Fora de escopo

- Compressão de capítulos antigos (>20 entradas) — backlog "Melhorias da Crônica".
- Busca na crônica (`POST /game/chronicle/search` via RAG) — backlog.
- Download .txt — backlog.
- Reconstruir capítulos retroativos para saves antigos (viram capítulo único).
- Mudar cadência/triggers de replan do campaign_manager (bug "plot twist frequente" é
  item separado; R5 só mitiga o efeito na crônica).
- Diário de quest/objetivos — é a spec 3.3 (quest log).

## 3. Design técnico

### Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `services/chronicle.py` | Templates de milestone, abertura de capítulo, append determinístico |
| `tests/test_fase31.py` | Suíte da fase |

### Arquivos alterados

- `state.py` — `ChronicleEntry`, `ChronicleChapter`; `chronicle: List[ChronicleChapter]`;
  `CampaignPlan.arc_title: str`
- `services/event_processor.py` — após cada `apply_event` bem-sucedido (inclusive cascata
  da rules engine), coleta milestones e devolve `chronicle` atualizado nos updates
- `agents/archivist.py` — `chronicle_entry` vira `ChronicleEntry(kind="prose")` no
  capítulo atual; prompt instrui a NÃO repetir fatos secos (mortes/conquistas já são
  milestones) e focar em cor narrativa
- `agents/campaign_manager.py` — `CampaignPlanModel.arc_title` + abertura de capítulo
  quando o título muda (fallback do plan usa título determinístico)
- `persistence.py` — backfill de `List[str]` → capítulo único no `load_game_state`
- `api.py` — `GameResponse.chronicle: List[Dict]` (capítulos); `/game/new` cria capítulo
  inicial; `format_response` serializa capítulos
- `game_engine.py` — criação de jogo espelha o capítulo inicial do `/game/new`
- `web/src/types.ts` + `web/src/components/Hud.tsx` (`ChronicleTab`) + `web/src/styles.css`
  — renderização por capítulos

### Schemas (state.py)

```python
class ChronicleEntry(TypedDict, total=False):
    text: str
    turn: int
    kind: str        # "milestone" (determinístico, do event_log) | "prose" (menestrel LLM)
    event_id: str    # só milestones — auditoria (aponta para GameEvent.event_id)


class ChronicleChapter(TypedDict, total=False):
    title: str
    started_turn: int
    location: str            # current_location no momento da abertura
    entries: List[ChronicleEntry]
```

`CampaignPlan` (existente) ganha `arc_title: str` (`total=False` — saves antigos não têm).

### services/chronicle.py

```python
# Tipos que merecem crônica (alto impacto). faction_relation_changed fica FORA
# (ruído — mudanças de relação são frequentes e já aparecem via reputação/2.7).
CHRONICLE_EVENT_TYPES = {
    "npc_killed", "location_control_changed", "quest_completed", "secret_revealed",
}

# Templates voltados ao JOGADOR (prosa curta), diferentes dos EVENT_TEMPLATES
# telegráficos do context_builder (que servem ao LLM). Reusa services.context_builder._name
# para resolver id canônico → nome.
CHRONICLE_TEMPLATES: Dict[str, str] = {
    "npc_killed": "{target} tombou{by_player}.",
    "location_control_changed": "{controller} tomou o controle de {target}.",
    "quest_completed": "A missão \"{target}\" foi concluída.",
    "secret_revealed": "Um segredo veio à luz: {fact}",
}

def render_milestone(event: GameEvent, projection: Dict) -> str
    # 1 frase; tipo fora de CHRONICLE_EVENT_TYPES ou template faltando → "".
    # secret_revealed usa world_projection.revealed_facts[event_id].fact.

def current_chapter(chronicle: List[ChronicleChapter]) -> ChronicleChapter
    # último capítulo; se lista vazia, cria "Crônica da jornada" (started_turn=0).

def append_entry(chronicle: List[ChronicleChapter], *, text: str, turn: int,
                 kind: str, event_id: str = "") -> List[ChronicleChapter]
    # PURO: retorna cópia rasa com entrada no capítulo atual (agentes retornam dict parcial).

def open_chapter(chronicle: List[ChronicleChapter], *, title: str, turn: int,
                 location: str) -> List[ChronicleChapter]
    # No-op (retorna original) se título == título do capítulo atual.

def default_chapter_title(region: str) -> str
    # f"O início da jornada — {region}" (capítulo 1, sem LLM).
```

### Integração event_processor

`process_pending_events` já itera eventos validados e chama `apply_event` (+ `run_rules`
que retorna eventos de cascata). Após cada aplicação bem-sucedida:

```python
milestone = render_milestone(event, projection)
if milestone:
    chronicle = append_entry(chronicle, text=milestone, turn=event.get("turn", 0),
                             kind="milestone", event_id=event["event_id"])
```

Eventos da cascata (`source="rule_engine"`) passam pelo mesmo caminho — "vácuo de poder"
aparece na crônica sem código especial. O dict de updates retornado ganha a chave
`chronicle` quando houve mudança.

### Integração archivist

No caminho estruturado (`isinstance(result, MemoryUpdate)`):

```python
if entry:
    updates["chronicle"] = append_entry(state.get("chronicle") or [],
                                        text=entry, turn=turn, kind="prose")
```

**Atenção à ordem de merge:** o archivist hoje faz `{**updates, **event_updates}` — se os
dois lados tocarem `chronicle`, os milestones de `event_updates` venceriam e a prosa se
perderia. Processar `event_updates` PRIMEIRO e appendar a prosa sobre o chronicle já
atualizado (ler de `event_updates.get("chronicle")` se presente, senão do state).

Prompt: adicionar à tarefa 3 — "NÃO registre mortes, conquistas de locais ou missões
concluídas como fato seco (o registro oficial já existe); escreva apenas a cor narrativa,
ou deixe vazio".

### Integração campaign_manager

`CampaignPlanModel` ganha:

```python
arc_title: str = Field(description="Short evocative arc title (3-6 words, PT-BR). "
                                   "KEEP the previous title if the story arc continues; "
                                   "change it ONLY when a truly new arc begins.")
```

Prompt do planner recebe o `arc_title` atual (se existir) com a mesma instrução de
persistência. No `campaign_manager_node`, após `_build_plan`:

```python
new_title = (new_plan.get("arc_title") or "").strip()
old_title = (state.get("campaign_plan") or {}).get("arc_title", "")
if new_title and new_title != old_title:
    updated_state["chronicle"] = open_chapter(state.get("chronicle") or [],
        title=new_title, turn=world["turn_count"], location=world.get("current_location", ""))
```

Fallback do plan (exceção do LLM): `arc_title` = título atual (não abre capítulo) ou
`default_chapter_title(current_loc)` se não houver plano. Guard de FallbackLLM: o acesso
a `plan.arc_title` já está dentro do `try` existente de `_build_plan`.

### Persistência (backfill)

Em `load_game_state`, no bloco de recuperação:

```python
raw_chron = raw_data.get("chronicle", [])
if raw_chron and isinstance(raw_chron[0], str):
    raw_chron = [{"title": "Crônica da jornada", "started_turn": 0, "location": "",
                  "entries": [{"text": t, "turn": 0, "kind": "prose"} for t in raw_chron]}]
```

`save_game_state` não muda (capítulos são dicts JSON-serializáveis).

### API + frontend

- `GameResponse.chronicle: List[Dict[str, Any]] = []` — capítulos serializados direto.
- `format_response`: filtra entradas vazias; mantém shape dos capítulos.
- `/game/new` e `game_engine.py`: `"chronicle": [ {título default, started_turn: 0, ...} ]`
  via `default_chapter_title(final_char["region"])`.
- `ChronicleTab` (Hud.tsx): capítulos em ordem reversa; header com `title` +
  `"desde o turno N"`; entradas reversas dentro do capítulo; `kind="milestone"` com marca
  própria (ex.: ⚔ em vez de ❧) e classe CSS distinta (`chron--milestone`).
- `web/src/types.ts`: `chronicle: ChronicleChapter[]` espelhando o schema.

## 4. Plano passo a passo

### Etapa 1 — services/chronicle.py puro

1. **Testes** (`tests/test_fase31.py`):
   - `test_render_milestone_npc_killed` — evento `npc_killed` de entidade canônica →
     frase com NOME (não id cru).
   - `test_render_milestone_tipo_ignorado` — `faction_relation_changed` → `""`.
   - `test_render_milestone_secret` — `secret_revealed` usa `revealed_facts[event_id].fact`.
   - `test_append_cria_capitulo_default` — chronicle vazio → capítulo "Crônica da jornada".
   - `test_open_chapter_mesmo_titulo_noop` — mesmo título → mesma lista (sem capítulo novo).
   - `test_append_e_puro` — lista original não é mutada.
2. **Implementação:** `services/chronicle.py` completo.
3. `uv run pytest` verde.

### Etapa 2 — Schema + backfill

1. **Testes:**
   - `test_save_antigo_chronicle_flat` — save com `chronicle: ["a", "b"]` carrega →
     1 capítulo, 2 entradas prose.
   - `test_save_novo_roundtrip` — save/load preserva capítulos.
2. **Implementação:** `state.py` (tipos) + `persistence.py` (backfill).
3. `uv run pytest` verde.

### Etapa 3 — Milestones no event_processor

1. **Testes:**
   - `test_evento_aplicado_gera_milestone` — `npc_killed` validado → updates contêm
     `chronicle` com entrada `kind="milestone"` e `event_id` correto.
   - `test_evento_rejeitado_sem_milestone` — proposta inválida → chronicle inalterado.
   - `test_cascata_gera_milestone` — morte de líder (2.7) → milestone da morte E do
     `location_control_changed` da cascata.
2. **Implementação:** hook em `process_pending_events`.
3. `uv run pytest` verde.

### Etapa 4 — Archivist (prose) + campaign_manager (arc_title)

1. **Testes:**
   - `test_archivist_prose_no_capitulo` — MockLLM com `chronicle_entry` → entrada
     `kind="prose"` no capítulo atual, `turn` correto.
   - `test_archivist_merge_prose_e_milestone` — turno com evento + prosa → chronicle
     final contém AMBOS (ordem de merge correta).
   - `test_replan_muda_arco_abre_capitulo` — arc_title novo → capítulo novo.
   - `test_replan_mesmo_arco_nao_abre` — arc_title igual → sem capítulo novo.
   - Regressão: suíte existente do archivist/campaign verde.
2. **Implementação:** os dois agentes + `mock_llm.py` (MockLLM devolve `arc_title` no
   CampaignPlanModel e mantém `chronicle_entry` no MemoryUpdate).
3. `uv run pytest` verde.

### Etapa 5 — API + frontend

1. **Testes:**
   - `test_game_new_capitulo_inicial` — `/game/new` → chronicle com 1 capítulo, título
     contém a região.
   - `test_format_response_capitulos` — `format_response` serializa capítulos.
2. **Implementação:** `api.py`, `game_engine.py`, `types.ts`, `ChronicleTab`, CSS.
3. `uv run pytest` verde + `cd web && npm run build` sem erro + `bash scripts/smoke_api.sh`.

## 5. Critérios de aceite

- [x] Morte de líder de fação (validada) SEMPRE aparece na crônica como milestone, mesmo
      em turno em que o archivist não roda o LLM (`test_evento_aplicado_gera_milestone`)
- [x] Cascata da rules engine (controle de local mudou) vira milestone auditável
      (`event_id`) — `test_cascata_gera_milestone`
- [x] Turno trivial (sem evento aplicado, sem prosa) não toca a crônica
      (`test_evento_rejeitado_sem_milestone`, `test_replan_mesmo_arco_nao_abre`)
- [x] Replan com arc_title novo abre capítulo; replan de rotina (mesmo arco) não abre
- [x] Save antigo (`List[str]`) carrega e aparece como capítulo único
- [x] Frontend mostra capítulos com separadores e distingue milestone de prosa
      (`ChronicleTab` por capítulos; ⚔ + `chron--milestone` vs ❧; `npm run build` ok)
- [x] `uv run pytest` verde (228 offline)
- [x] Guard de FallbackLLM em todo `with_structured_output` novo (arc_title acessado
      dentro do try existente; archivist já tem isinstance)
- [x] Saves antigos continuam carregando

## 6. Smoke test com LLM real

(≤4 requests, dentro da quota 20/dia/modelo)

1. Campanha nova → conferir capítulo inicial no HUD; jogar 1 turno banal → crônica
   inalterada (LLM do archivist pode nem rodar).
2. Matar um líder de fação canônico → aba Crônica mostra milestone da morte + milestone
   da cascata (controle mudou), SEM depender do texto do menestrel.
3. Forçar replan em local novo → verificar se o planner troca `arc_title` com bom senso
   (novo arco = novo capítulo; continuação = mesmo capítulo). Este é o ponto com maior
   risco de mapeamento (campo novo no structured output) — MockLLM não pega.

**Executado 2026-07-03** (2 req gemini-pro, direto em `_build_plan`): (A) sem arco
anterior → planner inventou `arc_title` "Fagulhas na Chuva Fria" (mapeamento ok,
PT-BR, 3-6 palavras); (B) com arco "A Sombra sobre Nova Arcádia" e mesma situação →
MANTEVE o título (instrução de persistência respeitada). Itens 1–2 são determinísticos
e já cobertos pela suíte offline (`test_fase31.py`) + smoke API mock.

## 7. Riscos & compatibilidade

- **Saves antigos:** backfill no load (R6); `arc_title` ausente em planos antigos → primeiro
  replan com título abre capítulo normalmente.
- **MockLLM/FallbackLLM:** milestones são 100% determinísticos (funcionam no mock e até
  sem LLM nenhum); `arc_title` novo no `CampaignPlanModel` precisa entrar no MockLLM e o
  fallback de `_build_plan` já cobre exceção. Risco clássico "MockLLM esconde bug de
  mapeamento" concentrado no `arc_title` → smoke real item 3 obrigatório.
- **Ordem de merge no archivist:** prosa e milestones tocam a mesma chave `chronicle` —
  teste dedicado (`test_archivist_merge_prose_e_milestone`).
- **Capítulos demais:** se o LLM trocar arc_title em todo replan, crônica fragmenta.
  Mitigação: instrução de persistência no prompt + passar título atual. Se persistir na
  prática, adicionar histerese determinística (mín. N turnos por capítulo) em iteração.
- **Quota/latência:** zero chamadas LLM novas (arc_title pega carona no call existente
  do planner; milestones são Python puro).
