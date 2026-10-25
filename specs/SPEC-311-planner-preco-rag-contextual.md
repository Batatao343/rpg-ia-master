# SPEC-311 — Planner que vê o mundo percebido, preço com motivo e RAG de lore contextual

> **Status:** `in-progress` (implementada em 25/10; falta revisão independente, suíte completa e smoke real; dono 24/10: "escreva specs para isso", onda 2 do mundo vivo; propostas R8, R9 e R10 da revisão orquestrada; as decisões D1–D4 da §9 têm default recomendado)
> **Criada:** 2026-10-24 · **Atualizada:** 2026-10-25
> **Origem:** `docs/mundo-vivo/REVISAO-ORQUESTRADA-2026-10-24.md` §4.1 (R8, R9, R10), achado A9 (§1.1, linha 49) e §2.1 (linhas 139-143).
> **Depende de:** SPEC-302, SPEC-303, SPEC-305, SPEC-307, SPEC-298 e SPEC-301 (`done`). **SPEC-308** (`approved`, helper `world_perception.event_perceived`) e **SPEC-309** (`approved`, módulo `services/perceived_world.py`) precisam estar `done` **só para a Etapa 4**. As Etapas 1 a 3 não dependem delas e podem pousar antes.
> **Desbloqueia:** nada formalmente. Dá mais munição às SPEC-312 (rumores) e SPEC-313 (quests ancoradas), porque o planner passa a tramar com o mundo percebido.
> **EXECUTOR_MODEL:** `Sonnet` (Terra: três costuras bounded) · **REVIEW_MODEL:** `Opus` (subagente independente) · **REVIEW_REQUIRED:** `true` (refatora a função de preço canônica, muda o ranking do RAG de lore e adiciona um gatilho de replan)
> **EVAL_AUTHORING_REQUIRED:** `false` (não toca evaluator, dataset nem `query_faiss_evidence`, usado por `evals/core/adapters.py`)

---

## 1. Contexto & Objetivo

A onda 296–307 construiu um motor de mundo determinístico, mas três consumidores de LLM ainda
trabalham cegos a ele:

1. **O planner (`campaign_manager`) não vê o mundo.** O prompt recebe local, clima legado, o pack
   `planning` e 2 chunks de lore (`agents/campaign_manager.py:141-185`). Não recebe quests ativas
   (nem as de mundo da SPEC-305), estado do local, crise, festa, estação nem `world.news`. O
   replan só dispara por `needs_replan`, primeiro plano, troca de região, intervalo de 15 turnos
   ou fim dos beats (`agents/campaign_manager.py:78-106`). Ninguém liga `needs_replan` quando o
   mundo muda: os únicos escritores são a viagem entre regiões, o fim dos beats
   (`agents/storyteller.py:1054-1063`, `:1724-1725`), o fim de combate (`agents/combat.py:1846`) e
   o action guard (`agents/action_guard.py:43`). Resultado: o arco narrativo pode ignorar ou
   contradizer um cerco que o herói acabou de testemunhar (achado A9).
2. **Loot e mercador não sabem por que o preço mudou.** `economy.price` compõe sete fatores
   (escassez por rota, passo fechado pela estação, mercador, relação com o keeper, controlador
   hostil, estado do local e desconto de patente; `services/economy.py:201-237`). O `_narrate` do
   loot recebe só uma linha mecânica (`agents/loot.py:250-254`) e o NPC-mercador não recebe nada
   sobre o próprio comércio (`agents/npc.py:1046-1113`). O jogador vê o número subir no
   `[SISTEMA]` e a prosa fica muda sobre o cerco que encareceu tudo.
3. **A lore chega em 2 chunks escolhidos sem contexto.** A query é `"{local} {último input}"`
   (`agents/storyteller.py:1296`, `agents/campaign_manager.py:143`); o FAISS devolve os 2 primeiros
   chunks públicos de k=6 (`rag.py:1154-1158`), sem olhar região, estação nem estado do local. No
   pack, os 2 chunks viram **um único fato indivisível**: se não couberem juntos na cota de lore,
   os dois caem (`services/context_builder.py:437-447`). A memória de sessão já é fatiada em
   linhas de até 600 caracteres (`:448-471`).

O objetivo é ligar esses três consumidores ao mundo **percebido**, sem chamada LLM nova. Vale a
regra de ouro da iniciativa (`docs/mundo-vivo/VISAO.md`, "Regra de ouro"): só entra o que o herói
viu ou ouviu. Vale também a regra "rótulos sem números" da SPEC-298: motivo de preço é palavra,
nunca multiplicador.

## 2. Requisitos

### A. Planner vê o mundo percebido (proposta R8)

- **R1 — Quests ativas no planner.** O prompt do planner ganha o bloco `<QUESTS_DO_HEROI>`, que só
  aparece se houver quest com `status == "active"`. Cada linha tem o formato
  `- {title} · origem: {origin_name}[ · tipo: mundo · prazo: {deadline_label}]`. O rótulo de prazo
  vem de `quest_log.public_quest_view(q, day)` (`services/quest_log.py:553`) e nunca é número de
  dia. As linhas não têm `id` nem "prova": o planner não conclui quest. Quests de mundo vêm
  primeiro; depois as outras, na ordem de `state["quests"]`. O teto é `PLANNER_QUESTS_MAX = 6`.
- **R2 — Notícias percebidas no planner.** O prompt do planner ganha `heard_block(world)`
  (`services/ambient.py:129`), o mesmo `<OUVIU_DIZER>` do storyteller. Ele contém o texto de
  template de `world.news[-3:]`, que já passou pela percepção (`services/world_perception.py:197`).
