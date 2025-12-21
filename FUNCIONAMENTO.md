# Funcionamento da Engine V8

Este documento descreve, passo a passo, como os módulos da engine interagem, quais garantias de validação existem e como o fluxo de um turno é executado.

## Estado de Jogo
- O estado é um `TypedDict` com mensagens, próximo nó (`next`), jogador, mundo, inimigos, party e NPCs (`state.py`).
- O mundo guarda `quest_plan` e `quest_plan_origin`, permitindo que a narrativa siga um arco definido.
- Mensagens acumuladas são usadas pelo LangGraph para manter o histórico conversacional.

## LLMs em Camadas (Tiered Compute)
- `ModelTier.FAST` usa `gemini-1.5-flash` para lógica simples; `ModelTier.SMART` usa `gemini-1.5-pro` com menos tentativas, priorizando raciocínio (`llm_setup.py`).
- Todos os nós chamam `get_llm`, que já traz tolerância a falhas (fallback que responde com mensagem clara se o provider não inicializar).

## RAG Multi-Índice
- `rag.py` gerencia ingestão e consulta de dois índices FAISS: `lore` (mundo) e `rules` (física/sistema).
- Bestiário, NPCs, Storyteller e Rules consultam RAG antes de gerar texto, garantindo consistência com o material fonte.

## Contratos e Governança
- Modelos Pydantic em `engine_utils.py` validam atualizações de dano e estamina: valores negativos são corrigidos, excessos disparam erro, evitando estouros de HP ou stamina irreais.
- O pipeline de aplicação de estado usa esses modelos antes de escrever no estado de jogo.

## Grafo de Agentes (LangGraph)
1. **Roteador (`agents/router.py`)** analisa a última entrada e decide o próximo nó (`storyteller`, `combat_agent`, `rules_agent`, `npc_actor`).
2. **Storyteller (`agents/storyteller.py`)**:
   - Se não houver plano ou o local mudou, chama o LLM SMART para criar um `quest_plan` de 3 passos.
   - Na execução, lê o primeiro passo do plano, narra, consome-o (pop) e adiciona mensagens ao histórico.
   - Possui retry estruturado e fallback plain-text para evitar crashes; impede duplicação de NPCs ao validar nomes.
3. **Regras (`agents/rules.py`)** resolve física e interações sistêmicas, consultando o índice `rules` via RAG.
4. **NPC Actor (`agents/npc.py`)** cria ou atualiza NPCs e responde diálogos no tier FAST por padrão, sempre ancorado em `lore`.
5. **Combate (`agents/combat.py`)**:
   - Usa tier FAST para minions e ativa Tree of Thoughts para chefes (BOSS), gerando três estratégias com o tier SMART e escolhendo a melhor.
   - Converte agressões contra NPCs em inimigos hostis dinamicamente quando não há `enemies` ativos.
6. **Ferramentas**: nós de ferramentas (ex.: rolagem de dados) são chamados quando o nó retorna `tool_calls`.

## Fluxo de Combate com Tree of Thoughts
1. Detecta inimigos ativos; se vazio e a entrada citar um NPC existente, gera um inimigo via Bestiário e marca-o como `ativo`.
2. Para BOSS:
   - Gera três estratégias (agressiva, defensiva, tática), cada uma com score de chance de vitória.
   - Seleciona a de maior score e executa a narrativa/ação correspondente.
3. Para minions, segue o fluxo rápido tradicional.

## Planejamento de Campanha (Plan-and-Execute)
- `quest_plan` vive em `world.quest_plan` e é regenerado quando vazio ou quando a localização muda.
- Cada execução do Storyteller consome o próximo passo, garantindo arco coeso e desfecho.

## Persistência e Ferramentas de Desenvolvimento
- `persistence.py` salva/carrega estado em JSON, mantendo compatibilidade com o schema.
- `test_suite_complete.py` oferece menu interativo com fábricas de estado para validar governança, geração de conteúdo, roteamento, storytelling, combate tático e memória de NPCs.
- `test_runner.py` e `simulation.py` ajudam a exercitar o grafo completo sem UI.

## Como Estender
- Adicione novos nós ao grafo em `main.py`, conectando-os via `add_node` e `add_edge`/`add_conditional_edges`.
- Para novas entidades, consulte RAG com `query_rag` e selecione o tier apropriado em `get_llm` para balancear custo e qualidade.
- Reuse os validadores de `engine_utils.py` ou crie novos modelos Pydantic para proteger o estado.
