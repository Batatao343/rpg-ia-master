# SPEC — Fase 2.5: Codex estruturado + World State Graph

> **Status:** `done` (2026-07-02 — suíte 112 verdes; smoke real: reindex + 1 turno narrando Valoria + secret filtrado)
> **Criada:** 2026-07-01 · **Atualizada:** 2026-07-02 (revisão: fonte = `lore_nova/`, universo Valoria)
> **Depende de:** — (primeira spec da série Mundo Vivo v1)
> **Desbloqueia:** [SPEC-003-fase-2.6-structured-events.md](SPEC-003-fase-2.6-structured-events.md), 2.7, 2.8

---

## 1. Contexto & Objetivo

Hoje o mundo muda via narrativa textual: o storyteller escreve "o portão caiu" e nada
estruturado registra isso. Em campanha longa, o risco é contradição — NPC morto fala,
local controlado muda sem evento, segredo vaza cedo.

Esta fase cria as **três camadas separadas**:

1. **Lore base (Codex)** — Markdown com frontmatter em `data/codex/`, imutável durante o jogo.
2. **Grafo estático autoral** — `data/graph/` (entities, edges, relation_types), também imutável.
3. **Estado dinâmico** — `event_log` (append-only) + `world_projection` (estado calculado), no save.

Princípio: *Lore base ≠ Estado vivo. LLM propõe, motor aplica* (nesta fase só a
fundação de dados; propostas estruturadas chegam na 2.6).

**Fonte do lore (revisão 2026-07-01):** o universo foi reescrito em `lore_nova/*.txt`
("Valoria" — Codex Omnia). Ele **substitui** o lore antigo: `world_lore.txt` deixa de ser
a fonte de ingestão nesta fase (arquivo removido na 2.5b), e os dados mecânicos atuais
(`factions.json`, `world_map.json`, `origins.json`, `bestiary.json`) serão realinhados ao
mundo novo na spec irmã [SPEC-002-fase-2.5b-valoria-dados-mecanicos.md](SPEC-002-fase-2.5b-valoria-dados-mecanicos.md).
Estado transitório aceito: até a 2.5b, o RAG narra Valoria enquanto o simulador de fações
ainda roda as fações antigas.

**Convenção de IDs canônicos (decisão desta spec):**

- Locais (macro-regiões): manter ids do mapa onde há overlap (`nova_arcadia`,
  `deserto_zhur`, `floresta_sussurros`, `montanhas_afiadas`, `skallgard`) + slugs novos
  para regiões novas (`pantano_melancolia`, `selva_xylos`, `aethelgard`, `ophidia`,
  `costa_negra`, `pradaria_ruinas`, `brekmar`, `ermo_branco`).
- Fações: slugs novos do lore Valoria (`legiao_ferro`, `mao_sombria`,
  `filhos_chama_azul`, ...). As fações antigas (`selo_palido`, `culto_clareira`, ...)
  saem de cena na 2.5b.
- NPCs = `npc_<slug>` (inclui os 13 Demônios e 7 Dragões — interpretáveis pelo
  npc_actor), monstros = `mon_<slug>`, raças = `race_<slug>`, artefatos únicos =
  `art_<slug>`, docs agregados sem nó no grafo = `story_<slug>` / `secret_<slug>`.
- Slugs sem acento (normalização unicode NFD), minúsculos, `_` como separador.
  Valerius (Lorde de Nova Arcádia) = `npc_valerius`.

## 2. Requisitos

- **R1** — Lore vive em `data/codex/**/*.md` com frontmatter YAML obrigatório
  (`id`, `type`, `name`, `tags`, `visibility`); campos opcionais (`aliases`,
  `related_entities`).
- **R2** — `data/graph/entities.json` lista toda entidade canônica com `id`, `type`,
  `name`, `aliases`, `tags`, `components`, `visibility`. IDs únicos (validado por teste).
- **R3** — `data/graph/edges.json` contém relações de lore base com tipos padronizados
  declarados em `data/graph/relation_types.json`. Toda edge aponta para entidades que
  existem em `entities.json` (validado por teste).
- **R4** — `GameState` ganha `event_log: List[GameEvent]` (append-only),
  `world_projection: WorldProjection` e `pending_world_events: List[Dict]`.
- **R5** — `services/graph_resolver.py` responde consultas combinando grafo base +
  `dynamic_edges` − `disabled_edges`, respeitando `visibility`.
- **R6** — `services/codex_loader.py` ingere o Codex no índice FAISS de lore
  preservando metadados (`id`, `type`, `tags`, `visibility`) em cada chunk.
