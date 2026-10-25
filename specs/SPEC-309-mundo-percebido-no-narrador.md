# SPEC-309 — Mundo percebido no narrador: templates do motor, memória do dia e `<MUNDO_PERCEBIDO>`

> **Status:** `in-progress` (implementada 24/10; aguarda revisão independente Opus; dono aprovou D1–D3 nos defaults em 24/10)
> **Criada:** 2026-10-24 · **Atualizada:** 2026-10-24
> **Origem:** `docs/mundo-vivo/REVISAO-ORQUESTRADA-2026-10-24.md` proposta **R2** (§4.1), achados **A7** e **A10** (§1.1), mapa de munição (§2.1); regras em `docs/mundo-vivo/VISAO.md:68-69` (rótulos sem números) e `:79-82` (regra de ouro)
> **Depende de:** **SPEC-308** (filtro de eventos do motor: helper `event_perceived(state, ev)`; precisa estar `done` antes da Etapa 2), SPEC-302 (`done`, motor/estados de local/digest), SPEC-303 e SPEC-307 (`done`, festas/calendário), SPEC-299/300/301/304 (`done`, tipos de evento de lei, companheiro, fação e destino de NPC)
> **Desbloqueia:** SPEC-311 (o planner passa a receber `<MUNDO_PERCEBIDO>`, proposta R8), SPEC-310 (o NPC reaproveita a mesma visão percebida)
> **EXECUTOR_MODEL:** `Sonnet` (bounded: um módulo novo + templates + 4 pontos de costura) · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (mexe em prompt de 3 agentes, na memória canônica do arquivista e na regra de ouro)
> **EVAL_AUTHORING_REQUIRED:** `false` (oráculo determinístico de não-vazamento nos testes; nenhum evaluator/dataset protegido é tocado)

---

## 1. Contexto & Objetivo

A onda 296–307 construiu um motor de mundo determinístico (pressões, crises, estados de
local, festas, lei, companheiros, patentes, destino de NPC). Quase nada disso chega à LLM.
O narrador recebe palavras de perigo, três notícias e, no dia que vira, um `[ECOS DO MUNDO]`
de 2 a 4 frases. Ele nunca é informado de que a cidade onde o herói está foi sitiada ou
entrou em festa, nem de que há sinais de guerra na região que o herói já ouviu. O
arquivista também não guarda que a cidade caiu, que um companheiro foi embora ou que o
herói cumpriu pena, porque esses eventos não têm template e renderizam como string vazia.

São três lacunas com a mesma causa: o motor não tem voz.

1. **Eventos invisíveis (A7).** `render_event` devolve `""` para todo tipo fora de
   `EVENT_TEMPLATES`. Esse texto vazio é a fonte de três consumidores: o pack
   `<ESTADO_ATUAL_DO_MUNDO>`, a memória canônica do arquivista e o texto de rumor do
   `npc_knowledge`.
2. **Narração diária sem rastro (A10).** `narrate_day` recebe só `FATO: <template>`. Seu
   texto entra no prompt do turno e some. A política `canonical_only` impede que o
   arquivista infira algo dele, mas nada no lugar vira memória.
3. **Prompt sem estado percebido.** O `public_label` do estado do local e a festa do dia já
   existem e não têm consumidor fora da API do mapa.

Esta spec dá voz ao motor **sem chamada LLM nova** e **sem quebrar a regra de ouro**: o
herói (e portanto o narrador) só sabe o que viu ou ouviu. O canal é sempre o mesmo. O motor
decide, um template determinístico escreve uma frase sem números, um filtro de percepção
decide quem pode ler (a SPEC-308 é dona do filtro) e a LLM só narra.

### 1.1 Problemas com evidência

