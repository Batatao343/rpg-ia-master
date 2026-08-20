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

### Por que resiliência em dois níveis (MockLLM + FallbackLLM)

`get_llm()` nunca levanta — o loop de jogo não pode morrer por causa de rede/quota/chave. Dois retornos não-Gemini:

- **`MockLLM`** (sem chave ou `RPG_FORCE_MOCK=1`): devolve **dados fictícios válidos** (instâncias Pydantic por agente). O jogo fica jogável e a suíte determinística e offline. Trade-off: como nunca falha o acesso a campo, **esconde bugs de mapeamento** que só aparecem no Gemini real.
- **`FallbackLLM`** (`RPG_NO_MOCK=1` sem chave, ou falha do provider): `with_structured_output(X).invoke()` devolve um `AIMessage`, **não** um `X`. Por isso todo nó precisa de guard (`try/except` ou `isinstance`). É o motivo da "convenção crítica" em `ESTADO_ATUAL.md`.

`max_retries=0` (fail-fast): o erro dominante é `429` de quota (não transitório, limite diário). Retry com backoff travava o turno por minutos antes de cair no fallback — pior UX que falhar em ~3s. A única repetição permitida no `RoutedLLM` é **semântica**: se a rede respondeu mas o structured output Pydantic veio inválido, regenera exatamente uma vez no mesmo provider/modelo. Erro HTTP/rede nunca usa essa repetição.

### Por que a mecânica é Python, não LLM (combate, dados, mundo)

O LLM é ótimo para linguagem, péssimo para aritmética consistente e regras. Então a IA **só identifica e narra**; os números resolvem em código determinístico:

- **Combate** (`combat_mechanics.py`): a IA traduz a fala livre → `CombatAction` (qual habilidade/alvo) e narra o log; Python faz iniciativa (d20+dex), DoT/condições, custos (stamina/mana) + cooldowns, saves por atributo real. Testável offline, jogável sem quota, números reproduzíveis.
- **Mundo / Fase 0** (`world_utils.py`): relógio, viagem (só entre locais conectados no grafo `data/world_map.json`, com fog of war via `visited`) e descanso são 100% determinísticos. O storyteller só narra o resultado.
- **Economia** (`loot.py`): o sinal do ouro (venda vs compra) é forçado por semântica em Python — não se confia no sinal que o LLM devolve.

Regra geral: **não confiar em sinal/valor numérico vindo do LLM sem validar.**

### Por que o modelo de mundo veio antes (Fase 0)

Mapa+fog, fações que se movem e itens regionais dependem de um alicerce comum: locais como grafo + relógio + região. Construir essas features sem o alicerce = retrabalho. Por isso a Fase 0 (mundo estruturado determinístico) precedeu a apresentação. Detalhes e sequência: `ROADMAP.md`.

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
    Storyteller: viagem/descanso/ruler (world_utils) + lore RAG + narrative_summary → narrativa; sinaliza beat_completed
    Combat: IA identifica ação/inimigos + narra; Python resolve 1 round (combat_mechanics). Vitória → next="loot"
    NPC: usa persona do NPC + histórico de interações
    Loot: gera loot/transação baseado em bestiary/artifacts.json + contexto regional
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
  "player": { "name", "class_name", "race", "level", "xp", "hp", "max_hp", "mana", "max_mana", "stamina", "max_stamina", "gold", "attributes (str/dex/con/int/wis/cha)", "inventory", "known_abilities", "defense", "attack_bonus", "active_conditions", "ability_cooldowns" },
  "world": { "current_location", "current_location_id", "visited", "world_clock": {"day", "period"}, "time_of_day", "turn_count", "danger_level", "weather", "quest_plan", "quest_plan_origin" },
  "party": [],
  "enemies": [],
  "npcs": {},
  "campaign_plan": { "location", "beats": [{"description", "status"}], "climax", "current_step", "last_planned_turn" },
  "needs_replan": false,
  "active_npc_name": null,
  "combat": null,
  "combat_target": null,
  "loot_source": null,
  "message_history": [{"type": "human|ai|system", "content": "..."}]
}
```

> Saves legados (schema antigo `class`/`abilities`) ainda carregam; campos novos (mana/stamina/`class_name`/`world_clock`/`combat`) entram via backfill (`world_utils.ensure_world`) ou ficam ausentes. Schema canônico: `state.py`.

---

## Variáveis de ambiente necessárias

```env
# Google AI (LLM + Embeddings) — em .env (NUNCA em .env.example, que é versionada)
GOOGLE_API_KEY=          # opcional — sem ela o jogo roda no MockLLM; Gemini + text-embedding-004
```

Free tier = **20 req/dia por modelo** (flash e pro têm buckets separados). E2e real de IA é inviável em lote no free tier; ativar billing para testar de verdade.

Flags de teste (env): `RPG_FORCE_MOCK=1` força MockLLM mesmo com chave (suíte); `RPG_NO_MOCK=1` força o `FallbackLLM` de erro (sem chave).

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