- **R7** — `persistence.py` serializa/desserializa os novos campos. Save antigo sem
  eles carrega com defaults vazios (event_log=[], projection vazia).
- **R8** — Codex gerado a partir de `lore_nova/*.txt` via `scripts/migrate_lore_nova.py`
  (reprodutível). `data/world_lore.txt` deixa de ser a fonte de ingestão (remoção do
  arquivo fica para a 2.5b).

### Fora de escopo

- LLM propor eventos (Fase 2.6). Nesta fase `event_log` só é populado por testes e
  por código determinístico futuro.
- Regras genéricas de propagação (Fase 2.7).
- Ranking/budget de contexto (Fase 2.8).
- Alterar prompts dos agentes (eles continuam usando `query_rag` como hoje).

## 3. Design técnico

### Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `data/codex/locations/*.md` etc. | Lore por entidade (locations, factions, npcs, races, items, monsters, secrets, rumors, world_story) |
| `scripts/migrate_lore_nova.py` | Parser `lore_nova/*.txt` → Codex + entities.json (reprodutível) |
| `data/graph/entities.json` | Lookup canônico de entidades (gerado pelo script, curável) |
| `data/graph/edges.json` | Relações de lore base |
| `data/graph/relation_types.json` | Tipos de relação permitidos |
| `services/__init__.py` | Pacote de serviços |
| `services/graph_resolver.py` | Consultas ao grafo (base + dinâmico) |
| `services/codex_loader.py` | Ingestão do Codex com metadados no FAISS |
| `tests/test_fase25.py` | Suíte da fase |

### Arquivos alterados

- `state.py` — novos TypedDicts + campos no `GameState`
- `persistence.py` — serializar/carregar `event_log`, `world_projection`, `pending_world_events`
- `rag.py` — `__main__` passa a chamar `codex_loader.ingest_codex()` para lore
  (rules continua via `ingest_file`); `query_rag` ganha param opcional
  `max_visibility: str = "public"` que filtra chunks por metadado

### Formato do Codex (frontmatter)

```markdown
---
id: portao_oeste
type: location
name: Portão Oeste
aliases: ["Portao Oeste", "posto avançado do oeste"]
tags: [estrada, fronteira]
visibility: public          # public | hidden | secret
related_entities: [nova_arcadia, selo_palido]
---

Posto avançado onde caravanas param antes de cruzar para as terras altas...
```

Migração de `lore_nova/` (UTF-8) via `scripts/migrate_lore_nova.py`. O parser entende
blocos `[CATEGORIA: X]` + `[TAGS: ...]`, marcadores `[CRIATURA:]` / `[MATERIAL:]` /
`[ITEM:]` / `[ARTEFATO ÚNICO...]` e cabeçalhos de seção `LOCAL:`. Tags do bloco viram
`tags:` do frontmatter. Mapeamento fonte → destino:

| Fonte (`lore_nova/`) | Destino (`data/codex/`) | Granularidade | visibility default |
|---|---|---|---|
| locations.txt | `locations/` | 1 md por macro-região | public |
| factions.txt | `factions/` | 1 md por fação | public |
| npcs.txt | `npcs/` | 1 md por NPC/demônio/dragão | public (override manual p/ trechos sensíveis) |
| races.txt | `races/` | 1 md por raça | public |
| creatures.txt | `monsters/` | 1 md por `[CRIATURA:]` + primordiais | public |
| items.txt | `items/` | 1 md por região (materiais+itens) + 1 md por `[ARTEFATO ÚNICO]` | public |
| secrets.txt | `secrets/` | 1 md por segredo | **secret** |
| faction_perspectives.txt | `factions/perspectivas/` | 1 md por bloco | **hidden** |
| rumors.txt | `rumors/` | agrupado por região (`story_rumores_<slug>`) | public |
| daily_life.txt | `world_story/` | agrupado por região | public |

Nós do grafo (`entities.json`) = locations, factions, npcs, races, monsters e artefatos
únicos (~230 entidades). Segredos, rumores, cotidiano e perspectivas são **docs do
Codex** (ids `secret_`/`story_`), ligados via `related_entities`, sem nó próprio.

O script sobrescreve a saída ao rodar de novo — curadoria manual (aliases,
`related_entities`, overrides de visibility) só depois da saída estabilizar.

### `data/graph/relation_types.json`