| # | Problema | Evidência |
|---|---|---|
| P1 | `render_event` só conhece 7 tipos; o resto vira `""` (exceção: `faction_membership_changed`, via `event_text`) | `services/context_builder.py:64-72`, `:177-198` |
| P2 | Texto vazio é descartado no pack (`add` ignora `""`), então os eventos do motor nunca entram no `<ESTADO_ATUAL_DO_MUNDO>` | `services/context_builder.py:227-229`, `:276-284` |
| P3 | O arquivista grava memória canônica só de evento com texto. Sem template, não há memória de queda de cidade, partida de companheiro, prisão ou falha de quest | `agents/archivist.py:190-214` (`if not text: continue` em `:201-202`) |
| P4 | Tipos sem template: `location_state_changed`, `world_crisis_warning`, `companion_left`/`_betrayed`/`_fate`, `crime_witnessed`, `law_resolved`, `quest_failed`, `unique_item_claimed`/`_lost`, `npc_fate_learned` | `services/structured_outputs.py:44-68`; payloads em `services/world_director.py:319-332`, `:470-481`; `services/companion_soul.py:856-861`, `:987-989`; `services/law.py:812-823`, `:1153-1159`; `services/npc_world.py:1158-1167` |
| P5 | `narrate_day` recebe só `FATO:` por item. Não sabe o estado do local, a estação nem a festa | `agents/world_simulator.py:248-262` |
| P6 | O texto do dia vai só para `<EVENTOS_DESTE_TURNO>`. O turno ganha `memory_fact_policy="canonical_only"` e nenhum fato canônico, então o dia percebido não deixa memória | `agents/storyteller.py:746-753`, `:1257-1263`, `:1780-1781`; `agents/archivist.py:691-748` |
| P7 | `memory_canonical_facts` (allowlist de fatos do motor que o arquivista grava como `canonical_event`) existe e é persistida, mas **nenhum** código de produção escreve nela. Ela também só é limpa sob `canonical_only`, o que duplicaria fatos fora dessa política | `agents/archivist.py:693-700`, `:983-985`, `:1079-1081`; `persistence.py:685`, `:1024`; `state.py:969` |
| P8 | Se um encontro na estrada ocupa `world_note`, a narração do dia é pulada (`world_note or _narrate_world(...)`) e os itens percebidos não deixam rastro além de `world.news` | `agents/storyteller.py:1236-1263` |
| P9 | `public_label` do estado do local só é lido pela API do mapa | `services/location_states.py:84-92`; revisão §1.2 (`api.py:2983`) |
| P10 | A festa do dia (`world_sim.festivals`, estado `festa` com `festival_id`) não entra em prompt nenhum | `services/world_calendar.py:438-530`; `data/world/festivals.json:4-30` |
| P11 | O storyteller já recebe estação/data (`Momento`/`Estação`) e as 3 últimas notícias (`<OUVIU_DIZER>`). O NPC e o combate não recebem estação nem festa | `agents/storyteller.py:1311-1330`, `:1443`, `:1452`; `services/ambient.py:129-141`; `agents/npc.py:1080-1081`; `agents/combat.py:1484-1496` |
| P12 | Efeito colateral: o texto de rumor do NPC vem de `render_event`. Tipos sem template (crime, estado de local) propagam sem texto | `services/npc_knowledge.py:263-276`, `:48-69` |

## 2. Requisitos

### A. Templates de evento (`render_event`)

- **R1 — Cobertura.** `render_event` devolve uma frase pt-BR não vazia para os tipos da
  tabela §3.2: `location_state_changed` (início de estado, festa e fim de estado),
  `world_crisis_warning`, `companion_left`, `companion_betrayed`, `companion_fate`,
  `crime_witnessed`, `law_resolved`, `quest_failed`, `unique_item_claimed` (só
  `holder == "player"`), `unique_item_lost` e `npc_fate_learned` (só `fate ∈ {morto,
  capturado}`). Tipo desconhecido continua `""` (`tests/test_fase28.py:103` segue valendo).
- **R2 — Rótulos sem números.** Nenhum template novo inclui severidade, pressão, banda,
  tensão, fase do diretor, `earliest_day`, ouro, multa, heat ou bounty. O único número
  permitido é o `[turno N]` já usado pelos 7 templates existentes. Teste: a frase sem o
  prefixo `[turno N]` não casa `\d`.
- **R3 — Nomes só conhecidos.** O nome de local vem do mapa (`gamedata.get_location`). O de
  fação passa pela regra de `world_perception._faction_label`: fação desconhecida vira o
  rótulo genérico. O de NPC passa por `npc_world.npc_label`. Companheiro usa
  `payload.name`. Teste: evento com fação não conhecida não contém o nome do catálogo.
- **R4 — Classe de percepção por tipo.** Cada tipo novo é classificado em §3.2 como:
  - **testemunhado** (o herói estava lá ou foi o autor): companheiro saiu/traiu, lei, falha
    de quest, item único, destino de NPC já sabido;
  - **do motor** (`location_state_changed`, `world_crisis_warning`, `companion_fate`): só
    aparece se `event_perceived(state, ev)` (SPEC-308) for `True`.

  `render_event` continua puro e sem filtro. O filtro fica nos consumidores (R6, R9).
- **R5 — Impacto no ranking.** `_IMPACT_BY_TYPE` ganha os tipos novos com os pesos da §3.2
  (`[BALANCEAR]`). Tipo ausente usa `_DEFAULT_IMPACT` (0,4), como hoje.
- **R6 — Pack.** `collect_dynamic_facts` renderiza os tipos novos no `current_state` **só**
  quando `event_perceived(state, ev)` é `True`. Isso já vale para os existentes quando a
  SPEC-308 pousar; esta spec só garante que os tipos novos passam pelo mesmo portão. Com
  `knowledge_filter` (rota NPC, SPEC-215) nada muda: o laço de eventos é pulado.

### B. Memória do dia percebido (`narrate_day` → memória canônica)

