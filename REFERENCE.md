# REFERENCE.md — Decisões arquiteturais e contexto do projeto

> Carregue este arquivo quando precisar de decisões estruturais:
> "leia o @REFERENCE.md antes de responder"

---

## Contexto do produto

RPG de texto dark fantasy com narração gerada por IA. Jogador digita ações em linguagem natural; o motor classifica a intenção, executa o agente correto e retorna narrativa coerente com o mundo e a sessão atual.

Dois modos de uso:
- **CLI** (`game_engine.py`) — terminal interativo com cores ANSI
- **API REST** (`api.py`) — backend para frontend web/mobile

---

## Decisões técnicas e seus motivos

### Por que LangGraph e não LangChain puro

LangGraph permite grafos de estados com arestas condicionais e ciclos — essencial para o roteamento STORY/COMBAT/NPC/LOOT. Com LangChain puro (chains lineares), adicionar um novo agente exige reescrever a cadeia inteira. Com LangGraph, é `add_node` + `add_edge`.

O fluxo `campaign_manager → dm_router → (agente) → archivist` é determinístico e auditável — cada nó sabe exatamente de onde veio e para onde vai.

### Por que FAISS e não ChromaDB ou Supabase pgvector

FAISS roda 100% local — sem servidor, sem latência de rede, sem custo. Para um RPG de texto onde o lore raramente muda, índices estáticos em disco são suficientes.

O sistema é híbrido: índices globais (lore/rules) são pré-gerados e imutáveis; índices de sessão são criados em runtime por save, isolando memórias entre partidas.

Se o projeto escalar para múltiplos usuários simultâneos via API, migrar para pgvector (Supabase) é a rota natural — a interface de `query_rag()` não muda.

### Por que Google Gemini e não OpenAI/Groq/Ollama

Gemini Flash tem latência baixa e custo menor que GPT-4 para o volume de um RPG interativo. O modelo `text-embedding-004` é gratuito dentro do tier padrão da API Google.

A abstração `ModelTier.FAST / ModelTier.SMART` em `llm_setup.py` permite trocar de provider sem tocar nos agentes — basta reimplementar `get_llm()`.

### Por que dois tiers de LLM (FAST e SMART)

Agentes que rodam todo turno (router, storyteller) precisam de latência baixa → `gemini-flash-latest`.  
Agentes que rodam esporadicamente e exigem qualidade (archivist, campaign_manager) → `gemini-pro-latest`.

Sem essa distinção, cada turno chamaria o modelo mais caro desnecessariamente.

### Por que memória híbrida (resumo + RAG por sessão)

O histórico de mensagens (`state["messages"]`) é truncado em ~15–20 mensagens para controlar tokens. Isso criaria amnésia narrativa.

Solução em dois níveis:
1. **Curto prazo**: `narrative_summary` — string comprimida com o "aqui e agora", atualizada pelo archivist a cada turno.
2. **Longo prazo**: FAISS por `game_id` — fatos permanentes ("Player matou o Rei") indexados pelo archivist e recuperados via RAG quando relevantes.

O archivist usa `ModelTier.SMART` justamente porque a qualidade do resumo e da extração de fatos impacta toda a coerência narrativa futura.

### Por que campaign_manager antes do router

O campaign_manager garante que sempre existe um plano narrativo (3–5 beats) antes de qualquer roteamento. O storyteller lê `active_step` do plano para saber o objetivo da cena atual — sem isso, a narrativa seria aleatória e sem progressão.

Replanning acontece quando:
- Não há plano (início de jogo)
- Jogador mudou de localização
- 10 turnos passaram sem replan
- Todos os beats foram concluídos
- `needs_replan = True` (flag explícita)

### Por que saves em JSON local e não banco de dados

Simplicidade operacional. Um save é um dict Python serializado — fácil de inspecionar, debugar e versionar manualmente se necessário.

O `game_id` (UUID) é o link entre o JSON de save e o índice FAISS da sessão. Se apagar um save, apagar também `data/saves_memory/{game_id}/`.

---

## Fluxo de um turno completo

```
Usuário digita ação
    ↓
[campaign_manager]
    Verifica se precisa de novo plano narrativo
    Se sim: chama Gemini Pro com lore RAG → gera 3-5 beats + climax
    ↓
[dm_router]
    Gemini Flash classifica intenção da última mensagem
    Retorna: route (STORY/COMBAT/NPC/LOOT), target, loot_context, confidence
    Injeta SystemMessage "COMBAT START" se for combate
    ↓
[agente especializado]
    Storyteller: busca lore RAG + narrative_summary → gera narrativa
    Combat: executa turno de combate com dice_system
    NPC: usa persona do NPC + histórico de interações
    Loot: gera loot baseado em bestiary/artifacts.json
    ↓
[archivist]
    Gemini Pro analisa últimas 8 mensagens
    Atualiza narrative_summary (curto prazo)
    Extrai fatos importantes → add_memory_to_session() (FAISS)
    ↓
END → save_game_state()
```

---

## Formato dos saves (saves/{game_id}.json)

```json
{
  "game_id": "uuid-v4",
  "narrative_summary": "string",
  "archivist_last_run": 0,
  "player": { "name", "class", "race", "level", "xp", "hp", "max_hp", "gold", "attributes", "inventory", "abilities", "defense", "attack_bonus", "active_conditions" },
  "world": { "current_location", "time_of_day", "turn_count", "danger_level", "quest_plan", "quest_plan_origin" },
  "party": [],
  "enemies": [],
  "npcs": {},
  "campaign_plan": { "location", "beats": [{"description", "status"}], "climax", "current_step", "last_planned_turn" },
  "combat_target": null,
  "loot_source": null,
  "message_history": [{"type": "human|ai|system", "content": "..."}]
}
```

---

## Variáveis de ambiente necessárias

```env
# Google AI (LLM + Embeddings)
GOOGLE_API_KEY=          # obrigatório — Gemini + text-embedding-004
```

Sem outras variáveis obrigatórias para rodar localmente. A API REST (api.py) herda as mesmas vars.

---

## Adicionando novo agente ao grafo

1. Criar `agents/meu_agente.py` com função `meu_agente_node(state: GameState) -> dict`
2. Em `main.py`: `workflow.add_node("meu_agente", meu_agente_node)`
3. Conectar saída ao archivist: `workflow.add_edge("meu_agente", "archivist")`
4. No router (`agents/router.py`): adicionar `MEU_TIPO = "meu_agente"` em `RouteType`
5. Em `main.py`, adicionar a rota condicional em `add_conditional_edges`

---

## Referências

- LangGraph: https://langchain-ai.github.io/langgraph/
- Gemini API (Python): https://ai.google.dev/gemini-api/docs
- FAISS (LangChain): https://python.langchain.com/docs/integrations/vectorstores/faiss/
- FastAPI: https://fastapi.tiangolo.com/
- uv: https://docs.astral.sh/uv/