- **R3 — `<MUNDO_PERCEBIDO>` no planner (Etapa 4, depende de 308/309).** O módulo
  `services/perceived_world.py` (SPEC-309 R13) ganha a audiência `"planning"`. Ela tem as linhas 1
  a 4 da SPEC-309 R14: estado do local atual, festa próxima no local, até 2 crises percebidas na
  região atual e a estação. Valem os mesmos limites `MAX_LINES`/`MAX_TOKENS` e o mesmo gate de
  modo (SPEC-309 R16-R17). O bloco entra no prompt do planner depois de `world_state_context`.
- **R4 — Instrução fixa do planner.** Junto dos blocos novos, entra o texto: "Estes são fatos que o
  herói conhece. O arco não pode contradizê-los. Você pode usar uma crise ou uma missão do herói
  como pano de fundo ou gancho de um beat. Não declare missão concluída nem fracassada, não invente
  prazo e não acrescente número, gravidade ou causa que não esteja escrito." O texto é pt-BR,
  porque o bloco 0 de idioma já exige pt-BR nos beats.
- **R5 — Regra de ouro no planner.** Os blocos de R1-R3 derivam só de `state["quests"]`,
  `world.news` e `perceived_world`. Nenhum deles lê `world_sim.pressures`, `bands`, `crises`,
  `tension`, a fase do diretor ou um `location_states` de local diferente do atual. O oráculo
  §3.6 cobre isso. O pack `planning` continua vendo arestas `hidden` (`context_builder.py:223`).
  Esse risco é anterior e fica fora de escopo (ver "Fora de escopo").
- **R6 — Gatilho de replan pelo mundo.** No turno em que o dia vira (`_perceive_world`,
  `agents/storyteller.py:682-717`), o storyteller liga `needs_replan=True` se pelo menos uma
  destas condições valer:
  - (a) **crise aberta percebida na região atual:** item percebido com `kind == "crise"` e
    `region_id == region_of(current_location_id)` (digest de `world_director.py:541-552`);
  - (b) **cidade caiu:** item percebido com `kind == "escala"` cujo `template_id` começa com
    `"ocupado."` ou `"ruina."` (`world_director.py:643-654`), na região atual (D1);
  - (c) **quest de mundo falhou:** `wq_events` deste turno contém `type == "quest_failed"`
    (`services/world_quests.py:807-808`). A quest é do herói, então ele sabe dela por definição.
  O gatilho lê **só** `perceived_items` e `wq_events`. Uma crise aberta em `world_sim.crises` que
  não foi percebida não dispara nada.
- **R7 — O gatilho vale em todos os caminhos de saída.** O resultado de R6 é somado a
  `travel_needs_replan` (`agents/storyteller.py:1054`), antes do encontro. Assim vale no retorno
  antecipado de emboscada (`:1179`), no caminho feliz (`:1692`, `:1766`) e no fallback (`:2007`).
- **R8 — Observabilidade fechada.** Ao disparar, o storyteller emite
  `log_event("campaign", "world_replan_trigger", cause=<enum>)`, com
  `cause ∈ {"crise_regiao", "queda_cidade", "quest_falhou"}`. Com mais de uma causa, vale a
  primeira na ordem de R6. O log não leva id, local nem nome.
- **R9 — Modos.** Com `RPG_WORLD_ENGINE != on`, `perceived_items` é vazio
  (`storyteller.py:685-686`) e (a)/(b) não disparam. Com `RPG_WORLD_QUESTS` em `off` ou `shadow`,
  não existe `quest_failed` (`world_quests.py:791-797`) e (c) não dispara. Nenhum comportamento
  muda nesses modos.

### B. Preço com motivo (proposta R9)

- **R10 — Fatores de preço explícitos, mesmo número.** `services/economy.py` ganha
  `price_factors(item_id, *, mode, state, merchant=None) -> list[PriceFactor]`, com os fatores na
  mesma ordem e nas mesmas condições de `price()` (`:201-237`). `price()` passa a ser
  `_round5(base_price(item_id) * prod(f.mult for f in price_factors(...)))`. Para toda entrada, o
  resultado tem de ser **idêntico** ao de antes. Um teste de caracterização escrito **antes** da
  refatoração prova isso (Etapa 2).
- **R11 — Motivos qualitativos.** Uma função nova, `economy.price_reasons(state, *, mode,
  item_id=None, merchant=None) -> list[PriceReason]`, transforma fatores em motivos:
  - um fator só vira motivo se `abs(mult - 1.0) >= REASON_MIN_DELTA` (0,05);
  - `SELL_FACTOR` nunca vira motivo (é constante do jogo, não do mundo);
  - o teto é `REASONS_MAX = 3`, ordenados por `abs(log(mult))` decrescente e depois por `code`
    (determinístico);
  - com `item_id=None`, valem só os fatores de local (estado do local, festa, controlador, relação,
    patente, mercador). Se algum item do estoque do mercador tiver fator de rota ou de passo
    `> 1`, entra também o motivo de rota correspondente.
- **R12 — Tabela normativa de motivos (§3.3).** Cada `code` tem uma frase fixa em pt-BR e uma
  direção (`encarece` ou `barateia`). A frase nunca contém número, `%`, multiplicador, `id` nem
  severidade. Ela nunca nomeia rota, local de origem da mercadoria nem a causa de bloqueio de
  rota. Uma fação só é nomeada se `faction_intel[id].known`. Senão vale a frase genérica.