- **R7 — Fato canônico do que foi percebido.** No turno em que `_perceive_world` devolve
  itens percebidos (`agents/storyteller.py:682-722`), o storyteller grava em
  `memory_canonical_facts` o **texto de template** de cada item (`world_perception.render`).
  É o mesmo texto que já vai para `world.news`. Vale haja ou não narração LLM do dia (P8).
  Ordem: a do digest. Itens com texto vazio ficam de fora. Duplicatas exatas são removidas.
  Teto: `DAY_FACTS_MAX = 6` (`[BALANCEAR]`).
- **R8 — Disparo e proveniência.** Se `memory_canonical_facts` não estiver vazia, o turno
  ganha `archive_due=True`. O arquivista grava cada fato como `canonical_event` com
  `source_id="engine_policy:{turn}"`, pelo caminho que já existe
  (`agents/archivist.py:734-748`). Esse prefixo é aceito por `source_is_applicable`
  (`services/memory_provenance.py:207-213`). Nenhum campo novo no `GameState`.
- **R9 — Sem duplicar com o evento.** Tipos **do motor** (`location_state_changed`,
  `world_crisis_warning`) **não** viram memória por `_event_memory_records`: a memória deles
  vem só por R7, no dia em que o herói percebe (e não no dia em que o motor decide). Tipos
  **testemunhados** viram memória por `_event_memory_records`. `companion_fate` também, mas
  só se `event_perceived` for `True`. Teste: crise aberta na região atual e percebida no
  mesmo turno gera **um** fato, não dois.
- **R10 — Limpeza sempre.** Depois de anexar os fatos ao ledger (`memory_facts`), o
  arquivista zera `memory_canonical_facts` mesmo sem `canonical_only`. A retentativa
  vetorial é da SPEC-234 e lê o ledger/`pending_memory_facts`, não esta allowlist. Teste: a
  2ª execução do arquivista não regrava o fato com outro `source_turn`.
- **R11 — Prosa da LLM não vira fato** (D1, default recomendado). O texto do `narrate_day`
  continua só no prompt do turno (`[ECOS DO MUNDO]`) e **não** é gravado como
  `canonical_event`. Ele é paráfrase da LLM: pode ter enfeite que não aconteceu, e
  `canonical_event` tem confiança `confirmed` (`services/memory_provenance.py:35-41`).
  Se o dono escolher D1-b, a prosa entra como `player_observation`, 1 por dia, com
  `source_id="engine_policy:day:{day}"`.
- **R12 — Munição do `narrate_day`.** `narrate_day(state, items)` passa a receber também, na
  mensagem humana, um bloco `CONTEXTO (não é fato novo):` com as linhas de
  `perceived_world_lines(state, audience="day")` (R14). O system prompt ganha uma frase:
  "use o CONTEXTO só para ambientar; os fatos continuam sendo só as linhas FATO". O guard de
  nomes (`agents/world_simulator.py:279-284`) e o fallback para template não mudam. Continua
  no máximo 1 chamada por ação.

### C. Bloco `<MUNDO_PERCEBIDO>`

- **R13 — Módulo puro.** O módulo novo `services/perceived_world.py` expõe
  `perceived_world_lines(state, *, audience) -> list[str]` e
  `perceived_world_block(state, *, audience) -> str`. Ambos são determinísticos (mesma
  entrada, mesma saída byte a byte), não usam `random`, não chamam LLM nem RAG e nunca
  levantam exceção (erro → `""` + `log_fallback`).
- **R14 — Conteúdo, em ordem de prioridade.** Só entra o que o herói percebe:
  1. **Local atual** (percebido por presença). Se `location_state(state, cur)` tiver
     estado, a linha é `"{local} está {public_label}."` (ex.: "Brekmar está sitiada.").
     Interior herda do pai (`services/location_states.py:27-39`). Com estado `festa` e
     `festival_id`, a linha é `"Hoje: {festival.name} — {local} está {label}."`.
  2. **Festa próxima no local atual** (presença). Registro de `world_sim.festivals` com
     `status == "anunciada"`, `cur` em `festival.location_ids` e
     `start_day - hoje <= FESTIVAL_HERALD_DAYS` dá `"Nos próximos dias: {festival.name}."`.
     Sem número de dias.
  3. **Crise percebida na região atual** (no máximo 2 linhas). Para cada `crisis_id`, o
     **último** evento `location_state_changed`/`world_crisis_warning` com
     `payload.crisis_id` igual, da região atual, com `event_perceived` `True`. Se for aviso:
     `"Há sinais de {rótulo_da_crise} em {região}."`. Se for estado aberto em outro local
     da região: `"Pelo que o herói soube, {local} está {label}."`. Se for fim de estado, a
     crise não gera linha. A linha deriva do que foi **percebido**, não de
     `world_sim.crises`. Assim o fim de uma crise que o herói não soube não some do bloco
     (sem vazamento por ausência).
  4. **Estação** (só nas audiências `npc`, `combat` e `day`): `"Estação: {label_for(season,
     região)}."`. Na audiência `story` a estação já está em `Momento`/`Estação`
     (`agents/storyteller.py:1323-1330`, `:1443`) e não se repete.
