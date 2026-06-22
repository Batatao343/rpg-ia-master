# rpg-ia-master

RPG de texto com IA — motor LangGraph multi-agente com RAG híbrido e memória por sessão.
Stack: Python 3.13 · FastAPI · LangGraph · FAISS · Google Gemini · uv

> **AO RETOMAR:** leia `@ESTADO_ATUAL.md` primeiro — estado atual, como rodar,
> bugs já corrigidos, limitações conhecidas e convenção crítica de resiliência.

---

## Comandos essenciais

```bash
# Instalar dependências
uv sync

# Rodar CLI (jogar no terminal)
python game_engine.py

# Rodar API REST
uvicorn api:app --reload --port 8000

# Re-indexar lore e regras (após editar data/world_lore.txt ou data/rules.txt)
python rag.py

# Testes
pytest tests/ -v
```

---

## Arquitetura — grafo LangGraph

```
START
  ↓
campaign_manager      # planeja arcos narrativos (3–5 beats) com RAG de lore
  ↓
dm_router             # classifica intenção: STORY | COMBAT | NPC | LOOT
  ↓ (condicional)
storyteller           → archivist → END
combat_agent          → archivist → END
npc_actor             → archivist → END
loot_agent            → archivist → END
```

**archivist** roda em todo fim de turno: atualiza `narrative_summary` (curto prazo) e persiste fatos no FAISS da sessão (longo prazo).

---

## LLM — dois tiers

`llm_setup.py` expõe `get_llm(temperature, tier)`. Sempre usar essa função — nunca instanciar Gemini direto.

| Tier | Modelo | Uso |
|---|---|---|
| `ModelTier.FAST` | `gemini-flash-latest` | router, storyteller (rápido) |
| `ModelTier.SMART` | `gemini-pro-latest` | archivist, campaign_manager (qualidade) |

Troca de modelo = só mudar `llm_setup.py`. Sem tocar nos agentes.

Variável obrigatória: `GOOGLE_API_KEY` no `.env`.

---

## RAG — sistema híbrido

`rag.py` — `query_rag(query, index_name, game_id)` busca em dois índices:

1. **Global** (`faiss_lore_index/`, `faiss_rules_index/`) — imutável durante o jogo, indexado de `data/world_lore.txt` e `data/rules.txt`
2. **Sessão** (`data/saves_memory/{game_id}/`) — dinâmico, criado pelo archivist via `add_memory_to_session()`

Embeddings: `models/text-embedding-004` (Google). Chunks: 500 tokens, overlap 50.

Para re-indexar lore global: `python rag.py` (ou chamar `ingest_file()` diretamente).

---

## Persistência

- Saves em `saves/{game_id}.json` — serializa mensagens LangChain para dicts simples
- `persistence.py` — `save_game_state()` / `load_game_state()`
- Memória vetorial por sessão em `data/saves_memory/{game_id}/`
- `load_game_state()` sem argumento carrega o save mais recente (por `ctime`)

---

## Estado do jogo (GameState)

Definido em `state.py` como TypedDict. Campos principais:

```
game_id             str          — UUID da sessão, isola memória RAG
narrative_summary   str          — resumo comprimido (short-term memory)
archivist_last_run  int          — turno da última execução do arquivista
player              PlayerStats  — name, class, race, hp, mana, stamina, gold, level, xp, attributes, inventory...
world               WorldState   — current_location, time_of_day, turn_count, danger_level, quest_plan...
messages            List[BaseMessage]  — histórico LangChain (operator.add)
campaign_plan       CampaignPlan — location, beats[], climax, current_step
enemies             List[EnemyStats]
npcs                Dict[str, Dict]
combat_target       Optional[str]
loot_source         Optional[str]   — "TREASURE" | "SHOP" | "CRAFT"
```

---

## Estrutura de pastas

```
agents/
  router.py           # dm_router_node — classifica intenção
  storyteller.py      # storyteller_node — narração
  combat.py           # combat_node
  npc.py              # npc_actor_node + generate_new_npc()
  loot.py             # loot_node
  archivist.py        # archive_node — memória curto/longo prazo
  campaign_manager.py # campaign_manager_node — planejamento de arcos
  bestiary.py         # helpers de bestiário
  class_themes.py     # temas narrativos por classe
  librarian.py        # utilitários de conhecimento
  ruler_completo.py   # regras completas
data/
  world_lore.txt      # lore indexado para FAISS (editar aqui, re-indexar depois)
  rules.txt           # regras indexadas para FAISS
  bestiary.json       # criaturas
  classes.json        # classes jogáveis
  origins.json        # raças e regiões
  artifacts.json      # artefatos
  player_abilities.json
faiss_lore_index/     # índice FAISS gerado — não editar à mão
faiss_rules_index/    # índice FAISS gerado — não editar à mão
saves/                # saves JSON por game_id
data/saves_memory/    # índices FAISS por sessão (gerado em runtime)
```

---

## Convenções de código

- Python 3.13+ com type hints em tudo
- Pydantic v2 para structured output do LLM (`llm.with_structured_output(Model)`)
- Async não usado — LangGraph roda síncrono neste projeto
- `httpx` se precisar HTTP externo (nunca `requests`)
- Prefixo `test_` em todos os arquivos e funções de teste
- Cada agente retorna dict parcial do GameState — nunca retornar o estado completo

---

## O que NÃO fazer

- Não instanciar `ChatGoogleGenerativeAI` direto — usar sempre `get_llm()`
- Não ler FAISS com `allow_dangerous_deserialization=False` — vai quebrar load
- Não commitar `.env` ou `saves/` com dados reais
- Não adicionar agentes ao grafo sem conectar ao `archivist` no final
- Não usar `requests` — projeto usa `httpx` se necessário
- Não editar os arquivos `faiss_*_index/` à mão — sempre re-gerar via `rag.py`

@REFERENCE.md
@ESTADO_ATUAL.md