```json
{
  "controls":    {"description": "Fação controla local", "source": "faction", "target": "location"},
  "enemy_of":    {"description": "Hostilidade mútua", "symmetric": true},
  "member_of":   {"description": "NPC pertence a fação", "source": "npc", "target": "faction"},
  "operates_in": {"description": "Fação/NPC atua na região", "target": "location"},
  "located_in":  {"description": "Entidade fica em local", "target": "location"},
  "leads":       {"description": "NPC lidera fação", "source": "npc", "target": "faction"}
}
```

### `data/graph/entities.json` (exemplo com IDs reais)

```json
{
  "npc_valerius": {
    "id": "npc_valerius",
    "type": "npc",
    "name": "Lorde Valerius",
    "aliases": ["Valerius", "o Lorde de Obsidiana"],
    "tags": ["noble", "ruler"],
    "visibility": "public",
    "components": {}
  },
  "legiao_ferro": {
    "id": "legiao_ferro",
    "type": "faction",
    "name": "A Legião de Ferro",
    "aliases": ["Legião"],
    "tags": ["ordem", "valerius", "corrupta"],
    "visibility": "public",
    "components": {}
  },
  "portao_oeste": {
    "id": "portao_oeste",
    "type": "location",
    "name": "Portão Oeste",
    "aliases": [],
    "tags": ["estrada", "fronteira"],
    "visibility": "public",
    "components": {}
  }
}
```

`components` fica vazio nesta fase — a Fase 2.7 preenche (`faction_leader`,
`power_vacuum_trigger`, etc.). O schema já existe para não migrar duas vezes.

### `data/graph/edges.json`

```json
[
  {"id": "e_legiao_opera_arcadia",  "source": "legiao_ferro",      "type": "operates_in", "target": "nova_arcadia", "visibility": "public"},
  {"id": "e_valerius_governa",      "source": "npc_valerius",      "type": "controls",    "target": "nova_arcadia", "visibility": "public"},
  {"id": "e_chama_inimiga_legiao",  "source": "filhos_chama_azul", "type": "enemy_of",    "target": "legiao_ferro", "visibility": "public"},
  {"id": "e_magda_lidera_mao",      "source": "npc_velha_magda",   "type": "leads",       "target": "mao_sombria",  "visibility": "secret"}
]
```

### `state.py` — novos tipos

```python
class GameEvent(TypedDict, total=False):
    event_id: str      # uuid4 hex
    turn: int          # world.turn_count no momento do evento
    type: str          # "npc_killed" | "secret_revealed" | "location_control_changed" | ...
    actor_id: str      # quem causou ("player", npc id, faction id, "system")
    target_id: str     # entidade afetada (id canônico)
    payload: Dict      # dados específicos do tipo
    source: str        # "combat" | "storyteller" | "rule_engine" | "system" | "test"

class EntityState(TypedDict, total=False):
    alive: bool
    location_id: str
    stability: int         # fações: -100..100
    extra: Dict            # estado adicional por componente

class DynamicEdge(TypedDict, total=False):
    id: str
    source: str
    type: str
    target: str
    created_by_event: str  # event_id de origem (auditoria)

class DisabledEdge(TypedDict, total=False):
    edge_id: str           # id da edge base desativada
    disabled_by_event: str

class RevealedFact(TypedDict, total=False):
    entity_id: str
    fact: str
    revealed_at_turn: int
    revealed_by_event: str

class WorldProjection(TypedDict, total=False):
    entities: Dict[str, EntityState]
    dynamic_edges: List[DynamicEdge]
    disabled_edges: List[DisabledEdge]
    revealed_facts: Dict[str, RevealedFact]     # chave = event_id revelador
    location_summaries: Dict[str, str]          # loc_id -> resumo dinâmico curto
```

No `GameState`:

```python
event_log: List[GameEvent]
world_projection: WorldProjection
pending_world_events: List[Dict]   # propostas ainda não validadas (Fase 2.6)
```

### `services/graph_resolver.py` — assinaturas

```python
def load_entities() -> Dict[str, dict]            # cache em módulo, lê data/graph/entities.json
def load_base_edges() -> List[dict]
def load_relation_types() -> Dict[str, dict]

def get_entity(entity_id: str) -> Optional[dict]  # lookup em entities.json

def resolve_edges(projection: WorldProjection, *,
                  entity_id: Optional[str] = None,
                  edge_type: Optional[str] = None,
                  include_hidden: bool = False) -> List[dict]
    # base_edges - disabled_edges + dynamic_edges; filtra visibility salvo include_hidden

def get_current_controller(location_id: str, projection: WorldProjection) -> Optional[str]
    # edge "controls" mais recente apontando para o local (dynamic vence base)

def is_alive(entity_id: str, projection: WorldProjection) -> bool
    # default True se entidade não tem EntityState
```