- **R15 — O que o bloco nunca contém.** Severidade, pressão, banda, tensão, fase do diretor,
  multiplicador de preço, dia de início/fim, `crisis_id`, fação atacante não conhecida,
  crise de outra região, local que o herói não percebeu, notícias (o storyteller já tem
  `<OUVIU_DIZER>`; o NPC fica com a SPEC-310). Teste-oráculo §3.6.
- **R16 — Orçamento.** No máximo `MAX_LINES = 4` linhas e `MAX_TOKENS = 120` tokens por
  `context_builder.estimate_tokens`. Se passar, cortam-se as linhas de menor prioridade
  (R14, de baixo para cima), nunca o meio de uma linha. Sem nada a dizer, o bloco é `""` e a
  tag não aparece (zero token, como `<LEI_NA_CENA>`).
- **R17 — Gate de modo.** Com `RPG_WORLD_ENGINE != on`, as linhas 1–3 não existem. No modo
  `shadow` a projeção real não é escrita (`services/world_engine.py:43-44`, `:631-633`) e
  a sombra nunca entra em prompt. A linha 4 depende só do calendário existir
  (`world_calendar.active_season`).
- **R18 — Storyteller.** O bloco entra logo após `{ambiente_block}`
  (`agents/storyteller.py:1451`), com a instrução fixa: "Fatos do mundo que o herói percebe.
  Pode ambientar a cena com eles; não invente causa, duração nem gravidade."
- **R19 — Combate e NPC.** A narração de combate (`agents/combat.py:1494-1496`) recebe o bloco
  `audience="combat"` concatenado ao `world_ctx`. O prompt do NPC
  (`agents/npc.py:1080-1081`) recebe `audience="npc"`, que é só a linha 1 (estado do local
  da cena, que o NPC também vê) mais a estação (D3). `prepare_encounter` e o planner ficam
  fora (o planner é da SPEC-311).

### D. Compatibilidade e efeitos colaterais

- **R20 — Rumor do NPC ganha texto.** Com R1, `npc_knowledge._subject_text` passa a ter texto
  para `location_state_changed`, `world_crisis_warning` e `crime_witnessed`, que já estão em
  `SUBJECT_PARAMS` (`services/npc_knowledge.py:55-62`). Teste: o texto do assunto não tem
  número fora do `[turno N]` e não nomeia fação desconhecida; assinatura secreta continua
  barrada por `_is_secret` (`:279-282`).
- **R21 — Saves antigos.** Nenhum campo novo de estado. `memory_canonical_facts` ausente vira
  `[]` (`persistence.py:1024`). Evento antigo sem `payload.crisis_id`, `previous` ou `name`
  renderiza com fallback (`"um local"`, `"um companheiro"`) ou `""`, sem levantar. Teste com
  um save fixture pré-302.
- **R22 — Sem chamada nova.** O número de invokes por turno é igual ao baseline. Teste com
  contador de `get_llm().invoke`, como nos testes da SPEC-302.

### Fora de escopo

- O filtro de percepção em si (`event_perceived`, `offscreen=True` em `_ev()`, `perceived_ids`
  ∪ `_known_sources` independente de `RPG_NPC_WORLD`): **SPEC-308**.
- O NPC saber de si, ver `world.news` da sua região e chamar `npc_knowledge_block`
  (proposta R3, A6): **SPEC-310**.
- O planner receber `<MUNDO_PERCEBIDO>`/`<QUESTS_ATIVAS>` e replanejar por crise (R8, A9), o
  motivo do preço no loot/mercador (R9) e a query RAG contextual (R10): **SPEC-311**.
- Templates para `npc_peril_warning`, `npc_offscreen_fate` e `npc_defected`. A forma
  percebida deles chega por `world.news` (templates `npc_*` de `world_perception.render`) e
  por `npc_fate_learned`. Também `world_quest_relief`, que deriva de `quest_completed`, já
  coberto.
- A visão do turno com eventos ainda pendentes. O bloco lê a projeção persistida, que é
  aplicada pelo `event_processor` depois do storyteller. Uma crise que abre neste turno no
  local atual aparece no bloco só no turno seguinte; no turno da abertura ela já está em
  `[ECOS DO MUNDO]` (`services/world_engine.py:629-633`: o tick usa uma cópia local da
  projeção).