- **R13 — Regra de ouro no preço.** O motivo de estado do local só sai para o local **atual**
  (presença), e só com `RPG_WORLD_ENGINE == on` (`location_effects` já é neutro fora disso,
  `services/location_states.py:47-48`). O motivo de rota diz só o que o mercador sabe ("mercadorias
  de fora não estão chegando"). Ele não revela o cerco que fechou a rota.
- **R14 — Loot narra o motivo.** Em `loot_node`, nas transações `buy`/`sell` aceitas e recusadas
  (`agents/loot.py:227-254`), o `context` passado a `_narrate` ganha uma linha
  `MOTIVOS DO PREÇO (cite no máximo um, com palavras; nunca números): - encarece: Brekmar está
  sitiada; ...`. A linha só aparece se `price_reasons` não for vazio. O modo `observe` e o texto
  `[SISTEMA]` não mudam. O validador `_validated_narrative` também não muda.
- **R15 — NPC-mercador sabe do próprio comércio.** No `npc_actor`, se o interlocutor tiver
  `keeper_of` (`services/reputation.py:1040`) e o mercador estiver no local atual, o prompt ganha
  `<SEU_COMERCIO>`. O bloco tem uma linha de direção geral ("Seus preços hoje estão mais altos que
  o normal." / "...mais baixos que o normal."), calculada pelo produto dos fatores de local de
  compra com o mesmo limiar de R11, e os motivos de `price_reasons(item_id=None)`. Fecha com a
  instrução: "Fale disso só se a conversa for sobre comércio. Nunca diga números nem
  porcentagens." Sem motivo, o bloco vale `""` e a tag não aparece. O bloco entra logo depois de
  `{atitude_block}` (`agents/npc.py:1061`).
- **R16 — Sem número, em teste.** Todo texto produzido por `price_reasons`, pela linha de R14 e
  pelo bloco de R15 casa com o oráculo de "sem número": nenhum dígito, nenhum `%`, nenhum
  `x<dígito>`, nenhum `id` de `MERCHANTS`/`FACTIONS`/`WORLD_MAP`.

### C. RAG de lore contextual (proposta R10)

- **R17 — Query composta.** O módulo novo `services/lore_query.py` expõe
  `compose_lore_query(state, base: str) -> str`. As partes entram nesta ordem, separadas por
  espaço, e as vazias são omitidas:
  1. nome do local atual;
  2. rótulo da região (`world_pressures.region_label`);
  3. `public_label` do local atual, só com motor `on` e estado presente
     (`location_states.location_state` + `public_label`);
  4. rótulo da estação (`world_calendar.active_season` + `label_for(season, region)`);
  5. nome do mês de Valoria, se houver calendário (`world_calendar.date_at`; confirmar a chave na
     Etapa 0);
  6. `base`, com o input do jogador truncado em `LORE_QUERY_INPUT_MAX = 300` caracteres.
  Uma parte com texto idêntico a outra já incluída (ex.: local `skallgard` na região Skallgard)
  entra só uma vez. A função é pura e determinística e nunca levanta (erro devolve `base` + `log_fallback`). A
  query nunca contém estado de outro local, crise, pressão, fação ou número.
- **R18 — Quem usa.** O storyteller (`storyteller.py:1296`), o planner (`campaign_manager.py:143`)
  e o NPC (`npc.py:958`, com `base = "{nome} {local} {última fala}"`) passam a chamar
  `build_context_pack` com `query=compose_lore_query(state, base)`. O combate
  (`agents/combat.py:479`, `:1484`) não muda. A mesma query serve lore, memória de sessão e ranking
  léxico, então continua havendo **um** embedding por pack (D4).
- **R19 — Lore fatiada no pack.** Em `assemble_pack` (`context_builder.py:437-447`), `lore_text`
  é dividido no separador do RAG (`"\n---\n"`, `rag.py:859`). Cada parte acima de 600 caracteres é
  cortada como a memória (`:453-458`). Cada pedaço vira um `ScoredFact` próprio da seção `lore`,
  com `source_id = "lore_content_" + sha256(pedaço)[:24]` (o prefixo de hoje) e score
  `1.0 - i * 0.0001`. O `lore_block` volta a juntar os pedaços escolhidos com `"\n---\n"`. Com
  cota para um só chunk, o primeiro entra; hoje os dois caem.
- **R20 — Preferência por região no metadado.** `rag.query_rag` e `rag.query_global_by_vector`
  ganham `prefer_region: str | None = None`. Com valor, dos candidatos **já filtrados por
  visibilidade** (k=6), sai uma ordenação estável em três faixas:
  - 0: as tags do chunk (`metadata["tags"]`, `services/codex_loader.py:66`) intersectam
    `region_lore_tags(prefer_region)`;
  - 1: as tags não indicam região nenhuma;
  - 2: as tags indicam só **outra** região.
  Dentro de cada faixa, vale a ordem do FAISS. Saem os `LORE_K` primeiros. Sem `prefer_region`, o
  comportamento é idêntico ao de hoje, com `LORE_K` no lugar do 2. `query_faiss_evidence`
  (`rag.py:760`) **não muda**: o eval adapter depende dele.
- **R21 — Perfil hosted.** No caminho `RPG_RUNTIME_PROFILE != legacy` (`rag.py:1108-1137`,
  `:978-992`), com `prefer_region` pede-se `k=6` ao `memory_store` e aplica-se a mesma ordenação
  sobre `MemoryDocument.metadata`. Sem `tags` no metadado, a ordenação é no-op (faixa 1 para todos).
- **R22 — Tabela de aliases de região.** A função
  `lore_query.region_lore_tags(region_id) -> frozenset[str]` devolve slugs (minúsculas, sem
  acento, não-alfanumérico vira `_`) de:
  - `region_id`;
  - `slug(region_label)`;
  - ids e `slug(name)` dos locais da região em `world_map.json`;
  - os aliases curados em `data/world/region_lore_tags.json` (novo; ex.:
    `"pradaria_ruinas": ["pradaria"]`).
  As tags do chunk são comparadas também em slug. O teste exige que cada uma das 12 regiões tenha
  pelo menos 1 alias presente nas tags de algum `.md` de `data/codex/`. A leitura é só do
  frontmatter, via `codex_loader.parse_codex_file`.
- **R23 — Quem passa a região.** `_build_context_pack` deriva
  `region = world_pressures.region_of(world.current_location_id)` para os propósitos `story`,
  `planning` e `npc` e repassa a região só aos leitores default de `context_sources`
  (`services/context_sources.py:79-89`). Os `custom_readers` (dublês de teste,
  `context_builder.py:642-658`) não mudam de assinatura.
- **R24 — Visibilidade intacta.** A ordenação nunca relaxa `max_visibility`. Um chunk `hidden`
  com a tag da região atual continua fora. Teste com um índice FAISS em memória e vetores fixos,
  no mesmo padrão dos testes de `query_faiss_evidence`.
- **R25 — Mais um chunk.** `LORE_K = 3` (era 2) nos dois caminhos (D2). A cota da seção `lore`
  (15% de 3.500) não muda. Com R19, o terceiro chunk só entra se couber.

### D. Compatibilidade

- **R26 — Sem estado novo.** Nenhum campo novo em `GameState` nem no save. Saves antigos carregam
  igual. O gatilho R6 usa só dados do turno.
- **R27 — Sem chamada LLM nova.** O número de `invoke` por turno no MockLLM é igual ao baseline.
  O teste conta `get_llm().invoke`, como nos testes da SPEC-302. O replan por mundo usa a chamada
  SMART que já existe e fica mais frequente só quando R6 dispara. Pelo desenho da 302 isso é raro:
  aviso de pelo menos 2 dias e uma crise por região por janela.
- **R28 — Reindex não é exigido.** As tags já estão no metadado de cada chunk do FAISS global
  (`codex_loader.py:62-70`). A Etapa 0 confirma isso no índice versionado e no `memory_store`
  hosted. Se o hosted não tiver tags, R21 fica no-op e vira follow-up (sem bloquear).

### Fora de escopo

- O filtro `event_perceived` e o `offscreen` dos eventos do motor: **SPEC-308**. O
  `<MUNDO_PERCEBIDO>` do storyteller, NPC, combate e `narrate_day`, mais os templates novos de
  `render_event`: **SPEC-309**. Aqui só se acrescenta a audiência `"planning"`.
- O NPC saber de si (fação, agenda, notícias da região, semente): **SPEC-310**. O `<SEU_COMERCIO>`
  de R15 é só o comércio do keeper.
- Tirar do pack `planning` as arestas e controladores `hidden`/`secret`
  (`context_builder.py:223`; risco "média" da revisão §1.6). Muda o contrato de segredo do planner
  e merece spec própria com revisão de `sanitize_beat`.
- Motivo de preço na UI ou na API (`public_market_snapshot`) e mudança de qualquer número da
  economia.
- Reindexar o Codex, mudar o tamanho de chunk do splitter (500/50) ou criar metadado `region` no
  ingest.
- Replan por aviso de crise (`kind == "aviso"`), por fim de crise, por festa ou por mudança de
  relação entre fações.
- Relações entre fações no planner (proposta R7) e pressões ou fase do diretor em qualquer prompt.
- Query composta no combate e no gerador de NPC/criatura.

## 3. Design técnico

### 3.1 Arquivos

| Arquivo | Mudança |
|---|---|
| `services/lore_query.py` (**novo**) | `compose_lore_query`, `region_lore_tags`, `slug`, `rerank_by_region(docs, region, k)` (puro: recebe docs com `.metadata`), constantes `LORE_QUERY_INPUT_MAX`, `LORE_K` |
| `data/world/region_lore_tags.json` (**novo**) | aliases curados por `region_id` (só os que o slug automático não cobre) |
| `services/planner_context.py` (**novo**) | `planner_quests_block(state)`, `world_replan_cause(state, perceived, wq_events) -> str \| None` (puros; o storyteller e o planner importam daqui, sem import cruzado entre agentes) |
| `services/economy.py` | `PriceFactor`, `price_factors`, `price` reescrito sobre os fatores; `PriceReason`, `price_reasons`, `market_direction`; constantes `REASON_MIN_DELTA`, `REASONS_MAX` |
| `services/perceived_world.py` (da 309) | `Audience` ganha `"planning"`; regra de linhas de R3 |
| `services/context_builder.py` | `assemble_pack` fatia a lore (R19); `_build_context_pack` deriva a região e repassa aos leitores default (R23) |
| `services/context_sources.py` | `_default_readers(..., prefer_region=None)` repassa a `rag` |
| `rag.py` | `prefer_region` em `query_rag`/`_query_rag_impl`/`query_global_by_vector`; `LORE_K`; hosted com `k=6` + rerank |
| `agents/campaign_manager.py` | query composta; blocos `<QUESTS_DO_HEROI>`, `<OUVIU_DIZER>`, `<MUNDO_PERCEBIDO>` + instrução R4 |
| `agents/storyteller.py` | gatilho R6 somado a `travel_needs_replan`; log R8; query composta |
| `agents/loot.py` | linha de motivos no `context` de `_narrate` (R14) |
| `agents/npc.py` | `<SEU_COMERCIO>` (R15); query composta |
| `tests/test_spec311_*.py` (**novos**) | §4 |

### 3.2 Assinaturas

```python
# services/economy.py
class PriceFactor(TypedDict):
    code: str  # "supply_local" | "supply_rota" | "supply_passo" | "mercador" | "relacao"
    # | "controlador_hostil" | "estado_local" | "festa" | "patente" | "venda"
    mult: float


class PriceReason(TypedDict):
    code: str
    direction: Literal["encarece", "barateia"]
    text: str  # frase da tabela §3.3, sem número


REASON_MIN_DELTA: float = 0.05
REASONS_MAX: int = 3


def price_factors(
    item_id: str, *, mode: str, state: dict, merchant: dict | None = None
) -> list[PriceFactor]: ...
def price(item_id: str, *, mode: str, state: dict, merchant: dict | None = None) -> int:
    """Inalterado no contrato e no número (R10)."""


def price_reasons(
    state: dict, *, mode: str, item_id: str | None = None, merchant: dict | None = None
) -> list[PriceReason]: ...
def market_direction(state: dict, merchant: dict) -> Literal["alta", "baixa", ""]: ...


# services/lore_query.py
LORE_K: int = 3
LORE_QUERY_INPUT_MAX: int = 300


def slug(text: str) -> str: ...
def compose_lore_query(state: dict, base: str) -> str: ...
def region_lore_tags(region_id: str) -> frozenset[str]: ...
def rerank_by_region(docs: list, region_id: str | None, k: int) -> list: ...


# services/planner_context.py
PLANNER_QUESTS_MAX: int = 6


def planner_quests_block(state: dict) -> str:
    """'' ou '<QUESTS_DO_HEROI>\n- ...\n</QUESTS_DO_HEROI>' (R1)."""


def world_replan_cause(state: dict, perceived: list[dict], wq_events: list[dict]) -> str | None:
    """'crise_regiao' | 'queda_cidade' | 'quest_falhou' | None (R6, ordem fixa)."""


# rag.py
def query_rag(
    query: str,
    index_name: str = "lore",
    game_id: str | None = None,
    max_visibility: str = "public",
    prefer_region: str | None = None,
) -> str: ...
def query_global_by_vector(
    vector: list[float],
    index_name: str = "lore",
    max_visibility: str = "public",
    prefer_region: str | None = None,
) -> str: ...
```

`price_factors`: o fator `supply_*` sai de `supply_factor` (`economy.py:164-181`). Para separar
`supply_passo` de `supply_rota`, calcula-se `supply_factor` sem os pares sazonais. Se esse valor
der `1.0` e o com pares der `SCARCE_MULT`, o código é `supply_passo`; senão, `supply_rota`.
`supply_local` corresponde a `ABUNDANT_MULT`. `estado_local` e `festa` são o mesmo fator de
`location_effects`. O código é `festa` quando o estado é `festa`; senão, `estado_local`. Fator igual
a `1.0` também entra na lista: a lista é o rastro do cálculo e o filtro de R11 vem depois.

### 3.3 Tabela de motivos (normativa)

`{local}` = nome do local atual no mapa. `{label}` = `location_states.public_label(row)`.
`{keeper}` = nome do keeper. `{fação}` = nome só se conhecida.

| code | Direção | Frase |
|---|---|---|
| `estado_local` | encarece | `{local} está {label}` (ex.: "Brekmar está sitiada") |
| `festa` | encarece/barateia | `é tempo de {festival.name}` |
| `supply_rota` | encarece | `mercadorias de fora não estão chegando` |
| `supply_passo` | encarece | `a estação fechou o caminho por onde a mercadoria vinha` |
| `supply_local` | barateia | `a mercadoria é feita aqui mesmo` |
| `mercador` | encarece | `este mercador cobra caro por natureza` |
| `mercador` | barateia | `este mercador costuma cobrar pouco` |
| `relacao` | ambos | `{keeper} {_ATTITUDE_PHRASE[tier]}` (`services/reputation.py:1096-1102`); com `relationship_basis.fame` diferente de 0, acrescenta-se ` e ouviu falar {bem\|mal} de você por aqui` |
| `controlador_hostil` | encarece | conhecida: `{fação} manda aqui e é hostil a você`; desconhecida: `quem manda aqui não vê você com bons olhos` |
| `patente` | barateia | `desconto pela sua patente em {fação}` (a fação do jogador é conhecida por definição) |

Código sem linha na tabela não vira motivo (falha fechada).

### 3.4 Exemplos (ids canônicos)

**Preço.** Herói em `brekmar`, mercador de `brekmar` (`data/merchants.json:60-63`,
`price_mult` 0,9), estado `cerco` severidade 1 (×1,5, `data/world/location_states.json:2`),
motor `on`, keeper neutro:

```
MOTIVOS DO PREÇO (cite no máximo um, com palavras; nunca números):
- encarece: Brekmar está sitiada
- barateia: este mercador costuma cobrar pouco
```

**Planner.** Herói em `skallgard`, quest de mundo ativa da 305 e aviso de guerra percebido:

```
<QUESTS_DO_HEROI>
- Defender os portões de Skallgard · origem: cartaz da guarda · tipo: mundo · prazo: em breve
- Entregar a carta de Brynja · origem: Brynja
</QUESTS_DO_HEROI>
<MUNDO_PERCEBIDO>
...linhas da SPEC-309, audiência planning...
</MUNDO_PERCEBIDO>
```

**Query.** Herói em `skallgard`, inverno, sem estado de local, input "procuro a forja":
`"Skallgard Noite Longa <mês> procuro a forja"` (local e região iguais entram uma vez). Os rótulos exatos de estação e de mês
vêm do calendário; o teste usa os valores de `world_calendar`, não literais.

### 3.5 Ordem no prompt do planner

```
<CONTEXT>
Location / Weather
{world_state_context}
{mundo_percebido_block}      # R3 (Etapa 4)
{heard_block}                # R2
{planner_quests_block}       # R1
{instrução R4}               # só se algum dos três blocos acima não for vazio
(Se o estado atual do mundo contradisser o lore, o estado atual VENCE.)
<LORE_CONTEXT>...
```

### 3.6 Oráculo da regra de ouro (testes)

Fixture `two_regions_state`: herói em `skallgard`, motor `on`. Dados:
- (a) `world_projection.location_states["brekmar"] = {"state": "cerco", "severity": 3}`, **não**
  percebido;
- (b) `world_sim.crises` com uma crise `fome` aberta em `skallgard`, cujo item de digest **não**
  está em `perceived_items`;
- (c) um item percebido `kind="crise"` de `praga` em `skallgard`;
- (d) um item percebido `kind="escala"`, `ocupado.crise.escala`, em `brekmar` (outra região).

Asserções:
1. As mensagens do planner (system + human) não contêm "Brekmar", "sitiada", "fome", número de
   severidade, `crisis_id`, nome de fação desconhecida, nem as chaves `pressures`/`bands`/
   `tension`.
2. `world_replan_cause` dá `"crise_regiao"` por (c). Sem (c), dá `None`: (b) não foi percebida e
   (d) é de outra região (D1 default).
3. `compose_lore_query` não contém "Brekmar" nem "sitiada".
4. `price_reasons` em `skallgard` não cita o cerco de Brekmar, mesmo que a rota para lá esteja
   bloqueada. Só sai "mercadorias de fora não estão chegando".

## 4. Plano passo a passo

Rodar só os arquivos de teste do escopo (`-q --lf -x`, no máximo `-n 2`). A suíte completa é do
coordenador no pouso.

### Etapa 0 — Pré-voo (sem código de produto)

1. Confirmar o status de 308/309 e o nome e lugar de `event_perceived` e de `perceived_world`. Se
   divergirem, atualizar esta spec no mesmo commit.
2. Confirmar a chave do nome do mês em `world_calendar.date_at` e se `memory_store` hosted guarda
   `tags` no metadado (R28). Registrar na §8.
3. Levantar os aliases de região faltantes com `Grep` nas tags de `data/codex/**` (frontmatter
   apenas) e escrever `data/world/region_lore_tags.json`.

### Etapa 1 — RAG contextual (R17-R25), sem dependência

1. **Testes** (`tests/test_spec311_lore_query.py`):
   - `test_compose_lore_query_order_and_parts` asserta a ordem de R17 para a fixture de
     `skallgard`; `test_compose_lore_query_omits_state_when_engine_off`;
   - `test_compose_lore_query_never_other_location` (oráculo 3);
     `test_compose_lore_query_truncates_input`;
   - `test_compose_lore_query_never_raises` (estado vazio devolve `base`);
   - `test_region_lore_tags_every_region_hits_codex` (R22);
   - `test_rerank_by_region_tiers_stable`: as 3 faixas, com ordem estável dentro de cada uma;
   - `test_rerank_never_relaxes_visibility`: FAISS em memória com um chunk `hidden` tagueado na
     região (R24); `test_query_global_by_vector_without_region_is_unchanged` (só `LORE_K`);
   - `test_assemble_pack_lore_split_first_chunk_survives`: cota para um chunk, o primeiro entra
     (R19); `test_assemble_pack_lore_ids_keep_prefix`;
   - `test_custom_readers_signature_untouched` (R23);
     `test_storyteller_planner_npc_use_composed_query` (captura `query` via dublê).
2. **Implementação:** `services/lore_query.py`, o JSON de aliases, `rag.py`, `context_sources.py`,
   `context_builder.py` e as três chamadas.
3. **Verificação:** os testes acima, mais `tests/test_fase28.py`, `tests/test_audit_export.py`,
   `tests/test_audit_redaction.py`, `tests/test_eval_memory_context.py` e
   `tests/test_resumo_budget_rigido.py` (consumidores de `assemble_pack`/`lore_content_`).

### Etapa 2 — Preço com motivo (R10-R16), sem dependência

1. **Testes primeiro** (`tests/test_spec311_price_reasons.py`):
   - `test_price_characterization_matrix`: escrito e **verde contra o código atual**, antes da
     refatoração. Cobre todo `MERCHANTS` × 3 itens do estoque × `buy`/`sell` × {sem estado, cerco
     sev 1-3, festa, rota bloqueada, passo fechado, controlador hostil, keeper hostil/leal,
     patente} e grava os inteiros esperados no próprio teste;
   - `test_price_equals_product_of_factors`;
   - `test_price_reasons_threshold_and_cap` (R11);
   - `test_price_reasons_table_phrases` (§3.3, com um caso por código);
   - `test_price_reasons_no_numbers_no_ids` (R16), com regex `\d|%|x\d` e varredura de ids;
   - `test_unknown_faction_generic_phrase` (R12);
   - `test_route_reason_never_names_cause` (oráculo 4);
   - `test_engine_off_no_location_reason` (R13);
   - `test_loot_narrate_context_has_reasons` (dublê captura o `HumanMessage`);
   - `test_loot_observe_unchanged`; `test_loot_no_reasons_no_line`;
   - `test_npc_keeper_block_present_only_for_keeper`;
   - `test_npc_keeper_block_empty_without_reasons` (R15).
2. **Implementação:** `price_factors`, depois `price()` sobre eles (a caracterização tem de
   continuar verde), depois `price_reasons`/`market_direction`, `loot.py` e `npc.py`.
3. **Verificação:** os testes acima mais os testes existentes de economia, loot e reputação
   (`Grep` por `economy.price`/`relation_price_mult` em `tests/`).

### Etapa 3 — Planner: quests, notícias e gatilho (R1, R2, R4-R9), sem dependência

1. **Testes** (`tests/test_spec311_planner.py`):
   - `test_planner_quests_block_format_no_ids_no_proof`; `test_planner_quests_block_world_first_and_cap`;
   - `test_planner_quests_block_empty_when_none` (a tag não aparece);
   - `test_planner_prompt_has_heard_and_quests` (dublê captura as mensagens do `invoke`);
   - `test_planner_instruction_only_with_blocks`;
   - `test_world_replan_cause_crise_regiao`, `..._queda_cidade_regiao_atual`,
     `..._queda_outra_regiao_none` (D1), `..._quest_falhou`, `..._priority_order`;
   - `test_world_replan_cause_ignores_unperceived_crisis` (oráculo 2);
   - `test_storyteller_sets_needs_replan_on_trigger` (caminho feliz);
     `test_storyteller_trigger_survives_encounter_return` (R7);
   - `test_trigger_logs_closed_enum` (R8); `test_trigger_inert_engine_off_and_quests_shadow` (R9).
2. **Implementação:** `services/planner_context.py`; injeção em `campaign_manager._build_plan`;
   cálculo em `storyteller_node`, logo antes de `travel_needs_replan` (`:1054`), com
   `perceived_items` e `wq_events`.
3. **Verificação:** os testes acima mais os testes existentes do planner (`Grep`
   `campaign_manager` em `tests/`).

### Etapa 4 — `<MUNDO_PERCEBIDO>` no planner (R3), **depende de 308 e 309 `done`**

1. **Testes** (`tests/test_spec311_planner.py`): `test_perceived_world_planning_audience_lines`
   (linhas 1-4 da 309); `test_planner_prompt_has_perceived_world`;
   `test_planner_golden_rule_oracle` (oráculo §3.6, asserção 1, sobre o prompt inteiro);
   `test_perceived_world_planning_budget` (≤ `MAX_LINES`/`MAX_TOKENS`).
2. **Implementação:** audiência `"planning"` em `services/perceived_world.py` e injeção no
   planner.
3. **Verificação:** os testes acima mais os testes da SPEC-309 (`tests/test_spec309_*.py`).

### Etapa 5 — Integração

1. **Testes** (`tests/test_spec311_integration.py`): `test_invoke_count_unchanged` (R27, um turno
   de viagem com dia virado, um de loja e um de NPC-keeper no MockLLM);
   `test_old_save_loads_and_plans` (R26, fixture de save pré-302).
2. **Verificação:** todos os `tests/test_spec311_*.py`; o hand-back lista a contagem.

## 5. Critérios de aceite

- [x] R1–R28 cobertos pelos testes da §4 (cada R citado no docstring do teste)
- [x] `test_price_characterization_matrix` escrito antes da refatoração e verde depois (R10)
- [x] Oráculo §3.6 verde (planner, gatilho, query e preço)
- [x] Nenhuma chamada LLM nova e nenhum `with_structured_output` novo (R27)
- [x] `query_faiss_evidence` e `evals/` intocados
- [x] Saves antigos carregam e o planner roda sobre eles (R26)
- [ ] `uv run pytest` verde (suíte completa offline, rodada pelo coordenador no pouso)
- [ ] Revisão independente Opus (`handoffs/SPEC-311-review.md`) sem P0/P1
- [ ] Smoke real (§6) executado e registrado na §8

## 6. Smoke test com LLM real

Pré-requisito: `RPG_WORLD_ENGINE=on`, `RPG_WORLD_QUESTS=on`, `RPG_NPC_KNOWLEDGE=on`, DeepSeek nas
`ROUTES`, índice de lore local presente. Teto total: US$ 0,80. O MockLLM devolve beats fixos e
não mostra se o planner contradiz a crise, se a prosa do loot vira número ou se a lore recuperada
mudou.

1. `uv run python -m playtest run --scenario mundo --turns 20 --real --max-cost 0.35 --seed 41`.
   O cenário abre crise em `nova_arcadia` (`playtest/scenarios.py:277-280`). Asserta `mock=False`
   e 0 violação `error`. No log, pelo menos 1 `campaign.world_replan_trigger` seguido de
   `campaign.replan reason=needs_replan`. Leitura humana: os beats do plano seguinte citam a crise
   só como gancho ou pano de fundo, sem número nem causa inventada, e não citam local não
   percebido.
2. `uv run python -m playtest run --scenario comercio --turns 10 --real --max-cost 0.20 --seed 42`.
   Em pelo menos 1 compra com motivo não vazio, a prosa cita no máximo um motivo, com palavras e
   sem número. O `[SISTEMA]` fica igual ao do motor.
3. Falar com um keeper (`npc_brynja_forja_fria`, `data/merchants.json:15-17`) num local com
   estado ou com relação não neutra (mesmo run ou `--profile comerciante --turns 8 --real
   --max-cost 0.15 --seed 43`). A fala sobre preço reflete o motivo sem número.
4. Lore: no transcrito do run 1, comparar 3 turnos com a mesma ação antes e depois do pouso.
   Pelo menos 1 chunk recuperado deve ser da região atual (tags), e nenhum chunk `hidden`.

Registrar run_ids, custo e trechos na §8. Se estourar o teto, parar e registrar.

## 7. Riscos & compatibilidade

- **Saves antigos:** nenhum campo novo (R26). Quest antiga sem `world_kind` sai sem "tipo: mundo".
- **Divergência de preço:** a refatoração de `price()` é o risco maior. A matriz de caracterização
  escrita antes (Etapa 2) é a rede de segurança. Se um caso divergir, o caso vence e a refatoração
  se ajusta.
- **Replan mais frequente:** cada disparo de R6 custa uma chamada SMART que já existe. A 302
  telegrafa crise com pelo menos 2 dias e limita aberturas por região, e o gatilho só olha a
  região atual. A frequência é medida no smoke 1. Se passar de 1 replan por mundo a cada 5 turnos
  em média, registrar e propor um cooldown em `last_planned_turn` (sem campo novo).
- **Arco jogado fora:** replan por crise troca os beats pendentes. Isso é desejado (o arco antigo
  ignorava o cerco), mas o `arc_title` pode mudar e abrir capítulo na crônica
  (`campaign_manager.py:365-374`). É aceitável: a crise é um arco novo.
- **Query composta dilui o input:** as palavras de contexto podem puxar lore genérica da região
  no lugar da coisa que o jogador citou. Mitigação: o input fica inteiro até 300 caracteres e
  `LORE_K` sobe para 3. O smoke 4 mede isso. Alternativa em D4.
- **Preferência por região esconde lore útil de outra região** (ex.: história de uma fação
  distante que o jogador perguntou). A faixa 2 não é descartada, só vai para o fim. Com
  `LORE_K = 3`, ainda entra se as faixas 0 e 1 não encherem. O filtro duro fica em D3.
- **Rumor de mercado como canal de informação:** "mercadorias de fora não estão chegando" diz ao
  jogador que algo fechou uma rota. Isso é aceitável pela regra de ouro: o mercador em cena sabe
  da própria falta, e o preço maior já é visível no `[SISTEMA]` desde a 302. A frase nunca nomeia
  rota nem causa.
- **Conflito de merge com a SPEC-310:** as duas editam o prompt de `agents/npc.py`. O bloco de R15
  é uma variável própria, inserida depois de `{atitude_block}`. Quem pousar depois rebaseia.
- **Conflito com a SPEC-309:** a audiência `"planning"` é uma extensão do módulo da 309. Se a 309
  pousar com outro contrato, a Etapa 4 se ajusta e esta spec é atualizada no mesmo commit.
- **MockLLM/FallbackLLM:** os blocos são texto, e o planner mantém o guard
  `isinstance(plan, CampaignPlanModel)` (`campaign_manager.py:206`). O `_narrate` do loot mantém o
  fallback mecânico.
- **Custo/latência:** no planner, até cerca de 250 tokens de entrada a mais (quests, notícias e
  mundo percebido). No loot e no NPC-keeper, até cerca de 60. Na lore, até 1 chunk a mais dentro da
  mesma cota. Continua um embedding por pack. No hosted, `k=6` em vez de 2 na consulta de lore.

## 8. Registro de execução

**Implementação (25/10, branch `spec-311`).** Etapas 0-5 feitas; testes novos em `tests/test_spec311_*.py`
(lore_query, price_reasons, planner, integration). Fora do escopo desta entrega: revisão Opus, suíte
completa (coordenador) e smoke §6 (não rodado por regra do dono).

**Etapa 0.** 308 e 309 já `done` na main (`world_perception.event_perceived`, `perceived_world`).
Nome do mês: `world_calendar.date_view(cal, day)["month"]` (cal de `calendar_for_read(world_sim, day)`;
cai em `world.date.month`). As 12 regiões têm o próprio `region_id` como tag em `data/codex/`; o JSON de
aliases só acrescenta os apelidos curtos (`pradaria`, `pantano`, `zhur`...). Hosted: nenhuma escrita de
`tags` no metadado do `memory_store` foi encontrada no repo, então a reordenação (R21) é no-op ali até
alguém gravar `tags` (follow-up, não bloqueia; R28).

**Desvios (todos pequenos):**
- `price()` multiplica **em sequência** (`p *= f.mult`), não `base * prod(...)`: preserva a associação de
  floats e o resultado idêntico (R10). `PriceFactor.code` ganhou `"venda"` (SELL_FACTOR no rastro).
- `price_reasons` com `item_id=None`: o motivo de rota entra se **algum** item do `base_stock` do mercador
  estiver escasso (primeiro encontrado), como em R11.
- Na linha de motivos do loot, em `sell` os verbos são "paga mais/paga menos" (em vez de
  encarece/barateia), porque o fator já é o do pagamento ao jogador. `PriceReason.direction` não muda.
- R20: faixa 2 ("só de outra região") usa só tags de **identidade** (id, rótulo, aliases) das 12 regiões;
  a faixa 0 usa o conjunto completo de `region_lore_tags` (inclui ids/nomes dos locais). Evita rebaixar
  chunk por nome genérico de local.
- R17: storyteller e planner passam como `base` só o input do jogador (o local já é a 1ª parte da query);
  o NPC mantém `"{nome} {local} {fala}"`. `RERANK_CANDIDATES = 6` e `LORE_SEP` são constantes novas.
- R3: a audiência `"planning"` só entrou no `Literal`; as linhas 1-4 da 309 já saem para qualquer audiência
  diferente de `npc`/`story`.
- R7: o fallback do storyteller só levava `needs_replan` em viagem; agora também leva quando o gatilho do
  mundo disparou.

Smoke §6: pendente (opt-in, coordenador).

## 9. Decisões do dono

Todas têm default recomendado. O executor segue o default se o dono não disser nada.

- **D1 — Queda de cidade em outra região dispara replan?** Default: **não, só na região atual**
  (evita replan por notícia distante; a notícia já chega por `<OUVIU_DIZER>`). Alternativa: em
  qualquer região percebida.
- **D2 — Quantos chunks de lore por consulta?** Default: **3** (cabe na cota de hoje depois de
  R19). Alternativa: manter 2.
- **D3 — Região como preferência ou como filtro?** Default: **preferência** (as três faixas de
  R20). Alternativa: filtro duro que descarta a faixa 2. É mais focado, mas zera a lore de outra
  região mesmo quando o jogador pergunta por ela.
- **D4 — Uma query composta para tudo ou só para a lore?** Default: **uma para tudo** (um
  embedding por pack, como hoje). Alternativa: query composta só para a lore. A memória de sessão
  fica com a query crua, ao custo de um segundo embedding por pack (latência e custo de embedding,
  não de LLM).