Sem estado global mutável além dos caches de leitura; `projection` sempre chega por
parâmetro (vem do `GameState`).

### `services/codex_loader.py` — assinaturas

```python
def parse_codex_file(path: str) -> tuple[dict, str]
    # (frontmatter, corpo); levanta ValueError se faltar campo obrigatório

def load_codex(codex_dir: str = "data/codex") -> List[Document]
    # 1 Document por chunk (RecursiveCharacterTextSplitter 500/50),
    # metadata = {id, type, name, tags, visibility}

def ingest_codex(codex_dir: str = "data/codex") -> None
    # gera faiss_lore_index a partir do Codex (substitui ingest_file p/ lore)
```

Frontmatter parseado com `yaml.safe_load` (PyYAML já é dependência transitiva do
LangChain; adicionar explícita em `pyproject.toml`).

### `query_rag` com visibilidade

```python
def query_rag(query, index_name="lore", game_id=None, max_visibility="public") -> str
```

Ordem de visibilidade: `public < hidden < secret`. Chunk entra no resultado se
`vis_rank(chunk.visibility) <= vis_rank(max_visibility)`. Chunks antigos sem metadado
contam como `public`. Chamadas existentes não mudam (default preserva comportamento).

## 4. Plano passo a passo

### Etapa 1 — Tipos no estado + persistência

1. **Testes** (`tests/test_fase25.py`):
   - `test_save_antigo_carrega_sem_event_log` — carrega JSON sem os campos novos;
     asserta `event_log == []`, `world_projection == {}` (ou defaults), sem exceção.
   - `test_save_roundtrip_event_log` — monta estado com 2 `GameEvent` + projection
     preenchida, `
     
     
     save_game_state` → `load_game_state`; asserta igualdade.
2. **Implementação:** tipos em `state.py`; `persistence.py` inclui os 3 campos em
   `save_data` e no load com defaults (`[]`, `{}`, `[]`).
3. `uv run pytest` verde.

### Etapa 2 — Grafo estático autoral

1. **Testes:**
   - `test_entities_ids_unicos_e_validos` — carrega `entities.json`; ids únicos,
     campos obrigatórios presentes, `type` em conjunto conhecido.
   - `test_edges_referenciam_entidades_existentes` — toda `source`/`target` de
     `edges.json` existe em `entities.json`; todo `type` existe em `relation_types.json`.
   - `test_locais_overlap_tem_entidade` — os 5 ids do mapa com overlap no mundo novo
     (`nova_arcadia`, `deserto_zhur`, `floresta_sussurros`, `montanhas_afiadas`,
     `skallgard`) têm entrada em `entities.json`. (Cobertura total do mapa fica para a
     2.5b, quando `world_map.json` for realinhado a Valoria.)
2. **Implementação:** `relation_types.json` e `edges.json` à mão (~40–60 edges
   principais extraídas de factions.txt/npcs.txt: `controls`, `leads`, `member_of`,
   `operates_in`, `located_in`, `enemy_of`; relações-segredo como Magda→Mão Sombria com
   `visibility: secret`). `entities.json` é gerado pelo script da Etapa 4 — nesta etapa
   as ordens podem se inverter na prática (script primeiro, edges depois).
3. `uv run pytest` verde.

### Etapa 3 — graph_resolver

1. **Testes:**
   - `test_controller_vem_do_lore_base` — projection vazia →
     `get_current_controller("nova_arcadia", {})` retorna controlador do lore base.
   - `test_dynamic_edge_vence_base` — projection com `disabled_edges` na edge base de
     controle + `dynamic_edge` `{"source": "mao_sombria", "type": "controls", "target": "brekmar"}`
     → `get_current_controller("brekmar", proj) == "mao_sombria"`.
   - `test_edge_hidden_nao_aparece_sem_flag` — `resolve_edges` sem `include_hidden`
     omite edges `visibility: hidden`.
   - `test_is_alive_default_true` + morto após `EntityState.alive=False`.
2. **Implementação:** `services/graph_resolver.py`.
3. `uv run pytest` verde.

### Etapa 4 — Migração do lore_nova para Codex (via script)

1. **Testes:**
   - `test_codex_frontmatter_valido` — varre `data/codex/**/*.md`; todo arquivo parseia
     e tem campos obrigatórios; `id` existe em `entities.json`
     (exceção: ids `story_<slug>` e `secret_<slug>` são docs sem nó no grafo).
   - `test_parse_codex_file_rejeita_sem_id` — arquivo sem `id` levanta `ValueError`.
   - `test_migracao_idempotente` — rodar o script 2x não duplica entidades.