- Crença do herói sobre crise já encerrada que ele não soube (estado "acho que ainda está
  sitiada"): R14.3 mostra a última versão percebida, sem modelar crença como a SPEC-304.
- Mudar o texto de `<OUVIU_DIZER>`, `<AMBIENTE>`, `world.news`, a crônica ou a API.
- Faixa de relação entre fações (A8, proposta R7).

## 3. Design técnico

### 3.1 Arquivos

| Arquivo | Mudança |
|---|---|
| `services/perceived_world.py` (**novo**) | `perceived_world_lines`, `perceived_world_block`, `CRISIS_LABELS`, constantes `MAX_LINES`, `MAX_TOKENS`, `DAY_FACTS_MAX`, helper `day_memory_facts(state, items)` |
| `services/context_builder.py` | `EVENT_TEMPLATES` e renderizadores especiais (§3.2); `_IMPACT_BY_TYPE`; portão `event_perceived` para os tipos novos em `collect_dynamic_facts` |
| `agents/archivist.py` | `_event_memory_records` pula tipos **do motor** e aplica `event_perceived` a `companion_fate` (R9); limpeza incondicional de `memory_canonical_facts` (R10) |
| `agents/storyteller.py` | grava `memory_canonical_facts` + `archive_due` a partir de `perceived_items` (R7–R8); injeta `<MUNDO_PERCEBIDO>` (R18) |
| `agents/world_simulator.py` | `narrate_day` acrescenta o bloco `CONTEXTO` (R12) |
| `agents/combat.py`, `agents/npc.py` | injeção do bloco (R19) |
| `tests/test_spec309_*.py` (**novos**) | §4 |

### 3.2 Templates novos (tabela normativa)

Prefixo `[turno {turn}]` como nos existentes. `{local}` = nome do mapa de `target_id` ou de
`payload.location_id`. `{label}` = `location_states.json[state].label`
(`data/world/location_states.json:2-8`). `{prev_label}` = label de `payload.previous`.

| Tipo | Classe | Frase | Impacto |
|---|---|---|---|
| `location_state_changed` (state ≠ "", `cause != "calendario"`) | motor | `{local} agora está {label}.` | 0.9 |
| `location_state_changed` (state = `festa`, `cause = "calendario"`) | motor | `{local} está {festival.label}: {festival.name}.` | 0.5 |
| `location_state_changed` (state = "") | motor | `{local} não está mais {prev_label}.` (sem `previous` → `""`) | 0.6 |
| `world_crisis_warning` | motor | `Há sinais de {CRISIS_LABELS[kind]} em {região}.` | 0.6 |
| `companion_left` | testemunhado | `{name} deixou o grupo.` | 0.8 |
| `companion_betrayed` | testemunhado | `{name} traiu o grupo e partiu.` (sem ouro levado) | 0.9 |
| `companion_fate` | motor (via `event_perceived`) | `{name} {fate_text}.` (`chronicle._FATE_TEXT`, `services/chronicle.py:66-70`) | 0.9 |
| `crime_witnessed` | testemunhado | `Houve {CRIME_LABELS[crime_type]} em {local}.` (D2) | 0.5 |
| `law_resolved` | testemunhado | `A pendência do herói com {código.name} foi resolvida ({MODE_LABELS[mode]}).` | 0.6 |
| `quest_failed` | testemunhado | `Missão fracassada: {payload.quest_title or target}.` | 0.7 |
| `unique_item_claimed` (holder = player) | testemunhado | `O herói obteve {item}, peça única no mundo.` | 0.5 |
| `unique_item_lost` | testemunhado | `O herói perdeu {item}.` | 0.5 |
| `npc_fate_learned` | testemunhado (já é percepção) | `Chegou a notícia: {who} {morreu/foi capturado}{ em local}.` (mesma lógica de `chronicle.py:108-116`) | 0.9 |

Rótulos fechados (constantes, pt-BR):

```python
CRISIS_LABELS = {
    "guerra": "guerra",
    "fome": "fome",
    "praga": "praga",
    "abismo": "o Abismo inquieto",
}
CRIME_LABELS = {
    "furto": "um furto",
    "agressao": "uma agressão",
    "homicidio": "um homicídio",
    "dano_propriedade": "dano a propriedade",
    "magia_ilegal": "magia proibida",
    "resistencia": "resistência à guarda",
    "evasao": "uma fuga da guarda",
}
MODE_LABELS = {
    "fine": "multa paga",
    "sentence": "pena cumprida",
    "expulsao": "expulsão",
    "bribe": "acerto por fora",
}
```

Chave fora da tabela vira `""` (frase descartada), nunca o id cru.

### 3.3 Assinaturas

```python
# services/perceived_world.py
Audience = Literal["story", "npc", "combat", "day"]
MAX_LINES: int = 4
MAX_TOKENS: int = 120
DAY_FACTS_MAX: int = 6


def perceived_world_lines(state: dict, *, audience: Audience) -> list[str]: ...
def perceived_world_block(state: dict, *, audience: Audience) -> str:
    """'' ou '<MUNDO_PERCEBIDO>\n{instrução}\n- linha\n...\n</MUNDO_PERCEBIDO>'."""


def day_memory_facts(state: dict, items: list[dict]) -> list[str]:
    """R7: textos de template dos itens percebidos (ordem do digest, sem vazio/duplicata, teto)."""


# contrato REAL da SPEC-308 (`services/world_perception.py`, já na main)
def event_perceived(state: dict, ev: dict) -> bool: ...
def perceived_projection(state: dict, projection: dict | None = None) -> dict: ...
# F2 (esta spec): ids de eventos que bloqueiam a rota a<->b e que o herói ainda não percebeu
def hidden_blocked_route_events(state: dict, a: str, b: str) -> list[str]: ...
```

A SPEC-308 pousou com este nome e lugar; `collect_dynamic_facts` e `_event_memory_records`
já aplicam `event_perceived` (R6 estava pronto), então esta spec só acrescentou o portão
de tipos do motor em `_event_memory_records` (R9).

### 3.4 Exemplo real (Brekmar/Skallgard, ids canônicos)

Herói em `skallgard`, motor `on`. Na região, um aviso de guerra foi percebido por rumor e
há festa anunciada no local:

```
<MUNDO_PERCEBIDO>
Fatos do mundo que o herói percebe. Pode ambientar a cena com eles; não invente causa, duração nem gravidade.
- Nos próximos dias: Noite dos Nomes.
- Há sinais de guerra em Skallgard.
</MUNDO_PERCEBIDO>
```

Mesmo estado, com um cerco aberto em outra região que **não** foi percebido: nenhuma linha
a mais, e o nome do local sitiado não aparece no prompt inteiro (§3.6).

### 3.5 Fluxo da memória do dia (R7–R10)

```
storyteller._perceive_world → perceived_items
  → updates["memory_canonical_facts"] = day_memory_facts(state, perceived_items)
  → updates["archive_due"] = True (se não vazio)
archivist: policy_facts → make_memory_fact(canonical_event, engine_policy:{turn}) → ledger
  → memory_canonical_facts = []  (sempre, R10)
_event_memory_records: pula location_state_changed/world_crisis_warning (R9)
```

Se `world_note` estiver ocupado por encontro (P8), R7 vale do mesmo jeito. A política
`canonical_only` continua sendo ligada só quando há `world_note`
(`agents/storyteller.py:1780-1781`), sem mudança.

### 3.6 Oráculo da regra de ouro (testes)

Fixture `world_state_two_regions`: herói em `skallgard`. `event_log` com (a) um
`location_state_changed` cerco em `brekmar` **não** percebido; (b) um `world_crisis_warning`
fome na região do herói **percebido** (id em `world_sim.perceived_ids`); (c) um
`companion_fate` não percebido. O oráculo afirma:

1. o nome "Brekmar" e o label "sitiada" não aparecem em `build_context_pack(...).world_state_block`,
   `perceived_world_block(audience=*)`, `memory_canonical_facts` nem nos registros de
   `_event_memory_records`;
2. a frase de (b) aparece no pack e no bloco;
3. o nome do companheiro de (c) com o texto de destino não aparece em lugar nenhum;
4. nenhum bloco/linha nova casa `\d` (fora do prefixo `[turno N]` do pack) nem as palavras
   `severidade|pressão|tensão|fase|banda|multa|recompensa`;
5. quando (a) passa a ser percebido (id adicionado ao ledger), "Brekmar" aparece no pack, e
   no bloco só se Brekmar for da região atual.

O oráculo é estrutural (substring/regex sobre texto determinístico). Não é LLM-as-judge.

## 4. Plano passo a passo

### Etapa 0 — Pré-requisito 308

1. Confirmar que a SPEC-308 está `done` e onde mora `event_perceived`. Se o nome divergir,
   ajustar §3.3 no mesmo commit.
2. Rodar os testes que já tocam `render_event`: `tests/test_fase28.py`, `tests/test_fase61.py`,
   `tests/test_spec301_llm.py` e `tests/test_npc_knowledge.py` (baseline verde).

### Etapa 1 — Templates (R1–R5, R20, R21)

1. **Testes** (`tests/test_spec309_templates.py`):
   - `test_each_new_type_renders_nonempty` (parametrizado pela tabela §3.2, payload real dos
     emissores);
   - `test_no_digits_besides_turn_prefix`;
   - `test_unknown_faction_not_named` (aviso de guerra com `faction_id` não conhecido);
   - `test_unique_item_other_holder_is_empty`;
   - `test_npc_fate_learned_only_dead_or_captured`;
   - `test_unknown_key_drops_sentence` (crime/mode fora da tabela → `""`);
   - `test_legacy_payload_does_not_raise` (payload vazio para cada tipo);
   - `test_unknown_type_still_empty`;
   - `test_npc_knowledge_subject_text_for_state_change` (R20: texto não vazio, sem número,
     assinatura secreta barrada).
2. **Implementação:** templates e renderizadores em `context_builder.py`; constantes de
   rótulo; `_IMPACT_BY_TYPE`.
3. **Verificação:** os arquivos da Etapa 0 + o novo, `-q`.

### Etapa 2 — Portão no pack e no arquivista (R6, R9)

1. **Testes** (`tests/test_spec309_golden_rule.py`): o oráculo §3.6 itens 1–5 para
   `world_state_block` e `_event_memory_records`; `test_engine_types_not_in_event_memory`;
   `test_witnessed_types_in_event_memory`; `test_companion_fate_needs_perception`.
2. **Implementação:** em `collect_dynamic_facts`, os tipos novos de classe "motor" passam por
   `event_perceived`. Em `_event_memory_records`, o conjunto `_DIGEST_MEMORY_TYPES` é pulado
   e `companion_fate` é filtrado.
3. **Verificação:** os novos + `tests/test_fase28.py` + testes do arquivista
   (`tests/test_conflict_summary_lifecycle.py`).

### Etapa 3 — Memória do dia (R7, R8, R10, R11)

1. **Testes** (`tests/test_spec309_day_memory.py`):
   - `test_perceived_items_become_canonical_facts` (texto = `world_perception.render`);
   - `test_no_items_no_facts_no_archive_due`;
   - `test_facts_written_even_when_encounter_took_world_note` (P8);
   - `test_archivist_persists_as_canonical_event_engine_policy`;
   - `test_archivist_clears_allowlist_without_canonical_only` (R10: 2ª execução não regrava);
   - `test_crisis_opened_and_perceived_same_turn_one_fact` (R9);
   - `test_llm_prose_not_stored_as_canonical` (R11, MockLLM com prosa distinta do template);
   - `test_cap_day_facts`.
2. **Implementação:** `day_memory_facts`; escrita em `storyteller.py` junto ao
   `sim_updates`/`updates`; limpeza no arquivista.
3. **Verificação:** os novos + testes da 302 de percepção (`tests/test_spec302_*perception*`
   ou equivalentes que cubram `_perceive_world`).

### Etapa 4 — Bloco `<MUNDO_PERCEBIDO>` (R13–R17)

1. **Testes** (`tests/test_spec309_perceived_block.py`):
   - `test_local_state_line_uses_public_label` (cerco → "sitiada");
   - `test_interior_inherits_parent_state`;
   - `test_festival_today_and_upcoming` (fixture de `world_sim.festivals`, `noite_dos_nomes`
     em `skallgard`);
   - `test_remote_crisis_only_if_perceived`;
   - `test_last_perceived_event_wins` (aviso → aberto → fim percebido);
   - `test_unperceived_end_keeps_last_known_line` (sem vazamento por ausência);
   - `test_other_region_never_listed`;
   - `test_story_audience_omits_season`, `test_npc_audience_local_and_season_only`;
   - `test_engine_off_or_shadow_no_state_lines`;
   - `test_budget_max_lines_and_tokens` (corta pela prioridade);
   - `test_deterministic_byte_equal` (2 chamadas + estado com dicts em outra ordem);
   - `test_never_raises_returns_empty` (estado corrompido);
   - `test_no_forbidden_words_or_digits` (oráculo §3.6.4).
2. **Implementação:** `services/perceived_world.py`.
3. **Verificação:** o arquivo novo, `-q`.

### Etapa 5 — Costura nos prompts (R12, R18, R19, R22)

1. **Testes** (`tests/test_spec309_prompts.py`, capturando o `SystemMessage`/`HumanMessage`
   via fake LLM como nos testes de prompt da 302/303):
   - `test_storyteller_prompt_has_block_after_ambiente`;
   - `test_storyteller_prompt_no_block_when_empty`;
   - `test_combat_narration_has_block`;
   - `test_npc_prompt_has_local_state_only`;
   - `test_narrate_day_human_message_has_context`;
   - `test_narrate_day_name_guard_unchanged`;
   - `test_invoke_count_unchanged` (R22);
   - `test_golden_rule_full_prompt` (oráculo §3.6 sobre o prompt inteiro do storyteller).
2. **Implementação:** injeções nos 4 agentes.
3. **Verificação:** os novos + `tests/test_storyteller*.py`, `tests/test_npc*.py` e
   `tests/test_combat*.py` do escopo (`-n 2` no máximo). A suíte completa fica com o
   coordenador no pouso.

## 5. Critérios de aceite

- [ ] R1–R22 cobertos pelos testes da §4 (cada R citado no docstring do teste)
- [ ] Oráculo §3.6 verde para pack, bloco (4 audiências), memória do evento e memória do dia
- [ ] Nenhuma chamada LLM nova (R22) e nenhum `with_structured_output` novo
- [ ] Bloco ≤ 4 linhas e ≤ 120 tokens em todos os testes; `""` quando não há nada
- [ ] `memory_canonical_facts` nunca sobrevive a uma execução do arquivista (R10)
- [ ] Saves antigos carregam e renderizam sem exceção (R21)
- [ ] `uv run pytest` verde (suíte completa offline, rodada pelo coordenador no pouso)
- [ ] Revisão independente Opus (`handoffs/SPEC-309-review.md`) sem P0/P1
- [ ] Smoke real (§6) executado e registrado na §8

## 6. Smoke test com LLM real

Pré-requisito: `RPG_WORLD_ENGINE=on`, `RPG_NPC_KNOWLEDGE=on`, `RPG_LAW=on`, DeepSeek nas
`ROUTES`, SPEC-308 pousada. Teto: US$ 0,80. O MockLLM não mostra se a prosa transforma
"sitiada" em número de soldados ou cita um local não percebido.

1. `uv run python -m playtest run --scenario mundo --turns 20 --real --max-cost 0.40 --seed 31`.
   Asserta `mock=False`, 0 violação `error`, invokes por turno iguais ao baseline da 302. No
   transcrito, ao menos 1 turno com `<MUNDO_PERCEBIDO>` não vazio (ler o prompt pela
   telemetria do harness) e prosa coerente com o rótulo, sem número de severidade.
2. No mesmo run: depois de um dia virado com item percebido, `memory_facts` tem um
   `canonical_event` com `source_id` `engine_policy:*` e texto igual a uma entrada de
   `world.news`, e `memory_canonical_facts == []` no save seguinte.
3. `uv run python -m playtest run --profile explorador --turns 20 --real --max-cost 0.40 --seed 32`.
   Leitura humana de 5 trechos: nenhum local em crise citado sem ter sido percebido, nenhuma
   fação desconhecida nomeada, nenhuma gravidade numérica e festa citada só no local dela
   ou anunciada ali.
4. Combate em local com estado (`--scenario mundo`, provocar um encontro): a narração cita o
   cerco ou a festa só como ambiente, sem mudar o log mecânico.

Registrar custo, run_ids e trechos na §8. Se estourar o teto, parar e registrar.

## 7. Riscos & compatibilidade

- **Saves antigos:** nenhum campo novo. Payloads antigos têm fallback (R21). Fatos de dias
  passados não são retroativos: só dias percebidos depois do pouso viram memória.
- **Dependência da 308:** sem `event_perceived`, as Etapas 2–5 não podem ser feitas (os
  templates novos aumentariam o vazamento A1). A Etapa 1 sozinha também não pode pousar
  antes da 308: os tipos do motor passariam a ter texto no pack sem filtro. Pousar 1+2
  juntas.
- **Rumor de NPC com texto novo (R20):** NPCs passam a repetir estado de local, aviso de
  crise e crime como `[OUVIU]/[BOATO]`. É o comportamento que a 299 R13 e a 302 R27 queriam
  e que estava mudo por falta de template. Risco: mais conversa sobre crime. Mitigação: o
  texto não diz quem cometeu (D2).
- **Ranking do pack:** mais fatos competem pela cota `current_state` (25% de 3.500). Os pesos
  da §3.2 são `[BALANCEAR]`. O teste de orçamento do pack existente deve continuar verde.
- **Atraso de 1 turno** do bloco na abertura de estado no local atual (Fora de escopo). O
  `[ECOS DO MUNDO]` do mesmo turno cobre.
- **MockLLM/FallbackLLM:** o bloco é texto. O `narrate_day` mantém o guard
  `isinstance(res, WorldDayNarration)` e o fallback de template.
- **Custo/latência:** +≤120 tokens de entrada no storyteller, no combate e no NPC, e +≤80
  no `narrate_day`. Nenhuma chamada a mais.

## 8. Registro de execução

- Implementação 24/10 (Sonnet): Etapas 1 e 2 no mesmo commit, 3-5 em seguida; sem desvio de requisito.
- **D1–D3:** defaults (só o template vira `canonical_event`; crime neutro; NPC com estado do local + estação).
- **R3:** `npc_fate_learned` usa `payload.name` (o evento só nasce quando o herói soube do destino, então o nome já é conhecido); fação nunca aparece nos templates novos.
- **R10:** a limpeza incondicional vale nos dois caminhos de retorno do arquivista (`elif policy_facts`).
- **F2 (follow-up da 308):** o servidor hoje **não recusa** viagem por rota bloqueada (o bloqueio é de comércio; só o mapa a mostra como indisponível). Implementado o equivalente: ao viajar por rota cujo bloqueio vem de evento não percebido, o `travel_note` manda narrar a descoberta e o `event_id` entra em `world_sim.perceived_ids` (`world_perception.hidden_blocked_route_events`). Teste `test_f2_*`.
- Testes: `tests/test_spec309_{templates,golden_rule,day_memory,perceived_block,prompts}.py`.
- Smoke real §6: pendente (coordenador).

## 9. Decisões do dono

- **D1 — Prosa do `narrate_day` na memória?** (a) **não** (recomendado): só o template vira
  `canonical_event` (R11); (b) também a prosa, como `player_observation`, 1 por dia.
- **D2 — Crime no texto compartilhado diz quem cometeu?** (a) **neutro** (recomendado):
  "Houve um furto em X." vale para pack, memória e rumor de NPC; (b) "O herói cometeu…"
  na memória e no pack, neutro no rumor, o que pede dois templates e um parâmetro de
  audiência em `render_event`.
- **D3 — NPC recebe o bloco já nesta spec?** (a) **sim, só o estado do local da cena e a
  estação** (recomendado; a SPEC-310 amplia); (b) não, e tudo de NPC fica na 310.