2. **Implementação:** `scripts/migrate_lore_nova.py` parseia `lore_nova/*.txt` e gera
   `data/codex/**/*.md` + `data/graph/entities.json` (ver tabela do §3). Slugs sem
   acento; tudo `encoding="utf-8"`. Docstring avisa que re-rodar sobrescreve curadoria.
   `parse_codex_file` + `load_codex` em `services/codex_loader.py`. `world_lore.txt`
   fica no repo mas deixa de ser ingerido (remoção na 2.5b).
3. Curadoria manual: aliases importantes (ex.: "A Víbora" → `npc_velha_magda`),
   `related_entities`, overrides de `visibility` em trechos sensíveis.
4. `uv run pytest` verde.

### Etapa 5 — Ingestão + visibilidade no RAG

1. **Testes** (offline — sem chave, `load_codex` não depende de embeddings):
   - `test_load_codex_gera_chunks_com_metadata` — chunks têm `metadata["visibility"]`
     e `metadata["id"]`.
   - `test_vis_rank_ordena` — helper de ranking `public < hidden < secret`.
2. **Implementação:** `ingest_codex`; `query_rag(max_visibility=...)` filtrando
   pós-busca (buscar `k` maior, ex. 6, e cortar após filtro); `rag.py __main__`
   chama `ingest_codex()` para lore.
3. `uv run pytest` verde. Rodar `uv run python rag.py` localmente (requer chave —
   se sem quota, deixar para o smoke test).

## 5. Critérios de aceite

- [x] `graph_resolver.get_current_controller("brekmar", projection)` retorna o
  controlador certo baseado em estado atual (dynamic edge), não apenas lore base
- [x] Save antigo (ex.: qualquer arquivo em `saves/` de antes da fase) carrega sem erro
- [x] Novo jogo inicializa com `event_log=[]` e projection vazia (game_engine.py + api.py)
- [x] Todo arquivo do Codex validado por teste (frontmatter + id existente)
- [x] `uv run pytest` verde (suíte completa offline — 112 testes)
- [x] Saves antigos continuam carregando

## 6. Smoke test com LLM real

1. `uv run python rag.py` — reindexa lore a partir do Codex sem erro (usa embeddings reais).
2. 1 turno de jogo real (`/game/new` + 1 ação de exploração): storyteller responde
   usando `query_rag` sobre o índice novo — narrativa cita lore de **Valoria**.
3. Conferir que chunk `visibility: secret` (ex.: pacto de Valerius) NÃO aparece no
   contexto do storyteller (adicionar print/log temporário do `lore_context`).

## 7. Riscos & compatibilidade

- **Saves antigos:** campos novos entram com default vazio no load — sem migração de dados.
- **MockLLM:** fase é quase toda determinística; nada muda no mock. `load_codex` roda
  offline (split não usa embeddings).
- **Encoding:** `lore_nova/*.txt` é UTF-8 com acentos PT-BR; toda leitura/escrita de
  Codex com `encoding="utf-8"` explícito (Windows default é cp1252).
- **Script vs curadoria:** re-rodar `migrate_lore_nova.py` sobrescreve curadoria manual
  do Codex/entities — curar só depois da saída estabilizar (aviso no docstring).
- **Incoerência transitória:** fações/mapa mecânicos antigos convivem com lore novo até
  a 2.5b — jogar "de verdade" só após 2.5b.
- **Lacuna de conteúdo:** `lore_nova/` não tem arquivo de cosmogonia/eras (Guerra do Céu
  Vermelho, Malagor aparecem de passagem) — `world_story/` fica ralo; candidato a
  `lore_nova/history.txt` futuro.
- **Curadoria pendente (pós-fase):** arquivos de NPC misturam descrição pública com
  "História real"/segredos no MESMO md `public` — o smoke mostrou que o pacto de
  Valerius aparece no contexto público via `npc_valerius.md` (os chunks de
  `secrets/` são filtrados corretamente). Mitigação futura: separar seções sensíveis
  de NPC em arquivos `visibility: hidden`, ou aceitar que o narrador conhece a
  motivação real (segredos "duros" já vivem em `secrets/`).
- **Índice FAISS:** reingestão troca o conteúdo de `faiss_lore_index/`; commit do índice
  regenerado junto (projeto já versiona os índices).
- **Quota:** só a reingestão + smoke consomem requests de embedding.
